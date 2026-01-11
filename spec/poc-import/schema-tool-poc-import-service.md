---
title: poc-import - MS Project and Excel Import Service Specification
version: 1.0
date_created: 2026-01-10
last_updated: 2026-01-10
owner: Waterfall Team
tags: [tool, poc-import, ms-project, excel, etl, validation]
---

# poc-import - MS Project and Excel Import Service Specification

## 1. Purpose & Scope

### Purpose

`poc-import` is a Flask-based ETL (Extract, Transform, Load) service that imports project data from MS Project XML files and Excel spreadsheets into the wfp-poc REST API. It provides both a command-line interface (CLI) for batch operations and REST API endpoints for programmatic access, serving as the primary data ingestion tool for the Waterfall project management ecosystem.

### Scope

**In Scope:**
- Parse MS Project 2010+ XML files (structure, tasks, milestones, resources, assignments)
- Parse Excel files for expenses and RAE (Reste À Engager) data
- Validate data integrity and business rules before import
- Transform source data into wfp-poc API payloads
- Orchestrate wfp-poc API calls with error handling and retry logic
- Support initial import and incremental reimport workflows
- Provide CLI interface for manual/scripted imports
- Provide REST API endpoints for programmatic imports (Phase 2 / future)
- Support MCP (Model Context Protocol) server for AI integration (Phase 2 / future)
- Provide detailed validation reports and import summaries

**Out of Scope:**
- MS Project binary .mpp file parsing (convert to XML first using MS Project or Project Server)
- Real-time synchronization (batch import only)
- Data export (handled by poc-export service)
- Web UI for file uploads (CLI and API only)
- Direct database access (API-only communication with wfp-poc)

### Intended Audience

- Project Managers importing planning data
- Financial Controllers importing expense data
- System Administrators automating import workflows
- Developers integrating poc-import into CI/CD pipelines

### Assumptions

- MS Project files exported to XML format before import
- Excel files follow defined column schemas (see Section 4)
- wfp-poc API is accessible and responsive
- User has valid JWT token with appropriate Guardian permissions
- Network connectivity between poc-import and wfp-poc

## 2. Definitions

| Term | Definition |
|------|------------|
| **Initial Import** | First-time import creating all entities (project, tasks, milestones, resources) |
| **Reimport** | Subsequent import updating planning data while preserving tracking data |
| **Structural Validation** | Verification that milestone count and names remain unchanged during reimport |
| **Planning Data** | MS Project-sourced data: WBS, task dates, durations, dependencies, resource assignments |
| **Tracking Data** | wfp-poc-sourced data preserved during reimport: expenses, actual dates, progress, RAE |
| **ms_project_guid** | MS Project Task GUID (UUID) - stable identifier for cross-system reconciliation when supported by the target API |
| **ms_project_uid** | MS Project Task UID (integer) - reconciliation key used by some wfp-poc sync operations; can change if tasks are renumbered/reordered in MS Project |
| **Upsert** | Operation that creates new record if reconciliation key not found, updates existing if found |
| **Bulk Import** | Single API request containing multiple entities (e.g., 100 tasks) |
| **Batch Processing** | Splitting large datasets into multiple bulk imports (e.g., 1000 tasks → 10 batches of 100) |
| **Dry Run** | Validation-only mode that reports errors without making API calls |
| **Correlation ID** | UUID tracking a request across services for debugging |

## 3. Requirements, Constraints & Guidelines

### Functional Requirements (REQ-xxx)

#### Core Parsing

- **REQ-001**: poc-import SHALL parse MS Project 2010+ XML files using the Microsoft Project XML schema
- **REQ-002**: poc-import SHALL parse Excel files in .xlsx format (OpenXML)
- **REQ-003**: poc-import SHALL extract Project metadata (name, dates, GUIDs) from MS Project XML
- **REQ-004**: poc-import SHALL extract Tasks with all attributes (name, dates, duration, WBS, GUIDs, UIDs)
- **REQ-005**: poc-import SHALL extract Task dependencies (PredecessorLink elements)
- **REQ-006**: poc-import SHALL extract Resources with attributes (name, type, rates)
- **REQ-007**: poc-import SHALL extract Assignments (Task-Resource links with work hours)
- **REQ-008**: poc-import SHALL identify Milestones (tasks with duration=0 or IsMilestone=1)

#### Validation

- **REQ-009**: poc-import SHOULD validate MS Project XML structure before processing (well-formed XML, required elements present). Full XSD validation MAY be implemented as a Phase 2 enhancement.
- **REQ-010**: poc-import SHALL validate Excel files have required columns (see Section 4)
- **REQ-011**: poc-import SHALL validate milestone structure consistency on reimport (count + names)
- **REQ-012**: poc-import SHALL reject reimport if milestone count changed from wfp-poc
- **REQ-013**: poc-import SHALL reject reimport if any milestone name changed from wfp-poc
- **REQ-014**: poc-import SHALL validate expense milestone_name matches existing milestones
- **REQ-015**: poc-import SHALL validate RAE milestone_name matches existing milestones
- **REQ-016**: poc-import SHALL validate RAE task breakdown sums equal milestone RAE amount
- **REQ-017**: poc-import SHALL validate all dates are ISO 8601 format
- **REQ-018**: poc-import SHALL validate all amounts are non-negative decimals
- **REQ-019**: poc-import SHALL provide validation report with line numbers and error descriptions

#### Transformation

- **REQ-020**: poc-import SHALL map MS Project Task GUID to ms_project_guid (stable identifier for reconciliation)
- **REQ-021**: poc-import SHALL preserve MS Project Task UID as ms_project_uid (reconciliation key + display)
- **REQ-022**: poc-import SHALL map MS Project PredecessorLink to wfp-poc task predecessor relationships (`predecessors` array)
  - For task sync, poc-import SHOULD send `predecessor_task_uid` (MS Project UID) as defined by wfp-poc.
