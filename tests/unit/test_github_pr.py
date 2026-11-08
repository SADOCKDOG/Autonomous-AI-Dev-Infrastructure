from __future__ import annotations

import pytest

from software_factory.git.github_pr import GitHubIntegrationError, GitHubPRClient


REPO = "SADOCKDOG/LIVESTOCK-MANAGER"
HEAD = "a" * 40
BASE = "b" * 40


def _client(monkeypatch, *, protections=None, rulesets=None, checks=None, files=None):
    client = GitHubPRClient(owner_authorization_app_id=30)
    protections = protections or {
        "enforce_admins": {"enabled": True},
        "allow_force_pushes": {"enabled": False},
        "allow_deletions": {"enabled": False},
        "required_pull_request_reviews": {
            "required_approving_review_count": 0,
            "require_code_owner_reviews": False,
            "require_last_push_approval": False,
        },
        "required_status_checks": {
            "strict": True,
            "checks": [
                {"context": "Product tests", "app_id": 10},
                {"context": "CodeQL", "app_id": 20},
                {"context": "Owner authorization", "app_id": 30},
            ],
        },
    }
    rulesets = [] if rulesets is None else rulesets
    checks = checks or [
        {"name": "Product tests", "conclusion": "success", "app": {"id": 10}},
        {"name": "CodeQL", "conclusion": "success", "app": {"id": 20}},
        {"name": "Owner authorization", "conclusion": "success", "app": {"id": 30}},
    ]
    files = files or [{
        "filename": "js/a.js", "status": "modified", "sha": "c" * 40,
        "additions": 1, "deletions": 1, "changes": 2, "patch": "@@ -1 +1 @@\n-old\n+new",
    }]

    def api_json(*args, **kwargs):
        endpoint = next((arg for arg in args if isinstance(arg, str) and arg.startswith("repos/")), "")
        if "/pulls/" in endpoint and not endpoint.endswith("/files") and "/merge" not in endpoint:
            return {
                "number": 321,
                "state": "open",
                "draft": False,
                "mergeable": True,
                "html_url": f"https://github.com/{REPO}/pull/321",
                "head": {"sha": HEAD, "ref": "feat/a"},
                "base": {"sha": BASE, "ref": "master", "repo": {"full_name": REPO}},
            }
        if endpoint.endswith("/protection"):
            return protections
        if endpoint.endswith("/rulesets?includes_parents=true"):
            return rulesets
        if endpoint.endswith("/merge"):
            return {"merged": True, "sha": "d" * 40}
        if "/collaborators/" in endpoint and endpoint.endswith("/permission"):
            return {"user": {"login": "SADOCKDOG"}, "permission": "admin"}
        return {}

    def api_pages(endpoint, collection_key=None):
        if endpoint.endswith("/files"):
            return files
        if "/check-runs" in endpoint:
            return checks
        raise AssertionError(f"Unexpected paginated endpoint: {endpoint}")

    monkeypatch.setattr(client, "_api_json", api_json)
    monkeypatch.setattr(client, "_api_pages", api_pages)
    return client


def test_inspect_binds_pr_sha_files_checks_and_source_app(monkeypatch):
    snapshot = _client(monkeypatch).inspect(REPO, 321)
    assert snapshot.head_sha == HEAD
    assert snapshot.base_sha == BASE
    assert snapshot.html_url.endswith("/pull/321")
    assert snapshot.files == ("js/a.js",)
    assert snapshot.diff_sha256
    assert snapshot.branch_protection_valid is True
    assert snapshot.required_checks_pass() is True


def test_missing_or_wrong_source_check_fails_closed(monkeypatch):
    checks = [
        {"name": "Product tests", "conclusion": "success", "app": {"id": 10}},
        {"name": "CodeQL", "conclusion": "failure", "app": {"id": 999}},
        {"name": "Owner authorization", "conclusion": "success", "app": {"id": 30}},
    ]
    snapshot = _client(monkeypatch, checks=checks).inspect(REPO, 321)
    assert snapshot.branch_protection_valid is True
    assert snapshot.required_checks_pass() is False


