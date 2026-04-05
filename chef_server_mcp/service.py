import base64
import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, cast
from urllib.parse import urljoin, urlparse

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey

from .config import (
    DEFAULT_AUTH_VERSION,
    DEFAULT_CHEF_VERSION,
    DEFAULT_SERVER_API_VERSION,
    DEFAULT_TIMEOUT_SECONDS,
    DEFAULT_USER_AGENT,
)
from .schemas import ChefApiResponse, ChefAuthData

logger = logging.getLogger("chef-server-mcp-server")


def parse_auth_data(auth_data: str) -> ChefAuthData:
    """Parse auth data JSON for per-request, stateless authentication."""
    try:
        parsed = json.loads(auth_data)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid auth_data JSON: {e}") from e

    if not isinstance(parsed, dict):
        raise ValueError("auth_data must decode to a JSON object")

    return cast(ChefAuthData, parsed)


def parse_json_argument(raw_json: str, field_name: str) -> Any:
    """Decode JSON string arguments used by MCP tools."""
    try:
        return json.loads(raw_json)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid {field_name} JSON: {e}") from e


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_path(path: str) -> str:
    cleaned = (path or "").strip()
    if not cleaned:
        return "/"

    parsed = urlparse(cleaned)
    if parsed.scheme and parsed.netloc:
        cleaned = parsed.path
    else:
        cleaned = cleaned.split("?", 1)[0].split("#", 1)[0]

    if not cleaned.startswith("/"):
        cleaned = f"/{cleaned}"

    # Collapse duplicate separators and remove trailing slash except root.
    segments = [segment for segment in cleaned.split("/") if segment]
    normalized = "/" + "/".join(segments)
    return normalized or "/"