- **REQ-023**: poc-import SHALL map MS Project Resource Type to wfp-poc enum
  - MS Project: 1=Labor, 0=Material, 2=Cost
  - wfp-poc: labor, material, cost
- **REQ-024**: poc-import SHALL map Excel milestone_name to milestone_id via wfp-poc `GET /v0/projects/{project_id}/milestones`
- **REQ-025**: poc-import SHALL calculate milestone budget_weight from task budget distribution
- **REQ-026**: poc-import SHALL convert MS Project dates to ISO 8601 UTC timestamps
- **REQ-027**: poc-import SHALL map Excel expense category to wfp-poc enum (labor, procurement, subcontracting, overhead)

#### API Orchestration

- **REQ-028**: poc-import SHALL authenticate API requests using JWT token (from config or CLI arg)
- **REQ-029**: poc-import SHALL include correlation_id in all API requests for tracing
- **REQ-030**: poc-import SHALL use POST for initial import (create entities)
- **REQ-031**: poc-import SHALL use `PUT /v0/projects/{project_id}/tasks/sync` for reimport.
  - For this POC, poc-import SHOULD follow the reconciliation behavior defined by wfp-poc (currently: `ms_project_uid` as reconciliation key), while still sending `ms_project_guid` when available.
- **REQ-032**: poc-import SHALL use `POST /v0/projects/{project_id}/expenses/bulk` for batch expense import
- **REQ-033**: poc-import SHALL use `POST /v0/milestones/{milestone_id}/rae` for each milestone RAE update
- **REQ-034**: poc-import SHALL implement retry logic for transient API errors (3 retries with exponential backoff)
- **REQ-035**: poc-import SHALL abort import on validation errors (4xx) without retry
- **REQ-036**: poc-import SHOULD provide POC-grade partial failure handling.
  - MVP: emit a resumable import report (per batch) including correlation_id and created/updated/failed counts.
  - Compensation/cleanup actions MUST be explicit and best-effort (no implicit rollback assumptions).

#### Workflows

- **REQ-037**: poc-import SHALL support `--mode=initial` for first-time import
- **REQ-038**: poc-import SHALL support `--mode=sync` for reimport with validation
- **REQ-039**: poc-import SHALL support `--dry-run` flag for validation without API calls
- **REQ-040**: poc-import SHALL support `--project-id` for reimport to existing project
- **REQ-041**: poc-import SHALL generate import summary report (created/updated/failed counts)
- **REQ-042**: poc-import SHALL log all operations with timestamps and correlation IDs

### Security Requirements (SEC-xxx)

- **SEC-001**: poc-import SHALL require valid JWT token for all wfp-poc API requests
- **SEC-002**: poc-import SHALL validate JWT token before starting import (401 → abort immediately)
- **SEC-003**: poc-import SHALL use HTTPS for all API communication in production
- **SEC-004**: poc-import SHALL NOT store JWT tokens in log files
- **SEC-005**: poc-import SHALL sanitize input data to prevent injection attacks
- **SEC-006**: poc-import SHALL validate file paths to prevent directory traversal attacks
- **SEC-007**: poc-import SHALL check Guardian permissions via wfp-poc (403 → abort with permission error)

### Performance Requirements (PERF-xxx)

- **PERF-001**: poc-import SHOULD process MS Project files up to 5000 tasks within 5 minutes in a typical POC environment.
  - Timing guidance: measure parsing/validation/client-side batching separately from external API latency.
- **PERF-002**: poc-import SHALL use bulk API calls for tasks (max 100 per request)
- **PERF-003**: poc-import SHALL use bulk API calls for expenses (max 200 per request)
- **PERF-004**: poc-import SHOULD process Excel files up to 10,000 rows within 2 minutes in a typical POC environment
- **PERF-005**: poc-import SHALL implement batch processing for large datasets (split into chunks)
- **PERF-006**: poc-import SHALL display progress indicator for operations > 30 seconds

### Constraints (CON-xxx)

- **CON-001**: poc-import SHALL only support MS Project 2010+ XML format (not 2007 or earlier)
- **CON-002**: poc-import SHALL only support .xlsx Excel format (not .xls or .csv)
- **CON-003**: poc-import SHALL require Python 3.9+ runtime environment
- **CON-004**: poc-import SHALL NOT exceed wfp-poc API rate limits (429 → exponential backoff)
- **CON-005**: poc-import SHALL NOT modify source files (read-only operations)
- **CON-006**: poc-import SHALL limit log file size (rotate at 50MB)

### Guidelines (GUD-xxx)

- **GUD-001**: Use lxml library for MS Project XML parsing (performance + schema validation)
- **GUD-002**: Use openpyxl or pandas for Excel file parsing
- **GUD-003**: Implement idempotent operations (re-running import with same data = same result)
- **GUD-004**: Provide verbose logging mode (--verbose) for debugging
- **GUD-005**: Use structured logging (JSON format) for production deployments
- **GUD-006**: Generate correlation ID once per import session, use for all API calls
- **GUD-007**: Fail fast on critical errors (invalid file format, authentication failure)
- **GUD-008**: Provide actionable error messages with resolution steps

## 4. Interfaces & Data Contracts

### 4.1. Command-Line Interface

#### Import MS Project XML (Initial Import)

```bash
poc-import msproject <file.xml> \
  --mode=initial \
  --token=<jwt_token> \
  --api-url=https://wfp-poc.example.com \
  [--company-id=<uuid>] \
  [--dry-run] \
  [--verbose] \
  [--output-report=report.json]
```

