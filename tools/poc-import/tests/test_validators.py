# Copyright (c) 2026 Waterfall Project
# SPDX-License-Identifier: Commercial

"""Tests for validators."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from poc_import.models import (
    Assignment,
    MSProjectData,
    ProjectMetadata,
    Resource,
    ResourceType,
    Task,
)
from poc_import.validators import (
    DataValidator,
    MilestoneValidator,
    ValidationError,
    validate_for_initial_import,
    validate_for_sync_import,
)


@pytest.fixture
def valid_project():
    """Create valid project metadata."""
    return ProjectMetadata(
        name="Test Project",
        start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        finish_date=datetime(2026, 12, 31, tzinfo=timezone.utc),
        guid=str(uuid4()),
    )


@pytest.fixture
def valid_task():
    """Create valid task."""
    return Task(
        uid=1,
        name="Test Task",
        wbs_code="1.1",
        planned_start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        planned_finish_date=datetime(2026, 1, 31, tzinfo=timezone.utc),
        duration_hours=160,
        is_milestone=False,
        guid=str(uuid4()),
    )


@pytest.fixture
def valid_milestone():
    """Create valid milestone."""
    return Task(
        uid=2,
        name="Milestone 1",
        wbs_code="1.0",
        planned_start_date=datetime(2026, 1, 31, tzinfo=timezone.utc),
        planned_finish_date=datetime(2026, 1, 31, tzinfo=timezone.utc),
        duration_hours=0,
        is_milestone=True,
        guid=str(uuid4()),
    )


@pytest.fixture
def valid_resource():
    """Create valid resource."""
    return Resource(
        uid=1,
        name="Test Resource",
        type=ResourceType.LABOR,
        standard_rate=100.0,
    )


@pytest.fixture
def valid_assignment():
    """Create valid assignment."""
    return Assignment(
        task_uid=1,
        resource_uid=1,
        work_hours=40,
    )


def test_extract_milestones(valid_task, valid_milestone):
    """Test milestone extraction."""
    tasks = [valid_task, valid_milestone]
    milestones = MilestoneValidator.extract_milestones(tasks)

    assert len(milestones) == 1
    assert milestones[0] == ("1.0", "Milestone 1")


def test_validate_milestone_consistency_success(valid_milestone):
    """Test successful milestone validation."""
    new_tasks = [valid_milestone]
    existing_milestones = [{"name": "Milestone 1"}]

    is_valid, errors = MilestoneValidator.validate_milestone_consistency(
        new_tasks, existing_milestones
    )

    assert is_valid
    assert len(errors) == 0


def test_validate_milestone_consistency_count_mismatch(valid_milestone):
    """Test milestone count mismatch."""
    new_tasks = [valid_milestone]
    existing_milestones = [
        {"name": "Milestone 1"},
        {"name": "Milestone 2"},
    ]

    is_valid, errors = MilestoneValidator.validate_milestone_consistency(
        new_tasks, existing_milestones
    )

    assert not is_valid
    assert any("count mismatch" in err for err in errors)


def test_validate_milestone_consistency_name_changed(valid_milestone):
    """Test milestone name change detection."""
    new_tasks = [valid_milestone]
    existing_milestones = [{"name": "Different Name"}]

    is_valid, errors = MilestoneValidator.validate_milestone_consistency(
        new_tasks, existing_milestones
    )

    assert not is_valid
    assert any("Missing milestones" in err for err in errors)


def test_validate_msproject_data_success(
    valid_project, valid_task, valid_resource, valid_assignment
):
    """Test successful data validation."""
    data = MSProjectData(
        project=valid_project,
        tasks=[valid_task],
        resources=[valid_resource],
        assignments=[valid_assignment],
    )

    is_valid, errors = DataValidator.validate_msproject_data(data)

    assert is_valid
    assert len(errors) == 0


def test_validate_msproject_data_empty_project_name(valid_project, valid_task):
    """Test validation with empty project name."""
    valid_project.name = ""
    data = MSProjectData(
        project=valid_project, tasks=[valid_task], resources=[], assignments=[]
    )

    is_valid, errors = DataValidator.validate_msproject_data(data)

    assert not is_valid
    assert any("Project name is required" in err for err in errors)


def test_validate_msproject_data_invalid_dates(valid_project, valid_task):
    """Test validation with invalid dates."""
    valid_project.finish_date = datetime(2025, 1, 1, tzinfo=timezone.utc)
    data = MSProjectData(
        project=valid_project, tasks=[valid_task], resources=[], assignments=[]
    )

    is_valid, errors = DataValidator.validate_msproject_data(data)

    assert not is_valid
    assert any("start_date must be before finish_date" in err for err in errors)


def test_validate_msproject_data_task_missing_name(valid_project, valid_task):
    """Test validation with missing task name."""
    valid_task.name = ""
    data = MSProjectData(
        project=valid_project, tasks=[valid_task], resources=[], assignments=[]
    )

    is_valid, errors = DataValidator.validate_msproject_data(data)

    assert not is_valid
    assert any("name is required" in err for err in errors)


def test_validate_msproject_data_negative_duration(valid_project, valid_task):
    """Test validation with negative duration."""
    valid_task.duration_hours = -10
    data = MSProjectData(
        project=valid_project, tasks=[valid_task], resources=[], assignments=[]
    )

    is_valid, errors = DataValidator.validate_msproject_data(data)

    assert not is_valid
    assert any("duration_hours cannot be negative" in err for err in errors)


def test_validate_msproject_data_milestone_with_duration(
    valid_project, valid_milestone
):
    """Test validation of milestone with non-zero duration."""
    valid_milestone.duration_hours = 8
    data = MSProjectData(
        project=valid_project,
        tasks=[valid_milestone],
        resources=[],
        assignments=[],
    )

    is_valid, errors = DataValidator.validate_msproject_data(data)

    assert not is_valid
    assert any("milestone tasks should have duration_hours=0" in err for err in errors)


def test_validate_msproject_data_duplicate_task_uid(valid_project, valid_task):
    """Test validation with duplicate task UID."""
    task2 = Task(
        uid=1,  # Duplicate UID
        name="Task 2",
        wbs_code="1.2",
        planned_start_date=datetime(2026, 2, 1, tzinfo=timezone.utc),
        planned_finish_date=datetime(2026, 2, 28, tzinfo=timezone.utc),
        duration_hours=160,
        is_milestone=False,
    )

    data = MSProjectData(
        project=valid_project,
        tasks=[valid_task, task2],
        resources=[],
        assignments=[],
    )

    is_valid, errors = DataValidator.validate_msproject_data(data)

    assert not is_valid
    assert any("duplicate uid" in err for err in errors)


def test_validate_msproject_data_negative_resource_rate(
    valid_project, valid_task, valid_resource
):
    """Test validation with negative resource rate."""
    valid_resource.standard_rate = -50.0
    data = MSProjectData(
        project=valid_project,
        tasks=[valid_task],
        resources=[valid_resource],
        assignments=[],
    )

    is_valid, errors = DataValidator.validate_msproject_data(data)

    assert not is_valid
    assert any("standard_rate cannot be negative" in err for err in errors)


def test_validate_msproject_data_assignment_invalid_task(
    valid_project, valid_task, valid_resource, valid_assignment
):
    """Test validation with assignment referencing non-existent task."""
    valid_assignment.task_uid = 999  # Non-existent
    data = MSProjectData(
        project=valid_project,
        tasks=[valid_task],
        resources=[valid_resource],
        assignments=[valid_assignment],
    )

    is_valid, errors = DataValidator.validate_msproject_data(data)

    assert not is_valid
    assert any("task_uid 999 not found" in err for err in errors)


def test_validate_for_initial_import_success(
    valid_project, valid_task, valid_resource, valid_assignment
):
    """Test successful initial import validation."""
    data = MSProjectData(
        project=valid_project,
        tasks=[valid_task],
        resources=[valid_resource],
        assignments=[valid_assignment],
    )

    # Should not raise
    validate_for_initial_import(data)


def test_validate_for_initial_import_failure(valid_project, valid_task):
    """Test failed initial import validation."""
    valid_task.name = ""  # Invalid
    data = MSProjectData(
        project=valid_project, tasks=[valid_task], resources=[], assignments=[]
    )

    with pytest.raises(ValidationError) as exc_info:
        validate_for_initial_import(data)

    assert "Initial import validation failed" in str(exc_info.value)


def test_validate_for_sync_import_success(valid_project, valid_milestone):
    """Test successful sync import validation."""
    data = MSProjectData(
        project=valid_project,
        tasks=[valid_milestone],
        resources=[],
        assignments=[],
    )
    existing_milestones = [{"name": "Milestone 1"}]

    # Should not raise
    validate_for_sync_import(data, existing_milestones)


def test_validate_for_sync_import_milestone_failure(valid_project, valid_milestone):
    """Test sync import validation with milestone mismatch."""
    data = MSProjectData(
        project=valid_project,
        tasks=[valid_milestone],
        resources=[],
        assignments=[],
    )
    existing_milestones = [{"name": "Different Milestone"}]

    with pytest.raises(ValidationError) as exc_info:
        validate_for_sync_import(data, existing_milestones)

    assert "Milestone validation failed" in str(exc_info.value)
