"""Snyk API v1 Python SDK Client.

Implements five core operations against https://api.snyk.io/api/v1/.
Authentication uses a token supplied in the ``Authorization`` header
with the format ``token <API_KEY>``.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import requests


class SnykApiError(Exception):
    """Raised when the Snyk API returns a non-success status code.

    Attributes:
        status_code: HTTP status code from the response.
        message: Error message returned by the API.
        error_ref: UUID error reference for Snyk support, if provided.
    """

    def __init__(self, status_code: int, message: str, error_ref: Optional[str] = None) -> None:
        self.status_code = status_code
        self.message = message
        self.error_ref = error_ref
        super().__init__(f"[{status_code}] {message}" + (f" (ref: {error_ref})" if error_ref else ""))


class SnykClient:
    """A lightweight client for the Snyk REST API v1.

    Args:
        api_key: Your Snyk API token (visible at https://snyk.io/account/).
        base_url: API base URL. Defaults to ``https://api.snyk.io/api/v1``.
    """

    def __init__(self, api_key: str, base_url: str = "https://api.snyk.io/api/v1") -> None:
        self.base_url = base_url.rstrip("/")
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"token {api_key}",
            "Content-Type": "application/json",
        })

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        """Send an HTTP request and return parsed JSON (or None for 204).

        Raises:
            SnykApiError: If the response status code indicates an error.
        """
        url = f"{self.base_url}{path}"
        resp = self._session.request(method, url, **kwargs)
        if resp.status_code in (200, 201):
            return resp.json()
        if resp.status_code == 204:
            return None
        # Attempt to parse error body
        try:
            body = resp.json()
        except ValueError:
            body = {}
        raise SnykApiError(
            status_code=resp.status_code,
            message=body.get("message") or body.get("error") or resp.text,
            error_ref=body.get("errorRef"),
        )

    # ------------------------------------------------------------------
    # 1. List all organizations the user has access to
    # ------------------------------------------------------------------

    def list_organizations(self) -> List[Dict[str, Any]]:
        """List all the organizations a user belongs to.

        Returns:
            A list of organization objects, each containing at minimum:
            - ``id`` (str): The organization ID.
            - ``name`` (str): The organization display name.
            - ``slug`` (str): URL-friendly organization name.
            - ``url`` (str): Web URL for the organization.
            - ``group`` (dict | None): Group info (``id``, ``name``) or None.
        """
        data = self._request("GET", "/orgs")
        return data.get("orgs", [])

    # ------------------------------------------------------------------
    # 2. List all projects in an organization
    # ------------------------------------------------------------------

    def list_projects(
        self,
        org_id: str,
        *,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """List all projects for a given organization.

        Uses ``POST /org/{orgId}/projects`` as defined in the spec.

        Args:
            org_id: The organization ID. The API key must have access to this organization.
            filters: Optional filter object that may contain:
                - ``name`` (str): Only projects whose name **starts with** this value.
                - ``origin`` (str): Exact match on project origin (e.g. ``"github"``).
                - ``type`` (str): Exact match on project type (e.g. ``"maven"``).
                - ``isMonitored`` (bool): Filter by monitoring status.
                - ``tags`` (dict): Tag-based filtering with ``includes`` list.
                - ``attributes`` (dict): Filter by ``criticality``, ``environment``, ``lifecycle``.

        Returns:
            A list of project objects.
        """
        body: Dict[str, Any] = {}
        if filters is not None:
            body["filters"] = filters
        data = self._request("POST", f"/org/{org_id}/projects", json=body)
        return data.get("projects", [])

    # ------------------------------------------------------------------
    # 3. Get vulnerability issues for a project
    # ------------------------------------------------------------------

    def get_aggregated_issues(
        self,
        org_id: str,
        project_id: str,
        *,
        include_description: bool = False,
        include_patched: bool = False,
        filters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Get aggregated vulnerability issues for a project.

        Uses ``POST /org/{orgId}/project/{projectId}/aggregated-issues``.

        Args:
            org_id: The organization ID. The API key must have access to this organization.
            project_id: The project ID to return issues for.
            include_description: If ``True``, include full vulnerability descriptions.
            include_patched: If ``True``, include already-patched vulnerabilities.
            filters: Optional filter object that may contain:
                - ``severities`` (list[str]): e.g. ``["high", "critical"]``.
                - ``exploitMaturity`` (list[str]): e.g. ``["mature", "proof-of-concept"]``.
                - ``types`` (list[str]): e.g. ``["vuln", "license"]``.
                - ``ignored`` (bool): Whether to include ignored issues.
                - ``patched`` (bool): Whether to include patched issues.
                - ``priority`` (dict): Priority score filtering.

        Returns:
            A dict with an ``issues`` key containing a list of aggregated issue objects.
            Each issue includes ``id``, ``issueType``, ``pkgName``, ``pkgVersions``,
            ``issueData`` (severity, title, CVSSv3, etc.), and ``fixInfo``.
        """
        body: Dict[str, Any] = {
            "includeDescription": include_description,
            "includePatched": include_patched,
        }
        if filters is not None:
            body["filters"] = filters
        return self._request(
            "POST",
            f"/org/{org_id}/project/{project_id}/aggregated-issues",
            json=body,
        )

    # ------------------------------------------------------------------
    # 4. Create a new organization
    # ------------------------------------------------------------------

    def create_organization(
        self,
        name: str,
        *,
        group_id: Optional[str] = None,
        source_org_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new organization.

        Uses ``POST /org``.

        Args:
            name: The name of the new organization (required).
            group_id: The group ID. The API key must have access to this group.
            source_org_id: The ID of an existing organization to copy settings from.
                If provided, this organization must be in the same group.
                Copied items include: source control integrations, container registry
                integrations, container orchestrator integrations, PaaS/serverless
                integrations, notification integrations, policies, ignore settings,
                language settings, IaC settings, and Snyk Code settings.
                NOT copied: service accounts, members, projects, notification preferences.

        Returns:
            The newly created organization object with ``id``, ``name``, ``slug``,
            ``url``, ``created``, and optionally ``group``.
        """
        body: Dict[str, Any] = {"name": name}
        if group_id is not None:
            body["groupId"] = group_id
        if source_org_id is not None:
            body["sourceOrgId"] = source_org_id
        return self._request("POST", "/org", json=body)

    # ------------------------------------------------------------------
    # 5. Delete a project
    # ------------------------------------------------------------------

    def delete_project(self, org_id: str, project_id: str) -> None:
        """Delete a project.

        Uses ``DELETE /org/{orgId}/project/{projectId}``.

        Args:
            org_id: The organization ID the project belongs to.
            project_id: The project ID to delete.

        Returns:
            None on success.

        Raises:
            SnykApiError: If the deletion fails (e.g. 404, 401).
        """
        self._request("DELETE", f"/org/{org_id}/project/{project_id}")