def _serialize_body(body: Any) -> bytes:
    if body is None:
        return b""
    if isinstance(body, bytes):
        return body
    if isinstance(body, str):
        return body.encode("utf-8")
    return json.dumps(body, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _sha256_b64(data: bytes) -> str:
    return base64.b64encode(hashlib.sha256(data).digest()).decode("utf-8")


def _sha1_b64(text: str) -> str:
    return base64.b64encode(hashlib.sha1(text.encode("utf-8")).digest()).decode("utf-8")


def _build_chef_signature_headers(
    auth_data: ChefAuthData,
    method: str,
    normalized_path: str,
    body_bytes: bytes,
) -> dict[str, str]:
    user_id = auth_data.get("user_id", "")
    if not user_id:
        raise ValueError("Chef signature auth requires auth_data.user_id")

    private_key = auth_data.get("private_key")
    private_key_base64 = auth_data.get("private_key_base64")
    if not private_key and not private_key_base64:
        raise ValueError(
            "Chef signature auth requires auth_data.private_key or auth_data.private_key_base64"
        )

    key_material = private_key
    if private_key_base64:
        try:
            key_material = base64.b64decode(private_key_base64).decode("utf-8")
        except Exception as e:
            raise ValueError(f"Invalid private_key_base64 value: {e}") from e

    if not key_material:
        raise ValueError("Unable to load private key material")

    key_bytes = key_material.encode("utf-8")
    loaded_private_key = cast(
        RSAPrivateKey,
        serialization.load_pem_private_key(key_bytes, password=None),
    )

    auth_version = auth_data.get("auth_version", DEFAULT_AUTH_VERSION)
    chef_version = auth_data.get("chef_version", DEFAULT_CHEF_VERSION)
    server_api_version = auth_data.get("server_api_version", DEFAULT_SERVER_API_VERSION)

    timestamp = _utc_timestamp()
    content_hash = _sha256_b64(body_bytes)
    upper_method = method.upper()

    if auth_version == "1.0":
        canonical_string = "\n".join(
            [
                f"Method:{upper_method}",
                f"Hashed Path:{_sha1_b64(normalized_path)}",
                f"X-Ops-Content-Hash:{content_hash}",
                f"X-Ops-Timestamp:{timestamp}",
                f"X-Ops-UserId:{user_id}",
            ]
        )
        signature = loaded_private_key.sign(
            canonical_string.encode("utf-8"),
            padding.PKCS1v15(),
            hashes.SHA1(),
        )
        x_ops_sign = "algorithm=sha1;version=1.0;"
    elif auth_version == "1.3":
        canonical_string = "\n".join(
            [
                f"Method:{upper_method}",
                f"Path:{normalized_path}",
                f"X-Ops-Content-Hash:{content_hash}",
                "X-Ops-Sign:version=1.3",
                f"X-Ops-Timestamp:{timestamp}",
                f"X-Ops-UserId:{user_id}",
                f"X-Ops-Server-API-Version:{server_api_version}",
            ]
        )
        signature = loaded_private_key.sign(
            canonical_string.encode("utf-8"),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        x_ops_sign = "version=1.3"
    else:
        raise ValueError("Unsupported auth_version. Use '1.0' or '1.3'.")

    signature_b64 = base64.b64encode(signature).decode("utf-8")
    auth_chunks = [signature_b64[i : i + 60] for i in range(0, len(signature_b64), 60)]

    headers = {
        "Accept": "application/json",
        "User-Agent": DEFAULT_USER_AGENT,
        "X-Chef-Version": chef_version,
        "X-Ops-Content-Hash": content_hash,
        "X-Ops-Sign": x_ops_sign,
        "X-Ops-Timestamp": timestamp,
        "X-Ops-Userid": user_id,
        "X-Ops-Server-API-Version": str(server_api_version),
    }

    for idx, chunk in enumerate(auth_chunks, start=1):
        headers[f"X-Ops-Authorization-{idx}"] = chunk

    return headers


def _build_basic_auth_headers(
    auth_data: ChefAuthData,
    body_bytes: bytes,
    has_body: bool,
) -> dict[str, str]:
    username = auth_data.get("basic_username", "")
    password = auth_data.get("basic_password", "")
    if not username or not password:
        raise ValueError(
            "Basic auth requires auth_data.basic_username and auth_data.basic_password"
        )

    token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("utf-8")
    headers = {
        "Accept": "application/json",
        "Authorization": f"Basic {token}",
        "User-Agent": DEFAULT_USER_AGENT,
        "X-Ops-Content-Hash": _sha256_b64(body_bytes),
    }
    if has_body:
        headers["Content-Type"] = "application/json"
    return headers


def _build_headers(
    auth_data: ChefAuthData,
    method: str,
    normalized_path: str,
    body_bytes: bytes,
    has_body: bool,
) -> dict[str, str]:
    auth_type = auth_data.get("auth_type", "chef-signature")
    if auth_type == "basic":
        return _build_basic_auth_headers(auth_data, body_bytes, has_body)

    headers = _build_chef_signature_headers(auth_data, method, normalized_path, body_bytes)
    if has_body:
        headers["Content-Type"] = "application/json"
    return headers


def perform_chef_request(
    server_url: str,
    auth_data: ChefAuthData,
    method: str,
    path: str,
    query_params: dict[str, Any] | None = None,
    body: Any = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> ChefApiResponse:
    """Perform a single Chef Server API request with per-call auth."""
    try:
        if not server_url:
            raise ValueError("server_url is required")

        normalized_path = _normalize_path(path)
        body_bytes = _serialize_body(body)
        has_body = method.upper() in {"POST", "PUT", "PATCH"}

        headers = _build_headers(auth_data, method, normalized_path, body_bytes, has_body)

        full_url = urljoin(server_url.rstrip("/") + "/", normalized_path.lstrip("/"))
        logger.info("Executing Chef API request %s %s", method.upper(), normalized_path)

        with httpx.Client(timeout=timeout_seconds) as client:
            response = client.request(
                method=method.upper(),
                url=full_url,
                headers=headers,
                params=query_params,
                content=body_bytes if has_body else None,
            )

        content_type = response.headers.get("Content-Type", "")
        response_headers = {
            "content-type": content_type,
            "x-request-id": response.headers.get("x-request-id", ""),
            "x-ops-request-id": response.headers.get("x-ops-request-id", ""),
        }

        if "application/json" in content_type.lower() and response.content:
            try:
                data: object = response.json()
            except Exception:
                data = response.text
        else:
            data = response.text

        return {
            "status_code": response.status_code,
            "headers": response_headers,
            "data": data,
        }
    except Exception as e:
        logger.error("Chef API request failed: %s", e, exc_info=True)
        return {"error": str(e)}
