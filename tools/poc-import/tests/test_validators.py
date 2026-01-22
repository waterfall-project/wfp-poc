# Copyright (c) 2026 Waterfall Project
# SPDX-License-Identifier: Commercial

"""Tests for validators."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from poc_import.models import (
    UNASSIGNED_RESOURCE_UID,
    Assignment,
    Dependency,
    MSProjectData,
    ProjectMetadata,
    Resource,
    ResourceType,
    Task,
)
from poc_import.parsers.msproject import MSProjectParser
from poc_import.validators import (
    DataValidator,
    MilestoneValidator,
    ValidationError,
    ValidationSeverity,
    validate_for_initial_import,
    validate_for_sync_import,
    validate_msproject_rules,
)


@pytest.fixture
def valid_project():
    """Create valid project metadata."""
    return ProjectMetadata(
        name="Test Project",
        start_date=datetime(2026, 1, 1, tzinfo=UTC),
        finish_date=datetime(2026, 12, 31, tzinfo=UTC),
        guid=str(uuid4()),
    )


@pytest.fixture
def valid_task():
    """Create valid task."""
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
def valid_milestone():
    """Create valid milestone."""
    return Task(
        uid=2,
        name="Milestone 1",
        wbs_code="1.0",
        planned_start_date=datetime(2026, 1, 31, tzinfo=UTC),
        planned_finish_date=datetime(2026, 1, 31, tzinfo=UTC),
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


def test_validate_rules_circular_dependency(valid_project):
    """Test circular dependency detection.

    Given: Tasks with a circular dependency
    When: Validation rules are executed
    Then: VAL-001 error is reported
    """
    tasks = [
        Task(uid=1, name="Task 1", wbs_code="1"),
        Task(uid=2, name="Task 2", wbs_code="2"),
        Task(uid=3, name="Task 3", wbs_code="3"),
    ]
    dependencies = [
        Dependency(task_uid=1, predecessor_task_uid=2, line_number=10),
        Dependency(task_uid=2, predecessor_task_uid=3, line_number=11),
        Dependency(task_uid=3, predecessor_task_uid=1, line_number=12),
    ]
    data = MSProjectData(
        project=valid_project,
        tasks=tasks,
        dependencies=dependencies,
        resources=[],
        assignments=[],
    )

    report = validate_msproject_rules(data)

    assert report.has_errors() is True
    assert any(issue.id == "VAL-001" for issue in report.checks)


def test_validate_rules_invalid_date_format(valid_project):
    """Test invalid date format detection.

    Given: Task with invalid date format
    When: Validation rules are executed
    Then: VAL-004 error is reported
    """
    task = Task(
        uid=1,
        name="Task 1",
        wbs_code="1",
        planned_start_date=None,
        planned_finish_date=None,
        planned_start_date_raw="15/01/2026",
    )
    data = MSProjectData(
        project=valid_project,
        tasks=[task],
        dependencies=[],
        resources=[],
        assignments=[],
    )

    report = validate_msproject_rules(data)

    assert report.has_errors() is True
    assert any(issue.id == "VAL-004" for issue in report.checks)


def test_validate_rules_missing_resource_reference(valid_project):
    """Test resource reference validation.

    Given: Assignment referencing a missing resource
    When: Validation rules are executed
    Then: VAL-006 error is reported
    """
    task = Task(uid=1, name="Task 1", wbs_code="1")
    assignment = Assignment(task_uid=1, resource_uid=99, line_number=42)
    data = MSProjectData(
        project=valid_project,
        tasks=[task],
        dependencies=[],
        resources=[],
        assignments=[assignment],
    )

    report = validate_msproject_rules(data)

    assert report.has_errors() is True
    assert any(issue.id == "VAL-006" for issue in report.checks)


def test_validate_rules_ignore_unassigned_resource(valid_project):
    """Test unassigned resource UID ignored.

    Given: Assignment uses unassigned resource sentinel
    When: Validation rules are executed
    Then: No missing resource error is reported
    """
    task = Task(uid=1, name="Task 1", wbs_code="1")
    assignment = Assignment(
        task_uid=1,
        resource_uid=UNASSIGNED_RESOURCE_UID,
        line_number=14010,
    )
    data = MSProjectData(
        project=valid_project,
        tasks=[task],
        dependencies=[],
        resources=[],
        assignments=[assignment],
    )

    report = validate_msproject_rules(data)

    assert report.has_errors() is False


def test_data_validator_allows_unassigned_resource(valid_project):
    """Test data validator allows unassigned resource UID.

    Given: Assignment uses unassigned resource sentinel
    When: DataValidator.validate_msproject_data is called
    Then: Data validation passes
    """
    task = Task(uid=1, name="Task 1", wbs_code="1")
    assignment = Assignment(
        task_uid=1,
        resource_uid=UNASSIGNED_RESOURCE_UID,
    )
    data = MSProjectData(
        project=valid_project,
        tasks=[task],
        dependencies=[],
        resources=[],
        assignments=[assignment],
    )

    is_valid, errors = DataValidator.validate_msproject_data(data)

    assert is_valid is True
    assert errors == []


def test_validate_rules_version_conflict(valid_project):
    """Test version conflict detection.

    Given: XML and API versions are different
    When: Validation rules are executed
    Then: VAL-007 error is reported
    """
    valid_project.ms_project_save_version = 14
    data = MSProjectData(
        project=valid_project,
        tasks=[],
        dependencies=[],
        resources=[],
        assignments=[],
    )
    api_project = {"ms_project_save_version": 15}

    report = validate_msproject_rules(data, api_project=api_project)

    assert report.has_errors() is True
    issue = next(issue for issue in report.checks if issue.id == "VAL-007")
    assert issue.severity == ValidationSeverity.ERROR


def test_validate_rules_version_warning_when_missing(valid_project):
    """Test version conflict warning when API version missing.

    Given: API project missing ms_project_save_version
    When: Validation rules are executed
    Then: VAL-007 warning is reported
    """
    valid_project.ms_project_save_version = 14
    data = MSProjectData(
        project=valid_project,
        tasks=[],
        dependencies=[],
        resources=[],
        assignments=[],
    )
    api_project: dict[str, object] = {}

    report = validate_msproject_rules(data, api_project=api_project)

    issue = next(issue for issue in report.checks if issue.id == "VAL-007")
    assert issue.severity == ValidationSeverity.WARNING


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
    valid_project.finish_date = datetime(2025, 1, 1, tzinfo=UTC)
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
        planned_start_date=datetime(2026, 2, 1, tzinfo=UTC),
        planned_finish_date=datetime(2026, 2, 28, tzinfo=UTC),
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


def test_validate_rules_circular_dependency_fixture(circular_dependency_xml_path):
    """Test circular dependency validation using fixture.

    Given: An XML fixture with a circular dependency
    When: MS Project validation rules are executed
    Then: VAL-001 is reported
    """
    parser = MSProjectParser(circular_dependency_xml_path)
    data = parser.parse()

    report = validate_msproject_rules(data)

    assert report.has_errors() is True
    assert any(issue.id == "VAL-001" for issue in report.checks)


def test_validate_rules_invalid_dates_fixture(invalid_dates_xml_path):
    """Test invalid dates validation using fixture.

    Given: An XML fixture with Finish < Start
    When: MS Project validation rules are executed
    Then: VAL-003 is reported
    """
    parser = MSProjectParser(invalid_dates_xml_path)
    data = parser.parse()

    report = validate_msproject_rules(data)

    assert report.has_errors() is True
    assert any(issue.id == "VAL-003" for issue in report.checks)


def test_validate_rules_missing_references_fixture(missing_references_xml_path):
    """Test missing references validation using fixture.

    Given: An XML fixture with missing predecessor references
    When: MS Project validation rules are executed
    Then: VAL-005 is reported
    """
    parser = MSProjectParser(missing_references_xml_path)
    data = parser.parse()

    report = validate_msproject_rules(data)

    assert report.has_errors() is True
    assert any(issue.id == "VAL-005" for issue in report.checks)


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
