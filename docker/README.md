# graphite-irondb Docker Image
Python 2 and Python 3 test and demonstration environment.
```
Available options:

-h, --help      Print this help and exit
--python2       Build for Python 2 (default false)
--python3       Build for Python 3 (default true)
--circonus-api  Circonus API Key needed to access api.circonus.com
--irondb-urls   IronDB URS (in case of direct server access)
```
## Instructions
>Note for macOS users: By default the /Users, /Volume, /private, /tmp and /var/folders directory are shared. If your project is outside this directory then it must be added to the list. Otherwise you may get Mounts denied or cannot start service errors at runtime. See the File Sharing section of https://docs.docker.com/desktop/mac/ for more details.


1. [Install Docker](https://docs.docker.com/get-docker/).
2. [Obtain Circonus API Token](https://docs.circonus.com/circonus/integrations/api/api-tokens/), needed to connect to the hosted Circonus API. 
3. If you have no Circonus API Token you would need direct access to IronDB installation, in that case you can put their URLs into `--irondb-urls` parameter:
```
./docker/run-docker.sh --irondb-urls http://host:port,http://host2:port2 --python3
```
4. Execute `./docker/run-docker.sh --circonus-api $CIRCONUS_API_KEY --python3`
5. Navigate to http://localhost:80/ to access Graphite-Web.