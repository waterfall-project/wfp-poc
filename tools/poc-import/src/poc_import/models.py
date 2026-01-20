# Copyright (c) 2026 Waterfall Project
# SPDX-License-Identifier: Commercial

"""Data models for poc-import."""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ImportMode(str, Enum):
    """Import mode."""

    INITIAL = "initial"
    SYNC = "sync"


class ResourceType(str, Enum):
    """Resource type mapping from MS Project."""

    LABOR = "labor"  # MS Project Type=1
    MATERIAL = "material"  # MS Project Type=0
    COST = "cost"  # MS Project Type=2


class DependencyType(str, Enum):
    """Task dependency type."""

    FS = "FS"  # Finish-to-Start (MS Project Type=1)
    SS = "SS"  # Start-to-Start (MS Project Type=0)
    FF = "FF"  # Finish-to-Finish (MS Project Type=2)
    SF = "SF"  # Start-to-Finish (MS Project Type=3)


class ProjectMetadata(BaseModel):
    """MS Project metadata."""

    name: str
    title: str | None = None
    start_date: datetime
    finish_date: datetime
    guid: str | None = None
    ms_project_save_version: int | None = None
    line_number: int | None = None


class TaskPredecessor(BaseModel):
    """Task predecessor relationship."""

    predecessor_task_uid: int
    type: DependencyType = DependencyType.FS
    lag: int = 0  # Lag in minutes
    line_number: int | None = None


class Task(BaseModel):
    """MS Project task."""

    uid: int
    guid: str | None = None
    name: str
    wbs_code: str | None = None
    is_summary: bool = False
    is_milestone: bool = False
    planned_start_date: datetime | None = None
    planned_finish_date: datetime | None = None
    planned_start_date_raw: str | None = None
    planned_finish_date_raw: str | None = None
    duration_hours: float | None = None
    budget: float | None = None
    percent_complete: float = 0
    is_critical: bool = False
    predecessors: list[TaskPredecessor] = Field(default_factory=list)
    line_number: int | None = None
    raw_fields: dict[str, Any] = Field(default_factory=dict)


class Dependency(BaseModel):
    """Task dependency derived from predecessor links."""

    task_uid: int
    predecessor_task_uid: int
    type: DependencyType = DependencyType.FS
    lag: int = 0
    line_number: int | None = None
    raw_fields: dict[str, Any] = Field(default_factory=dict)


class Resource(BaseModel):
    """MS Project resource."""

    uid: int
    guid: str | None = None
    name: str
    type: ResourceType
    standard_rate: float | None = None
    max_units: float = 1.0
    line_number: int | None = None
    raw_fields: dict[str, Any] = Field(default_factory=dict)


class Assignment(BaseModel):
    """Task-resource assignment."""

    task_uid: int
    resource_uid: int
    work_hours: float = 0
    units: float = 1.0
    line_number: int | None = None
    raw_fields: dict[str, Any] = Field(default_factory=dict)


class MSProjectData(BaseModel):
    """Complete MS Project parsed data."""

    project: ProjectMetadata
    tasks: list[Task]
    dependencies: list[Dependency] = Field(default_factory=list)
    resources: list[Resource]
    assignments: list[Assignment]


class ImportReport(BaseModel):
    """Import operation report."""

    correlation_id: str
    mode: ImportMode
    success: bool
    created_count: int = 0
    updated_count: int = 0
    failed_count: int = 0
    validation_errors: list[str] = Field(default_factory=list)
    api_errors: list[str] = Field(default_factory=list)
    project_id: UUID | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
