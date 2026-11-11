"""Scope guards: the desktop console only authorizes and revokes.

Merge execution is deliberately absent from this build until the API exposes a
SHA-bound execution endpoint and the owner enables it. These tests fail if the
forbidden client/signer surfaces are reintroduced.
"""

from desktop_console import owner_auth_client, owner_signer


def test_console_client_exposes_no_merge_or_execution_calls():
    client = owner_auth_client.OwnerAuthorizationClient()
    assert not hasattr(client, "merge")
    assert not hasattr(client, "execution_context")


def test_console_signer_exposes_no_execution_namespace():
    assert not hasattr(owner_signer, "EXECUTE_NAMESPACE")
