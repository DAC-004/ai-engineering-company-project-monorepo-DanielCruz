"""Local OIDC issuer for MCP Auth resource-server tests.

Serves OpenID Connect discovery and a JWKS document, and signs RS256 access
tokens. It is an authorization server for token validation, not a substitute
for mcpauth.
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass

import jwt
import uvicorn
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

KEY_ID = "healthcore-test"


@dataclass
class OidcIssuer:
    """Running discovery server plus the key used to mint test access tokens."""

    issuer: str
    private_key_pem: bytes
    server: uvicorn.Server
    thread: threading.Thread

    def mint_access_token(
        self,
        *,
        audience: str,
        scopes: list[str],
        client_id: str,
        subject: str = "healthcore-operator",
    ) -> str:
        issued_at = int(time.time())
        payload = {
            "iss": self.issuer,
            "sub": subject,
            "aud": audience,
            "iat": issued_at,
            "exp": issued_at + 600,
            "scope": " ".join(scopes),
            "client_id": client_id,
        }
        token = jwt.encode(
            payload,
            self.private_key_pem,
            algorithm="RS256",
            headers={"kid": KEY_ID},
        )
        if isinstance(token, bytes):
            return token.decode("ascii")
        return token

    def stop(self) -> None:
        self.server.should_exit = True
        self.thread.join(timeout=5)


def start_oidc_issuer(port: int) -> OidcIssuer:
    """Bind an OIDC discovery document and JWKS on 127.0.0.1."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_key_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_jwk = json.loads(RSAAlgorithm.to_jwk(private_key.public_key()))
    public_jwk.update({"kid": KEY_ID, "use": "sig", "alg": "RS256"})
    issuer = f"http://127.0.0.1:{port}"
    metadata = {
        "issuer": issuer,
        "authorization_endpoint": f"{issuer}/authorize",
        "token_endpoint": f"{issuer}/token",
        "jwks_uri": f"{issuer}/jwks",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code"],
        "code_challenge_methods_supported": ["S256"],
        "subject_types_supported": ["public"],
        "id_token_signing_alg_values_supported": ["RS256"],
    }

    def openid_configuration(_request: Request) -> JSONResponse:
        return JSONResponse(metadata)

    def jwks(_request: Request) -> JSONResponse:
        return JSONResponse({"keys": [public_jwk]})

    app = Starlette(
        routes=[
            Route("/.well-known/openid-configuration", openid_configuration),
            Route("/jwks", jwks),
        ]
    )
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, name="oidc-issuer", daemon=True)
    thread.start()
    _wait_until_started(server, thread)
    return OidcIssuer(
        issuer=issuer,
        private_key_pem=private_key_pem,
        server=server,
        thread=thread,
    )


def _wait_until_started(server: uvicorn.Server, thread: threading.Thread) -> None:
    for _ in range(100):
        if server.started:
            return
        if not thread.is_alive():
            break
        time.sleep(0.05)
    raise RuntimeError("OIDC issuer did not start")
