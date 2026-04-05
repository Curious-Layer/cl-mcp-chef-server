import logging

CHEF_API_DOCS_URL = "https://docs.chef.io/server/api_chef_server/"
DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_CHEF_VERSION = "18.0.0"
DEFAULT_SERVER_API_VERSION = "1"
DEFAULT_AUTH_VERSION = "1.3"
DEFAULT_USER_AGENT = "cl-mcp-chef-server/1.0.0"


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler()],
    )