def test_any_active_unverified_ruleset_or_bypass_blocks(monkeypatch):
    rulesets = [{
        "enforcement": "active",
        "conditions": {"ref_name": {"include": ["refs/heads/master"], "exclude": []}},
        "bypass_actors": [{"actor_id": 5, "bypass_mode": "always"}],
        "rules": [],
    }]
    snapshot = _client(monkeypatch, rulesets=rulesets).inspect(REPO, 321)
    assert snapshot.has_bypass is True
    assert snapshot.has_unverified_ruleset is True
    assert snapshot.branch_protection_valid is False


def test_missing_required_checks_or_strict_base_policy_fails_closed(monkeypatch):
    protection = {
        "enforce_admins": {"enabled": True},
        "allow_force_pushes": {"enabled": False},
        "allow_deletions": {"enabled": False},
        "required_pull_request_reviews": {"required_approving_review_count": 0},
        "required_status_checks": None,
    }
    snapshot = _client(monkeypatch, protections=protection).inspect(REPO, 321)
    assert snapshot.branch_protection_valid is False
    assert snapshot.required_checks_pass() is False


def test_no_write_methods_on_readonly_client():
    client = GitHubPRClient()
    assert not hasattr(client, "merge_sha_preconditioned")
    assert not hasattr(client, "merge_ready")


def test_mutating_api_is_rejected(monkeypatch):
    client = GitHubPRClient()
    called = []
    monkeypatch.setattr("software_factory.git.github_pr.subprocess.run", lambda *a, **k: called.append(True))
    with pytest.raises(GitHubIntegrationError, match="Mutating"):
        client._api_json("repos/x/y/pulls/1/merge", method="PUT")
    assert not called


def test_fields_are_forbidden_on_readonly_client():
    client = GitHubPRClient()
    with pytest.raises(GitHubIntegrationError, match="Fields are forbidden"):
        client._api_json("repos/x/y/pulls/1", fields={"state": "open"})


def test_default_method_is_forced_get(monkeypatch):
    client = GitHubPRClient()
    captured: list[list[str]] = []
    class Completed:
        returncode = 0
        stdout = '{"ok": true}'
    monkeypatch.setattr(
        "software_factory.git.github_pr.subprocess.run",
        lambda cmd, **kw: (captured.append(list(cmd)), Completed())[1],
    )
    result = client._api_json("repos/x/y/pulls/1")
    assert result == {"ok": True}
    assert captured and captured[0][1:4] == ["api", "--method", "GET"]


def test_verify_app_installation_admin_true(monkeypatch):
    client = _client(monkeypatch)
    assert client.verify_app_installation_admin(REPO, "SADOCKDOG") is True


def test_verify_app_installation_admin_false_on_invalid_repo():
    client = GitHubPRClient()
    assert client.verify_app_installation_admin("not a repo", "SADOCKDOG") is False
    assert client.verify_app_installation_admin(REPO, "") is False


def test_unexpected_ruleset_enforcement_fails_closed(monkeypatch):
    rulesets = [{"enforcement": "mystery", "conditions": {"ref_name": {"include": ["refs/heads/*"], "exclude": []}}, "bypass_actors": []}]
    snapshot = _client(monkeypatch, rulesets=rulesets).inspect(REPO, 321)
    assert snapshot.has_unverified_ruleset is True
    assert snapshot.branch_protection_valid is False


def test_owner_check_app_pinning_required(monkeypatch):
    client = GitHubPRClient(owner_authorization_app_id=999)
    base = _client(monkeypatch)
    # Reuse base monkeypatches but with wrong owner app pin: unpin client app id
    client2 = GitHubPRClient(owner_authorization_app_id=999)
    # swap in the same mocks as base
    client2._api_json = base._api_json
    client2._api_pages = base._api_pages
    snapshot = client2.inspect(REPO, 321)
    assert snapshot.branch_protection_valid is False
