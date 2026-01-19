# Copyright (c) 2026 Waterfall Project
# SPDX-License-Identifier: Commercial

"""Tests for API client."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
import requests_mock

from poc_import.api.client import WfpApiClient, WfpApiError
from poc_import.models import (
    Assignment,
    MSProjectData,
    ProjectMetadata,
    Resource,
    ResourceType,
    Task,
)


@pytest.fixture
def api_client():
    """Create API client for testing."""
    return WfpApiClient(
        base_url="http://localhost:5000",
        token="test-token",
        correlation_id="test-correlation-id",
    )


@pytest.fixture
def sample_project():
    """Create sample project metadata."""
    return ProjectMetadata(
        name="Test Project",
        start_date=datetime(2026, 1, 1, tzinfo=UTC),
        finish_date=datetime(2026, 12, 31, tzinfo=UTC),
        guid=str(uuid4()),
    )


@pytest.fixture
def sample_task():
    """Create sample task."""
    return Task(
        uid=1,
        name="Test Task",
        wbs_code="1.1",
        planned_start_date=datetime(2026, 1, 1, tzinfo=UTC),
        planned_finish_date=datetime(2026, 1, 31, tzinfo=UTC),
        duration_hours=160,
        is_milestone=False,
        guid=str(uuid4()),
    )


@pytest.fixture
def sample_resource():
    """Create sample resource."""
    return Resource(
        uid=1,
        name="Test Resource",
        type=ResourceType.LABOR,
        standard_rate=100.0,
    )


@pytest.fixture
def sample_assignment():
    """Create sample assignment."""
    return Assignment(
        task_uid=1,
        resource_uid=1,
        work_hours=40,
    )


def test_client_initialization(api_client):
    """Test API client initialization."""
    assert api_client.base_url == "http://localhost:5000"
    assert api_client.token == "test-token"
    assert api_client.correlation_id == "test-correlation-id"
    assert "Authorization" in api_client.session.headers
    assert api_client.session.headers["Authorization"] == "Bearer test-token"


def test_validate_token_success(api_client):
    """Test successful token validation."""
    with requests_mock.Mocker() as m:
        m.get("http://localhost:5000/health", json={"status": "ok"})
        result = api_client.validate_token()
        assert result["status"] == "ok"


def test_validate_token_failure(api_client):
    """Test token validation failure."""
    with requests_mock.Mocker() as m:
        m.get("http://localhost:5000/health", status_code=401)
        with pytest.raises(WfpApiError) as exc_info:
            api_client.validate_token()
        assert exc_info.value.status_code == 401


def test_create_project_success(api_client, sample_project):
    """Test successful project creation."""
    project_id = str(uuid4())
    with requests_mock.Mocker() as m:
        m.post(
            "http://localhost:5000/v0/projects",
            json={
                "id": project_id,
                "name": sample_project.name,
                "start_date": sample_project.start_date.isoformat(),
                "finish_date": sample_project.finish_date.isoformat(),
            },
        )

        result = api_client.create_project(sample_project)

        assert result["id"] == project_id
        assert result["name"] == sample_project.name


def test_create_project_error(api_client, sample_project):
    """Test project creation error."""
    with requests_mock.Mocker() as m:
        m.post(
            "http://localhost:5000/v0/projects",
            status_code=400,
            json={"detail": "Invalid project data"},
        )

        with pytest.raises(WfpApiError) as exc_info:
            api_client.create_project(sample_project)

        assert exc_info.value.status_code == 400


def test_get_project_success(api_client):
    """Test successful project retrieval."""
    project_id = str(uuid4())
    with requests_mock.Mocker() as m:
        m.get(
            f"http://localhost:5000/v0/projects/{project_id}",
            json={"id": project_id, "name": "Test Project"},
        )

        result = api_client.get_project(project_id)

        assert result["id"] == project_id
        assert result["name"] == "Test Project"


def test_get_project_milestones_success(api_client):
    """Test successful milestone retrieval."""
    project_id = str(uuid4())
    with requests_mock.Mocker() as m:
        m.get(
            f"http://localhost:5000/v0/projects/{project_id}/milestones",
            json={
                "data": [
                    {"id": str(uuid4()), "name": "Milestone 1"},
                    {"id": str(uuid4()), "name": "Milestone 2"},
                ]
            },
        )

        result = api_client.get_project_milestones(project_id)

        assert len(result) == 2
        assert result[0]["name"] == "Milestone 1"


def test_create_tasks_bulk_success(api_client, sample_task):
    """Test successful bulk task creation."""
    project_id = str(uuid4())
    tasks = [sample_task]

    with requests_mock.Mocker() as m:
        m.post(
            f"http://localhost:5000/v0/projects/{project_id}/tasks/bulk",
            json={"created_count": 1, "failed_count": 0, "task_ids": [str(uuid4())]},
        )

        result = api_client.create_tasks_bulk(project_id, tasks)

        assert result["created_count"] == 1
        assert result["failed_count"] == 0


def test_create_tasks_bulk_too_many(api_client, sample_task):
    """Test bulk task creation with too many tasks."""
    project_id = str(uuid4())
    tasks = [sample_task] * 101  # Exceed limit

    with pytest.raises(ValueError, match="Too many tasks"):
        api_client.create_tasks_bulk(project_id, tasks)


def test_sync_tasks_success(api_client, sample_task):
    """Test successful task sync."""
    project_id = str(uuid4())
    tasks = [sample_task]

    with requests_mock.Mocker() as m:
        m.put(
            f"http://localhost:5000/v0/projects/{project_id}/tasks/sync",
            json={
                "created_count": 0,
                "updated_count": 1,
                "failed_count": 0,
            },
        )

        result = api_client.sync_tasks(project_id, tasks)

        assert result["created_count"] == 0
        assert result["updated_count"] == 1
        assert result["failed_count"] == 0


def test_create_resources_bulk_success(api_client, sample_resource):
    """Test successful bulk resource creation."""
    project_id = str(uuid4())
    resources = [sample_resource]

    with requests_mock.Mocker() as m:
        # Mock individual resource creation
        m.post(
            "http://localhost:5000/v0/resources",
            json={
                "data": {
                    "id": str(uuid4()),
                    "name": sample_resource.name,
                },
                "message": "Resource created successfully",
            },
        )

        result = api_client.create_resources_bulk(project_id, resources)

        assert result["created_count"] == 1
        assert result["failed_count"] == 0


def test_create_assignments_bulk_success(api_client, sample_assignment):
    """Test bulk assignment creation (not implemented - returns errors)."""
    project_id = str(uuid4())
    assignments = [sample_assignment]

    with pytest.raises(WfpApiError, match="requires UID->UUID mapping"):
        api_client.create_assignments_bulk(project_id, assignments)


def test_import_msproject_data_initial(
    api_client, sample_project, sample_task, sample_resource, sample_assignment
):
    """Test full MS Project initial import orchestration."""
    project_id = str(uuid4())

    data = MSProjectData(
        project=sample_project,
        tasks=[sample_task],
        resources=[sample_resource],
        assignments=[sample_assignment],
    )

    with requests_mock.Mocker() as m:
        # Mock bulk API calls
        m.post(
            f"http://localhost:5000/v0/projects/{project_id}/tasks/bulk",
            json={"created_count": 1, "failed_count": 0},
        )
        # Mock individual resource creation
        m.post(
            "http://localhost:5000/v0/resources",
            json={
                "data": {"id": str(uuid4()), "name": sample_resource.name},
                "message": "Resource created",
            },
        )

        result = api_client.import_msproject_data(project_id, data, mode="initial")

        assert result["mode"] == "initial"
        assert result["tasks_created"] == 1
        assert result["resources_created"] == 1
        assert result["assignments_created"] == 0  # Not implemented
        assert result["assignments_failed"] == 1  # Skipped
        assert result["tasks_failed"] == 0


def test_import_msproject_data_sync(api_client, sample_project, sample_task):
    """Test full MS Project sync orchestration."""
    project_id = str(uuid4())

    data = MSProjectData(
        project=sample_project,
        tasks=[sample_task],
        resources=[],
        assignments=[],
    )

    with requests_mock.Mocker() as m:
        m.put(
            f"http://localhost:5000/v0/projects/{project_id}/tasks/sync",
            json={"created_count": 0, "updated_count": 1, "failed_count": 0},
        )

        result = api_client.import_msproject_data(project_id, data, mode="sync")

        assert result["mode"] == "sync"
        assert result["tasks_updated"] == 1
        assert result["resources_created"] == 0  # Skipped in sync mode


def test_import_msproject_data_with_batching(api_client, sample_project, sample_task):
    """Test MS Project import with batch processing."""
    project_id = str(uuid4())

    # Create 150 tasks to test batching (should create 2 batches)
    tasks = [sample_task] * 150

    data = MSProjectData(
        project=sample_project,
        tasks=tasks,
        resources=[],
        assignments=[],
    )

    with requests_mock.Mocker() as m:
        # Mock both batch calls
        m.post(
            f"http://localhost:5000/v0/projects/{project_id}/tasks/bulk",
            json={"created_count": 100, "failed_count": 0},
        )

        result = api_client.import_msproject_data(
            project_id, data, mode="initial", batch_size=100
        )

        # Should have made 2 API calls (100 + 50 tasks)
        assert result["tasks_created"] == 200  # 100 + 100 from 2 calls
        assert len(m.request_history) == 2


def test_api_error_handling(api_client):
    """Test API error handling."""
    project_id = str(uuid4())

    with requests_mock.Mocker() as m:
        m.get(
            f"http://localhost:5000/v0/projects/{project_id}",
            status_code=403,
            json={"detail": "Permission denied"},
        )

        with pytest.raises(WfpApiError) as exc_info:
            api_client.get_project(project_id)

        assert exc_info.value.status_code == 403
        assert "Permission denied" in str(exc_info.value)
