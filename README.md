# CL Chef Server MCP Server

A Model Context Protocol (MCP) server that exposes the Chef Infra Server API for generic, stateless, multi-tenant API operations.

## Overview

This MCP is an integration server for Chef Infra Server and follows Curious Layer standards:

- Stateless and multi-tenant by design
- Per-request authentication (no shared in-memory auth/session state)
- Generic API coverage for all Chef Server endpoints via tool calls

## Authentication

All tenant-facing tools require authentication input on every call.

### Chef Signature Auth (default)

Use this auth payload format in auth_data:

```json
{
  "auth_type": "chef-signature",
  "user_id": "pivotal",
  "private_key": "-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----",
  "auth_version": "1.3",
  "chef_version": "18.0.0",
  "server_api_version": "1"
}
```

Notes:
- private_key_base64 can be used instead of private_key.
- auth_version supports 1.3 (recommended) and 1.0.

### Basic Auth (for endpoints like /_stats)

```json
{
  "auth_type": "basic",
  "basic_username": "statsuser",
  "basic_password": "your-password"
}
```

## Tools

This server exposes dedicated tools per endpoint functionality (instead of a generic wrapper).

- health_check

Global endpoint tools:
- chef_authenticate_user
- chef_get_license
- chef_list_organizations_global
- chef_create_organization_global
- chef_get_organization_global
- chef_update_organization_global
- chef_delete_organization_global
- chef_get_stats
- chef_get_status
- chef_list_users_global
- chef_create_user_global
- chef_get_user_global
- chef_update_user_global
- chef_delete_user_global
- chef_list_user_keys_global
- chef_create_user_key_global
- chef_get_user_key_global
- chef_update_user_key_global
- chef_delete_user_key_global
- chef_get_universe_global

Organization endpoint tools:
- chef_list_association_requests
- chef_create_association_request
- chef_delete_association_request
- chef_list_clients
- chef_create_client
- chef_get_client
- chef_update_client
- chef_delete_client
- chef_list_client_keys
- chef_create_client_key
- chef_get_client_key
- chef_update_client_key
- chef_delete_client_key
- chef_list_containers
- chef_create_container
- chef_get_container
- chef_delete_container
- chef_list_cookbook_artifacts
- chef_get_cookbook_artifact
- chef_get_cookbook_artifact_version
- chef_upsert_cookbook_artifact_version
- chef_delete_cookbook_artifact_version
- chef_list_cookbooks
- chef_get_latest_cookbooks
- chef_get_latest_recipes
- chef_get_cookbook
- chef_get_cookbook_version
- chef_upsert_cookbook_version
- chef_delete_cookbook_version
- chef_list_data_bags
- chef_create_data_bag
- chef_get_data_bag
- chef_create_data_bag_item
- chef_delete_data_bag
- chef_get_data_bag_item
- chef_update_data_bag_item
- chef_delete_data_bag_item
- chef_list_environments
- chef_create_environment
- chef_get_default_environment
- chef_get_environment
- chef_update_environment
- chef_delete_environment
- chef_get_environment_cookbook
- chef_resolve_environment_cookbook_versions
- chef_list_environment_cookbooks
- chef_list_environment_nodes
- chef_list_environment_recipes
- chef_get_environment_role_run_list
- chef_list_groups
- chef_create_group
- chef_get_group
- chef_update_group
- chef_delete_group
- chef_list_nodes
- chef_create_node
- chef_get_node
- chef_update_node
- chef_delete_node
- chef_head_node
- chef_list_policies
- chef_list_policy_groups
- chef_get_principal
- chef_get_required_recipe
- chef_list_roles
- chef_create_role
- chef_get_role
- chef_update_role
- chef_delete_role
- chef_list_role_environments
- chef_get_role_environment
- chef_create_sandbox
- chef_commit_sandbox
- chef_list_search_indexes
- chef_search_index
- chef_partial_search_index
- chef_get_updated_since
- chef_list_org_users
- chef_associate_org_user
- chef_get_org_user
- chef_disassociate_org_user

## Setup

```bash
pip install -r requirements.txt
```

## Running the Server

```bash
# stdio
python server.py

# sse
python server.py --transport sse --host 127.0.0.1 --port 8001

# streamable-http
python server.py --transport streamable-http --host 127.0.0.1 --port 8001
```

## Example Tool Calls

### Global endpoint request

```json
{
  "tool": "chef_list_organizations_global",
  "arguments": {
    "auth_data": "{\"auth_type\":\"chef-signature\",\"user_id\":\"pivotal\",\"private_key\":\"-----BEGIN RSA PRIVATE KEY-----\\n...\\n-----END RSA PRIVATE KEY-----\"}",
    "server_url": "https://chef.example.com",
    "path_params": "{}",
    "query_params": "{}"
  }
}
```

### Organization-scoped request

```json
{
  "tool": "chef_list_nodes",
  "arguments": {
    "auth_data": "{\"auth_type\":\"chef-signature\",\"user_id\":\"my-client\",\"private_key\":\"-----BEGIN RSA PRIVATE KEY-----\\n...\\n-----END RSA PRIVATE KEY-----\"}",
    "server_url": "https://chef.example.com",
    "path_params": "{\"organization\":\"my-org\"}",
    "query_params": "{}"
  }
}
```

### Basic auth endpoint request

```json
{
  "tool": "chef_get_stats",
  "arguments": {
    "auth_data": "{\"auth_type\":\"basic\",\"basic_username\":\"statsuser\",\"basic_password\":\"secret\"}",
    "server_url": "https://chef.example.com",
    "path_params": "{}",
    "query_params": "{\"format\":\"json\"}"
  }
}
```

## Project Structure

```text
cl-mcp-chef-server/
|-- server.py
|-- requirements.txt
|-- README.md
`-- chef_server_mcp/
    |-- __init__.py
    |-- cli.py
    |-- config.py
    |-- tools.py
    |-- schemas.py
    `-- service.py
```

## Resources

- Chef Infra Server API docs: https://docs.chef.io/server/api_chef_server/
- FastMCP docs: https://gofastmcp.com/v2/getting-started/welcome