**Parameters:**
- `<file.xml>`: Path to MS Project XML file (required)
- `--mode`: Import mode: `initial` or `sync` (required)
- `--token`: JWT authentication token (required, can use env var WFP_JWT_TOKEN)
- `--api-url`: wfp-poc API base URL (required, can use env var WFP_API_URL)
- `--company-id`: Company UUID for multi-tenant isolation (optional; preferred source is JWT claims as enforced by wfp-poc)
- `--project-id`: Existing project UUID (required for sync mode)
- `--dry-run`: Validate only, do not call API (optional)
- `--verbose`: Enable detailed logging (optional)
- `--output-report`: Save import report to JSON file (optional)

**Exit Codes:**
- `0`: Success (all entities imported/updated)
- `1`: Validation errors (invalid file format, business rule violations)
- `2`: API errors (4xx client errors, permission denied)
- `3`: System errors (network failure, file not found)

#### Import MS Project XML (Reimport/Sync)

```bash
poc-import msproject <file.xml> \
  --mode=sync \
  --project-id=<uuid> \
  --token=<jwt_token> \
  --api-url=https://wfp-poc.example.com \
  [--dry-run] \
  [--verbose]
```

#### Import Expenses from Excel

```bash
poc-import expenses <file.xlsx> \
  --project-id=<uuid> \
  --token=<jwt_token> \
  --api-url=https://wfp-poc.example.com \
  [--dry-run] \
  [--verbose] \
  [--output-report=report.json]
```

**Excel Format (expenses):**

| Column | Type | Required | Description | Example |
|--------|------|----------|-------------|---------|
| expense_date | Date | Yes | Date of expense (YYYY-MM-DD) | 2026-03-31 |
| description | String | Yes | Expense description | Q1 Labor Costs |
| amount | Decimal | Yes | Expense amount (>= 0) | 150000.00 |
| category | Enum | Yes | labor, procurement, subcontracting, overhead | labor |
| milestone_name | String | Yes | Milestone allocation (must match wfp-poc) | Phase 1 Complete |
| invoice_number | String | No | Invoice reference | INV-2026-0123 |
| payment_reference | String | No | Payment tracking reference | PAY-2026-0045 |

**Validation Rules:**
- Date format: ISO 8601 (YYYY-MM-DD) or Excel date serial
- Amount: Non-negative decimal, max 15 digits, 2 decimal places
- Category: Case-insensitive match to enum values (labor, procurement, subcontracting, overhead)
- milestone_name: Must exist in project (normalized match: trim, collapse internal whitespace, case-insensitive)
- Duplicate detection: Same date + description + amount → skip or update (configurable)

#### Import RAE from Excel

```bash
poc-import rae <file.xlsx> \
  --project-id=<uuid> \
  --token=<jwt_token> \
  --api-url=https://wfp-poc.example.com \
  [--dry-run] \
  [--verbose] \
  [--output-report=report.json]
```

**Excel Format (RAE):**

| Column | Type | Required | Description | Example |
|--------|------|----------|-------------|---------|
| date | Date | Yes | RAE measurement date (YYYY-MM-DD) | 2026-06-30 |
| milestone_name | String | Yes | Milestone name (must match wfp-poc) | Phase 2 Complete |
| amount | Decimal | Yes | Estimated remaining cost (>= 0) | 75000.00 |
| comment | String | No | Explanation for estimate | Backend delay adds 15K |
| task_name | String | No* | Task breakdown (multiple rows per milestone) | Backend API Development |
| task_status | Enum | No* | not_started, in_progress, completed | in_progress |
| task_budget | Decimal | No* | Task budget from MS Project | 100000.00 |
| task_estimate | Decimal | No* | PM estimate to complete this task | 65000.00 |

*Required if providing task-level breakdown

**Validation Rules:**
- Date format: ISO 8601 or Excel date serial
- milestone_name: Must exist in project (normalized match: trim, collapse internal whitespace, case-insensitive)
- Amount: Non-negative decimal
- If task breakdown provided: Σ(task_estimate) MUST equal milestone amount
- task_status: Enum validation (not_started, in_progress, completed)
- One RAE record per milestone per date (upsert if duplicate)

### 4.2. MS Project XML Input Schema

#### Project Element

```xml
<Project>
  <Name>Project Baguera Phase 1</Name>
  <Title>Infrastructure Modernization</Title>
  <StartDate>2026-01-15T08:00:00</StartDate>
  <FinishDate>2027-12-31T17:00:00</FinishDate>
  <GUID>42DA3870-5DF4-EF11-9360-F4EE08B24B68</GUID>
  <Tasks>...</Tasks>
  <Resources>...</Resources>
  <Assignments>...</Assignments>
</Project>
```

**Mapping to wfp-poc API:**
```json
POST /v0/projects
{
  "company_id": "<from JWT claims (preferred); or from CLI arg in testing/mocked mode>",
  "name": "<Name>",
  "title": "<Title>",
  "start_date": "<StartDate ISO 8601>",
  "finish_date": "<FinishDate ISO 8601>",
  "ms_project_project_guid": "<GUID>",
  "status": "planning"
}
```

#### Task Element

```xml
<Task>
  <UID>1</UID>
  <GUID>A1B2C3D4-E5F6-4A5B-8C9D-0E1F2A3B4C5D</GUID>
  <ID>1</ID>
  <Name>Requirements Analysis</Name>
  <WBS>1.1.1</WBS>
  <OutlineLevel>3</OutlineLevel>
  <Start>2026-01-15T08:00:00</Start>
  <Finish>2026-02-15T17:00:00</Finish>
  <Duration>PT240H0M0S</Duration>
  <PercentComplete>0</PercentComplete>
  <Critical>1</Critical>
  <Milestone>0</Milestone>
  <Summary>0</Summary>
  <Cost>50000</Cost>
  <PredecessorLink>
    <PredecessorUID>0</PredecessorUID>
    <Type>1</Type>  <!-- FS=1, SS=0, FF=2, SF=3 -->
    <LinkLag>0</LinkLag>
  </PredecessorLink>
</Task>
```

