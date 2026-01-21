# Copyright (c) 2026 Waterfall Project
# SPDX-License-Identifier: Commercial

"""Integration tests for import flows and rollback."""

from __future__ import annotations

import time
from uuid import uuid4

import pytest
import requests

from poc_import.api.client import WfpApiClient, WfpApiError
from poc_import.config import Config
from poc_import.parsers.msproject import MSProjectParser


def _wait_for_service(base_url: str, timeout_seconds: int = 30) -> bool:
    """Wait for the wfp-poc service to be ready.

    Args:
        base_url: Base URL for the service.
        timeout_seconds: Timeout in seconds.

    Returns:
        True if service is available, False otherwise.
    """
    deadline = time.monotonic() + timeout_seconds
    health_url = f"{base_url.rstrip('/')}/health"
    while time.monotonic() < deadline:
        try:
            response = requests.get(health_url, timeout=2)
            if response.status_code == 200:
                return True
        except requests.RequestException:
            pass
        time.sleep(1)
    return False


def _extract_project_id(response: dict) -> str:
    """Extract project ID from API response.

    Args:
        response: API response payload.

    Returns:
        Project UUID string.

    Raises:
        ValueError: If project ID cannot be found.
    """
    project_id = response.get("data", {}).get("id") or response.get("id")
    if not project_id:
        raise ValueError("Project ID not found in response")
    return str(project_id)


@pytest.fixture(scope="session")
def wfp_api_client() -> WfpApiClient:
    """Create API client for integration tests.

    Returns:
        Configured WfpApiClient.
    """
    config = Config()
    token = config.jwt_token or config.build_jwt_token()
    if not token:
        pytest.skip("JWT token not available for integration tests")

    if not _wait_for_service(config.api_url):
        pytest.skip("wfp-poc service not available for integration tests")

    return WfpApiClient(
        config.api_url,
        token,
        correlation_id=str(uuid4()),
        company_id=config.company_id,
    )


def test_happy_path_import(simple_project_xml_path, wfp_api_client):
    """Test full import flow against real service.

    Given: A simple MS Project XML fixture
    When: Tasks, resources, assignments, and dependencies are imported
    Then: Entities are created in the wfp-poc service
    """
    parser = MSProjectParser(simple_project_xml_path)
    data = parser.parse()

    project_response = wfp_api_client.create_project(data.project)
    project_id = _extract_project_id(project_response)

    created_task_ids: list[str] = []
    created_resource_ids: list[str] = []
    created_assignment_ids: list[str] = []
    task_map: dict[int, str] = {}
    resource_map: dict[int, str] = {}

    try:
        for task in data.tasks:
            result = wfp_api_client.create_task(project_id, task)
            task_id = result.get("task_id")
            task_map.update(result.get("task_map", {}))
            if task_id:
                created_task_ids.append(task_id)

        for resource in data.resources:
            result = wfp_api_client.create_resource(resource)
            resource_id = result.get("resource_id")
            resource_map.update(result.get("resource_map", {}))
            if resource_id:
                created_resource_ids.append(resource_id)

        for assignment in data.assignments:
            result = wfp_api_client.create_assignment(
                project_id,
                assignment,
                task_map,
                resource_map,
            )
            assignment_id = result.get("assignment_id")
            if assignment_id:
                created_assignment_ids.append(assignment_id)

        if data.dependencies:
            wfp_api_client.sync_tasks(project_id, data.tasks)

        tasks_response = wfp_api_client.list_project_tasks(project_id)
        tasks = tasks_response.get("data", [])
        assert len(tasks) == len(data.tasks)

    finally:
        wfp_api_client.rollback_import(
            project_id,
            task_ids=created_task_ids,
            assignment_ids=created_assignment_ids,
            resource_ids=created_resource_ids,
        )
        wfp_api_client._request(
            "DELETE",
            f"/v0/projects/{project_id}",
        )


def test_rollback_on_failure(simple_project_xml_path, wfp_api_client):
    """Test rollback behavior after a failure.

    Given: Tasks and resources are created
    When: Assignment creation fails
    Then: Rollback removes created entities
    """
    parser = MSProjectParser(simple_project_xml_path)
    data = parser.parse()

    project_response = wfp_api_client.create_project(data.project)
    project_id = _extract_project_id(project_response)

    created_task_ids: list[str] = []
    created_resource_ids: list[str] = []

    try:
        for task in data.tasks:
            result = wfp_api_client.create_task(project_id, task)
            task_id = result.get("task_id")
            if task_id:
                created_task_ids.append(task_id)

        for resource in data.resources:
            result = wfp_api_client.create_resource(resource)
            resource_id = result.get("resource_id")
            if resource_id:
                created_resource_ids.append(resource_id)

        with pytest.raises(WfpApiError):
            wfp_api_client.create_assignment(
                project_id,
                data.assignments[0],
                task_map={},
                resource_map={},
            )

        wfp_api_client.rollback_import(
            project_id,
            task_ids=created_task_ids,
            resource_ids=created_resource_ids,
        )

        tasks_response = wfp_api_client.list_project_tasks(project_id)
        tasks = tasks_response.get("data", [])
        assert tasks == []

    finally:
        wfp_api_client.rollback_import(
            project_id,
            task_ids=created_task_ids,
            resource_ids=created_resource_ids,
        )
        wfp_api_client._request(
            "DELETE",
            f"/v0/projects/{project_id}",
        )


def test_auth_error_invalid_token():
    """Test authentication error handling.

    Given: An invalid JWT token
    When: The API client lists projects
    Then: A 401 error is raised
    """
    config = Config()
    if not _wait_for_service(config.api_url):
        pytest.skip("wfp-poc service not available for integration tests")

    client = WfpApiClient(
        config.api_url,
        token="invalid-token",
        correlation_id=str(uuid4()),
        company_id=config.company_id,
    )

    with pytest.raises(WfpApiError) as exc_info:
        client.list_projects()

    assert exc_info.value.status_code == 401
