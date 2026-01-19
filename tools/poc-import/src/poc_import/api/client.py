# Copyright (c) 2026 Waterfall Project
# SPDX-License-Identifier: Commercial

"""wfp-poc REST API client with authentication and retry logic."""

import logging
import math
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from poc_import.models import (
    Assignment,
    MSProjectData,
    ProjectMetadata,
    Resource,
    Task,
)

logger = logging.getLogger(__name__)


class WfpApiError(Exception):
    """Base exception for wfp-poc API errors."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        response_data: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data


class WfpApiClient:
    """Client for wfp-poc REST API with authentication and retry logic.

    Implements REQ-028 through REQ-036:
    - JWT authentication
    - Correlation ID tracking
    - Retry logic for transient errors
    - Bulk operations
    - Error handling
    """

    def __init__(
        self,
        base_url: str,
        token: str,
        correlation_id: str,
        company_id: str | None = None,
        timeout: int = 30,
    ):
        """Initialize API client.

        Args:
            base_url: wfp-poc API base URL (e.g., http://localhost:5000)
            token: JWT authentication token
            correlation_id: Unique ID for request tracing
            company_id: Optional company UUID for multi-tenant isolation
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.correlation_id = correlation_id
        self.company_id = company_id
        self.timeout = timeout

        # Configure session with retry logic
        self.session = requests.Session()

        # Retry configuration: 3 retries with exponential backoff
        # REQ-034: Implement retry logic for transient API errors
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST", "PUT", "DELETE"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        # Set default headers
        self.session.headers.update(
            {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "X-Correlation-ID": self.correlation_id,
            }
        )

        if self.company_id:
            self.session.headers.update({"X-Company-ID": self.company_id})

        logger.info(
            f"Initialized WfpApiClient [base_url={self.base_url}, "
            f"correlation_id={self.correlation_id}]"
        )

    def _handle_response(self, response: requests.Response) -> dict[str, Any]:
        """Handle API response and raise appropriate errors.

        Args:
            response: HTTP response object

        Returns:
            Response JSON data

        Raises:
            WfpApiError: For API errors (4xx, 5xx)
        """
        try:
            response.raise_for_status()
            return response.json() if response.content else {}
        except requests.exceptions.HTTPError as e:
            error_data = None
            try:
                error_data = response.json()
            except ValueError:
                error_data = {"detail": response.text}

            # REQ-035: Abort import on validation errors (4xx) without retry
            message = (
                error_data.get("message")
                or error_data.get("detail")
                or error_data.get("error")
                or str(e)
            )

            if 400 <= response.status_code < 500:
                logger.error(f"Client error {response.status_code}: {error_data}")
                raise WfpApiError(
                    f"API client error: {message}",
                    status_code=response.status_code,
                    response_data=error_data,
                ) from e

            # Server errors will be retried by the session retry strategy
            logger.error(f"Server error {response.status_code}: {error_data}")
            raise WfpApiError(
                f"API server error: {message}",
                status_code=response.status_code,
                response_data=error_data,
            ) from e

    def _request(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Send an HTTP request with consistent error handling.

        Args:
            method: HTTP method (GET/POST/PUT/DELETE).
            path: API path (e.g., "/v0/projects").
            **kwargs: Requests parameters (json, params, timeout, etc.).

        Returns:
            Parsed JSON response.

        Raises:
            WfpApiError: On network or HTTP errors.
        """
        url = f"{self.base_url}{path}"
        if "timeout" not in kwargs:
            kwargs["timeout"] = self.timeout

        try:
            response = self.session.request(method, url, **kwargs)
        except requests.exceptions.Timeout as exc:
            raise WfpApiError(
                f"API timeout after {self.timeout}s",
                status_code=None,
            ) from exc
        except requests.exceptions.RequestException as exc:
            raise WfpApiError(
                f"API request failed: {exc}",
                status_code=None,
            ) from exc

        return self._handle_response(response)

    def _convert_hours_to_iso8601_duration(self, duration_hours: float) -> str:
        """Convert duration in hours to ISO 8601 duration format.

        Args:
            duration_hours: Duration in hours (can be fractional)

        Returns:
            ISO 8601 duration string (e.g., "PT8H30M0S")

        Examples:
            8.0 -> "PT8H0M0S"
            8.333 -> "PT8H20M0S" (rounded)
            8.5 -> "PT8H30M0S"
        """
        # Use math.modf for more reliable extraction of integer and fractional parts
        fractional_hours, hours_float = math.modf(duration_hours)
        hours = int(hours_float)
        # Use rounding instead of truncation to avoid precision loss,
        # e.g. 8.333 hours -> 8 hours 20 minutes rather than 19 minutes.
        minutes = int(round(fractional_hours * 60))
        # Handle edge case where rounding yields 60 minutes.
        if minutes == 60:
            hours += 1
            minutes = 0
        return f"PT{hours}H{minutes}M0S"

    def _build_project_code(self, project: ProjectMetadata) -> str:
        """Build a project code for API requirements.

        Args:
            project: Project metadata from MS Project

        Returns:
            Project code string (max 50 chars).
        """
        if project.guid:
            return project.guid[:50]
        return (project.name or "MSPROJECT")[:50]

    def validate_token(self) -> dict[str, Any]:
        """Validate JWT token by calling health endpoint.

        Returns:
            Health check response

        Raises:
            WfpApiError: If token is invalid (401)
        """
        logger.debug("Validating JWT token...")
        return self._request("GET", "/health")

    def create_project(self, project: ProjectMetadata) -> dict[str, Any]:
        """Create a new project.

        Args:
            project: Project metadata from MS Project

        Returns:
            Created project data with UUID

        Raises:
            WfpApiError: On API error
        """
        logger.info(f"Creating project: {project.name}")

        payload = {
            "name": project.name,
            "code": self._build_project_code(project),
            "title": project.title,
            "start_date": project.start_date.isoformat(),
            "finish_date": project.finish_date.isoformat(),
        }

        # Add optional fields
        if project.guid:
            payload["ms_project_guid"] = project.guid

        data = self._request("POST", "/v0/projects", json=payload)
        logger.info(f"Created project: {data.get('id')}")
        return data

    def get_project(self, project_id: str) -> dict[str, Any]:
        """Get project details.

        Args:
            project_id: Project UUID

        Returns:
            Project data

        Raises:
            WfpApiError: On API error
        """
        logger.debug(f"Getting project: {project_id}")
        return self._request("GET", f"/v0/projects/{project_id}")

    def get_project_milestones(self, project_id: str) -> list[dict[str, Any]]:
        """Get all milestones for a project.

        Args:
            project_id: Project UUID

        Returns:
            List of milestone objects

        Raises:
            WfpApiError: On API error
        """
        logger.debug(f"Getting milestones for project: {project_id}")
        data = self._request(
            "GET",
            f"/v0/projects/{project_id}/milestones",
        )
        milestones: list[dict[str, Any]] = data.get("data", [])
        return milestones

    def list_projects(
        self,
        page: int | None = None,
        per_page: int | None = None,
    ) -> dict[str, Any]:
        """List projects.

        Args:
            page: Optional page number
            per_page: Optional items per page

        Returns:
            API response data

        Raises:
            WfpApiError: On API error
        """
        logger.debug("Listing projects")
        params: dict[str, Any] = {}
        if page is not None:
            params["page"] = page
        if per_page is not None:
            params["per_page"] = per_page

        return self._request("GET", "/v0/projects", params=params)

    def list_project_tasks(
        self,
        project_id: str,
        page: int | None = None,
        per_page: int | None = None,
    ) -> dict[str, Any]:
        """List tasks for a project.

        Args:
            project_id: Project UUID
            page: Optional page number
            per_page: Optional items per page

        Returns:
            API response data

        Raises:
            WfpApiError: On API error
        """
        logger.debug("Listing tasks for project: %s", project_id)
        params: dict[str, Any] = {}
        if page is not None:
            params["page"] = page
        if per_page is not None:
            params["per_page"] = per_page

        return self._request(
            "GET",
            f"/v0/projects/{project_id}/tasks",
            params=params,
        )

    def get_project_task(self, project_id: str, task_id: str) -> dict[str, Any]:
        """Get task details for a project.

        Args:
            project_id: Project UUID
            task_id: Task UUID

        Returns:
            Task data

        Raises:
            WfpApiError: On API error
        """
        logger.debug("Getting task %s for project %s", task_id, project_id)
        return self._request(
            "GET",
            f"/v0/projects/{project_id}/tasks/{task_id}",
        )

    def list_resources(
        self,
        page: int | None = None,
        per_page: int | None = None,
    ) -> dict[str, Any]:
        """List company-scoped resources.

        Args:
            page: Optional page number
            per_page: Optional items per page

        Returns:
            API response data

        Raises:
            WfpApiError: On API error
        """
        logger.debug("Listing resources")
        params: dict[str, Any] = {}
        if page is not None:
            params["page"] = page
        if per_page is not None:
            params["per_page"] = per_page

        return self._request("GET", "/v0/resources", params=params)

    def list_project_resources(
        self,
        project_id: str,
        page: int | None = None,
        per_page: int | None = None,
    ) -> dict[str, Any]:
        """List resources for a project.

        Args:
            project_id: Project UUID
            page: Optional page number
            per_page: Optional items per page

        Returns:
            API response data

        Raises:
            WfpApiError: On API error
        """
        logger.debug("Listing resources for project: %s", project_id)
        params: dict[str, Any] = {}
        if page is not None:
            params["page"] = page
        if per_page is not None:
            params["per_page"] = per_page

        return self._request(
            "GET",
            f"/v0/projects/{project_id}/resources",
            params=params,
        )

    def get_resource(self, resource_id: str) -> dict[str, Any]:
        """Get resource details.

        Args:
            resource_id: Resource UUID

        Returns:
            Resource data

        Raises:
            WfpApiError: On API error
        """
        logger.debug("Getting resource: %s", resource_id)
        return self._request("GET", f"/v0/resources/{resource_id}")

    def list_assignments(
        self,
        project_id: str,
        page: int | None = None,
        per_page: int | None = None,
    ) -> dict[str, Any]:
        """List assignments for a project.

        Args:
            project_id: Project UUID
            page: Optional page number
            per_page: Optional items per page

        Returns:
            API response data

        Raises:
            WfpApiError: On API error
        """
        logger.debug("Listing assignments for project: %s", project_id)
        params: dict[str, Any] = {}
        if page is not None:
            params["page"] = page
        if per_page is not None:
            params["per_page"] = per_page

        return self._request(
            "GET",
            f"/v0/projects/{project_id}/assignments",
            params=params,
        )

    def get_assignment(self, project_id: str, assignment_id: str) -> dict[str, Any]:
        """Get assignment details for a project.

        Args:
            project_id: Project UUID
            assignment_id: Assignment UUID

        Returns:
            Assignment data

        Raises:
            WfpApiError: On API error
        """
        logger.debug("Getting assignment %s for project %s", assignment_id, project_id)
        return self._request(
            "GET",
            f"/v0/projects/{project_id}/assignments/{assignment_id}",
        )

    def list_dependencies(
        self,
        project_id: str,
        page: int | None = None,
        per_page: int | None = None,
    ) -> dict[str, Any]:
        """List dependencies for a project.

        Args:
            project_id: Project UUID
            page: Optional page number
            per_page: Optional items per page

        Returns:
            API response data

        Raises:
            WfpApiError: On API error
        """
        logger.debug("Listing dependencies for project: %s", project_id)
        params: dict[str, Any] = {}
        if page is not None:
            params["page"] = page
        if per_page is not None:
            params["per_page"] = per_page

        return self._request(
            "GET",
            f"/v0/projects/{project_id}/dependencies",
            params=params,
        )

    def get_dependency(self, project_id: str, dependency_id: str) -> dict[str, Any]:
        """Get dependency details for a project.

        Args:
            project_id: Project UUID
            dependency_id: Dependency UUID

        Returns:
            Dependency data

        Raises:
            WfpApiError: On API error
        """
        logger.debug(
            "Getting dependency %s for project %s",
            dependency_id,
            project_id,
        )
        return self._request(
            "GET",
            f"/v0/projects/{project_id}/dependencies/{dependency_id}",
        )

    def create_tasks_bulk(self, project_id: str, tasks: list[Task]) -> dict[str, Any]:
        """Create tasks in bulk (initial import).

        REQ-030: Use POST for initial import
        REQ-002: Use bulk API calls for tasks (max 100 per request)

        Args:
            project_id: Project UUID
            tasks: List of tasks to create (max 100)

        Returns:
            Bulk creation response with created task IDs

        Raises:
            WfpApiError: On API error
        """
        if len(tasks) > 100:
            raise ValueError(f"Too many tasks in batch: {len(tasks)} (max 100)")

        logger.info(f"Creating {len(tasks)} tasks for project {project_id}")

        # Transform tasks to API payload
        task_payloads = []
        for task in tasks:
            start_date = task.planned_start_date or task.planned_finish_date
            finish_date = task.planned_finish_date or task.planned_start_date
            payload: dict[str, Any] = {
                "name": task.name,
                "wbs": task.wbs_code or "",
                "start": start_date.isoformat() if start_date else None,
                "finish": finish_date.isoformat() if finish_date else None,
                "is_milestone": task.is_milestone,
            }

            # Add duration in ISO 8601 format (PT8H0M0S)
            if task.duration_hours is not None:
                payload["duration"] = self._convert_hours_to_iso8601_duration(
                    task.duration_hours
                )

            # Add optional fields
            if task.guid:
                payload["ms_project_guid"] = task.guid
            if task.uid:
                payload["ms_project_uid"] = task.uid

            # Add predecessors if present
            if task.predecessors:
                # TaskCreate requires predecessor_task_id (UUID) which we don't have
                # at initial creation time. Predecessors are applied during sync.
                pass

            task_payloads.append(payload)

        data = self._request(
            "POST",
            f"/v0/projects/{project_id}/tasks/bulk",
            json={"tasks": task_payloads},
            timeout=self.timeout * 2,  # Longer timeout for bulk
        )
        task_map: dict[int, str] = {}
        tasks_data = data.get("data", {}).get("tasks", [])
        if isinstance(tasks_data, list):
            for task_data in tasks_data:
                if not isinstance(task_data, dict):
                    continue
                ms_uid = task_data.get("ms_project_uid")
                task_id = task_data.get("id")
                if isinstance(ms_uid, int) and isinstance(task_id, str):
                    task_map[ms_uid] = task_id
                elif isinstance(ms_uid, str) and isinstance(task_id, str):
                    try:
                        task_map[int(ms_uid)] = task_id
                    except ValueError:
                        continue
        logger.info(
            f"Created {data.get('created_count', 0)} tasks, "
            f"failed {data.get('failed_count', 0)}"
        )
        data["task_map"] = task_map
        return data

    def sync_tasks(self, project_id: str, tasks: list[Task]) -> dict[str, Any]:
        """Sync tasks (update for reimport).

        REQ-031: Use PUT for reimport with reconciliation

        Args:
            project_id: Project UUID
            tasks: List of tasks to sync

        Returns:
            Sync response with created/updated/failed counts

        Raises:
            WfpApiError: On API error
        """
        logger.info(f"Syncing {len(tasks)} tasks for project {project_id}")

        # Transform tasks to API payload
        task_payloads = []
        for task in tasks:
            start_date = task.planned_start_date or task.planned_finish_date
            finish_date = task.planned_finish_date or task.planned_start_date
            payload: dict[str, Any] = {
                "ms_project_uid": task.uid,  # Required for sync reconciliation
                "name": task.name,
                "planned_start_date": start_date.isoformat() if start_date else None,
                "planned_finish_date": finish_date.isoformat() if finish_date else None,
            }

            # Add duration in ISO 8601 format (PT8H0M0S)
            if task.duration_hours is not None:
                payload["duration"] = self._convert_hours_to_iso8601_duration(
                    task.duration_hours
                )

            # Add predecessors if present
            if task.predecessors:
                predecessors_list: list[dict[str, Any]] = [
                    {
                        "predecessor_task_uid": pred.predecessor_task_uid,
                        "type": pred.type.value,
                        "lag": pred.lag,  # Keep in minutes as per spec
                    }
                    for pred in task.predecessors
                ]
                payload["predecessors"] = predecessors_list

            task_payloads.append(payload)

        data = self._request(
            "PUT",
            f"/v0/projects/{project_id}/tasks/sync",
            json={"tasks": task_payloads},
            timeout=self.timeout * 2,
        )
        logger.info(
            f"Synced tasks: created={data.get('created_count', 0)}, "
            f"updated={data.get('updated_count', 0)}, "
            f"failed={data.get('failed_count', 0)}"
        )
        return data

    def create_resources_bulk(
        self, project_id: str, resources: list[Resource]
    ) -> dict[str, Any]:
        """Create resources in bulk (individual API calls - no bulk endpoint).

        Args:
            project_id: Project UUID (unused - resources are company-scoped)
            resources: List of resources to create

        Returns:
            Bulk creation response

        Raises:
            WfpApiError: On API error
        """
        logger.info(f"Creating {len(resources)} resources (company-scoped)")

        created_count = 0
        failed_count = 0
        resource_ids = []
        resource_map: dict[int, str] = {}
        errors = []

        # Transform resources to API payload and create individually
        for idx, resource in enumerate(resources):
            try:
                payload: dict[str, Any] = {
                    "name": resource.name,
                    "type": resource.type.value,
                }

                # Add optional fields
                if resource.standard_rate is not None:
                    payload["standard_rate"] = float(resource.standard_rate)
                if resource.uid:
                    payload["ms_project_uid"] = resource.uid

                result = self._request(
                    "POST",
                    "/v0/resources",
                    json=payload,
                )
                resource_data = result.get("data", {})
                resource_id = resource_data.get("id")
                resource_ids.append(resource_id)
                if resource_id and resource.uid is not None:
                    resource_map[resource.uid] = resource_id
                created_count += 1
            except WfpApiError as e:
                logger.warning(
                    f"Failed to create resource {idx}: {resource.name} - {e}"
                )
                failed_count += 1
                errors.append({"index": idx, "name": resource.name, "error": str(e)})

        logger.info(f"Created {created_count} resources, failed {failed_count}")
        return {
            "created_count": created_count,
            "failed_count": failed_count,
            "resource_ids": resource_ids,
            "resource_map": resource_map,
            "errors": errors,
        }

    def create_assignments_bulk(
        self, project_id: str, assignments: list[Assignment]
    ) -> dict[str, Any]:
        """Create assignments in bulk (individual API calls - no bulk endpoint).

        Args:
            project_id: Project UUID
            assignments: List of assignments to create

        Returns:
            Bulk creation response

        Raises:
            WfpApiError: On API error
        """
        logger.info(f"Creating {len(assignments)} assignments for project {project_id}")
        raise WfpApiError(
            "Assignment creation requires UID->UUID mapping. "
            "Use create_assignments_with_mapping instead.",
            status_code=400,
        )

    def create_assignments_with_mapping(
        self,
        project_id: str,
        assignments: list[Assignment],
        task_map: dict[int, str],
        resource_map: dict[int, str],
    ) -> dict[str, Any]:
        """Create assignments with UID-to-UUID mapping.

        Args:
            project_id: Project UUID
            assignments: Parsed assignments
            task_map: Map of MS Project task UID -> task UUID
            resource_map: Map of MS Project resource UID -> resource UUID

        Returns:
            Bulk creation response
        """
        created_count = 0
        failed_count = 0
        assignment_ids: list[str] = []
        errors: list[dict[str, Any]] = []

        for idx, assignment in enumerate(assignments):
            task_id = task_map.get(assignment.task_uid)
            resource_id = resource_map.get(assignment.resource_uid)
            if not task_id or not resource_id:
                failed_count += 1
                errors.append(
                    {
                        "index": idx,
                        "error": "Missing task/resource mapping for assignment",
                    }
                )
                continue

            payload: dict[str, Any] = {
                "task_id": task_id,
                "resource_id": resource_id,
                "work_hours": self._convert_hours_to_iso8601_duration(
                    assignment.work_hours
                ),
                "percent_allocation": int(round(assignment.units * 100)),
            }

            try:
                result = self._request(
                    "POST",
                    f"/v0/projects/{project_id}/assignments",
                    json=payload,
                )
                assignment_id = result.get("data", {}).get("id")
                if assignment_id:
                    assignment_ids.append(assignment_id)
                created_count += 1
            except WfpApiError as e:
                failed_count += 1
                errors.append({"index": idx, "error": str(e)})

        return {
            "created_count": created_count,
            "failed_count": failed_count,
            "assignment_ids": assignment_ids,
            "errors": errors,
        }

    def import_msproject_data(
        self,
        project_id: str,
        data: MSProjectData,
        mode: str,
        batch_size: int = 100,
    ) -> dict[str, Any]:
        """Orchestrate full MS Project import with batching.

        REQ-036: Provide partial failure handling with resumable reports

        Args:
            project_id: Project UUID
            data: Parsed MS Project data
            mode: Import mode ('initial' or 'sync')
            batch_size: Number of tasks per batch (max 100)

        Returns:
            Import summary with counts and failed batches

        Raises:
            WfpApiError: On critical API errors
        """
        logger.info(
            f"Starting {mode} import for project {project_id} "
            f"[tasks={len(data.tasks)}, resources={len(data.resources)}, "
            f"assignments={len(data.assignments)}]"
        )

        summary: dict[str, Any] = {
            "mode": mode,
            "project_id": project_id,
            "tasks_created": 0,
            "tasks_updated": 0,
            "tasks_failed": 0,
            "resources_created": 0,
            "resources_failed": 0,
            "assignments_created": 0,
            "assignments_failed": 0,
            "failed_batches": [],
        }

        task_map: dict[int, str] = {}
        resource_map: dict[int, str] = {}

        try:
            # Import tasks in batches (REQ-005: Batch processing)
            for i in range(0, len(data.tasks), batch_size):
                batch_num = i // batch_size + 1
                batch_tasks = data.tasks[i : i + batch_size]

                logger.info(
                    f"Processing task batch {batch_num} ({len(batch_tasks)} tasks)"
                )

                try:
                    if mode == "initial":
                        result = self.create_tasks_bulk(project_id, batch_tasks)
                        summary["tasks_created"] += result.get("created_count", 0)
                        task_map.update(result.get("task_map", {}))
                    else:  # sync mode
                        result = self.sync_tasks(project_id, batch_tasks)
                        summary["tasks_created"] += result.get("created_count", 0)
                        summary["tasks_updated"] += result.get("updated_count", 0)

                    summary["tasks_failed"] += result.get("failed_count", 0)

                except WfpApiError as e:
                    logger.error(f"Task batch {batch_num} failed: {e}", exc_info=True)
                    # Cast to correct type for appending
                    from typing import cast

                    cast(list[dict[str, Any]], summary["failed_batches"]).append(
                        {
                            "batch_type": "tasks",
                            "batch_num": batch_num,
                            "error": str(e),
                        }
                    )
                    # Continue with next batch (partial failure)

            # Apply predecessors after initial creation using sync endpoint
            if mode == "initial" and any(task.predecessors for task in data.tasks):
                logger.info("Applying task predecessors via sync...")
                for i in range(0, len(data.tasks), batch_size):
                    batch_num = i // batch_size + 1
                    batch_tasks = data.tasks[i : i + batch_size]

                    try:
                        result = self.sync_tasks(project_id, batch_tasks)
                        summary["tasks_updated"] += result.get("updated_count", 0)
                        summary["tasks_failed"] += result.get("failed_count", 0)
                    except WfpApiError as e:
                        logger.error(
                            "Predecessor sync batch %s failed: %s",
                            batch_num,
                            e,
                            exc_info=True,
                        )
                        from typing import cast

                        cast(list[dict[str, Any]], summary["failed_batches"]).append(
                            {
                                "batch_type": "tasks_sync",
                                "batch_num": batch_num,
                                "error": str(e),
                            }
                        )

            # Import resources (only for initial mode)
            if mode == "initial" and data.resources:
                try:
                    result = self.create_resources_bulk(project_id, data.resources)
                    summary["resources_created"] = result.get("created_count", 0)
                    summary["resources_failed"] = result.get("failed_count", 0)
                    resource_map = result.get("resource_map", {})
                except WfpApiError as e:
                    logger.error(f"Resource import failed: {e}", exc_info=True)
                    from typing import cast

                    cast(list[dict[str, Any]], summary["failed_batches"]).append(
                        {
                            "batch_type": "resources",
                            "error": str(e),
                        }
                    )

            # Import assignments (only for initial mode)
            if mode == "initial" and data.assignments:
                try:
                    result = self.create_assignments_with_mapping(
                        project_id,
                        data.assignments,
                        task_map,
                        resource_map,
                    )
                    summary["assignments_created"] = result.get("created_count", 0)
                    summary["assignments_failed"] = result.get("failed_count", 0)
                except WfpApiError as e:
                    logger.error(f"Assignment import failed: {e}", exc_info=True)
                    from typing import cast

                    cast(list[dict[str, Any]], summary["failed_batches"]).append(
                        {
                            "batch_type": "assignments",
                            "error": str(e),
                        }
                    )

            logger.info(
                f"Import completed: {summary['tasks_created']} tasks created, "
                f"{summary['tasks_updated']} updated, "
                f"{summary['tasks_failed']} failed"
            )

            return summary

        except Exception as e:
            logger.exception("Critical error during import")
            raise WfpApiError(f"Import failed: {str(e)}") from e
