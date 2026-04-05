from typing import Literal, TypedDict


class ChefAuthData(TypedDict, total=False):
    auth_type: Literal["chef-signature", "basic"]
    user_id: str
    private_key: str
    private_key_base64: str
    auth_version: Literal["1.0", "1.3"]
    chef_version: str
    server_api_version: str
    basic_username: str
    basic_password: str


class ToolError(TypedDict):
    error: str


class ChefApiResponse(TypedDict, total=False):
    status_code: int
    headers: dict[str, str]
    data: object
    text: str
    error: str
