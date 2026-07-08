from app.auth.oauth import GoogleOAuthClient
from app.config import Settings


def test_authorization_url_uses_pkce_and_minimal_scope_only():
    settings = Settings(
        google_client_id="client-id",
        google_client_secret="client-secret",
        app_base_url="http://localhost:8080",
    )
    client = GoogleOAuthClient(settings)

    authorization_url, code_verifier = client.authorization_url("state-123")

    assert code_verifier
    assert "code_challenge=" in authorization_url
    assert "https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fdocuments.readonly" in authorization_url
    assert "include_granted_scopes" not in authorization_url