**Mapping to wfp-poc API (Initial Import):**
```json
POST /v0/projects/{project_id}/tasks/bulk
{
  "tasks": [
    {
      "ms_project_guid": "<GUID>",
      "ms_project_uid": "<UID>",
      "name": "<Name>",
      "wbs_code": "<WBS>",
      "is_summary": false,
      "planned_start_date": "<Start ISO 8601>",
      "planned_finish_date": "<Finish ISO 8601>",
      "duration_hours": 240,
      "budget": 50000,
      "percent_complete": 0,
      "is_critical": true,
      "type": "task",
      "predecessors": []
    }
  ]
}
```

**Mapping to wfp-poc API (Reimport/Sync):**
```json
PUT /v0/projects/{project_id}/tasks/sync
{
  "tasks": [
    {
      "ms_project_guid": "<GUID>",
      "ms_project_uid": "<UID>",
      "name": "<Name>",
      "planned_start_date": "<Start ISO 8601>",
      "planned_finish_date": "<Finish ISO 8601>",
      "duration_hours": 240,
      "predecessors": [
        {"predecessor_task_uid": "<PredecessorUID>", "type": "FS", "lag": 0}
      ]
    }
  ]
}
```

#### Resource Element

```xml
<Resource>
  <UID>1</UID>
  <GUID>B2C3D4E5-F6A7-4B8C-9D0E-1F2A3B4C5D6E</GUID>
  <Name>John Doe</Name>
  <Type>1</Type>  <!-- 1=Labor, 0=Material, 2=Cost -->
  <StandardRate>750</StandardRate>  <!-- Per hour -->
  <MaxUnits>1.0</MaxUnits>
  <EmailAddress>john.doe@example.com</EmailAddress>
</Resource>
```

**Mapping to wfp-poc API:**
```json
POST /v0/projects/{project_id}/resources/bulk
{
  "resources": [
    {
      "ms_project_uid": 1,
      "name": "John Doe",
      "type": "labor",
      "standard_rate": 750.00,
      "max_units": 1.0,
      "email": "john.doe@example.com"
    }
  ]
}
```

#### Assignment Element

```xml
<Assignment>
  <UID>1</UID>
  <TaskUID>10</TaskUID>
  <ResourceUID>5</ResourceUID>
  <Work>PT80H0M0S</Work>
  <Start>2026-01-15T08:00:00</Start>
  <Finish>2026-02-15T17:00:00</Finish>
  <Units>1.0</Units>  <!-- 100% allocation -->
</Assignment>
```

**Mapping to wfp-poc API:**
```json
POST /v0/projects/{project_id}/assignments/bulk
{
  "assignments": [
    {
      "task_id": "<resolved from TaskUID>",
      "resource_id": "<resolved from ResourceUID>",
      "work_hours": 80.0,
      "allocation_percent": 100.0,
      "start_date": "2026-01-15T08:00:00Z",
      "finish_date": "2026-02-15T17:00:00Z"
    }
  ]
}
```

### 4.3. Output - Import Report

**Success Report (JSON):**
```json
{
  "status": "success",
  "correlation_id": "a1b2c3d4-e5f6-4a5b-8c9d-0e1f2a3b4c5d",
  "import_type": "msproject_initial",
  "source_file": "/path/to/project.xml",
  "timestamp": "2026-01-10T14:30:00Z",
  "duration_seconds": 45.2,
  "project": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "Project Baguera Phase 1"
  },
  "summary": {
    "tasks": {"created": 150, "updated": 0, "failed": 0},
    "milestones": {"created": 5, "updated": 0, "failed": 0},
    "resources": {"created": 25, "updated": 0, "failed": 0},
    "assignments": {"created": 300, "updated": 0, "failed": 0}
  },
  "warnings": [
    "Task 'Testing Phase' has no predecessors (may be intentional)",
    "Resource 'Contractor A' has no email address"
  ]
}
```

**Validation Error Report (JSON):**
```json
{
  "status": "validation_failed",
  "correlation_id": "b2c3d4e5-f6a7-4b8c-9d0e-1f2a3b4c5d6e",
  "import_type": "msproject_sync",
  "source_file": "/path/to/project_v2.xml",
  "timestamp": "2026-01-10T15:45:00Z",
  "errors": [
    {
      "code": "MILESTONE_COUNT_MISMATCH",
      "severity": "error",
      "message": "Milestone count changed: expected 5, found 6",
      "details": {
        "expected_count": 5,
        "actual_count": 6,
        "new_milestone": "Phase 2.5 Testing"
      },
      "resolution": "Remove milestone 'Phase 2.5 Testing' from MS Project or add it manually in wfp-poc first"
    },
    {
      "code": "TASK_GUID_MISSING",
      "severity": "warning",
      "message": "Task 'New Feature' has no GUID (new task added in MS Project)",
      "details": {
        "task_name": "New Feature",
        "task_uid": 156
      },
      "resolution": "New tasks will be created (this is expected for added tasks)"
    }
  ],
  "summary": {
    "total_errors": 1,
    "total_warnings": 1,
    "blocking_errors": 1
  }
}
```

