# Copyright (c) 2026 Waterfall Project
# SPDX-License-Identifier: Commercial

"""Data models for poc-import."""

from datetime import datetime
from enum import Enum
from typing import Optional
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
    title: Optional[str] = None
    start_date: datetime
    finish_date: datetime
    guid: Optional[str] = None


class TaskPredecessor(BaseModel):
    """Task predecessor relationship."""

    predecessor_task_uid: int
    type: DependencyType = DependencyType.FS
    lag: int = 0  # Lag in minutes


class Task(BaseModel):
    """MS Project task."""

    uid: int
    guid: Optional[str] = None
    name: str
    wbs_code: Optional[str] = None
    is_summary: bool = False
    is_milestone: bool = False
    planned_start_date: Optional[datetime] = None
    planned_finish_date: Optional[datetime] = None
    duration_hours: Optional[float] = None
    budget: Optional[float] = None
    percent_complete: float = 0
    is_critical: bool = False
    predecessors: list[TaskPredecessor] = Field(default_factory=list)


class Resource(BaseModel):
    """MS Project resource."""

    uid: int
    guid: Optional[str] = None
    name: str
    type: ResourceType
    standard_rate: Optional[float] = None
    max_units: float = 1.0


class Assignment(BaseModel):
    """Task-resource assignment."""

    task_uid: int
    resource_uid: int
    work_hours: float = 0
    units: float = 1.0


class MSProjectData(BaseModel):
    """Complete MS Project parsed data."""

    project: ProjectMetadata
    tasks: list[Task]
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
    project_id: Optional[UUID] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
