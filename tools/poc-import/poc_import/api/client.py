# Copyright (c) 2026 Waterfall Project
# SPDX-License-Identifier: Commercial

"""wfp-poc REST API client with authentication and retry logic."""

import logging
from typing import Any, Optional

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
        status_code: Optional[int] = None,
        response_data: Optional[dict[str, Any]] = None,
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
        company_id: Optional[str] = None,
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
            if 400 <= response.status_code < 500:
                logger.error(f"Client error {response.status_code}: {error_data}")
                raise WfpApiError(
                    f"API client error: {error_data.get('detail', str(e))}",
                    status_code=response.status_code,
                    response_data=error_data,
                ) from e

            # Server errors will be retried by the session retry strategy
            logger.error(f"Server error {response.status_code}: {error_data}")
            raise WfpApiError(
                f"API server error: {error_data.get('detail', str(e))}",
                status_code=response.status_code,
                response_data=error_data,
            ) from e

    def validate_token(self) -> dict[str, Any]:
        """Validate JWT token by calling health endpoint.

        Returns:
            Health check response

        Raises:
            WfpApiError: If token is invalid (401)
        """
        logger.debug("Validating JWT token...")
        response = self.session.get(f"{self.base_url}/health", timeout=self.timeout)
        return self._handle_response(response)

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
            "start_date": project.start_date.isoformat(),
            "finish_date": project.finish_date.isoformat(),
        }

        # Add optional fields
        if project.guid:
            payload["ms_project_guid"] = project.guid

        response = self.session.post(
            f"{self.base_url}/v0/projects",
            json=payload,
            timeout=self.timeout,
        )

        data = self._handle_response(response)
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
        response = self.session.get(
            f"{self.base_url}/v0/projects/{project_id}",
            timeout=self.timeout,
        )
        return self._handle_response(response)

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
        response = self.session.get(
            f"{self.base_url}/v0/projects/{project_id}/milestones",
            timeout=self.timeout,
        )
        data = self._handle_response(response)
        milestones: list[dict[str, Any]] = data.get("milestones", [])
        return milestones

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
                hours = int(task.duration_hours)
                fractional_hours = task.duration_hours - hours
                # Use rounding instead of truncation to avoid precision loss,
                # e.g. 8.333 hours -> 8 hours 20 minutes rather than 19.
                minutes = int(round(fractional_hours * 60))
                # Handle edge case where rounding yields 60 minutes.
                if minutes == 60:
                    hours += 1
                    minutes = 0
                payload["duration"] = f"PT{hours}H{minutes}M0S"

            # Add optional fields
            if task.guid:
                payload["ms_project_guid"] = task.guid
            if task.uid:
                payload["ms_project_uid"] = task.uid

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

        response = self.session.post(
            f"{self.base_url}/v0/projects/{project_id}/tasks/bulk",
            json={"tasks": task_payloads},
            timeout=self.timeout * 2,  # Longer timeout for bulk
        )

        data = self._handle_response(response)
        logger.info(
            f"Created {data.get('created_count', 0)} tasks, "
            f"failed {data.get('failed_count', 0)}"
        )
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
                hours = int(task.duration_hours)
                fractional_hours = task.duration_hours - hours
                # Use rounding instead of truncation to avoid precision loss,
                # e.g. 8.333 hours -> 8 hours 20 minutes rather than 19.
                minutes = int(round(fractional_hours * 60))
                # Handle edge case where rounding yields 60 minutes.
                if minutes == 60:
                    hours += 1
                    minutes = 0
                payload["duration"] = f"PT{hours}H{minutes}M0S"

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

        response = self.session.put(
            f"{self.base_url}/v0/projects/{project_id}/tasks/sync",
            json={"tasks": task_payloads},
            timeout=self.timeout * 2,
        )

        data = self._handle_response(response)
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

                response = self.session.post(
                    f"{self.base_url}/v0/resources",
                    json=payload,
                    timeout=self.timeout,
                )

                result = self._handle_response(response)
                resource_ids.append(result.get("data", {}).get("id"))
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

        # Transform assignments to API payload and create individually
        # Note: assignments need task_id/resource_id which we don't have yet
        # This is a limitation - we'd need to resolve UIDs to UUIDs first
        logger.warning(
            "Assignment creation requires task_id/resource_id mapping "
            "which is not implemented yet"
        )

        # For now, return empty result
        # TODO: Implement UID to UUID resolution after tasks/resources
        return {
            "created_count": 0,
            "failed_count": len(assignments),
            "assignment_ids": [],
            "errors": [
                {
                    "index": idx,
                    "error": "UID to UUID mapping not implemented - skipped",
                }
                for idx in range(len(assignments))
            ],
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

            # Import resources (only for initial mode)
            if mode == "initial" and data.resources:
                try:
                    result = self.create_resources_bulk(project_id, data.resources)
                    summary["resources_created"] = result.get("created_count", 0)
                    summary["resources_failed"] = result.get("failed_count", 0)
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
                    result = self.create_assignments_bulk(project_id, data.assignments)
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