**Expense Import Report:**
```json
{
  "status": "success",
  "correlation_id": "c3d4e5f6-a7b8-4c9d-0e1f-2a3b4c5d6e7f",
  "import_type": "expenses",
  "source_file": "/path/to/expenses_q2.xlsx",
  "timestamp": "2026-06-30T18:00:00Z",
  "duration_seconds": 2.5,
  "project": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "Project Baguera Phase 1"
  },
  "summary": {
    "expenses": {
      "total_rows": 125,
      "created": 120,
      "updated": 0,
      "skipped": 5,
      "failed": 0
    },
    "total_amount": 485000.00,
    "milestones": [
      {
        "milestone_id": "d4e5f6a7-b8c9-4d5e-1f2a-3b4c5d6e7f8a",
        "milestone_name": "Phase 1 Complete",
        "expenses_count": 45,
        "total_amount": 165000.00
      },
      {
        "milestone_id": "e5f6a7b8-c9d0-4e5f-2a3b-4c5d6e7f8a9b",
        "milestone_name": "Phase 2 Complete",
        "expenses_count": 75,
        "total_amount": 320000.00
      }
    ]
  },
  "warnings": [
    "Row 15: Duplicate expense skipped (2026-04-15, 'Server License', 5000.00)",
    "Row 23: invoice_number missing for expense > $10,000"
  ]
}
```

**RAE Import Report:**
```json
{
  "status": "success",
  "correlation_id": "d4e5f6a7-b8c9-4d0e-1f2a-3b4c5d6e7f8a",
  "import_type": "rae",
  "source_file": "/path/to/rae_june_2026.xlsx",
  "timestamp": "2026-06-30T18:30:00Z",
  "duration_seconds": 1.8,
  "project": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "Project Baguera Phase 1"
  },
  "summary": {
    "milestones": {
      "total": 5,
      "updated": 5,
      "failed": 0
    },
    "total_rae": 235000.00,
    "milestones_detail": [
      {
        "milestone_id": "c3d4e5f6-a7b8-4c9d-0e1f-2a3b4c5d6e7f",
        "milestone_name": "Phase 1 Complete",
        "rae": 0,
        "task_breakdown": 0
      },
      {
        "milestone_id": "d4e5f6a7-b8c9-4d5e-1f2a-3b4c5d6e7f8a",
        "milestone_name": "Phase 2 Complete",
        "rae": 85000.00,
        "task_breakdown": 3
      },
      {
        "milestone_id": "e5f6a7b8-c9d0-4e5f-2a3b-4c5d6e7f8a9b",
        "milestone_name": "Phase 3 Complete",
        "rae": 150000.00,
        "task_breakdown": 1
      }
    ]
  },
  "warnings": []
}
```

## 5. Acceptance Criteria

### Initial Import

- **AC-001**: Given a valid MS Project XML file with 100 tasks, When I run `poc-import msproject file.xml --mode=initial`, Then all 100 tasks SHALL be created in wfp-poc with correct GUIDs
- **AC-002**: Given a MS Project file with milestones (duration=0), When imported, Then milestones SHALL be created as separate entities linked to milestone_tasks
- **AC-003**: Given a MS Project file with task dependencies, When imported, Then predecessor relationships SHALL be preserved using MS Project UID references (wfp-poc `predecessor_task_uid`)
- **AC-004**: Given a MS Project file with resources, When imported, Then resources SHALL be created with correct types (labor/material/cost)
- **AC-005**: Given a MS Project file with assignments, When imported, Then task-resource assignments SHALL link to correct task_id and resource_id

### Reimport/Sync

- **AC-006**: Given an existing project with 5 milestones, When I reimport MS Project with 5 milestones (same names), Then import SHALL succeed and update planning data
- **AC-007**: Given an existing project with 5 milestones, When I reimport MS Project with 6 milestones, Then import SHALL fail with MILESTONE_COUNT_MISMATCH error
- **AC-008**: Given an existing project with milestone "Phase 1", When I reimport MS Project with "Phase 1A", Then import SHALL fail with MILESTONE_NAME_MISMATCH error
- **AC-009**: Given a task with actual_start_date in wfp-poc, When I reimport with new planned_start_date, Then actual_start_date SHALL be preserved (tracking data)
- **AC-010**: Given a task with 50% progress in wfp-poc, When I reimport, Then percent_complete SHALL be preserved (tracking data)

### Expense Import

- **AC-011**: Given a valid Excel file with 50 expense rows, When I run `poc-import expenses file.xlsx`, Then all 50 expenses SHALL be created via POST /v0/projects/{project_id}/expenses/bulk
- **AC-012**: Given an expense row with milestone_name "Phase 1", When imported, Then milestone_id SHALL be resolved from wfp-poc GET /v0/projects/{project_id}/milestones API
- **AC-013**: Given an expense row with invalid milestone_name, When validated, Then SHALL fail with "Milestone not found: {name}" error
- **AC-014**: Given duplicate expense (same date + description + amount), When imported, Then SHALL skip with warning (configurable: skip or update)
- **AC-015**: Given expense with negative amount, When validated, Then SHALL fail with "Amount must be >= 0" error

### RAE Import

- **AC-016**: Given a valid RAE Excel file with 5 milestones, When imported, Then 5 POST /v0/milestones/{milestone_id}/rae API calls SHALL be made
- **AC-017**: Given a RAE row with task breakdown, When validated, Then Σ(task_estimate) SHALL equal milestone amount or fail
- **AC-018**: Given a RAE row with invalid task_status, When validated, Then SHALL fail with "Invalid status: must be not_started, in_progress, or completed"
- **AC-019**: Given duplicate RAE for same milestone + date, When imported, Then SHALL upsert (update existing record)
- **AC-020**: Given a RAE Excel file, When imported successfully, Then import report SHALL show total_rae and per-milestone breakdown

### Error Handling

