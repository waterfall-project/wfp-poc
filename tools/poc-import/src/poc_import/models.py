# Copyright (c) 2026 Waterfall Project
# SPDX-License-Identifier: Commercial

"""Data models for poc-import."""

from datetime import date, datetime
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


class ExcelFileType(str, Enum):
    """Excel file type."""

    EXPENSES = "expenses"
    RAE = "rae"


class ExpenseRow(BaseModel):
    """Single expense row parsed from Excel."""

    row_number: int
    purchase_document: str | None = None
    fiscal_year: int | None = None
    period: int | None = None
    otp_element: str | None = None
    resource_name: str | None = None
    vendor_name: str | None = None
    accounting_nature: str | None = None
    accounting_nature_label: str | None = None
    reference_number: str | None = None
    amount: float | None = None
    expense_date: date | None = None
    description: str | None = None
    origin_group: str | None = None
    purchase_reference: str | None = None


class ExpenseEntry(BaseModel):
    """Grouped expense entry ready for listing or import."""

    entry_id: int
    reference_number: str | None
    expense_date: date | None
    amount: float
    category: str
    description: str | None
    purchase_document: str | None
    fiscal_year: int | None
    period: int | None
    otp_element: str | None
    resource_name: str | None
    vendor_name: str | None
    accounting_nature: str | None
    accounting_nature_label: str | None
    origin_group: str | None
    purchase_reference: str | None
    row_numbers: list[int] = Field(default_factory=list)
    grouped_rows: int = 1


class ExcelExpensesData(BaseModel):
    """Parsed Excel expenses data with grouping summary."""

    file_path: str
    sheet_name: str
    rows: list[ExpenseRow]
    entries: list[ExpenseEntry]
    total_rows: int
    total_amount: float
    period_start: date | None
    period_end: date | None
    unique_references: int
    grouped_count: int
    missing_references: int
    purchase_rows: int
    purchase_amount: float
    time_rows: int
    time_amount: float


class RAETaskBreakdown(BaseModel):
    """RAE task breakdown entry."""

    task_name: str
    amount: float
    comment: str | None = None


class RAEEntry(BaseModel):
    """RAE entry parsed from Excel."""

    entry_id: int
    milestone_name: str
    remaining_amount: float | None
    forecast_date: date | None
    task_breakdown: list[RAETaskBreakdown] = Field(default_factory=list)
    breakdown_sum: float = 0.0
    row_number: int | None = None
    parse_error: str | None = None


class ExcelRAEData(BaseModel):
    """Parsed Excel RAE data."""

    file_path: str
    sheet_name: str
    entries: list[RAEEntry]
    total_rows: int
    total_remaining: float
    milestone_count: int
    forecast_period: str | None
