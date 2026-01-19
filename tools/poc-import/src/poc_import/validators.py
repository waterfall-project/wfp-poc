# Copyright (c) 2026 Waterfall Project
# SPDX-License-Identifier: Commercial

"""Validation logic for import data and business rules."""

import logging
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from poc_import.models import Assignment, Dependency, MSProjectData, Task

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Base exception for validation errors."""

    def __init__(self, message: str, errors: list[dict[str, Any]] | None = None):
        super().__init__(message)
        self.errors = errors or []


class ValidationSeverity(str, Enum):
    """Validation issue severity."""

    ERROR = "error"
    WARNING = "warning"


class ValidationIssue(BaseModel):
    """Single validation issue with context and line number."""

    id: str
    severity: ValidationSeverity
    message: str
    line: int | None = None
    context: dict[str, Any] = Field(default_factory=dict)


class ValidationReport(BaseModel):
    """Aggregated validation report."""

    status: str
    summary: dict[str, int]
    checks: list[ValidationIssue]

    def has_errors(self) -> bool:
        """Return True if report contains any error-level issues."""
        return self.summary.get("errors", 0) > 0


class MilestoneValidator:
    """Validator for milestone structure consistency.

    REQ-011: Validate milestone structure consistency on reimport
    REQ-012: Reject reimport if milestone count changed
    REQ-013: Reject reimport if any milestone name changed
    """

    @staticmethod
    def extract_milestones(tasks: list[Task]) -> list[tuple[str, str]]:
        """Extract milestone names from task list.

        Args:
            tasks: List of tasks

        Returns:
            List of (wbs, name) tuples for milestones
        """
        milestones = [
            (task.wbs_code, task.name)
            for task in tasks
            if task.is_milestone and task.wbs_code is not None
        ]
        # Sort by WBS for consistent comparison
        return sorted(milestones, key=lambda x: x[0])

    @staticmethod
    def validate_milestone_consistency(
        new_tasks: list[Task], existing_milestones: list[dict[str, str]]
    ) -> tuple[bool, list[str]]:
        """Validate that milestones haven't changed.

        Args:
            new_tasks: Tasks from new MS Project file
            existing_milestones: Milestones from wfp-poc API

        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []

        # Extract milestones from new tasks
        new_milestones = MilestoneValidator.extract_milestones(new_tasks)
        new_milestone_names = {name for _, name in new_milestones}

        # Extract names from existing milestones
        existing_milestone_names = {m["name"] for m in existing_milestones}

        # REQ-012: Check count
        if len(new_milestones) != len(existing_milestones):
            errors.append(
                f"Milestone count mismatch: expected {len(existing_milestones)}, "
                f"got {len(new_milestones)}"
            )

        # REQ-013: Check names
        added = new_milestone_names - existing_milestone_names
        removed = existing_milestone_names - new_milestone_names

        if added:
            errors.append(f"New milestones not allowed: {sorted(added)}")

        if removed:
            errors.append(f"Missing milestones: {sorted(removed)}")

        is_valid = len(errors) == 0

        if is_valid:
            logger.info(
                f"Milestone validation passed: {len(new_milestones)} milestones"
            )
        else:
            logger.error(f"Milestone validation failed: {errors}")

        return is_valid, errors


