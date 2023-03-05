#!/usr/bin/env bash -x

#original script: https://betterdev.blog/minimal-safe-bash-script-template/

set -Eeuo pipefail
trap cleanup SIGINT SIGTERM ERR EXIT

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd -P)
parent_dir=$(dirname $script_dir)

usage() {
  cat <<EOF
Usage: $(basename "${BASH_SOURCE[0]}") [-h] [-v] [-f] -p param_value arg1 [arg2...]

Script description here.

Available options:

-h, --help      Print this help and exit
--python2       Build for Python 2
--python3       Build for Python 3
--circonus-api  Circonus API Key needed to access api.circonus.com
--test-only     Only run unit tests


EOF
  exit
}

cleanup() {
  trap - SIGINT SIGTERM ERR EXIT
  # script cleanup here
}

setup_colors() {
  if [[ -t 2 ]] && [[ -z "${NO_COLOR-}" ]] && [[ "${TERM-}" != "dumb" ]]; then
    NOFORMAT='\033[0m' 
    RED='\033[0;31m' 
    GREEN='\033[0;32m' 
    ORANGE='\033[0;33m' 
    BLUE='\033[0;34m' 
    PURPLE='\033[0;35m' 
    CYAN='\033[0;36m' 
    YELLOW='\033[1;33m'
  else
    NOFORMAT='' RED='' GREEN='' ORANGE='' BLUE='' PURPLE='' CYAN='' YELLOW=''
  fi
}

msg() {
  echo >&2 -e "${1-}"
}

die() {
  local msg=$1
  local code=${2-1} # default exit status 1
  msg "$msg"
  exit "$code"
}

parse_params() {
  # default values of variables set from params
  test_only=false
  CIRCONUS_API_KEY=''
  IRONDB_URL=''
  python_version=0
  python3=false
  python2=false
  circonus_key_set=false
  irondb_url_set=false
  flatcc=true

  while :; do
    case "${1-}" in
    -h | --help) usage ;;
    --no-color) NO_COLOR=1 ;;
    --python2)
      python2=true
      python_version=2
      ;; 
    --python3)
      python3=true
      python_version=3
      ;; 
    --circonus-api)
      CIRCONUS_API_KEY="${2-}"
      circonus_key_set=true
      shift
      ;;
    --irondb-urls)
      IRONDB_URLS="${2-}"
      irondb_urls_set=true
      shift
      ;;
    --test-only)
      test_only=true
      ;;
    --pure-python)
      flatcc=false
      ;;
    -?*) die "Unknown option: $1" ;;
    *) break ;;
    esac
    shift
  done

  args=("$@")

  # check required params and arguments
  [[ ${circonus_key_set} = false ]] && [[ ${test_only} = false ]] && [[ ${irondb_urls_set} = false ]]\
   && die "You need to set either CIRCONUS_API_KEY or IRONDB_URLS"
  [[ ${circonus_key_set} = true ]] && [[ ${irondb_urls_set} = true ]]\
   && die "You need to set either CIRCONUS_API_KEY or IRONDB_URLS but not both"
  [[ $python2 = true ]] && [[ $python3 = true ]] \
   && die "Please select either --python2 or --python3."
  [[ ${#args[@]} -gt 0 ]] && die "Unexepected arguments."

  return 0
}

parse_params "$@"
setup_colors

# script logic here
cd $script_dir
msg "${BLUE}Parameters:${NOFORMAT}"
[[ ! -z "${CIRCONUS_API_KEY}" ]] && msg "- Circonus API Key: ${CIRCONUS_API_KEY}"
[[ ! -z "${IRONDB_URLS}" ]] && msg "- IronDB URLS: ${IRONDB_URLS}"
msg "- Python Version: ${python_version}"
msg "- Test only: ${test_only}"
msg "- Pure Python: ${flatcc}"

msg "${BLUE}Stopping any instances of graphite-irondb container${NOFORMAT}"

p2_containers=$(docker container ps -f "ancestor=circonus-labs/graphite-irondb-python2" | awk 'NR>1 {print $1}') \
 || die "Failed to check for running containers"
p3_containers=$(docker container ps -f "ancestor=circonus-labs/graphite-irondb-python3" | awk 'NR>1 {print $1}') \
 || die "Failed to check for running containers"
containers=("${p2_containers[@]}" "${p3_containers[@]}")

for CONTAINER in $containers
do
    msg "${RED}Stopping ${CONTAINER}${NOFORMAT}"
    docker stop $CONTAINER || die "Failed to check for stop container"
    msg "${RED}${CONTAINER} Stopped${NOFORMAT}"
done

msg "${GREEN}Complete${NOFORMAT}"

if [[ ${circonus_key_set} = true ]]; then
  _IRONDB_PARAMS="-e IRONDB_CIRCONUS_TOKEN=${CIRCONUS_API_KEY} "
else
  _IRONDB_PARAMS="-e IRONDB_URLS=${IRONDB_URLS} "
fi

msg "${BLUE}Building Docker Container...${NOFORMAT}"
if [[ ${python_version} -eq 3 ]]
then 
    docker build $script_dir/python3 -t circonus-labs/graphite-irondb-python3 \
    || die "Build failed."
    msg "${BLUE}Running Docker Container...${NOFORMAT}"
    docker run --rm -v $(dirname $(pwd)):/graphite-irondb \
     -p 8080:80 \
     ${_IRONDB_PARAMS} \
     -e TEST_ONLY=$test_only \
     -e FLATCC=$flatcc \
     --name graphite-irondb-python3 \
     circonus-labs/graphite-irondb-python3 \
     || msg "${YELLOW}Container stopped.${NOFORMAT}"; true
else
    docker build $script_dir/python2 -t circonus-labs/graphite-irondb-python2 \
    || die "Build failed."
    msg "${BLUE}Running Docker Container...${NOFORMAT}"
    docker run --rm -v $(dirname $(pwd)):/graphite-irondb \
     -p 8080:80 \
     ${_IRONDB_PARAMS} \
     -e TEST_ONLY=$test_only \
     -e FLATCC=$flatcc \
     --name graphite-irondb-python2 \
     circonus-labs/graphite-irondb-python2 \
     || msg "${YELLOW}Container stopped.${NOFORMAT}"; true
fi

msg "${GREEN}Done${NOFORMAT}"