- **AC-021**: Given invalid JWT token, When import starts, Then SHALL fail immediately with 401 error and clear message
- **AC-022**: Given insufficient permissions (Guardian 403), When API call made, Then SHALL abort with permission error and required operation
- **AC-023**: Given network timeout during import, When retry count < 3, Then SHALL retry with exponential backoff
- **AC-024**: Given 4xx validation error from API, When received, Then SHALL NOT retry and SHALL report error details
- **AC-025**: Given --dry-run flag, When import executed, Then NO API calls SHALL be made, only validation report generated

### Performance

- **AC-026**: Given a MS Project file with 1000 tasks, When imported, Then SHOULD complete within 3 minutes (batch processing)
- **AC-027**: Given an Excel file with 5000 expense rows, When imported, Then SHOULD use bulk API (max 200 per request) and complete within 5 minutes
- **AC-028**: Given a MS Project file with 5000 tasks, When imported, Then SHALL split into batches of 100 tasks per API call

## 6. Rationale & Context

### Why Flask Service with CLI?

**Architecture Decision: Flask Service + CLI (not pure CLI)**

Alternative approaches considered:

| Approach | Pros | Cons | Decision |
|----------|------|------|----------|
| **Pure CLI Tool** | Simple, no server overhead, easy deployment | No API for future integrations (MCP, webhooks), harder to add web UI later | ❌ Rejected |
| **Flask Service + CLI** ✅ | Consistent with wfp-poc, supports CLI + API, enables MCP/webhooks, shared parsers library | Slightly more complex initial setup | ✅ **Chosen** |
| **Separate CLI + API Services** | Maximum separation of concerns | Duplicate parser logic, more deployment complexity | ❌ Rejected |

**Chosen Architecture Benefits:**
- ✅ **Reusable Parsers**: `app/parsers/` used by both CLI and REST API
- ✅ **Consistent Stack**: Same Flask patterns as wfp-poc (resources, schemas, utils)
- ✅ **Future-Proof**: Easy to add REST endpoints for programmatic imports
- ✅ **MCP Support**: Can expose MCP server using Flask app context
- ✅ **Testing**: Leverage Flask test client for integration tests
- ✅ **Monitoring**: Standard Flask metrics, logging, error handling

**Layered Architecture:**
```
┌─────────────────────────────────────┐
│         CLI Interface               │ ← Flask Click commands
├─────────────────────────────────────┤
│      REST API (optional)            │ ← Flask-RESTful resources
├─────────────────────────────────────┤
│         Services Layer              │ ← Orchestration logic
│  • ImportService                    │
│  • WfpApiClient                     │
├─────────────────────────────────────┤
│         Parsers Layer               │ ← Pure logic (reusable)
│  • MSProjectParser                  │
│  • ExcelExpenseParser               │
│  • ExcelRAEParser                   │
│  • Validators                       │
└─────────────────────────────────────┘
```

**File Structure:**
```
poc-import/
├── app/
│   ├── __init__.py           # Flask app factory
│   ├── config.py             # Configuration classes
│   ├── cli.py                # CLI commands (flask import msproject ...)
│   ├── parsers/              # 🔧 REUSABLE PARSING LOGIC
│   │   ├── __init__.py
│   │   ├── msproject_parser.py    # MS Project XML → Python objects
│   │   ├── excel_expense_parser.py # Excel expenses → Python objects
│   │   ├── excel_rae_parser.py     # Excel RAE → Python objects
│   │   └── validators.py           # Business rule validation
│   ├── services/             # 🎯 ORCHESTRATION LOGIC
│   │   ├── __init__.py
│   │   ├── import_service.py       # High-level import workflows
│   │   └── wfp_api_client.py       # wfp-poc API wrapper
│   ├── resources/            # 🌐 REST API (future)
│   │   ├── __init__.py
│   │   └── import_resource.py
│   ├── schemas/              # Marshmallow schemas
│   │   └── import_schema.py
│   └── utils/
│       ├── logger.py
│       └── retry.py
├── tests/
│   ├── unit/
│   │   ├── test_msproject_parser.py
│   │   ├── test_excel_parser.py
│   │   └── test_validators.py
│   └── integration/
│       └── test_import_workflows.py
├── run.py                    # CLI entry point: python run.py ...
├── pyproject.toml
└── README.md
```

**CLI Usage (Flask Click commands):**
```bash
# Using Flask CLI
flask --app poc_import import msproject project.xml --mode=initial --company-id=...

# Or standalone entry point
python run.py import msproject project.xml --mode=initial --company-id=...
```

**Future REST API (when needed):**
```bash
# Start service
flask --app poc_import run --port=5001

# Import via API
curl -X POST http://localhost:5001/v0/import/msproject \
  -H "Authorization: Bearer $JWT" \
  -F "file=@project.xml" \
  -F "mode=initial" \
  -F "company_id=..."
```

### Why CLI as Primary Interface (despite Flask)?

- **Automation**: Easy integration into CI/CD pipelines and scheduled jobs
- **Simplicity**: No server needed for batch imports
- **Performance**: Direct file processing, no HTTP overhead for large files
- **Debugging**: stdout/stderr logging for troubleshooting
- **Future Growth**: Can add REST API later without rewriting parsers

### Why ms_project_guid for Reconciliation?

MS Project has 3 identifiers:
- `<UID>` (integer): Display ID, **UNSTABLE** - changes when tasks reordered or deleted
- `<GUID>` (UUID): Globally unique, **STABLE** across all operations
- `<ID>` (integer): Row number, changes frequently

Preferred approach: use GUID for reconciliation whenever the target API supports it.

Current POC constraint: wfp-poc task sync currently uses `ms_project_uid` as the reconciliation key. Therefore, poc-import MUST preserve and send `ms_project_uid` for sync, and SHOULD also send `ms_project_guid` when available for future-proofing.

