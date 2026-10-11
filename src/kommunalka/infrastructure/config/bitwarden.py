"""Secrets from Bitwarden Secrets Manager through the official SDK."""

from uuid import UUID

from bitwarden_sdk import BitwardenClient


def read_secrets(access_token: str, organization_id: UUID) -> dict[str, str]:
    """Every secret the machine account can read in the organization, by key."""
    client = BitwardenClient()
    client.auth().login_access_token(access_token)
    identifiers = client.secrets().list(str(organization_id)).data
    if identifiers is None or not identifiers.data:
        return {}
    secrets = client.secrets().get_by_ids([secret.id for secret in identifiers.data]).data
    return {secret.key: secret.value for secret in secrets.data} if secrets else {}
