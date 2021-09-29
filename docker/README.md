# graphite-irondb Docker Image
Python 2 and Python 3 test and demonstration environment.
```
Available options:

-h, --help      Print this help and exit
--python2       Build for Python 2
--python3       Build for Python 3
--circonus-api  Circonus API Key needed to access api.circonus.com
--test-only     Only run unit tests
```
## Instructions
>Note for macOS users: By default the /Users, /Volume, /private, /tmp and /var/folders directory are shared. If your project is outside this directory then it must be added to the list. Otherwise you may get Mounts denied or cannot start service errors at runtime. See the File Sharing section of https://docs.docker.com/desktop/mac/ for more details.


1. [Install Docker](https://docs.docker.com/get-docker/).
2. [Obtain Circonus API Token](https://docs.circonus.com/circonus/integrations/api/api-tokens/), needed to connect to the hosted Circonus API.
3. Execute ./docker/run-docker.sh --circonus-api $CIRCONUS_API_KEY --python3
4. Navigate to http://localhost:8080/ to access Graphite-Web.