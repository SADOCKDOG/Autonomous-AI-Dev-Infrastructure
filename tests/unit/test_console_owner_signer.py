import base64
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from desktop_console import owner_signer


def make_test_key(tmp_path: Path):
    handle = tmp_path / "owner-key-handle"
    handle.write_text("synthetic hardware handle", encoding="ascii")
    blob = b"synthetic public blob"
    (tmp_path / "owner-key-handle.pub").write_text(
        "sk-ssh-ed25519@openssh.com " + base64.b64encode(blob).decode() + " owner-key\n",
        encoding="ascii",
    )
    key_id = "SHA256:" + base64.b64encode(hashlib.sha256(blob).digest()).decode().rstrip("=")
    return handle, key_id


def test_legacy_console_signer_requires_fido_type_and_owner_sha(tmp_path):
    handle, key_id = make_test_key(tmp_path)
    with pytest.raises(owner_signer.OwnerSignerError, match="incorrecta"):
        owner_signer._broker_sign(
            {"repository": "SADOCKDOG/LIVESTOCK-MANAGER", "pr_number": 204, "head_sha": "a" * 40},
            key_handle_path=handle,
            expected_key_id=key_id,
            namespace=owner_signer.AUTH_NAMESPACE,
            signature_output=tmp_path / "sig",
            input_fn=lambda _prompt: "b" * 12,
            run_command=lambda *_a, **_kw: (_ for _ in ()).throw(AssertionError("must not sign")),
            output_fn=lambda _line: None,
        )


def test_legacy_console_broker_shows_signed_scope_and_uses_hardware_verification(tmp_path):
    handle, key_id = make_test_key(tmp_path)
    payload = {
        "repository": "SADOCKDOG/LIVESTOCK-MANAGER",
        "pr_number": 204,
        "head_sha": "c" * 40,
        "base_ref": "master",
        "base_sha": "d" * 40,
        "scope": {"operation": "MERGE", "allowed_files": ["js/a.js"], "allow_agent_execution": False},
        "decision": "AUTHORIZE_MERGE",
    }
    shown = []

    def fake_run(command, **_kwargs):
        target = Path(command[-1])
        Path(str(target) + ".sig").write_text(
            "-----BEGIN SSH SIGNATURE-----\ntest\n-----END SSH SIGNATURE-----\n",
            encoding="ascii",
        )
        assert "verify-required" not in command
        return SimpleNamespace(returncode=0)

    owner_signer._broker_sign(
        payload,
        key_handle_path=handle,
        expected_key_id=key_id,
        namespace=owner_signer.AUTH_NAMESPACE,
        signature_output=tmp_path / "signature.out",
        input_fn=lambda _prompt: payload["head_sha"][-12:],
        run_command=fake_run,
        output_fn=shown.append,
    )
    assert any("SADOCKDOG/LIVESTOCK-MANAGER" in line for line in shown)
    assert any(payload["head_sha"] in line for line in shown)
    assert any("allow_agent_execution" in line for line in shown)