class DataValidator:
    """Validator for data integrity and business rules."""

    @staticmethod
    def validate_msproject_data(data: MSProjectData) -> tuple[bool, list[str]]:
        """Validate MS Project data for integrity.

        REQ-017: Validate all dates are ISO 8601 format
        REQ-018: Validate all amounts are non-negative decimals

        Args:
            data: Parsed MS Project data

        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []

        # Validate project metadata
        if not data.project.name or not data.project.name.strip():
            errors.append("Project name is required")

        if data.project.start_date >= data.project.finish_date:
            errors.append("Project start_date must be before finish_date")

        # Validate tasks
        task_uids: set[int] = set()
        for i, task in enumerate(data.tasks):
            task_errors = []

            # Check required fields
            if not task.name or not task.name.strip():
                task_errors.append("name is required")

            if not task.wbs_code or not task.wbs_code.strip():
                task_errors.append("wbs_code is required")

            # Check dates
            if task.planned_start_date and task.planned_finish_date:
                if task.planned_start_date > task.planned_finish_date:
                    task_errors.append(
                        "planned_start_date must be before planned_finish_date"
                    )

            # Check duration
            if task.duration_hours is not None and task.duration_hours < 0:
                task_errors.append("duration_hours cannot be negative")

            # Check milestone consistency
            if (
                task.is_milestone
                and task.duration_hours is not None
                and task.duration_hours > 0
            ):
                task_errors.append("milestone tasks should have duration_hours=0")

            # Check UID uniqueness
            if task.uid:
                if task.uid in task_uids:
                    task_errors.append(f"duplicate uid: {task.uid}")
                task_uids.add(task.uid)

            if task_errors:
                errors.append(f"Task {i + 1} ({task.name}): {'; '.join(task_errors)}")

        # Validate task dependencies
        for i, task in enumerate(data.tasks):
            if task.predecessors:
                for pred in task.predecessors:
                    if pred.predecessor_task_uid not in task_uids:
                        errors.append(
                            f"Task {i + 1} ({task.name}): "
                            f"predecessor UID {pred.predecessor_task_uid} not found"
                        )

        # Validate resources
        resource_uids: set[int] = set()
        for i, resource in enumerate(data.resources):
            resource_errors = []

            if not resource.name or not resource.name.strip():
                resource_errors.append("name is required")

            # Check UID uniqueness
            if resource.uid:
                if resource.uid in resource_uids:
                    resource_errors.append(f"duplicate uid: {resource.uid}")
                resource_uids.add(resource.uid)

            # Check rates are non-negative
            if resource.standard_rate is not None and resource.standard_rate < 0:
                resource_errors.append("standard_rate cannot be negative")

            if resource_errors:
                errors.append(
                    f"Resource {i + 1} ({resource.name}): {'; '.join(resource_errors)}"
                )

        # Validate assignments
        for i, assignment in enumerate(data.assignments):
            assignment_errors = []

            if assignment.task_uid not in task_uids:
                assignment_errors.append(f"task_uid {assignment.task_uid} not found")

            if assignment.resource_uid not in resource_uids:
                assignment_errors.append(
                    f"resource_uid {assignment.resource_uid} not found"
                )

            if assignment.work_hours < 0:
                assignment_errors.append("work_hours cannot be negative")

            if assignment_errors:
                errors.append(f"Assignment {i + 1}: {'; '.join(assignment_errors)}")

        is_valid = len(errors) == 0

        if is_valid:
            logger.info(
                f"Data validation passed: {len(data.tasks)} tasks, "
                f"{len(data.resources)} resources, "
                f"{len(data.assignments)} assignments"
            )
        else:
            logger.error(f"Data validation failed with {len(errors)} errors")
            for i, error in enumerate(errors, 1):
                logger.error(f"  Error {i}: {error}")

        return is_valid, errors


def validate_msproject_rules(
    data: MSProjectData,
    api_project: dict[str, Any] | None = None,
    strict: bool = False,
) -> ValidationReport:
    """Validate MS Project data against VAL-001 to VAL-007.

    Args:
        data: Parsed MS Project data.
        api_project: Optional project payload from API.
        strict: Treat warnings as errors when True.

    Returns:
        Validation report with errors and warnings.
    """
    issues: list[ValidationIssue] = []

    task_uids = {task.uid for task in data.tasks}
    resource_uids = {resource.uid for resource in data.resources}

    _validate_circular_dependencies(data.dependencies, issues)
    _validate_task_dates(data.tasks, issues)
    _validate_references(
        data.dependencies,
        data.assignments,
        task_uids,
        resource_uids,
        issues,
    )
    _validate_version_conflict(data, api_project, issues)

    errors = sum(1 for issue in issues if issue.severity == ValidationSeverity.ERROR)
    warnings = sum(
        1 for issue in issues if issue.severity == ValidationSeverity.WARNING
    )

    if strict and warnings:
        for issue in issues:
            if issue.severity == ValidationSeverity.WARNING:
                issue.severity = ValidationSeverity.ERROR
        errors += warnings
        warnings = 0

    status = "failed" if errors else "passed"
    summary = {"passed": 0, "warnings": warnings, "errors": errors}
    return ValidationReport(status=status, summary=summary, checks=issues)


def _validate_circular_dependencies(
    dependencies: list[Dependency],
    issues: list[ValidationIssue],
) -> None:
    """Validate circular dependencies (VAL-001)."""
    adjacency: dict[int, list[tuple[int, int | None]]] = {}
    for dep in dependencies:
        adjacency.setdefault(dep.task_uid, []).append(
            (dep.predecessor_task_uid, dep.line_number)
        )

    visited: set[int] = set()
    stack: set[int] = set()
    path: list[int] = []

    def dfs(node: int) -> None:
        if node in stack:
            cycle_start_index = path.index(node)
            cycle_path = path[cycle_start_index:] + [node]
            cycle_text = " \u2192 ".join(f"#{uid}" for uid in cycle_path)
            issues.append(
                ValidationIssue(
                    id="VAL-001",
                    severity=ValidationSeverity.ERROR,
                    message=(
                        f"Circular dependency detected involving tasks: {cycle_text}"
                    ),
                    line=_find_dependency_line(node, cycle_path, dependencies),
                    context={"cycle": cycle_path},
                )
            )
            return

        if node in visited:
            return

        visited.add(node)
        stack.add(node)
        path.append(node)
        for neighbor, _line in adjacency.get(node, []):
            dfs(neighbor)
        path.pop()
        stack.remove(node)

    for node in adjacency:
        if node not in visited:
            dfs(node)


def _find_dependency_line(
    node: int,
    cycle_path: list[int],
    dependencies: list[Dependency],
) -> int | None:
    """Find a line number for a dependency within a cycle."""
    if len(cycle_path) < 2:
        return None
    pairs = list(zip(cycle_path[:-1], cycle_path[1:], strict=False))
    for src, dest in pairs:
        for dep in dependencies:
            if dep.task_uid == src and dep.predecessor_task_uid == dest:
                return dep.line_number
    for dep in dependencies:
        if dep.task_uid == node:
            return dep.line_number
    return None


def _validate_task_dates(tasks: list[Task], issues: list[ValidationIssue]) -> None:
    """Validate task date rules (VAL-002 to VAL-004)."""
    for task in tasks:
        if task.is_milestone and (
            task.planned_start_date is None or task.planned_finish_date is None
        ):
            issues.append(
                ValidationIssue(
                    id="VAL-002",
                    severity=ValidationSeverity.ERROR,
                    message=(f"Milestone '#{task.uid} - {task.name}' has no date"),
                    line=task.line_number,
                    context={"task_id": task.uid},
                )
            )

        if task.planned_start_date and task.planned_finish_date:
            if task.planned_finish_date < task.planned_start_date:
                issues.append(
                    ValidationIssue(
                        id="VAL-003",
                        severity=ValidationSeverity.ERROR,
                        message=(
                            f"Task #{task.uid} end date ({task.planned_finish_date}) "
                            f"< start date ({task.planned_start_date})"
                        ),
                        line=task.line_number,
                        context={"task_id": task.uid},
                    )
                )

        if task.planned_start_date_raw and task.planned_start_date is None:
            issues.append(
                ValidationIssue(
                    id="VAL-004",
                    severity=ValidationSeverity.ERROR,
                    message=(
                        "Invalid date format "
                        f"'{task.planned_start_date_raw}' for task #{task.uid}. "
                        "Expected ISO 8601: YYYY-MM-DD"
                    ),
                    line=task.line_number,
                    context={"task_id": task.uid},
                )
            )

        if task.planned_finish_date_raw and task.planned_finish_date is None:
            issues.append(
                ValidationIssue(
                    id="VAL-004",
                    severity=ValidationSeverity.ERROR,
                    message=(
                        "Invalid date format "
                        f"'{task.planned_finish_date_raw}' for task #{task.uid}. "
                        "Expected ISO 8601: YYYY-MM-DD"
                    ),
                    line=task.line_number,
                    context={"task_id": task.uid},
                )
            )


def _validate_references(
    dependencies: list[Dependency],
    assignments: list[Assignment],
    task_uids: set[int],
    resource_uids: set[int],
    issues: list[ValidationIssue],
) -> None:
    """Validate references (VAL-005 and VAL-006)."""
    for dep in dependencies:
        if dep.predecessor_task_uid not in task_uids:
            issues.append(
                ValidationIssue(
                    id="VAL-005",
                    severity=ValidationSeverity.ERROR,
                    message=(
                        f"Task #{dep.task_uid} references non-existent "
                        f"predecessor #{dep.predecessor_task_uid}"
                    ),
                    line=dep.line_number,
                    context={
                        "task_id": dep.task_uid,
                        "predecessor_id": dep.predecessor_task_uid,
                    },
                )
            )

    for assignment in assignments:
        if assignment.resource_uid not in resource_uids:
            issues.append(
                ValidationIssue(
                    id="VAL-006",
                    severity=ValidationSeverity.ERROR,
                    message=(
                        "Assignment references non-existent resource "
                        f"#{assignment.resource_uid}"
                    ),
                    line=getattr(assignment, "line_number", None),
                    context={"resource_id": assignment.resource_uid},
                )
            )


def _validate_version_conflict(
    data: MSProjectData,
    api_project: dict[str, Any] | None,
    issues: list[ValidationIssue],
) -> None:
    """Validate MS Project version conflicts (VAL-007)."""
    if api_project is None:
        return

    api_version = api_project.get("ms_project_save_version")
    xml_version = data.project.ms_project_save_version

    if api_version is None:
        issues.append(
            ValidationIssue(
                id="VAL-007",
                severity=ValidationSeverity.WARNING,
                message=(
                    "Version conflict detection unavailable: "
                    "ms_project_save_version missing in API response."
                ),
                line=data.project.line_number,
                context={},
            )
        )
        return

    if xml_version is None:
        issues.append(
            ValidationIssue(
                id="VAL-007",
                severity=ValidationSeverity.WARNING,
                message=(
                    "Version conflict detection unavailable: "
                    "SaveVersion missing in XML."
                ),
                line=data.project.line_number,
                context={},
            )
        )
        return

    if api_version != xml_version:
        issues.append(
            ValidationIssue(
                id="VAL-007",
                severity=ValidationSeverity.ERROR,
                message=(
                    "Version conflict detected. XML version: "
                    f"{xml_version}, Database version: {api_version}. "
                    "Project modified after export. Re-export before import."
                ),
                line=data.project.line_number,
                context={
                    "xml_version": xml_version,
                    "api_version": api_version,
                },
            )
        )


def validate_for_initial_import(data: MSProjectData) -> None:
    """Validate MS Project data for initial import.

    Args:
        data: Parsed MS Project data

    Raises:
        ValidationError: If validation fails
    """
    is_valid, errors = DataValidator.validate_msproject_data(data)

    if not is_valid:
        raise ValidationError(
            f"Initial import validation failed with {len(errors)} errors",
            errors=[{"error": err} for err in errors],
        )


def validate_for_sync_import(
    data: MSProjectData, existing_milestones: list[dict[str, str]]
) -> None:
    """Validate MS Project data for sync/reimport.

    Args:
        data: Parsed MS Project data
        existing_milestones: Milestones from wfp-poc API

    Raises:
        ValidationError: If validation fails
    """
    # First validate data integrity
    is_valid, errors = DataValidator.validate_msproject_data(data)

    if not is_valid:
        raise ValidationError(
            f"Sync import data validation failed with {len(errors)} errors",
            errors=[{"error": err} for err in errors],
        )

    # Then validate milestone consistency
    is_valid, milestone_errors = MilestoneValidator.validate_milestone_consistency(
        data.tasks, existing_milestones
    )

    if not is_valid:
        raise ValidationError(
            f"Milestone validation failed: {', '.join(milestone_errors)}",
            errors=[{"error": err} for err in milestone_errors],
        )