Using GUID (when supported) ensures:
- ✅ Reimport correctly updates same tasks even after reordering
- ✅ Round-trip compatibility (export → edit → reimport)
- ✅ No duplicate tasks created on reimport

### Why Milestone Structure Validation?

Milestones define budget_weight for EVM calculations. Changing milestone structure mid-project would:
- ❌ Invalidate historical EVM calculations (PV, EV recalculated with different weights)
- ❌ Break expense allocation (expenses linked to milestone_id)
- ❌ Corrupt RAE data (RAE per milestone)

Strict validation prevents data corruption and ensures EVM integrity.

### Why Bulk API Calls?

- **Performance**: 1000 tasks → 10 API calls (100 each) instead of 1000 individual calls
- **Atomicity**: Bulk operations can be atomic (all-or-nothing)
- **Rate Limiting**: Reduces likelihood of hitting API rate limits
- **Network Efficiency**: Fewer round-trips, less overhead

### Why Hybrid Approach (CLI + API)?

Alternative approaches considered:
1. **Direct DB Access**: Tightly coupled, breaks abstraction, no Guardian auth
2. **Web UI Upload**: Complex, requires web server, harder to automate
3. **CLI + API (chosen)**: Decoupled, leverages existing API, automatable

## 7. Dependencies & External Integrations

### External Systems

- **EXT-001**: wfp-poc REST API - Core dependency for all data persistence
- **EXT-002**: Identity Service (via wfp-poc) - JWT token validation
- **EXT-003**: Guardian Service (via wfp-poc) - Permission checking

### Technology Platform Dependencies

- **PLT-001**: Python 3.9+ - Runtime environment
- **PLT-002**: Flask - Web framework (service layer, optional REST API)
- **PLT-003**: lxml library - MS Project XML parsing with schema validation
- **PLT-004**: openpyxl or pandas - Excel file parsing (.xlsx format)
- **PLT-005**: requests library - HTTP client for wfp-poc API
- **PLT-006**: Click - CLI framework (Flask built-in CLI support)
- **PLT-007**: python-dateutil - Date parsing and timezone handling
- **PLT-008**: SQLAlchemy - ORM for optional import job tracking (future)

### Infrastructure Dependencies

- **INF-001**: Network connectivity - HTTP/HTTPS access to wfp-poc API
- **INF-002**: File system access - Read source files, write logs/reports

### Compliance Dependencies

- **COM-001**: MS Project 2010+ XML Schema - Vendor-defined schema compliance

## 8. Examples & Edge Cases

### Example 1: Initial Import Success

```bash
# Step 1: Export MS Project to XML
# File: project_baguera.xml (150 tasks, 5 milestones, 25 resources)

# Step 2: Run import
poc-import msproject project_baguera.xml \
  --mode=initial \
  --company-id=550e8400-e29b-41d4-a716-446655440000 \
  --token=$WFP_JWT_TOKEN \
  --api-url=https://wfp-poc.example.com \
  --output-report=import_report.json

# Output:
# ✅ Parsing project_baguera.xml...
# ✅ Validated: 150 tasks, 5 milestones, 25 resources
# ✅ Creating project...
# ✅ Importing tasks (batch 1/2): 100 tasks
# ✅ Importing tasks (batch 2/2): 50 tasks
# ✅ Importing milestones: 5 milestones
# ✅ Importing resources: 25 resources
# ✅ Importing assignments: 300 assignments
# ✅ Import completed in 45.2 seconds
# 📊 Report saved to import_report.json
```

### Example 2: Reimport with Structural Validation

```bash
# Scenario: PM updated task dates in MS Project, kept milestone structure

poc-import msproject project_baguera_v2.xml \
  --mode=sync \
  --project-id=a1b2c3d4-e5f6-4a5b-8c9d-0e1f2a3b4c5d \
  --token=$WFP_JWT_TOKEN \
  --api-url=https://wfp-poc.example.com

# Output:
# ✅ Parsing project_baguera_v2.xml...
# ✅ Fetching existing project...
# ✅ Validating milestone structure...
#    Expected: 5 milestones
#    Found: 5 milestones ✅
#    Names match: ✅
# ✅ Syncing tasks (batch 1/2): 100 tasks (95 updated, 5 new)
# ✅ Syncing tasks (batch 2/2): 50 tasks (48 updated, 2 new)
# ✅ Sync completed in 28.3 seconds
# 📊 Updated: 143 tasks, Created: 7 tasks
```

### Example 3: Reimport Failure - Milestone Changed

```bash
# Scenario: PM accidentally added new milestone in MS Project

poc-import msproject project_baguera_v3.xml \
  --mode=sync \
  --project-id=a1b2c3d4-e5f6-4a5b-8c9d-0e1f2a3b4c5d \
  --token=$WFP_JWT_TOKEN \
  --api-url=https://wfp-poc.example.com

# Output:
# ✅ Parsing project_baguera_v3.xml...
# ✅ Fetching existing project...
# ❌ Validating milestone structure...
#    Expected: 5 milestones
#    Found: 6 milestones ❌
# 
# ❌ IMPORT FAILED: Milestone structure changed
# 
# Error Details:
#   Code: MILESTONE_COUNT_MISMATCH
#   Message: Milestone count increased from 5 to 6
#   New milestone: "Phase 2.5 Integration Testing"
# 
# Resolution Options:
#   1. Remove milestone from MS Project and retry import
#   2. Add milestone manually in wfp-poc first:
#      POST https://wfp-poc.example.com/v0/projects/{project_id}/milestones
#      {
#        "project_id": "a1b2c3d4-e5f6-4a5b-8c9d-0e1f2a3b4c5d",
#        "name": "Phase 2.5 Integration Testing",
#        "target_date": "2026-09-15",
#        "budget_weight": 0.08
#      }
#      Then recalculate budget_weight for other milestones (total must = 1.0)
#      Then retry import
# 
# Exit code: 1 (Validation failed)
```

