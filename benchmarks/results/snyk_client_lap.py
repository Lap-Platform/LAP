"""Snyk API Python SDK - built from LAP spec."""

from typing import Any, Dict, List, Optional
import requests


class SnykAPIError(Exception):
    """Raised when the Snyk API returns a non-success status code."""

    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        self.message = message
        super().__init__(f"Snyk API error {status_code}: {message}")


class SnykClient:
    """Client for the Snyk REST API (v1).

    Authentication is via API token passed in the ``Authorization`` header
    as ``token <api_token>``.

    Args:
        api_token: Snyk API token used for authentication.
        base_url: Base URL for the Snyk API. Defaults to
            ``https://api.snyk.io/api/v1``.
        timeout: Request timeout in seconds. Defaults to 30.
    """

    def __init__(
        self,
        api_token: str,
        base_url: str = "https://api.snyk.io/api/v1",
        timeout: int = 30,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"token {api_token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _request(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        """Send a request and raise :class:`SnykAPIError` on failure."""
        url = f"{self.base_url}{path}"
        kwargs.setdefault("timeout", self.timeout)
        response = self._session.request(method, url, **kwargs)
        if not response.ok:
            try:
                detail = response.json()
            except ValueError:
                detail = response.text
            raise SnykAPIError(response.status_code, str(detail))
        return response

    # ------------------------------------------------------------------
    # 1. List all organizations the user has access to
    #    GET /orgs  → 200
    # ------------------------------------------------------------------

    def list_organizations(self) -> Dict[str, Any]:
        """List all organizations the authenticated user has access to.

        Endpoint: ``GET /orgs``

        Returns:
            dict: JSON response containing the list of organizations.
        """
        response = self._request("GET", "/orgs")
        return response.json()

    # ------------------------------------------------------------------
    # 2. List all projects in an organization
    #    POST /org/{orgId}/projects  → 200
    # ------------------------------------------------------------------

    def list_projects(
        self,
        org_id: str,
        filters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """List all projects in the given organization.

        Endpoint: ``POST /org/{orgId}/projects``

        Args:
            org_id: The organization ID.
            filters: Optional filter criteria (map). For example you can
                filter by name, origin, type, etc.

        Returns:
            dict: JSON response containing the list of projects.
        """
        body: Dict[str, Any] = {}
        if filters is not None:
            body["filters"] = filters
        response = self._request("POST", f"/org/{org_id}/projects", json=body)
        return response.json()

    # ------------------------------------------------------------------
    # 3. Get aggregated vulnerability issues for a project
    #    POST /org/{orgId}/project/{projectId}/aggregated-issues  → 200
    # ------------------------------------------------------------------

    def get_project_issues(
        self,
        org_id: str,
        project_id: str,
        filters: Optional[Dict[str, Any]] = None,
        include_description: bool = False,
        include_introduced_through: bool = False,
    ) -> Dict[str, Any]:
        """Get aggregated vulnerability issues for a project.

        Endpoint: ``POST /org/{orgId}/project/{projectId}/aggregated-issues``

        Args:
            org_id: The organization ID.
            project_id: The project ID.
            filters: Optional filter criteria (map).
            include_description: Whether to include full issue descriptions.
            include_introduced_through: Whether to include the dependency
                paths that introduced each issue.

        Returns:
            dict: JSON response containing aggregated issues.
        """
        body: Dict[str, Any] = {}
        if filters is not None:
            body["filters"] = filters
        if include_description:
            body["includeDescription"] = True
        if include_introduced_through:
            body["includeIntroducedThrough"] = True
        response = self._request(
            "POST",
            f"/org/{org_id}/project/{project_id}/aggregated-issues",
            json=body,
        )
        return response.json()

    # ------------------------------------------------------------------
    # 4. Create a new organization
    #    POST /org  → 201
    # ------------------------------------------------------------------

    def create_organization(
        self,
        name: str,
        group_id: Optional[str] = None,
        source_org_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new organization.

        Endpoint: ``POST /org``

        Args:
            name: The name of the new organization (required).
            group_id: Optional group ID to place the organization in.
            source_org_id: Optional organization ID to copy settings from.

        Returns:
            dict: JSON response with the newly created organization.

        Raises:
            SnykAPIError: 400 (bad request), 401 (unauthorized), or
                422 (unprocessable entity).
        """
        body: Dict[str, Any] = {"name": name}
        if group_id is not None:
            body["groupId"] = group_id
        if source_org_id is not None:
            body["sourceOrgId"] = source_org_id
        response = self._request("POST", "/org", json=body)
        return response.json()

    # ------------------------------------------------------------------
    # 5. Delete a project
    #    DELETE /org/{orgId}/project/{projectId}  → 200
    # ------------------------------------------------------------------

    def delete_project(self, org_id: str, project_id: str) -> None:
        """Delete a project from an organization.

        Endpoint: ``DELETE /org/{orgId}/project/{projectId}``

        Args:
            org_id: The organization ID.
            project_id: The project ID to delete.

        Returns:
            None
        """
        self._request("DELETE", f"/org/{org_id}/project/{project_id}")
