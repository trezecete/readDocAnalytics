from __future__ import annotations

import os
from typing import Any

from google_auth_oauthlib.flow import Flow
from oauthlib.oauth2 import OAuth2Error
from pydantic import BaseModel

from app.config import Settings
from app.errors import ConfigurationError, UserFacingError


class CredentialsData(BaseModel):
    token: str
    refresh_token: str | None = None
    token_uri: str = "https://oauth2.googleapis.com/token"
    client_id: str | None = None
    client_secret: str | None = None
    scopes: list[str]


class GoogleOAuthClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def authorization_url(self, state: str) -> tuple[str, str]:
        flow = self._build_flow()
        authorization_url, _ = flow.authorization_url(
            access_type="online",
            state=state,
            prompt="consent",
        )
        if not flow.code_verifier:
            raise ConfigurationError("Nao foi possivel iniciar o fluxo OAuth com PKCE.")
        return authorization_url, flow.code_verifier

    def fetch_credentials(
        self,
        authorization_response: str,
        code_verifier: str | None,
    ) -> CredentialsData:
        if not code_verifier:
            raise UserFacingError(
                "Sessao OAuth incompleta. Recomece o login para gerar um novo verificador PKCE.",
                status_code=400,
            )

        flow = self._build_flow(code_verifier=code_verifier)
        try:
            flow.fetch_token(authorization_response=authorization_response)
        except OAuth2Error as exc:
            raise UserFacingError(
                "O Google recusou a troca do codigo OAuth. Recomece o login e confirme o "
                "redirect URI configurado.",
                status_code=400,
            ) from exc
        credentials = flow.credentials
        return CredentialsData(
            token=credentials.token,
            refresh_token=credentials.refresh_token,
            token_uri=credentials.token_uri,
            client_id=credentials.client_id,
            client_secret=credentials.client_secret,
            scopes=list(credentials.scopes or self.settings.docs_oauth_scopes),
        )

    def _build_flow(self, code_verifier: str | None = None) -> Flow:
        if not self.settings.google_client_id or not self.settings.google_client_secret:
            raise ConfigurationError(
                "OAuth Google nao configurado. Defina GOOGLE_CLIENT_ID e GOOGLE_CLIENT_SECRET.",
                status_code=500,
            )

        if self.settings.oauth_redirect_uri.startswith("http://localhost"):
            os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")

        client_config: dict[str, Any] = {
            "web": {
                "client_id": self.settings.google_client_id,
                "client_secret": self.settings.google_client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [self.settings.oauth_redirect_uri],
            }
        }
        flow = Flow.from_client_config(
            client_config,
            scopes=self.settings.docs_oauth_scopes,
            code_verifier=code_verifier,
            autogenerate_code_verifier=code_verifier is None,
        )
        flow.redirect_uri = self.settings.oauth_redirect_uri
        return flow