### Example 4: Expense Import with Validation Errors

```bash
poc-import expenses expenses_q2.xlsx \
  --project-id=a1b2c3d4-e5f6-4a5b-8c9d-0e1f2a3b4c5d \
  --token=$WFP_JWT_TOKEN \
  --api-url=https://wfp-poc.example.com

# Output:
# ✅ Parsing expenses_q2.xlsx...
# ❌ Validation errors found:
# 
# Row 15: ❌ milestone_name "Phase 1a Complete" not found
#         Available milestones: Phase 1 Complete, Phase 2 Complete, ...
#         
# Row 23: ❌ amount "-5000.00" is negative (must be >= 0)
# 
# Row 45: ⚠️  category "labour" not recognized (did you mean "Labor"?)
# 
# Row 67: ⚠️  Duplicate expense (2026-04-15, "Server License", 5000.00)
#         Will be skipped
# 
# Summary: 2 errors, 2 warnings
# ❌ Import aborted due to validation errors
# 
# Exit code: 1 (Validation failed)
```

### Example 5: RAE Import Success

```bash
poc-import rae rae_june_2026.xlsx \
  --project-id=a1b2c3d4-e5f6-4a5b-8c9d-0e1f2a3b4c5d \
  --token=$WFP_JWT_TOKEN \
  --api-url=https://wfp-poc.example.com

# Output:
# ✅ Parsing rae_june_2026.xlsx...
# ✅ Validated 5 milestones with RAE data
# ✅ Phase 1 Complete: RAE = $0 (completed)
# ✅ Phase 2 Complete: RAE = $85,000 (3 tasks: 65K + 0 + 20K = 85K ✓)
# ✅ Phase 3 Complete: RAE = $150,000 (not started, using budget)
# ✅ Phase 4 Complete: RAE = $0 (not started, but no budget allocated)
# ✅ Phase 5 Complete: RAE = $0 (completed)
# ✅ Importing to wfp-poc...
# ✅ POST /v0/milestones/{milestone_id}/rae (Phase 1) → 201 Created
# ✅ POST /v0/milestones/{milestone_id}/rae (Phase 2) → 201 Created
# ✅ POST /v0/milestones/{milestone_id}/rae (Phase 3) → 201 Created
# ✅ POST /v0/milestones/{milestone_id}/rae (Phase 4) → 201 Created
# ✅ POST /v0/milestones/{milestone_id}/rae (Phase 5) → 201 Created
# ✅ Import completed in 1.8 seconds
# 📊 Total RAE: $235,000.00
```

### Example 6: Dry Run (Validation Only)

```bash
poc-import msproject project_baguera_v4.xml \
  --mode=sync \
  --project-id=a1b2c3d4-e5f6-4a5b-8c9d-0e1f2a3b4c5d \
  --token=$WFP_JWT_TOKEN \
  --api-url=https://wfp-poc.example.com \
  --dry-run

# Output:
# ✅ Parsing project_baguera_v4.xml...
# ✅ Fetching existing project... (read-only)
# ✅ Validating milestone structure... ✅
# ✅ Validating tasks... ✅
# ✅ Validation successful
# 
# 🔍 DRY RUN - No API calls made
# 
# Would perform:
#   - Update 148 tasks
#   - Create 2 new tasks
#   - Update 0 milestones
#   - Update 25 resources
# 
# To execute import, remove --dry-run flag
# 
# Exit code: 0 (Validation passed)
```

## 9. Validation Criteria

### File Format Validation

- **VAL-001**: MS Project XML file SHOULD pass structural validation (well-formed XML, required sections present). Full XSD validation MAY be added as Phase 2.
- **VAL-002**: Excel file SHALL be .xlsx format (OpenXML), reject .xls or .csv
- **VAL-003**: Excel file SHALL contain required columns (see Section 4)
- **VAL-004**: Excel date columns SHALL be valid dates (ISO 8601 or Excel serial number)

### Business Logic Validation

- **VAL-005**: Milestone structure SHALL match existing project on reimport (count + names)
- **VAL-006**: Expense milestone_name SHALL exist in project milestones (normalized match: trim + case-insensitive)
- **VAL-007**: RAE milestone_name SHALL exist in project milestones (normalized match: trim + case-insensitive)
- **VAL-008**: RAE task breakdown (if provided) SHALL sum to milestone RAE amount
- **VAL-009**: All amounts SHALL be non-negative decimals
- **VAL-010**: Task GUID SHALL be a valid UUID string (case-insensitive). Version-specific enforcement (v4) is not required for this POC.

### API Integration Validation

- **VAL-011**: JWT token SHALL be valid (not expired, valid signature)
- **VAL-012**: API responses SHALL be 2xx for success, 4xx/5xx handled appropriately
- **VAL-013**: Bulk API payloads SHALL not exceed size limits (tasks: 100, expenses: 200)
- **VAL-014**: Correlation ID SHALL be consistent across all API calls in single import session

## 10. Related Specifications / Further Reading

- [Integration Specification - Waterfall Project Management Services](integration-wfp-services.md)
- [WFP-POC REST API Specification](wfp-poc/schema-api-project-management-evm.md)
- [Microsoft Project XML Schema Reference](https://docs.microsoft.com/en-us/office-project/xml-data-interchange/project-xml-data-interchange-schema-reference)
- [OpenXML Excel Format Specification](https://www.ecma-international.org/publications-and-standards/standards/ecma-376/)

---

**End of Specification**
