import base64
import struct

import pytest

from software_factory.security.owner_authorization import (
    OWNER_AUTH_NAMESPACE,
    require_fido_presence_and_verification,
    sshsig_fido_flags,
)


def ssh_string(value: bytes) -> bytes:
    return struct.pack(">I", len(value)) + value


def fido_signature(flags: int, algorithm: bytes = b"sk-ssh-ed25519@openssh.com") -> str:
    if algorithm == b"sk-ecdsa-sha2-nistp256@openssh.com":
        public_key = ssh_string(algorithm) + ssh_string(b"nistp256") + ssh_string(b"public-key") + ssh_string(b"ssh:")
    else:
        public_key = ssh_string(algorithm) + ssh_string(b"public-key") + ssh_string(b"ssh:")
    if algorithm == b"sk-ecdsa-sha2-nistp256@openssh.com":
        signature_data = ssh_string(b"r") + ssh_string(b"s")
    else:
        signature_data = ssh_string(b"signature-bytes")
    signature_field = ssh_string(algorithm) + signature_data + bytes([flags]) + struct.pack(">I", 3)
    body = (
        b"SSHSIG"
        + struct.pack(">I", 1)
        + ssh_string(public_key)
        + ssh_string(OWNER_AUTH_NAMESPACE.encode())
        + ssh_string(b"")
        + ssh_string(b"sha512")
        + ssh_string(signature_field)
    )
    encoded = base64.b64encode(body).decode()
    return f"-----BEGIN SSH SIGNATURE-----\n{encoded}\n-----END SSH SIGNATURE-----\n"


def test_fido_signature_requires_presence_and_user_verification_flags():
    require_fido_presence_and_verification(fido_signature(0x05), OWNER_AUTH_NAMESPACE)
    with pytest.raises(ValueError, match="presence and verification"):
        require_fido_presence_and_verification(fido_signature(0x01), OWNER_AUTH_NAMESPACE)


def test_software_signature_algorithm_is_rejected():
    with pytest.raises(ValueError, match="not FIDO-backed"):
        require_fido_presence_and_verification(fido_signature(0x05, b"ssh-ed25519"), OWNER_AUTH_NAMESPACE)


def test_wrong_namespace_and_malformed_signature_are_rejected():
    with pytest.raises(ValueError, match="namespace mismatch"):
        require_fido_presence_and_verification(fido_signature(0x05), "other-domain")
    with pytest.raises(ValueError):
        require_fido_presence_and_verification("not a signature", OWNER_AUTH_NAMESPACE)


def test_software_signature_and_missing_user_verification_are_not_trusted():
    software_signature = fido_signature(0x05, b"ssh-ed25519")
    with pytest.raises(ValueError, match="not FIDO-backed"):
        require_fido_presence_and_verification(software_signature, OWNER_AUTH_NAMESPACE)

    presence_only = fido_signature(0x01)
    with pytest.raises(ValueError, match="presence and verification"):
        require_fido_presence_and_verification(presence_only, OWNER_AUTH_NAMESPACE)


def test_ecdsa_fido_signature_flags_are_parsed():
    require_fido_presence_and_verification(
        fido_signature(0x05, b"sk-ecdsa-sha2-nistp256@openssh.com"),
        OWNER_AUTH_NAMESPACE,
    )


def test_flags_without_presence_are_rejected():
    with pytest.raises(ValueError, match="presence and verification"):
        require_fido_presence_and_verification(fido_signature(0x04), OWNER_AUTH_NAMESPACE)


def test_sshsig_flags_parser_returns_namespace_and_flags():
    namespace, flags = sshsig_fido_flags(fido_signature(0x05))
    assert namespace == OWNER_AUTH_NAMESPACE
    assert flags == 0x05


def test_truncated_sshsig_body_is_rejected():
    valid = fido_signature(0x05)
    broken = valid.replace(valid.splitlines()[1], "aGVsbG8=")
    with pytest.raises(ValueError):
        require_fido_presence_and_verification(broken, OWNER_AUTH_NAMESPACE)


def test_invalid_base64_is_rejected():
    with pytest.raises(ValueError):
        require_fido_presence_and_verification(
            "-----BEGIN SSH SIGNATURE-----\n!!!not-base64!!!\n-----END SSH SIGNATURE-----\n",
            OWNER_AUTH_NAMESPACE,
        )


def test_algorithm_mismatch_is_rejected():
    # ECDSA public key type but Ed25519 signature algorithm inside the field.
    public_key = ssh_string(b"sk-ecdsa-sha2-nistp256@openssh.com") + ssh_string(b"nistp256") + ssh_string(b"pub") + ssh_string(b"ssh:")
    signature_field = ssh_string(b"sk-ssh-ed25519@openssh.com") + ssh_string(b"sig") + bytes([0x05]) + struct.pack(">I", 1)
    body = (
        b"SSHSIG" + struct.pack(">I", 1)
        + ssh_string(public_key)
        + ssh_string(OWNER_AUTH_NAMESPACE.encode())
        + ssh_string(b"")
        + ssh_string(b"sha512")
        + ssh_string(signature_field)
    )
    encoded = base64.b64encode(body).decode()
    sig = f"-----BEGIN SSH SIGNATURE-----\n{encoded}\n-----END SSH SIGNATURE-----\n"
    with pytest.raises(ValueError, match="does not match"):
        require_fido_presence_and_verification(sig, OWNER_AUTH_NAMESPACE)
