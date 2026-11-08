"""Read-only PR inspection client for Owner Authorization.

PR-1 delivers only inspection of PR identity, GitHub App installation/permissions
and required checks. This module never writes to GitHub and never invokes merge
or any other mutating endpoint. The merge executor and its reconciliation arrive
in a later PR with isolated integration testing.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import subprocess
from dataclasses import dataclass
from typing import Any

from software_factory.security.owner_authorization import REPOSITORY_RE


class GitHubIntegrationError(RuntimeError):
    pass


@dataclass(frozen=True)
class PRSnapshot:
    repository: str
    pr_number: int
    html_url: str
    state: str
    merged: bool
    merge_commit_sha: str | None
    draft: bool
    head_sha: str
    head_ref: str
    base_ref: str
    base_sha: str
    mergeable: bool
    files: tuple[str, ...]
    file_details: tuple[dict[str, Any], ...]
    diff_sha256: str
    required_checks: tuple[dict[str, Any], ...]
    check_results: dict[str, dict[str, Any]]
    branch_protection_valid: bool
    has_bypass: bool
    has_unverified_ruleset: bool
    owner_authorization_check: str

    def required_checks_pass(self, include_owner_authorization: bool = True) -> bool:
        required = [item for item in self.required_checks]
        if not include_owner_authorization:
            required = [item for item in required if item["context"] != self.owner_authorization_check]
        if not required:
            return False
        for item in required:
            result = self.check_results.get(item["context"])
            if not result or result.get("conclusion") != "success":
                return False
            expected_app = item.get("app_id")
            if expected_app is not None and result.get("app_id") != expected_app:
                return False
        return True

    def model(self) -> dict[str, Any]:
        return {
            "repository": self.repository,
            "pr_number": self.pr_number,
            "html_url": self.html_url,
            "state": self.state,
            "merged": self.merged,
            "merge_commit_sha": self.merge_commit_sha,
            "draft": self.draft,
            "head_sha": self.head_sha,
            "head_ref": self.head_ref,
            "base_ref": self.base_ref,
            "base_sha": self.base_sha,
            "mergeable": self.mergeable,
            "files": list(self.files),
            "file_details": list(self.file_details),
            "diff_sha256": self.diff_sha256,
            "required_checks": list(self.required_checks),
            "check_results": dict(self.check_results),
            "branch_protection_valid": self.branch_protection_valid,
            "has_bypass": self.has_bypass,
            "has_unverified_ruleset": self.has_unverified_ruleset,
            "owner_authorization_check": self.owner_authorization_check,
            "required_checks_pass": self.required_checks_pass(),
        }


class GitHubPRClient:
    """Read-only GitHub inspection. No mutating methods exist on this client."""

    def __init__(
        self,
        gh: str = "gh",
        owner_authorization_check: str = "Owner authorization",
        owner_authorization_app_id: int | None = None,
        timeout: int = 20,
    ):
        self.gh = gh
        self.owner_authorization_check = owner_authorization_check
        self.owner_authorization_app_id = owner_authorization_app_id
        self.timeout = timeout

    def _api_json(self, *args: str, method: str | None = None, fields: dict[str, str] | None = None) -> Any:
        if method is not None and method.upper() != "GET":
            raise GitHubIntegrationError("Mutating GitHub requests are not supported by this client")
        cmd = [self.gh, "api"]
        if method:
            cmd += ["--method", method]
        for key, value in (fields or {}).items():
            cmd += ["-f", f"{key}={value}"]
        cmd += list(args)
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=self.timeout, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise GitHubIntegrationError("GitHub API no disponible; operación detenida") from exc
        if result.returncode != 0:
            # Do not surface raw CLI output: it can contain headers or sensitive diagnostics.
            raise GitHubIntegrationError(f"GitHub API falló (exit={result.returncode})")
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise GitHubIntegrationError("GitHub API devolvió JSON inválido") from exc

    def _api_pages(self, endpoint: str, collection_key: str | None = None) -> list[dict[str, Any]]:
        result = self._api_json("--paginate", "--slurp", endpoint, method="GET")
        if not isinstance(result, list):
            raise GitHubIntegrationError("Respuesta paginada inválida")
        flattened: list[dict[str, Any]] = []
        for page in result:
            if isinstance(page, list):
                flattened.extend(item for item in page if isinstance(item, dict))
            elif isinstance(page, dict) and collection_key and isinstance(page.get(collection_key), list):
                flattened.extend(item for item in page[collection_key] if isinstance(item, dict))
            else:
                raise GitHubIntegrationError("Página GitHub inválida")
        return flattened

    def verify_app_installation_admin(self, repository: str, github_login: str) -> bool:
        """Verify the trusted GitHub installation identity has admin visibility.

        Read-only collaborator permission lookup. It never authorizes by itself:
        the App installation, repository and least-privilege scope are revalidated
        by the caller against the service allowlist before any action.
        """
        if not github_login or not REPOSITORY_RE.fullmatch(repository):
            return False
        try:
            permission = self._api_json(f"repos/{repository}/collaborators/{github_login}/permission", method="GET")
        except GitHubIntegrationError:
            return False
        user = permission.get("user") or {}
        return str(user.get("login", "")).lower() == github_login.lower() and permission.get("permission") == "admin"

    @staticmethod
    def _matching_ruleset(rule_set: dict[str, Any], ref: str) -> bool:
        conditions = rule_set.get("conditions") or {}
        ref_name = conditions.get("ref_name") or {}
        include = ref_name.get("include") or []
        exclude = ref_name.get("exclude") or []
        if not include:
            return True
        full_ref = f"refs/heads/{ref}"
        return any(fnmatch.fnmatchcase(full_ref, pattern) for pattern in include) and not any(
            fnmatch.fnmatchcase(full_ref, pattern) for pattern in exclude
        )

    def inspect(self, repository: str, pr_number: int) -> PRSnapshot:
        pr = self._api_json(f"repos/{repository}/pulls/{pr_number}")
        if pr.get("number") != pr_number or pr.get("base", {}).get("repo", {}).get("full_name", "").lower() != repository.lower():
            raise GitHubIntegrationError("La PR no pertenece al repositorio solicitado")

        head_sha = str(pr.get("head", {}).get("sha", ""))
        base_ref = str(pr.get("base", {}).get("ref", ""))
        base_sha = str(pr.get("base", {}).get("sha", ""))
        if len(head_sha) != 40 or len(base_sha) != 40 or not base_ref:
            raise GitHubIntegrationError("GitHub no devolvió HEAD/base completos")

        files = self._api_pages(f"repos/{repository}/pulls/{pr_number}/files")
        file_manifest = [
            {
                "filename": str(item.get("filename", "")),
                "status": str(item.get("status", "")),
                "sha": str(item.get("sha", "")),
                "additions": int(item.get("additions", 0)),
                "deletions": int(item.get("deletions", 0)),
                "changes": int(item.get("changes", 0)),
                "patch": item.get("patch"),
                "patch_sha256": hashlib.sha256(str(item.get("patch", "")).encode("utf-8")).hexdigest() if item.get("patch") is not None else None,
            }
            for item in files
        ]
        if not file_manifest or any(not item["filename"] for item in file_manifest):
            raise GitHubIntegrationError("No se pudo obtener el manifiesto completo de archivos de la PR")
        file_manifest.sort(key=lambda item: item["filename"])
        diff_digest = hashlib.sha256(
            json.dumps(file_manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

        protection = self._api_json(f"repos/{repository}/branches/{base_ref}/protection")
        required = protection.get("required_status_checks")
        if not isinstance(required, dict):
            required = {}
        checks = required.get("checks") or []
        contexts = required.get("contexts") or []
        required_checks: dict[str, dict[str, Any]] = {}
        for context in contexts:
            required_checks[str(context)] = {"context": str(context), "app_id": None}
        for item in checks:
            if isinstance(item, dict) and item.get("context"):
                required_checks[str(item["context"])] = {
                    "context": str(item["context"]),
                    "app_id": item.get("app_id"),
                }

        check_runs = self._api_pages(
            f"repos/{repository}/commits/{head_sha}/check-runs?per_page=100",
            collection_key="check_runs",
        )
        check_results: dict[str, dict[str, Any]] = {}
        for run in check_runs:
            name = str(run.get("name", ""))
            if not name:
                continue
            conclusion = str(run.get("conclusion") or run.get("status") or "missing").lower()
            candidate = {
                "conclusion": conclusion,
                "app_id": (run.get("app") or {}).get("id"),
                "updated_at": str(run.get("completed_at") or run.get("started_at") or ""),
            }
            current = check_results.get(name)
            if current is None or candidate["updated_at"] >= current["updated_at"]:
                check_results[name] = candidate

        rulesets = self._api_json(f"repos/{repository}/rulesets?includes_parents=true", method="GET")
        has_bypass = False
        has_unverified_ruleset = False
        if isinstance(rulesets, list):
            for rule_set in rulesets:
                enforcement = rule_set.get("enforcement")
                if enforcement not in ("active", "evaluate", "disabled"):
                    # Unknown/missing enforcement: fail closed.
                    has_unverified_ruleset = True
                    continue
                if enforcement != "active" or not self._matching_ruleset(rule_set, base_ref):
                    continue
                # Until every active ruleset rule type is explicitly evaluated,
                # stop rather than assuming it is harmless.
                has_unverified_ruleset = True
                if rule_set.get("bypass_actors"):
                    has_bypass = True

        required_pull_request_reviews = protection.get("required_pull_request_reviews") or {}
        owner_check = required_checks.get(self.owner_authorization_check)
        owner_check_source_pinned = bool(
            owner_check
            and self.owner_authorization_app_id is not None
            and owner_check.get("app_id") == self.owner_authorization_app_id
        )
        branch_protection_valid = bool(
            protection.get("enforce_admins", {}).get("enabled") is True
            and protection.get("allow_force_pushes", {}).get("enabled") is False
            and protection.get("allow_deletions", {}).get("enabled") is False
            and isinstance(protection.get("required_pull_request_reviews"), dict)
            and int(required_pull_request_reviews.get("required_approving_review_count", 0)) == 0
            and required_pull_request_reviews.get("require_code_owner_reviews") is not True
            and required_pull_request_reviews.get("require_last_push_approval") is not True
            and bool(required_checks)
            and required.get("strict") is True
            and not has_bypass
            and not has_unverified_ruleset
            and owner_check_source_pinned
        )

        return PRSnapshot(
            repository=repository,
            pr_number=pr_number,
            html_url=str(pr.get("html_url", "")),
            state=str(pr.get("state", "unknown")).lower(),
            merged=bool(pr.get("merged", False)),
            merge_commit_sha=pr.get("merge_commit_sha"),
            draft=bool(pr.get("draft", False)),
            head_sha=head_sha,
            head_ref=str(pr.get("head", {}).get("ref", "")),
            base_ref=base_ref,
            base_sha=base_sha,
            mergeable=pr.get("mergeable") is True,
            files=tuple(item["filename"] for item in file_manifest),
            file_details=tuple(file_manifest),
            diff_sha256=diff_digest,
            required_checks=tuple(required_checks[name] for name in sorted(required_checks)),
            check_results=check_results,
            branch_protection_valid=branch_protection_valid,
            has_bypass=has_bypass,
            has_unverified_ruleset=has_unverified_ruleset,
            owner_authorization_check=self.owner_authorization_check,
        )
