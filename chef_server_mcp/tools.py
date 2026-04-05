import json
import logging
import re
from dataclasses import dataclass
from typing import Any

from fastmcp import FastMCP
from pydantic import Field

from .config import CHEF_API_DOCS_URL, DEFAULT_TIMEOUT_SECONDS
from .service import parse_auth_data, parse_json_argument, perform_chef_request

logger = logging.getLogger("chef-server-mcp-server")
PATH_PARAM_PATTERN = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


@dataclass(frozen=True)
class EndpointSpec:
    tool_name: str
    method: str
    path_template: str
    description: str
    requires_body: bool = False


ENDPOINT_SPECS: list[EndpointSpec] = [
    # Global endpoints
    EndpointSpec("chef_authenticate_user", "POST", "/authenticate_user", "Authenticate a user against Chef Infra Server.", True),
    EndpointSpec("chef_get_license", "GET", "/license", "Get Chef Infra Server license information."),
    EndpointSpec("chef_list_organizations_global", "GET", "/organizations", "List all organizations on the Chef Infra Server."),
    EndpointSpec("chef_create_organization_global", "POST", "/organizations", "Create an organization on the Chef Infra Server.", True),
    EndpointSpec("chef_get_organization_global", "GET", "/organizations/{organization}", "Get details for a named organization."),
    EndpointSpec("chef_update_organization_global", "PUT", "/organizations/{organization}", "Update a named organization.", True),
    EndpointSpec("chef_delete_organization_global", "DELETE", "/organizations/{organization}", "Delete a named organization."),
    EndpointSpec("chef_get_stats", "GET", "/_stats", "Get Chef Infra Server statistics endpoint response."),
    EndpointSpec("chef_get_status", "GET", "/_status", "Get Chef Infra Server status response."),
    EndpointSpec("chef_list_users_global", "GET", "/users", "List users on the Chef Infra Server."),
    EndpointSpec("chef_create_user_global", "POST", "/users", "Create a user on the Chef Infra Server.", True),
    EndpointSpec("chef_get_user_global", "GET", "/users/{username}", "Get details for a global user."),
    EndpointSpec("chef_update_user_global", "PUT", "/users/{username}", "Update a global user.", True),
    EndpointSpec("chef_delete_user_global", "DELETE", "/users/{username}", "Delete a global user."),
    EndpointSpec("chef_list_user_keys_global", "GET", "/users/{username}/keys", "List keys for a global user."),
    EndpointSpec("chef_create_user_key_global", "POST", "/users/{username}/keys", "Create a key for a global user.", True),
    EndpointSpec("chef_get_user_key_global", "GET", "/users/{username}/keys/{key_name}", "Get a specific key for a global user."),
    EndpointSpec("chef_update_user_key_global", "PUT", "/users/{username}/keys/{key_name}", "Update a specific key for a global user.", True),
    EndpointSpec("chef_delete_user_key_global", "DELETE", "/users/{username}/keys/{key_name}", "Delete a specific key for a global user."),
    EndpointSpec("chef_get_universe_global", "GET", "/universe", "Get Chef universe cookbook metadata."),
    # Organization endpoints
    EndpointSpec("chef_list_association_requests", "GET", "/organizations/{organization}/association_requests", "List pending organization association requests."),
    EndpointSpec("chef_create_association_request", "POST", "/organizations/{organization}/association_requests", "Create an organization association request.", True),
    EndpointSpec("chef_delete_association_request", "DELETE", "/organizations/{organization}/association_requests/{request_id}", "Delete an organization association request."),
    EndpointSpec("chef_list_clients", "GET", "/organizations/{organization}/clients", "List organization API clients."),
    EndpointSpec("chef_create_client", "POST", "/organizations/{organization}/clients", "Create an organization API client.", True),
    EndpointSpec("chef_get_client", "GET", "/organizations/{organization}/clients/{client_name}", "Get details for an organization API client."),
    EndpointSpec("chef_update_client", "PUT", "/organizations/{organization}/clients/{client_name}", "Update an organization API client.", True),
    EndpointSpec("chef_delete_client", "DELETE", "/organizations/{organization}/clients/{client_name}", "Delete an organization API client."),
    EndpointSpec("chef_list_client_keys", "GET", "/organizations/{organization}/clients/{client_name}/keys", "List keys for an organization API client."),
    EndpointSpec("chef_create_client_key", "POST", "/organizations/{organization}/clients/{client_name}/keys", "Create a key for an organization API client.", True),
    EndpointSpec("chef_get_client_key", "GET", "/organizations/{organization}/clients/{client_name}/keys/{key_name}", "Get a specific key for an organization API client."),
    EndpointSpec("chef_update_client_key", "PUT", "/organizations/{organization}/clients/{client_name}/keys/{key_name}", "Update a specific key for an organization API client.", True),
    EndpointSpec("chef_delete_client_key", "DELETE", "/organizations/{organization}/clients/{client_name}/keys/{key_name}", "Delete a specific key for an organization API client."),
    EndpointSpec("chef_list_containers", "GET", "/organizations/{organization}/containers", "List organization containers."),
    EndpointSpec("chef_create_container", "POST", "/organizations/{organization}/containers", "Create an organization container.", True),
    EndpointSpec("chef_get_container", "GET", "/organizations/{organization}/containers/{container_name}", "Get details for an organization container."),
    EndpointSpec("chef_delete_container", "DELETE", "/organizations/{organization}/containers/{container_name}", "Delete an organization container."),
    EndpointSpec("chef_list_cookbook_artifacts", "GET", "/organizations/{organization}/cookbook_artifacts", "List cookbook artifacts in an organization."),
    EndpointSpec("chef_get_cookbook_artifact", "GET", "/organizations/{organization}/cookbook_artifacts/{cookbook_name}", "Get cookbook artifact versions for a cookbook."),
    EndpointSpec("chef_get_cookbook_artifact_version", "GET", "/organizations/{organization}/cookbook_artifacts/{cookbook_name}/{identifier}", "Get a cookbook artifact version."),
    EndpointSpec("chef_upsert_cookbook_artifact_version", "PUT", "/organizations/{organization}/cookbook_artifacts/{cookbook_name}/{identifier}", "Create or update a cookbook artifact version.", True),
    EndpointSpec("chef_delete_cookbook_artifact_version", "DELETE", "/organizations/{organization}/cookbook_artifacts/{cookbook_name}/{identifier}", "Delete a cookbook artifact version."),
    EndpointSpec("chef_list_cookbooks", "GET", "/organizations/{organization}/cookbooks", "List cookbooks in an organization."),
    EndpointSpec("chef_get_latest_cookbooks", "GET", "/organizations/{organization}/cookbooks/_latest", "Get latest cookbook versions in an organization."),
    EndpointSpec("chef_get_latest_recipes", "GET", "/organizations/{organization}/cookbooks/_recipes", "Get latest recipe names in an organization."),
    EndpointSpec("chef_get_cookbook", "GET", "/organizations/{organization}/cookbooks/{cookbook_name}", "Get cookbook versions for a cookbook."),
    EndpointSpec("chef_get_cookbook_version", "GET", "/organizations/{organization}/cookbooks/{cookbook_name}/{version}", "Get a cookbook version."),
    EndpointSpec("chef_upsert_cookbook_version", "PUT", "/organizations/{organization}/cookbooks/{cookbook_name}/{version}", "Create or update a cookbook version.", True),
    EndpointSpec("chef_delete_cookbook_version", "DELETE", "/organizations/{organization}/cookbooks/{cookbook_name}/{version}", "Delete a cookbook version."),
    EndpointSpec("chef_list_data_bags", "GET", "/organizations/{organization}/data", "List data bags in an organization."),
    EndpointSpec("chef_create_data_bag", "POST", "/organizations/{organization}/data", "Create a data bag in an organization.", True),
    EndpointSpec("chef_get_data_bag", "GET", "/organizations/{organization}/data/{data_bag}", "Get data bag entries for a data bag."),
    EndpointSpec("chef_create_data_bag_item", "POST", "/organizations/{organization}/data/{data_bag}", "Create a data bag item.", True),
    EndpointSpec("chef_delete_data_bag", "DELETE", "/organizations/{organization}/data/{data_bag}", "Delete a data bag."),
    EndpointSpec("chef_get_data_bag_item", "GET", "/organizations/{organization}/data/{data_bag}/{item_id}", "Get a data bag item."),
    EndpointSpec("chef_update_data_bag_item", "PUT", "/organizations/{organization}/data/{data_bag}/{item_id}", "Update a data bag item.", True),
    EndpointSpec("chef_delete_data_bag_item", "DELETE", "/organizations/{organization}/data/{data_bag}/{item_id}", "Delete a data bag item."),
    EndpointSpec("chef_list_environments", "GET", "/organizations/{organization}/environments", "List environments in an organization."),
    EndpointSpec("chef_create_environment", "POST", "/organizations/{organization}/environments", "Create an environment in an organization.", True),
    EndpointSpec("chef_get_default_environment", "GET", "/organizations/{organization}/environments/_default", "Get the _default environment."),
    EndpointSpec("chef_get_environment", "GET", "/organizations/{organization}/environments/{environment}", "Get an environment."),
    EndpointSpec("chef_update_environment", "PUT", "/organizations/{organization}/environments/{environment}", "Update an environment.", True),
    EndpointSpec("chef_delete_environment", "DELETE", "/organizations/{organization}/environments/{environment}", "Delete an environment."),
    EndpointSpec("chef_get_environment_cookbook", "GET", "/organizations/{organization}/environments/{environment}/cookbooks/{cookbook_name}", "Get cookbook versions for an environment and cookbook."),
    EndpointSpec("chef_resolve_environment_cookbook_versions", "POST", "/organizations/{organization}/environments/{environment}/cookbook_versions", "Resolve cookbook versions required by an environment run list.", True),
    EndpointSpec("chef_list_environment_cookbooks", "GET", "/organizations/{organization}/environments/{environment}/cookbooks", "List cookbooks available to an environment."),
    EndpointSpec("chef_list_environment_nodes", "GET", "/organizations/{organization}/environments/{environment}/nodes", "List nodes in an environment."),
    EndpointSpec("chef_list_environment_recipes", "GET", "/organizations/{organization}/environments/{environment}/recipes", "List recipes in an environment."),
    EndpointSpec("chef_get_environment_role_run_list", "GET", "/organizations/{organization}/environments/{environment}/roles/{role_name}", "Get role run list for an environment."),
    EndpointSpec("chef_list_groups", "GET", "/organizations/{organization}/groups", "List groups in an organization."),
    EndpointSpec("chef_create_group", "POST", "/organizations/{organization}/groups", "Create a group in an organization.", True),
    EndpointSpec("chef_get_group", "GET", "/organizations/{organization}/groups/{group_name}", "Get a group."),
    EndpointSpec("chef_update_group", "PUT", "/organizations/{organization}/groups/{group_name}", "Update a group.", True),
    EndpointSpec("chef_delete_group", "DELETE", "/organizations/{organization}/groups/{group_name}", "Delete a group."),
    EndpointSpec("chef_list_nodes", "GET", "/organizations/{organization}/nodes", "List nodes in an organization."),
    EndpointSpec("chef_create_node", "POST", "/organizations/{organization}/nodes", "Create a node in an organization.", True),
    EndpointSpec("chef_get_node", "GET", "/organizations/{organization}/nodes/{node_name}", "Get a node."),
    EndpointSpec("chef_update_node", "PUT", "/organizations/{organization}/nodes/{node_name}", "Update a node.", True),
    EndpointSpec("chef_delete_node", "DELETE", "/organizations/{organization}/nodes/{node_name}", "Delete a node."),
    EndpointSpec("chef_head_node", "HEAD", "/organizations/{organization}/nodes/{node_name}", "Check if a node exists."),
    EndpointSpec("chef_list_policies", "GET", "/organizations/{organization}/policies", "List policies in an organization."),
    EndpointSpec("chef_list_policy_groups", "GET", "/organizations/{organization}/policy_groups", "List policy groups in an organization."),
    EndpointSpec("chef_get_principal", "GET", "/organizations/{organization}/principals/{principal_name}", "Get principal details in an organization."),
    EndpointSpec("chef_get_required_recipe", "GET", "/organizations/{organization}/required_recipe", "Get required recipe text for an organization."),
    EndpointSpec("chef_list_roles", "GET", "/organizations/{organization}/roles", "List roles in an organization."),
    EndpointSpec("chef_create_role", "POST", "/organizations/{organization}/roles", "Create a role in an organization.", True),
    EndpointSpec("chef_get_role", "GET", "/organizations/{organization}/roles/{role_name}", "Get a role."),
    EndpointSpec("chef_update_role", "PUT", "/organizations/{organization}/roles/{role_name}", "Update a role.", True),
    EndpointSpec("chef_delete_role", "DELETE", "/organizations/{organization}/roles/{role_name}", "Delete a role."),
    EndpointSpec("chef_list_role_environments", "GET", "/organizations/{organization}/roles/{role_name}/environments", "List role environments for a role."),
    EndpointSpec("chef_get_role_environment", "GET", "/organizations/{organization}/roles/{role_name}/environments/{environment}", "Get role run list for a role/environment combination."),
    EndpointSpec("chef_create_sandbox", "POST", "/organizations/{organization}/sandboxes", "Create a sandbox in an organization.", True),
    EndpointSpec("chef_commit_sandbox", "PUT", "/organizations/{organization}/sandboxes/{sandbox_id}", "Commit a sandbox in an organization.", True),
    EndpointSpec("chef_list_search_indexes", "GET", "/organizations/{organization}/search", "List available search indexes in an organization."),
    EndpointSpec("chef_search_index", "GET", "/organizations/{organization}/search/{index}", "Run a search query against an index."),
    EndpointSpec("chef_partial_search_index", "POST", "/organizations/{organization}/search/{index}", "Run a partial search query against an index.", True),
    EndpointSpec("chef_get_updated_since", "GET", "/organizations/{organization}/updated_since", "Get organization updates since a sequence number."),
    EndpointSpec("chef_list_org_users", "GET", "/organizations/{organization}/users", "List users associated with an organization."),
    EndpointSpec("chef_associate_org_user", "POST", "/organizations/{organization}/users", "Associate a user with an organization.", True),
    EndpointSpec("chef_get_org_user", "GET", "/organizations/{organization}/users/{username}", "Get a user's association details in an organization."),
    EndpointSpec("chef_disassociate_org_user", "DELETE", "/organizations/{organization}/users/{username}", "Remove a user association from an organization."),
]


def _maybe_parse_json_object(raw_json: str, field_name: str) -> dict[str, Any]:
    if not raw_json.strip():
        return {}

    parsed = parse_json_argument(raw_json, field_name)
    if parsed is None:
        return {}
    if not isinstance(parsed, dict):
        raise ValueError(f"{field_name} must be a JSON object")
    return parsed


def _required_path_params(path_template: str) -> list[str]:
    return PATH_PARAM_PATTERN.findall(path_template)


def _build_path(path_template: str, path_params: dict[str, Any]) -> str:
    required = _required_path_params(path_template)
    missing = [
        key
        for key in required
        if key not in path_params or str(path_params.get(key, "")).strip() == ""
    ]
    if missing:
        raise ValueError(
            f"Missing required path_params keys: {', '.join(sorted(missing))}"
        )

    resolved_values = {
        key: str(path_params[key]).strip().strip("/") for key in required
    }
    return path_template.format(**resolved_values)


def _register_endpoint_tool(mcp: FastMCP, spec: EndpointSpec) -> None:
    required_params = _required_path_params(spec.path_template)
    if required_params:
        path_param_description = (
            "JSON object for path variables. Required keys: "
            + ", ".join(required_params)
            + "."
        )
    else:
        path_param_description = "JSON object for path variables. Use '{}' for none."

    body_description = "JSON string request body."
    if not spec.requires_body:
        body_description += " Optional for this endpoint."

    @mcp.tool(name=spec.tool_name, description=spec.description)
    def endpoint_tool(
        auth_data: str = Field(
            ...,
            description="JSON string auth payload. Use chef-signature auth for tenant-facing Chef API calls; use basic auth for endpoints like /_stats when needed.",
        ),
        server_url: str = Field(
            ...,
            description="Chef Server base URL, for example https://chef.example.com.",
        ),
        path_params: str = Field("{}", description=path_param_description),
        query_params: str = Field(
            "{}", description="JSON object string for query string parameters."
        ),
        body: str = Field("", description=body_description),
        timeout_seconds: float = Field(
            DEFAULT_TIMEOUT_SECONDS,
            description="Request timeout in seconds.",
        ),
    ) -> str:
        try:
            parsed_auth = parse_auth_data(auth_data)
            parsed_path_params = _maybe_parse_json_object(path_params, "path_params")
            parsed_query_params = _maybe_parse_json_object(
                query_params, "query_params"
            )

            if spec.method in {"GET", "HEAD", "DELETE"} and body.strip():
                raise ValueError(
                    f"body is not supported for {spec.tool_name} ({spec.method})"
                )
            if spec.requires_body and not body.strip():
                raise ValueError(f"body is required for {spec.tool_name}")

            parsed_body: Any = None
            if body.strip():
                parsed_body = parse_json_argument(body, "body")

            path = _build_path(spec.path_template, parsed_path_params)
            result = perform_chef_request(
                server_url=server_url,
                auth_data=parsed_auth,
                method=spec.method,
                path=path,
                query_params=parsed_query_params,
                body=parsed_body,
                timeout_seconds=timeout_seconds,
            )
            return json.dumps(result)
        except Exception as e:
            logger.error("Failed %s: %s", spec.tool_name, e)
            return json.dumps({"error": str(e)})


def register_tools(mcp: FastMCP) -> None:
    @mcp.tool(
        name="health_check",
        description="Check server readiness and return Chef API docs reference.",
    )
    def health_check() -> str:
        return json.dumps(
            {
                "status": "ok",
                "server": "CL Chef Server MCP Server",
                "docs": CHEF_API_DOCS_URL,
            }
        )

    for endpoint_spec in ENDPOINT_SPECS:
        _register_endpoint_tool(mcp, endpoint_spec)
