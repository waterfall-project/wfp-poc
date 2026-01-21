---
title: poc-import CLI - Interactive MS Project & Excel Import Tool
version: 1.0
date_created: 2026-01-18
last_updated: 2026-01-18
owner: Waterfall Team
tags: [tool, cli, poc-import, ms-project, excel, etl, validation, interactive-shell]
---

# poc-import CLI - Interactive MS Project & Excel Import Tool

## 1. Introduction

`poc-import` is an interactive command-line tool for importing, analyzing, and debugging MS Project XML files and Excel spreadsheets before importing them into the wfp-poc API. Built on click-shell, it provides a REPL environment for inspecting source data, validating business rules, and performing granular imports to support migration, troubleshooting, and development workflows.

## 2. Purpose & Scope

### Purpose

`poc-import` serves three primary roles in the Waterfall ecosystem:

1. **Smooth Migration Tool**: Enables gradual adoption of Waterfall by maintaining MS Project compatibility. Organizations accustomed to MS Project for years can continue using familiar workflows while transitioning to the Waterfall platform. The tool will eventually be integrated as a service within the Waterfall suite.

2. **Diagnostic & Debug Tool**: MS Project's open format allows construction of planning structures incompatible with EVM-based project management. poc-import provides inspection capabilities to understand validation criteria and troubleshoot import failures.

3. **Development Tool**: During development phases, enables comparison between database structures in wfp-poc service and source data being synchronized, facilitating schema refinement and business rule validation.

### Scope

**In Scope:**

- Interactive shell (REPL) for all operations
- Parse MS Project 2010+ XML files (project metadata, tasks, milestones, resources, assignments, dependencies)
- Parse Excel files for expenses and RAE (Reste À Engager) data
- Load and inspect source files in memory without API calls
- List and show individual entities (tasks, resources, dependencies, assignments)
- Validate data integrity and EVM business rules before import
- Query wfp-poc API to inspect existing project data
- Select active project context for import operations
- Import complete projects or individual entities (task-by-task for debugging)
- Detect concurrent modifications via MS Project version tracking
- Rollback on import failure to preserve database consistency
- Progress indicators for long-running operations
- Detailed validation reports with line numbers
- Support UUID-based reconciliation cycle (import → export → modify → re-import)

**Out of Scope:**

- MS Project binary .mpp file parsing (convert to XML using MS Project first)
- Non-interactive batch mode (context too complex for scripting)
- Real-time synchronization (batch import only)
- Data export (handled by separate poc-export tool)
- Web UI (CLI only)
- Direct database access (API-only communication)
- Caching of API responses
- Bulk/batch API calls in V1 (1 call per entity)

### Intended Audience

**Technical Users Only:**

- **Developers**: Debugging import issues, refining validation rules, comparing data structures
- **Support Engineers**: Investigating customer-reported import failures, analyzing XML/Excel files
- **Project Managers** (technical): Testing imports, validating data before production import via web frontend

**Note**: End-users access import functionality through the Waterfall web frontend, not directly via this CLI.

### Assumptions

- Users are comfortable with terminal/console operations
- MS Project files exported to XML format before using poc-import
- Excel files follow defined column schemas (see Section 8)
- wfp-poc API is accessible and responsive
- Valid JWT token available (auto-generated from .env or manually provided)
- Network connectivity between poc-import and wfp-poc
- Python 3.11+ installed
- Users understand EVM concepts and MS Project structure

## 3. Definitions

| Term | Definition |
|------|------------|
| **Initial Import** | First-time import creating all entities (project, tasks, milestones, resources) in wfp-poc from MS Project XML. |
| **Re-import** | Subsequent import after export from wfp-poc, modification in MS Project, and re-import to calculate EVM milestone shifts. |
| **UUID Cycle** | Workflow where UUIDs assigned by wfp-poc during initial import are preserved in export, modified MS Project maintains them, and re-import uses them for entity matching (UUID exists = update, else = create). |
| **Planning Data** | MS Project-sourced data: WBS, task names, dates, durations, dependencies, resource assignments. |
| **Tracking Data** | wfp-poc-sourced data preserved during re-import: expenses, actual dates, progress updates, RAE entries. |
| **ms_project_guid** | MS Project Task GUID (UUID format) - stable identifier for cross-system reconciliation. Preserved in UUID cycle. |
| **ms_project_uid** | MS Project Task UID (integer) - can change if tasks renumbered/reordered in MS Project. Less stable than GUID. |
| **Milestone** | Task with duration=0 or IsMilestone=1 flag in MS Project. Critical for EVM calculations (milestone pose/shift tracking). |
| **Jalon** | French term for Milestone. Used interchangeably in this specification. |
| **Dry Run** | Validation-only mode (`--dry-run` flag) that reports errors without making API calls or modifying wfp-poc database. |
| **Progress Bar** | Visual indicator displayed during long operations (parsing large XML, importing many tasks). |
| **Correlation ID** | UUID tracking a request across services for debugging. Generated automatically or passed via header. |
| **Shell State** | Session context maintained in interactive shell: selected project, loaded XML file, loaded Excel file. |
| **Rollback** | Automatic reversal of partial import if operation fails mid-way to maintain database consistency. |
| **EVM** | Earned Value Management - project management methodology tracking planned value, earned value, and actual cost. |
| **RAE** | Reste À Engager (French) - remaining budget to commit. Forecast of future expenses. |
| **OTP Code** | Ordre de Travaux Prévisionnels (French) - project code + optional task sub-code used in ERP systems. |

## 4. Rationale & Context

### Business Context

Organizations migrating to Waterfall often have years of MS Project expertise and data. An abrupt switch creates adoption barriers and risks data loss. poc-import enables a **smooth migration path**:

1. **Initial Import**: Import existing MS Project planning into wfp-poc
2. **Enrichment**: Add resources, assignments, expenses via wfp-poc web UI or API
3. **Export**: Use poc-export to generate enriched MS Project XML with wfp-poc UUIDs embedded
4. **Modify**: Adjust schedules, add sub-tasks in MS Project (familiar environment)
5. **Re-import**: Import modified XML to update planning data while preserving tracking data

### UUID Reconciliation Strategy

**Problem**: How does poc-import know if a task in XML is new or existing?

**Solution**: UUID-based reconciliation cycle:

- **Initial Import**: wfp-poc assigns UUID to each created task (API response returns UUIDs)
- **Export**: poc-export embeds wfp-poc UUIDs into MS Project XML custom fields or GUID elements
- **Re-import**: poc-import reads UUID from XML:
  - UUID exists in wfp-poc → UPDATE existing task (preserve tracking data)
  - UUID not found → CREATE new task

**Critical**: Project ID not used for reconciliation (no stable project ID in MS Project format). Users must explicitly select target project via `service select <project_id>` command before import.

### Version Conflict Detection

**Problem**: User A exports project, User B modifies it via API, User A re-imports stale export → overwrites User B's changes.

**Solution**: MS Project XML contains version/timestamp fields. poc-import compares:
- XML version field vs wfp-poc project version
- If mismatch → reject import with error message

**Implementation**: Requires wfp-poc project model to store version field (to be implemented).

### Debugging & Development Use Cases

**Scenario 1 - Customer Support**:
1. Customer reports import failure
2. Customer sends XML file + wfp-poc logs
3. Support engineer opens poc-import shell
4. `xml load customer_file.xml` → inspect structure
5. `xml validate` → identify validation errors
6. `service select <project_id>` → select customer's project
7. `xml import task <problematic_task_id>` → reproduce error with single task
8. Analyze logs, identify root cause, file bug or explain to customer

**Scenario 2 - Schema Evolution**:
1. Developer adds new field to wfp-poc Task model
2. Export sample project to XML
3. Modify XML to include new field
4. `xml load modified.xml`
5. `xml show task <id>` → verify field parsed correctly
6. `xml import task <id>` → test import, check API payload
7. Iterate until schema stable

### EVM-Specific Validations

Earned Value Management requires strict milestone tracking:
- Milestones define reporting periods (pose dates)
- Shifting milestone dates recalculates EVM metrics
- Deleting milestone with declared pose → breaks EVM history

**Validation rules** (to be refined):
- Cannot delete milestone that has pose date declared in wfp-poc
- Cannot rename milestone after pose (breaks expense/RAE associations)
- Milestone date changes must be intentional (warn user if >7 days shift)

## 5. Requirements, Constraints & Guidelines

### 5.1. Functional Requirements (REQ-xxx)

#### Core Parsing - MS Project XML

- **REQ-001**: poc-import SHALL parse MS Project 2010+ XML files using lxml library
- **REQ-002**: poc-import SHALL extract Project metadata: name, start/finish dates, MS Project version field
- **REQ-003**: poc-import SHALL extract all Task fields: UID, GUID, Name, WBS, Start, Finish, Duration, PercentComplete, IsMilestone, PredecessorLink, custom fields
- **REQ-004**: poc-import SHALL extract all Resource fields: UID, GUID, Name, Type, StandardRate, OvertimeRate
- **REQ-005**: poc-import SHALL extract all Assignment fields: TaskUID, ResourceUID, Work, Units
- **REQ-006**: poc-import SHALL extract all Dependency fields (PredecessorLink): PredecessorUID, Type (FF/FS/SF/SS), LinkLag
- **REQ-007**: poc-import SHALL identify milestones as tasks with Duration=0 OR IsMilestone=1
- **REQ-008**: poc-import SHALL preserve UUID values from XML for reconciliation (GUID elements or custom fields)
- **REQ-009**: poc-import SHALL detect XML parsing errors and report line numbers
- **REQ-010**: poc-import SHALL support loading MS Project XML files up to 50MB (approximately 10,000 tasks) for parsing and inspection in memory; V1 validation/import support and performance targets apply to projects up to 1,000 tasks (see PERF-001)

#### Core Parsing - Excel

- **REQ-011**: poc-import SHALL parse Excel .xlsx files using openpyxl library
- **REQ-012**: poc-import SHALL support `--type expenses` flag to load expense data
- **REQ-013**: poc-import SHALL support `--type rae` flag to load RAE (budget forecast) data
- **REQ-014**: poc-import SHALL validate required columns exist on load (see Section 8)
- **REQ-015**: poc-import SHALL validate column data types (dates, amounts) on load
- **REQ-016**: poc-import SHALL group expense rows by "Nº pièce référence" field (sum amounts for same reference)
- **REQ-017**: poc-import SHALL handle empty "Nº pièce référence" fields (bank fees, general costs) as individual expenses

#### XML Inspection Commands

- **REQ-018**: poc-import SHALL provide `xml load <filepath>` command that loads XML into memory and displays summary: project name, task count (with milestone count), resource count, assignment count, dependency count
- **REQ-019**: poc-import SHALL provide `xml list tasks` command displaying table: ID | WBS | Name | Start | Finish | Duration | IsMilestone
- **REQ-020**: poc-import SHALL provide `xml list resources` command displaying table: ID | Name | Type | Rate
- **REQ-021**: poc-import SHALL provide `xml list dependencies` command displaying table: ID | From Task | To Task | Type | Lag
- **REQ-022**: poc-import SHALL provide `xml list assignments` command displaying table: ID | Task | Resource | Work
- **REQ-023**: poc-import SHALL provide `xml show task <id>` command displaying ALL MS Project fields (even non-imported ones), with color coding to distinguish imported vs display-only fields
- **REQ-024**: poc-import SHALL provide `xml show resource <id>` command displaying full resource details
- **REQ-025**: poc-import SHALL provide `xml show dependency <id>` command displaying full dependency details
- **REQ-026**: poc-import SHALL provide `xml show assignment <id>` command displaying full assignment details
- **REQ-027**: poc-import SHALL provide `xml show info` command displaying project-level metadata

#### XML Import Commands

- **REQ-028**: poc-import SHALL provide `xml import project` command that imports entire project (all tasks, resources, dependencies, assignments) to wfp-poc
- **REQ-028a**: poc-import SHALL provide `xml import create-project` command that creates a new project from loaded XML and imports all entities
- **REQ-029**: poc-import SHALL require active project selection via `service select <project_id>` before import (reject if no project selected)
- **REQ-030**: poc-import SHALL display progress bar during `xml import project` showing: "Importing tasks: 45/156 (29%)"
- **REQ-031**: poc-import SHALL display import summary after completion: "✓ Project imported: 156 tasks, 23 resources, 89 assignments, 134 dependencies"
- **REQ-032**: poc-import SHALL support `xml import project --dry-run` flag for validation-only mode (no API calls)
- **REQ-033**: poc-import SHALL support `xml import project --continue-on-error` flag to continue importing remaining entities if one fails (default: stop on first error)
- **REQ-034**: poc-import SHALL provide `xml import task <id>` command for importing single task (debugging)
- **REQ-035**: poc-import SHALL provide `xml import task <id> --dry-run` flag for validating single task import
- **REQ-036**: poc-import SHALL perform rollback on import failure: delete all entities created during failed import operation

#### Validation Commands

- **REQ-037**: poc-import SHALL provide `xml validate` command that runs all validation rules without making API calls
- **REQ-038**: poc-import SHALL display validation report with format: "ERROR: [Task #45] End date (2026-01-10) < Start date (2026-01-15) (line 342)"
- **REQ-039**: poc-import SHALL display validation summary: "Validation completed: 3 errors, 5 warnings"
- **REQ-040**: poc-import SHALL exit with code 2 if validation fails

#### Service Query Commands

- **REQ-041**: poc-import SHALL provide `service list projects` command displaying table: ID | Name | Start Date | End Date | Task Count
- **REQ-042**: poc-import SHALL provide `service select <project_id>` command that sets active project context and displays: "✓ Project selected: Project Name (156 tasks)"
- **REQ-043**: poc-import SHALL provide `service show project` command displaying full project details from wfp-poc (requires active project)
- **REQ-044**: poc-import SHALL provide `service list tasks` command displaying tasks for active project only
- **REQ-045**: poc-import SHALL provide `service show task <id>` command displaying task details + dependencies + assignments
- **REQ-046**: poc-import SHALL provide `service show dependency <id>` command displaying dependency details
- **REQ-047**: poc-import SHALL provide `service list resources` command displaying resources for active project
- **REQ-048**: poc-import SHALL provide `service show resource <id>` command displaying resource details + assignments
- **REQ-049**: poc-import SHALL provide `service list assignments` command displaying assignments for active project
- **REQ-050**: poc-import SHALL provide `service show assignment <id>` command displaying assignment details
- **REQ-050a**: poc-import SHALL provide `service delete project [project_id]` command that deletes selected project (or provided ID)
- **REQ-050b**: poc-import SHALL provide `service delete task <id>` command that deletes a task for the selected project
- **REQ-050c**: poc-import SHALL provide `service delete resource <id>` command that deletes a resource
- **REQ-050d**: poc-import SHALL provide `service delete assignment <id>` command that deletes an assignment for the selected project

#### Excel Commands

- **REQ-051**: poc-import SHALL provide `excel load <filepath> --type expenses` command that loads and validates expense Excel file
- **REQ-052**: poc-import SHALL display Excel load summary: "✓ Excel loaded: depenses_2025.xlsx | Type: Expenses | Rows: 342 | Period: 2025-01 to 2025-12 | Total: 1,245,678.50 EUR | Unique references: 298 (44 grouped)"
- **REQ-053**: poc-import SHALL provide `excel list expenses` command displaying table: ID | Reference | Date | Amount | Description
- **REQ-054**: poc-import SHALL provide `excel show expense <id>` command displaying full expense details
- **REQ-055**: poc-import SHALL provide `excel import expenses` command that sends expenses to wfp-poc in ADD mode (historical data, never updates)
- **REQ-056**: poc-import SHALL support `excel import expenses --dry-run` flag for validation-only
- **REQ-057**: poc-import SHALL provide `excel load <filepath> --type rae` command for RAE budget forecast files
- **REQ-058**: poc-import SHALL provide `excel list rae` command displaying table: ID | Milestone | Remaining Amount | Forecast Date
- **REQ-059**: poc-import SHALL provide `excel show rae <id>` command displaying full RAE details
- **REQ-060**: poc-import SHALL provide `excel import rae` command that sends RAE data to wfp-poc

### 5.2. Security Requirements (SEC-xxx)

**Authentication:**
- **SEC-001**: poc-import SHALL support JWT token authentication for wfp-poc API calls
- **SEC-002**: poc-import SHALL auto-generate JWT token from `.env` file containing `WFP_API_USER_ID`, `WFP_API_COMPANY_ID`, `WFP_API_SECRET_KEY`
- **SEC-003**: poc-import SHALL support manual JWT token via `--token <jwt>` CLI flag (overrides .env)
- **SEC-004**: poc-import SHALL include JWT token in `Authorization: Bearer <token>` header for all wfp-poc API requests
- **SEC-005**: poc-import SHALL exit with error if no valid JWT available and API call required

**Multi-Environment:**
- **SEC-006**: poc-import SHALL support multiple environment configurations via `--env dev|staging|prod` flag
- **SEC-007**: poc-import SHALL load environment-specific `.env.dev`, `.env.staging`, `.env.prod` files
- **SEC-008**: poc-import SHALL default to `.env` file if no `--env` flag provided

**Credentials Management:**
- **SEC-009**: poc-import SHALL NOT log JWT tokens or API secret keys
- **SEC-010**: poc-import SHALL NOT include credentials in error messages or validation reports
- **SEC-011**: poc-import SHALL store `.env` files in `tools/poc-import/.env` (never commit to git)

### 5.3. Performance Requirements (PERF-xxx)

- **PERF-001**: poc-import SHALL support V1 validation and import workflows for projects with up to 1000 tasks (hard supported limit); larger projects MAY load for inspection but are best-effort and out of scope for V1 performance guarantees
- **PERF-002**: poc-import SHALL make 1 API call per entity in V1 (no bulk operations)
- **PERF-003**: poc-import SHALL display progress bar for operations creating/updating >10 entities
- **PERF-004**: poc-import SHALL support configurable API timeout (default: 30 seconds) via `--timeout <seconds>` flag
- **PERF-005**: poc-import SHALL parse 1000-task MS Project XML file in <5 seconds
- **PERF-006**: poc-import SHALL complete validation of 1000-task project in <10 seconds
- **PERF-007**: poc-import SHALL respond to list/show commands in <2 seconds (excluding API latency)

### 5.4. Constraints (CON-xxx)

**Platform:**
- **CON-001**: poc-import SHALL require Python 3.11 or higher
- **CON-002**: poc-import SHALL run in virtual environment (venv recommended)
- **CON-003**: poc-import SHALL support Linux, macOS, Windows (via WSL or native Python)

**Execution Mode:**
- **CON-004**: poc-import SHALL operate in interactive shell mode ONLY (no batch/scripting mode)
- **CON-005**: poc-import SHALL NOT support piping commands from stdin or executing command sequences non-interactively
- **CON-006**: Rationale for CON-004/CON-005: Session context (selected project, loaded files) too complex for reliable scripting

**State Management:**
- **CON-007**: poc-import SHALL maintain session state in memory: selected project ID, loaded XML data, loaded Excel data
- **CON-008**: poc-import SHALL reset state on exit (no persistent state file)
- **CON-009**: poc-import SHALL NOT cache wfp-poc API responses (always fetch fresh data)

**Error Handling:**
- **CON-010**: poc-import SHALL perform automatic rollback on import failure
- **CON-011**: poc-import SHALL delete all entities created during a failed `xml import project` operation
- **CON-012**: poc-import SHALL preserve database consistency by rejecting partial imports (unless `--continue-on-error` flag used)

**Dependencies:**
- **CON-013**: poc-import SHALL use lxml for XML parsing (not xml.etree due to performance and XPath support)
- **CON-014**: poc-import SHALL use openpyxl for Excel parsing (supports .xlsx only, not .xls)
- **CON-015**: poc-import SHALL use click-shell for interactive REPL
- **CON-016**: poc-import SHALL use rich for console output formatting (tables, progress bars, color)
- **CON-017**: poc-import SHALL use requests for HTTP API calls
- **CON-018**: poc-import SHALL use pydantic for data validation and models

## 6. CLI Command Specifications

### 6.1. XML Group Commands

#### Command: `xml load <filepath>`

**Purpose**: Load MS Project XML file into memory and display summary statistics.

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| filepath | Path | Yes | Absolute or relative path to MS Project XML file |

**Options:**
| Option | Type | Default | Description |
|--------|------|---------|-------------|
| --validate | Flag | False | Run validation rules immediately after loading |

**Output Format:**
```
✓ XML loaded: project_name.xml

Project: "Waterfall Platform Development"
- Start Date: 2026-01-15
- End Date: 2026-12-31
- MS Project Version: 14.0 (Project 2010)

Entities:
- Tasks: 156 (12 milestones, 144 regular tasks)
- Resources: 23
- Assignments: 89
- Dependencies: 134

Use 'xml list tasks' to view tasks or 'xml validate' to check for errors.
```

**Exit Codes:**
- 0: Success
- 1: File not found, XML parse error, or invalid MS Project schema
- 2: Validation errors (if --validate flag used)

**Error Examples:**
```
ERROR: File not found: /path/to/missing.xml
ERROR: XML parse error at line 342: Unexpected closing tag </Task>
ERROR: Invalid MS Project XML: Missing required element <Project>
```

**State Changes:**
- Stores parsed XML data in shell state
- Replaces previously loaded XML (warns user if XML already loaded)

---

#### Command: `xml list tasks`

**Purpose**: Display table of all tasks from loaded XML.

**Prerequisites:** XML file must be loaded via `xml load`

**Options:**
| Option | Type | Default | Description |
|--------|------|---------|-------------|
| --milestones-only | Flag | False | Show only milestone tasks |
| --sort-by | Choice | wbs | Sort order: wbs, start, finish, name |
| --output | Choice | table | Output format: table, json, csv |

**Output Format:**
```
Tasks (156 total, 12 milestones):

 ID  │ WBS     │ Name                              │ Start      │ Finish     │ Duration │ Milestone
═════╪═════════╪═══════════════════════════════════╪════════════╪════════════╪══════════╪═══════════
 1   │ 1       │ Waterfall Platform                │ 2026-01-15 │ 2026-12-31 │ 250d     │  
 2   │ 1.1     │ Phase 1: Foundation               │ 2026-01-15 │ 2026-03-31 │ 76d      │  
 3   │ 1.1.1   │ Project Setup                     │ 2026-01-15 │ 2026-01-22 │ 7d       │  
 4   │ 1.1.2   │ Infrastructure                    │ 2026-01-23 │ 2026-02-15 │ 24d      │  
 5   │ 1.1.M1  │ Foundation Complete               │ 2026-03-31 │ 2026-03-31 │ 0d       │ ✓  
...
```

**Exit Codes:**
- 0: Success
- 1: No XML loaded (use `xml load` first)

---

#### Command: `xml list resources`

**Purpose**: Display table of all resources from loaded XML.

**Prerequisites:** XML file must be loaded

**Output Format:**
```
Resources (23 total):

 ID  │ Name           │ Type     │ Standard Rate │ Overtime Rate │ Email  
═════╪════════════════╪══════════╪═══════════════╪═══════════════╪════════════════════
 1   │ John Doe       │ Work     │ 85.00/h       │ 127.50/h      │ john.doe@example.com
 2   │ Jane Smith     │ Work     │ 95.00/h       │ 142.50/h      │ jane.smith@example.com
 3   │ Server Hosting │ Cost     │ 2500.00/month │ -             │ -  
...
```

---

#### Command: `xml list dependencies`

**Purpose**: Display table of all task dependencies (predecessor links).

**Prerequisites:** XML file must be loaded

**Output Format:**
```
Dependencies (134 total):

 ID  │ From Task (Predecessor)           │ To Task (Successor)               │ Type │ Lag  
═════╪═══════════════════════════════════╪═══════════════════════════════════╪══════╪═══════
 1   │ #3 - Project Setup                │ #4 - Infrastructure               │ FS   │ 0d  
 2   │ #4 - Infrastructure               │ #6 - Backend API                  │ FS   │ 0d  
 3   │ #6 - Backend API                  │ #7 - Frontend UI                  │ SS   │ +5d  
 4   │ #7 - Frontend UI                  │ #8 - Integration Testing          │ FS   │ -2d  
...
```

**Dependency Types:**
- FS: Finish-to-Start (predecessor must finish before successor starts)
- SS: Start-to-Start (both tasks start together)
- FF: Finish-to-Finish (both tasks finish together)
- SF: Start-to-Finish (successor finishes when predecessor starts)

---

#### Command: `xml list assignments`

**Purpose**: Display table of all resource assignments to tasks.

**Prerequisites:** XML file must be loaded

**Output Format:**
```
Assignments (89 total):

 ID  │ Task                              │ Resource       │ Work    │ Units │ Cost  
═════╪═══════════════════════════════════╪════════════════╪═════════╪═══════╪═══════════
 1   │ #3 - Project Setup                │ John Doe       │ 40h     │ 100%  │ 3,400.00  
 2   │ #4 - Infrastructure               │ Jane Smith     │ 120h    │ 100%  │ 11,400.00
 3   │ #6 - Backend API                  │ John Doe       │ 80h     │ 50%   │ 6,800.00  
...
```

---

#### Command: `xml show info`

**Purpose**: Display detailed project-level metadata.

**Prerequisites:** XML file must be loaded

**Output Format:**
```
Project Metadata:

  Name: Waterfall Platform Development
  GUID: {A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
  Version: 14.0 (Microsoft Project 2010)

  Schedule:
    Start Date: 2026-01-15
    Finish Date: 2026-12-31
    Status Date: 2026-01-18
    Current Date: 2026-01-18

  Properties:
    Author: Project Manager
    Company: Waterfall Corp
    Creation Date: 2025-12-01
    Last Saved: 2026-01-17 15:30:00

  Counters:
    Tasks: 156 (12 milestones)
    Resources: 23
    Assignments: 89
    Dependencies: 134

  Custom Fields:
    wfp_project_id: 123e4567-e89b-12d3-a456-426614174000
    wfp_version: 5
    wfp_exported_at: 2026-01-17T15:30:00Z
```

---

#### Command: `xml show task <task_id>`

**Purpose**: Display all fields for a specific task, including fields not imported to wfp-poc.

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| task_id | Integer | Yes | MS Project Task UID |

**Prerequisites:** XML file must be loaded

**Output Format:**
```
Task #42: Backend API - Authentication Module

[Core Fields - Imported to wfp-poc]
  UUID: 123e4567-e89b-12d3-a456-426614174000
  UID: 42
  GUID: {42ABC123-4567-890A-BCDE-F12345678901}
  Name: Backend API - Authentication Module
  WBS: 1.2.3.1
  Outline Level: 4

[Schedule - Imported]
  Start Date: 2026-02-15
  Finish Date: 2026-03-10
  Duration: 24 days
  Duration Format: Days
  Percent Complete: 35%

[Properties - Imported]
  Is Milestone: No
  Is Summary: No
  Is Critical: Yes

[Tracking - Display Only]
  Actual Start: 2026-02-15
  Actual Finish: -
  Actual Duration: 8.4 days
  Actual Cost: 12,350.00
  Remaining Duration: 15.6 days

[Custom Fields - Display Only]
  Priority: High
  Risk Level: Medium
  Technical Lead: John Doe

[Dependencies]
  Predecessors:
    - #40: Backend API - Core Framework (FS, 0 days)
    - #41: Database Schema Design (FS, +2 days)
  Successors:
    - #43: API Testing (FS, 0 days)
    - #45: Frontend Integration (SS, +5 days)

[Assignments]
  - John Doe: 80h (100%) = 6,800.00
  - Jane Smith: 40h (50%) = 3,800.00

[Notes]
  Implementation uses JWT tokens with RSA-256 signing.
  Must coordinate with Identity service team.

Legend:
  Green text = Fields imported to wfp-poc
  Gray text  = Display-only fields (not imported)
```

---

#### Command: `xml show resource <resource_id>`

**Purpose**: Display full details for a specific resource.

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| resource_id | Integer | Yes | MS Project Resource UID |

**Output Format:**
```
Resource #5: John Doe

[Core Fields]
  UUID: 987e6543-e21b-12d3-a456-426614174999
  UID: 5
  GUID: {5ABC1234-5678-90AB-CDEF-123456789012}
  Name: John Doe
  Type: Work

[Rates]
  Standard Rate: 85.00 / hour
  Overtime Rate: 127.50 / hour
  Cost Per Use: 0.00

[Properties]
  Email: john.doe@example.com
  Initials: JD
  Group: Development Team
  Max Units: 100%

[Assignments] (12 tasks)
  - #3:  Project Setup (40h)
  - #42: Backend API - Authentication Module (80h)
  - #45: Frontend Integration (60h)
  ... (9 more)

  Total Work: 820 hours
  Total Cost: 69,700.00
```

---

#### Command: `xml show dependency <dependency_id>`

**Purpose**: Display full details for a specific dependency.

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| dependency_id | Integer | Yes | Sequential ID from dependency list |

**Output Format:**
```
Dependency #23

From: #40 - Backend API - Core Framework
  └─ Finish Date: 2026-02-14

To: #42 - Backend API - Authentication Module
  └─ Start Date: 2026-02-15

Type: Finish-to-Start (FS)
Lag: 0 days

Effect: Task #42 cannot start until Task #40 finishes.
```

---

#### Command: `xml show assignment <assignment_id>`

**Purpose**: Display full details for a specific resource assignment.

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| assignment_id | Integer | Yes | Sequential ID from assignment list |

**Output Format:**
```
Assignment #34

Task: #42 - Backend API - Authentication Module
  └─ Duration: 24 days (2026-02-15 to 2026-03-10)

Resource: #5 - John Doe
  └─ Standard Rate: 85.00 / hour

Work: 80 hours
Units: 100% (full-time allocation)
Cost: 6,800.00

Schedule:
  Start: 2026-02-15
  Finish: 2026-03-10
  Peak Units: 100%
```

---

#### Command: `xml validate`

**Purpose**: Run all validation rules against loaded XML without making API calls.

**Prerequisites:** XML file must be loaded

**Options:**
| Option | Type | Default | Description |
|--------|------|---------|-------------|
| --strict | Flag | False | Treat warnings as errors |
| --output | Choice | console | Output format: console, json, html |

**Output Format:**
```
Running validation checks...

✓ XML structure valid
✓ All task dates valid (end >= start)
✓ No circular dependencies detected
✗ 3 tasks missing resource assignments (#23, #45, #67)
⚠ 5 tasks have duration > 30 days (consider breaking down)
✗ Task #89: References non-existent predecessor #99 (line 1234)
⚠ Milestone #12: Date changed by 15 days since last export

Validation Summary:
  ✓ Passed: 42
  ⚠ Warnings: 6
  ✗ Errors: 2

Recommendation: Fix 2 errors before importing. Use 'xml show task <id>' for details.
```

**Exit Codes:**
- 0: No errors (warnings allowed)
- 2: Validation errors found

---

#### Command: `xml import create-project`

**Purpose**: Create a new project from loaded XML and import all entities.

**Prerequisites:**
- XML file must be loaded

**Options:**
| Option | Type | Default | Description |
|--------|------|---------|-------------|
| --dry-run | Flag | False | Validate and preview import without executing |
| --continue-on-error | Flag | False | Continue importing remaining entities if one fails |
| --batch-size | Integer | 1 | Future: entities per API call (V1 always uses 1) |

**Output Format:**
```
Creating project from XML...

Project created: 123e4567-...

Validation: ✓ Passed (0 errors, 2 warnings)

Importing tasks...
 ████████████████████░░░░░░░░ 156/156 (100%)

Importing resources...
 ████████████████████████████ 23/23 (100%)

Importing assignments...
 ████████████████████████████ 89/89 (100%)

Importing dependencies...
 ████████████████████████████ 134/134 (100%)

✓ Import completed successfully

Duration: 2m 34s

Use 'service show project' to verify imported data.
```

**Exit Codes:**
- 0: Import successful
- 1: Import failed (with rollback + project deletion)
- 2: Validation failed (--dry-run or pre-import validation)

**Error Handling:**
- On failure: Automatic rollback deletes all entities created during this import session
- Project created by this command is deleted if import fails

---

#### Command: `xml import project`

**Purpose**: Import entire project (all tasks, resources, dependencies, assignments) to wfp-poc.

**Prerequisites:**
- XML file must be loaded
- Project must be selected via `service select <project_id>`

**Options:**
| Option | Type | Default | Description |
|--------|------|---------|-------------|
| --dry-run | Flag | False | Validate and preview import without executing |
| --continue-on-error | Flag | False | Continue importing remaining entities if one fails |
| --batch-size | Integer | 1 | Future: entities per API call (V1 always uses 1) |

**Output Format:**
```
Starting project import...

Target Project: Waterfall Platform Development (id: 123e4567-...)

Validation: ✓ Passed (0 errors, 2 warnings)

Importing tasks...
 ████████████████████░░░░░░░░ 156/156 (100%)

Importing resources...
 ████████████████████████████ 23/23 (100%)

Importing assignments...
 ████████████████████████████ 89/89 (100%)

Importing dependencies...
 ████████████████████████████ 134/134 (100%)

✓ Import completed successfully

Summary:
  - Tasks created: 98, updated: 58
  - Resources created: 5, updated: 18
  - Assignments created: 45, updated: 44
  - Dependencies created: 78, updated: 56

Duration: 2m 34s

Use 'service list tasks' to verify imported data.
```

**Exit Codes:**
- 0: Import successful
- 1: Import failed (with rollback)
- 2: Validation failed (--dry-run or pre-import validation)

**Error Handling:**
- On failure: Automatic rollback deletes all entities created during this import session
- Display: "✗ Import failed at task #45. Rolling back changes..."
- If `--continue-on-error`: Skip failed entity, log error, continue with next

---

#### Command: `xml import task <task_id>`

**Purpose**: Import single task for debugging purposes.

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| task_id | Integer | Yes | MS Project Task UID |

**Prerequisites:**
- XML file must be loaded
- Project must be selected via `service select`

**Options:**
| Option | Type | Default | Description |
|--------|------|---------|-------------|
| --dry-run | Flag | False | Validate without executing |
| --with-dependencies | Flag | False | Also import task dependencies |
| --with-assignments | Flag | False | Also import task assignments |

**Output Format:**
```
Importing task #42...

Task: Backend API - Authentication Module
  WBS: 1.2.3.1
  Duration: 24 days (2026-02-15 to 2026-03-10)

✓ Task created successfully
  UUID: 123e4567-e89b-12d3-a456-426614174000

Dependencies skipped (use --with-dependencies to include)
Assignments skipped (use --with-assignments to include)

Use 'service show task 123e4567-...' to verify.
```

---

### 6.2. Service Group Commands

#### Command: `service list projects`

**Purpose**: Query wfp-poc API and display all projects accessible to authenticated user.

---

#### Command: `service delete project [project_id]`

**Purpose**: Delete a project. Uses selected project if no ID is provided.

**Prerequisites:**
- JWT token available

**Output Format:**
```
✓ Project deleted: <project_id>
```

---

#### Command: `service delete task <task_id>`

**Purpose**: Delete a task for the selected project.

**Prerequisites:**
- Project selected via `service select`

**Output Format:**
```
✓ Task deleted: <task_id>
```

---

#### Command: `service delete resource <resource_id>`

**Purpose**: Delete a resource by ID.

**Output Format:**
```
✓ Resource deleted: <resource_id>
```

---

#### Command: `service delete assignment <assignment_id>`

**Purpose**: Delete an assignment for the selected project.

**Prerequisites:**
- Project selected via `service select`

**Output Format:**
```
✓ Assignment deleted: <assignment_id>
```

**Prerequisites:** Valid JWT token (from .env or --token flag)

**Options:**
| Option | Type | Default | Description |
|--------|------|---------|-------------|
| --company-id | UUID | From .env | Filter by company |
| --output | Choice | table | Output format: table, json |

**Output Format:**
```
Projects (12 total):

 ID                                   │ Name                          │ Start Date │ End Date   │ Tasks │ Status  
══════════════════════════════════════╪═══════════════════════════════╪════════════╪════════════╪═══════╪══════════
 123e4567-e89b-12d3-a456-426614174000 │ Waterfall Platform            │ 2026-01-15 │ 2026-12-31 │ 156   │ Active  
 223e4567-e89b-12d3-a456-426614174001 │ Mobile App Redesign           │ 2025-11-01 │ 2026-06-30 │ 89    │ Active  
 323e4567-e89b-12d3-a456-426614174002 │ Legacy System Migration       │ 2025-09-15 │ 2026-03-31 │ 234   │ Completed
...

Use 'service select <id>' to select a project.
```

**Exit Codes:**
- 0: Success
- 1: API error (network, authentication, server error)

---

#### Command: `service select <project_id>`

**Purpose**: Set active project context for import operations.

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| project_id | UUID | Yes | wfp-poc project UUID |

**Output Format:**
```
✓ Project selected: Waterfall Platform Development

Details:
  ID: 123e4567-e89b-12d3-a456-426614174000
  Start: 2026-01-15
  End: 2026-12-31
  Tasks: 156 (12 milestones)
  Resources: 23
  Version: 5
  Last Updated: 2026-01-17 15:30:00

This project is now active for import operations.
Use 'xml import project' to import loaded XML.
```

**State Changes:**
- Stores project_id in shell state
- All subsequent `service show/list` commands operate on this project
- All `xml import` commands target this project

**Exit Codes:**
- 0: Success
- 1: Project not found or access denied

---

#### Command: `service show project`

**Purpose**: Display full details of currently selected project.

**Prerequisites:** Project must be selected via `service select`

**Output Format:**
```
Project: Waterfall Platform Development

[Metadata]
  ID: 123e4567-e89b-12d3-a456-426614174000
  Name: Waterfall Platform Development
  Company ID: 456e7890-ab12-34cd-5678-901234567890

[Schedule]
  Start Date: 2026-01-15
  Finish Date: 2026-12-31
  Duration: 351 days
  Actual Start: 2026-01-15
  Actual Finish: -
  Percent Complete: 23%

[Counters]
  Tasks: 156 (12 milestones)
  Resources: 23
  Assignments: 89
  Dependencies: 134
  Expenses: 342
  Progress Updates: 28

[Version Control]
  MS Project Version: 14.0
  Export Version: 5
  Last Exported: 2026-01-17 15:30:00
  Last Modified: 2026-01-18 09:15:00

[Budget]
  Planned Budget: 1,500,000.00 EUR
  Actual Cost: 345,678.00 EUR
  Remaining: 1,154,322.00 EUR

Use 'service list tasks' to view tasks.
```

---

#### Command: `service list tasks`

**Purpose**: Display tasks for currently selected project.

**Prerequisites:** Project must be selected

**Options:**
| Option | Type | Default | Description |
|--------|------|---------|-------------|
| --milestones-only | Flag | False | Show only milestones |
| --critical-path | Flag | False | Show only critical path tasks |

**Output Format:**
```
Tasks for project: Waterfall Platform Development (156 total)

 ID                                   │ WBS     │ Name                              │ Start      │ Finish     │ Progress
══════════════════════════════════════╪═════════╪═══════════════════════════════════╪════════════╪════════════╪═══════════
 423e4567-e89b-12d3-a456-426614174010 │ 1       │ Waterfall Platform                │ 2026-01-15 │ 2026-12-31 │ 23%  
 523e4567-e89b-12d3-a456-426614174011 │ 1.1     │ Phase 1: Foundation               │ 2026-01-15 │ 2026-03-31 │ 45%  
 623e4567-e89b-12d3-a456-426614174012 │ 1.1.1   │ Project Setup                     │ 2026-01-15 │ 2026-01-22 │ 100%  
...

Use 'service show task <id>' for details.
```

---

#### Command: `service show task <task_id>`

**Purpose**: Display full task details from wfp-poc, including dependencies and assignments.

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| task_id | UUID | Yes | wfp-poc task UUID |

**Output Format:**
```
Task: Backend API - Authentication Module

[Core]
  ID: 623e4567-e89b-12d3-a456-426614174012
  MS Project UID: 42
  MS Project GUID: {42ABC123-4567-890A-BCDE-F12345678901}
  Name: Backend API - Authentication Module
  WBS: 1.2.3.1

[Schedule]
  Start: 2026-02-15 (Planned), 2026-02-15 (Actual)
  Finish: 2026-03-10 (Planned), - (Actual)
  Duration: 24 days
  Percent Complete: 35%

[Properties]
  Is Milestone: No
  Is Critical: Yes
  Priority: High

[Dependencies] (3 total)
  Predecessors:
    - 523e4567-...: Backend API - Core Framework (FS, 0d)
    - 573e4567-...: Database Schema Design (FS, +2d)
  Successors:
    - 723e4567-...: API Testing (FS, 0d)

[Assignments] (2 resources)
  - John Doe (623e4567-...): 80h (100%)
  - Jane Smith (723e4567-...): 40h (50%)

[Tracking]
  Expenses: 5 entries, 12,350.00 EUR
  Progress Updates: 3 entries
  Last Update: 2026-01-17 (Week 3 complete)

Use 'service show dependency <dep_id>' for dependency details.
```

---

#### Command: `service show dependency <dependency_id>`

**Purpose**: Display full dependency details.

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| dependency_id | UUID | Yes | wfp-poc dependency UUID |

**Output Format:**
```
Dependency: 823e4567-e89b-12d3-a456-426614174099

Predecessor: #40 - Backend API - Core Framework
  └─ ID: 523e4567-e89b-12d3-a456-426614174010
  └─ Finish: 2026-02-14

Successor: #42 - Backend API - Authentication Module
  └─ ID: 623e4567-e89b-12d3-a456-426614174012
  └─ Start: 2026-02-15

Type: Finish-to-Start (FS)
Lag: 0 days

Status: Active
Created: 2026-01-15 10:30:00
Updated: 2026-01-17 14:20:00
```

---

#### Command: `service list resources`

**Purpose**: Display resources for currently selected project.

**Prerequisites:** Project must be selected

**Output Format:**
```
Resources for project: Waterfall Platform Development (23 total)

 ID                                   │ Name           │ Type     │ Rate      │ Assignments
══════════════════════════════════════╪════════════════╪══════════╪═══════════╪════════════
 723e4567-e89b-12d3-a456-426614174020 │ John Doe       │ Work     │ 85.00/h   │ 12  
 823e4567-e89b-12d3-a456-426614174021 │ Jane Smith     │ Work     │ 95.00/h   │ 8  
 923e4567-e89b-12d3-a456-426614174022 │ Server Hosting │ Cost     │ 2500/month│ 1  
...

Use 'service show resource <id>' for details.
```

---

#### Command: `service show resource <resource_id>`

**Purpose**: Display full resource details with assignments.

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| resource_id | UUID | Yes | wfp-poc resource UUID |

**Output Format:**
```
Resource: John Doe

[Core]
  ID: 723e4567-e89b-12d3-a456-426614174020
  MS Project UID: 5
  Name: John Doe
  Type: Work

[Rates]
  Standard Rate: 85.00 / hour
  Overtime Rate: 127.50 / hour

[Properties]
  Email: john.doe@example.com
  Max Units: 100%
  Group: Development Team

[Assignments] (12 tasks)
  - #3:  Project Setup (40h) - 100% complete
  - #42: Backend API - Authentication Module (80h) - 35% complete
  - #45: Frontend Integration (60h) - 0% complete
  ... (9 more)

[Statistics]
  Total Work: 820 hours
  Total Cost: 69,700.00 EUR
  Completed Work: 287 hours (35%)
  Remaining Work: 533 hours
```

---

#### Command: `service list assignments`

**Purpose**: Display resource assignments for currently selected project.

**Prerequisites:** Project must be selected

**Output Format:**
```
Assignments for project: Waterfall Platform Development (89 total)

 ID                                   │ Task                              │ Resource       │ Work  │ Progress
══════════════════════════════════════╪═══════════════════════════════════╪════════════════╪═══════╪═══════════
 a23e4567-e89b-12d3-a456-426614174030 │ Project Setup                     │ John Doe       │ 40h   │ 100%  
 b23e4567-e89b-12d3-a456-426614174031 │ Infrastructure                    │ Jane Smith     │ 120h  │ 80%  
 c23e4567-e89b-12d3-a456-426614174032 │ Backend API - Authentication      │ John Doe       │ 80h   │ 35%  
...

Use 'service show assignment <id>' for details.
```

---

#### Command: `service show assignment <assignment_id>`

**Purpose**: Display full assignment details.

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| assignment_id | UUID | Yes | wfp-poc assignment UUID |

**Output Format:**
```
Assignment: c23e4567-e89b-12d3-a456-426614174032

Task: #42 - Backend API - Authentication Module
  └─ ID: 623e4567-e89b-12d3-a456-426614174012
  └─ Duration: 24 days (2026-02-15 to 2026-03-10)
  └─ Progress: 35%

Resource: John Doe
  └─ ID: 723e4567-e89b-12d3-a456-426614174020
  └─ Standard Rate: 85.00 / hour

[Allocation]
  Work: 80 hours
  Units: 100% (full-time)
  Cost: 6,800.00 EUR

[Progress]
  Actual Work: 28 hours
  Remaining Work: 52 hours
  Percent Complete: 35%

[Tracking]
  Start: 2026-02-15 (Planned), 2026-02-15 (Actual)
  Finish: 2026-03-10 (Planned), - (Actual)

Created: 2026-01-15 10:45:00
Updated: 2026-01-17 16:00:00
```

---

### 6.3. Excel Group Commands

#### Command: `excel load <filepath> --type <type>`

**Purpose**: Load Excel file into memory and validate immediately.

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| filepath | Path | Yes | Path to Excel .xlsx file |

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| --type | Choice | Yes | - | File type: expenses or rae |

**Output Format (Expenses):**
```
✓ Excel loaded: depenses_2025.xlsx

Type: Expenses
Sheet: "Dépenses"

Data Summary:
  - Total Rows: 342
  - Period: 2025-01 to 2025-12
  - Total Amount: 1,245,678.50 EUR
  - Unique References: 298 (44 grouped by "Nº pièce référence")
  - Missing References: 12 rows (bank fees, general costs)

Breakdown by Type:
  - Achats (Purchases): 234 rows, 987,543.00 EUR
  - Pointages (Time tracking): 108 rows, 258,135.50 EUR

Validation: ✓ Passed (0 errors, 2 warnings)
  ⚠ 2 rows missing "Elément d'OTP" (OTP allocation key)

Use 'excel list expenses' to view entries or 'excel import expenses' to import.
```

**Output Format (RAE):**
```
✓ Excel loaded: rae_q1_2026.xlsx

Type: RAE (Reste À Engager)
Sheet: "RAE Forecast"

Data Summary:
  - Total Rows: 45
  - Milestones: 12
  - Total Remaining Budget: 854,321.50 EUR
  - Forecast Period: Q1 2026

Validation: ✓ Passed (0 errors)

Use 'excel list rae' to view entries or 'excel import rae' to import.
```

**Exit Codes:**
- 0: Success
- 1: File not found, Excel parse error, or missing required columns
- 2: Validation errors

---

#### Command: `excel list expenses`

**Purpose**: Display loaded expense entries.

**Prerequisites:** Expenses Excel file must be loaded

**Options:**
| Option | Type | Default | Description |
|--------|------|---------|-------------|
| --year | Integer | All | Filter by fiscal year |
| --month | Integer | All | Filter by period (1-12) |
| --sort-by | Choice | date | Sort: date, amount, reference |

**Output Format:**
```
Expenses (342 total, showing grouped entries):

 ID  │ Reference    │ Date       │ Amount     │ Type      │ Description/Resource  
═════╪══════════════╪════════════╪════════════╪═══════════╪═══════════════════════════
 1   │ 4500123456   │ 2025-01-15 │ 12,500.00  │ Achat     │ Serveurs Dell PowerEdge  
 2   │ 4500123457   │ 2025-01-20 │ 3,450.00   │ Achat     │ Licences logicielles  
 3   │ -            │ 2025-01-25 │ 850.00     │ Pointage  │ John Doe (80h)  
 4   │ -            │ 2025-01-28 │ 1,200.00   │ Pointage  │ Jane Smith (120h)  
 5   │ 4500123458   │ 2025-02-03 │ 8,750.00   │ Achat     │ MacBook Pro (x5)  
...

Total: 1,245,678.50 EUR

Use 'excel show expense <id>' for full details.
```

---

#### Command: `excel show expense <expense_id>`

**Purpose**: Display full details for a specific expense entry.

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| expense_id | Integer | Yes | Sequential ID from expense list |

**Output Format (Purchase):**
```
Expense #1

[Type] Achat (Purchase)

[Reference]
  Document d'achat: 4500123456
  Nº pièce référence: 4500123456
  Référence: PO-2025-0023

[Financial]
  Amount: 12,500.00 EUR
  Exercice comptable: 2025
  Période: 1 (January)
  Date: 2025-01-15

[Classification]
  Désign.nat.comptable: Matériel informatique
  Elément d'OTP: PROJ-001-INFRA (Project allocation key - optional sub-code)

[Supplier]
  Nom 1: Dell Technologies France

[Description]
  Texte: Serveurs Dell PowerEdge R750 (x2)
          - RAM: 256GB each
          - Storage: 4TB NVMe

[Status]
  Ready to import: Yes
  Target Milestone: Infrastructure (assigned by date: 2025-01-15)
```

**Output Format (Time Tracking):**
```
Expense #3

[Type] Pointage (Time Tracking)

[Reference]
  Nº pièce référence: - (no reference)

[Financial]
  Amount: 850.00 EUR
  Exercice comptable: 2025
  Période: 1 (January)
  Date: 2025-01-25

[Classification]
  Désign.nat.comptable: Main d'oeuvre
  Elément d'OTP: PROJ-001-DEV (Project allocation key - optional sub-code)

[Resource]
  Nom Matricule: John Doe (ID: EMP-12345)
  Hours: 80h
  Rate: 10.625 EUR/h (calculated)

[Status]
  Ready to import: Yes
  Target Milestone: Development (assigned by date: 2025-01-25)
```

---

#### Command: `excel import expenses`

**Purpose**: Import all loaded expenses to wfp-poc in ADD mode (creates new entries, never updates).

**Prerequisites:**
- Expenses Excel file must be loaded
- Project must be selected via `service select`

**Options:**
| Option | Type | Default | Description |
|--------|------|---------|-------------|
| --dry-run | Flag | False | Validate without executing |
| --skip-existing | Flag | True | Skip expenses with same reference already in wfp-poc |

**Output Format:**
```
Starting expense import...

Target Project: Waterfall Platform Development (id: 123e4567-...)

Pre-import validation: ✓ Passed

Importing expenses...
 ████████████████████████████ 298/298 (100%)

✓ Import completed successfully

Summary:
  - Expenses created: 298
  - Skipped (duplicates): 44
  - Total amount imported: 1,189,123.50 EUR

Duration: 45s

Note: Expenses are assigned to milestones by date.
      Verify assignments with 'service show project'.
```

**Exit Codes:**
- 0: Import successful
- 1: Import failed
- 2: Validation failed

---

#### Command: `excel list rae`

**Purpose**: Display loaded RAE (budget forecast) entries.

**Prerequisites:** RAE Excel file must be loaded

**Output Format:**
```
RAE - Reste À Engager (45 entries):

 ID  │ Milestone                         │ Remaining Budget │ Forecast Date │ Task Breakdown
═════╪═══════════════════════════════════╪══════════════════╪═══════════════╪════════════════
 1   │ Phase 1: Foundation               │ 125,000.00       │ 2026-03-31    │ 12 tasks  
 2   │ Phase 2: Core Development         │ 345,000.00       │ 2026-06-30    │ 28 tasks  
 3   │ Phase 3: Integration              │ 234,500.00       │ 2026-09-30    │ 18 tasks  
 4   │ Phase 4: Testing                  │ 149,821.50       │ 2026-12-31    │ 15 tasks  
...

Total RAE: 854,321.50 EUR

Use 'excel show rae <id>' for details.
```

---

#### Command: `excel show rae <rae_id>`

**Purpose**: Display full RAE entry details including task breakdown.

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| rae_id | Integer | Yes | Sequential ID from RAE list |

**Output Format:**
```
RAE Entry #2

[Milestone]
  Name: Phase 2: Core Development
  Forecast Date: 2026-06-30

[Budget]
  Remaining Amount: 345,000.00 EUR
  Allocated to Tasks: 345,000.00 EUR
  Unallocated: 0.00 EUR

[Task Breakdown] (28 tasks)
  - Backend API Framework:      45,000.00 EUR
  - Database Implementation:    32,500.00 EUR
  - Authentication Module:      28,000.00 EUR
  - Frontend Core:              55,000.00 EUR
  - API Integration:            38,500.00 EUR
  ... (23 more tasks)

[Validation]
  ✓ Sum of task breakdown equals milestone RAE
  ✓ All tasks exist in loaded XML
  ✓ Milestone date matches XML

Ready to import: Yes
```

---

#### Command: `excel import rae`

**Purpose**: Import RAE budget forecasts to wfp-poc.

**Prerequisites:**
- RAE Excel file must be loaded
- Project must be selected via `service select`

**Options:**
| Option | Type | Default | Description |
|--------|------|---------|-------------|
| --dry-run | Flag | False | Validate without executing |

**Output Format:**
```
Starting RAE import...

Target Project: Waterfall Platform Development (id: 123e4567-...)

Pre-import validation: ✓ Passed

Importing RAE entries...
 ████████████████████████████ 12/12 (100%)

✓ Import completed successfully

Summary:
  - Milestones updated: 12
  - Total RAE amount: 854,321.50 EUR
  - Task breakdowns: 73 entries

Duration: 12s

Use 'service show project' to verify budget allocations.
```

**Exit Codes:**
- 0: Import successful
- 1: Import failed
- 2: Validation failed

---

## 7. Data Schemas - Excel Files

### 7.1. Expenses Excel Schema

**Sheet Name**: "Dépenses" (or first sheet if different)

**Required Columns:**

| Column Name | Type | Required | Description | Example |
|-------------|------|----------|-------------|---------|
| Document d'achat | String | No | ERP internal reference for purchase order. Empty for time tracking. | 4500123456 |
| Exercice comptable | Integer | Yes | Fiscal year of expense | 2025 |
| Période | Integer | Yes | Month of expense (1-12) | 1 (January) |
| Elément d'OTP | String | Yes | ERP allocation key (OTP). Format: `PROJ-XXX` or `PROJ-XXX-TASKCODE`. Sent to wfp-poc expense API as `otp_element` (string). V1 does not require a Task `code` field. | PROJ-001-INFRA |
| Nom Matricule | String | Conditional | Resource name for time tracking entries. Required if `Document d'achat` is empty. | John Doe (ID: EMP-12345) |
| Nom 1 | String | Conditional | Supplier name for purchase entries. Required if `Document d'achat` is not empty. | Dell Technologies France |
| Nature comptable | String | No | Accounting nature code. **Not used for EVM - ignore during import**. | 6100 |
| Désign.nat.comptable | String | Yes | Expense type classification. Used for statistics by expense type. | Matériel informatique, Main d'oeuvre, Licences logicielles |
| Nº pièce référence | String | No | Expense reference ID. **Grouping key**: rows with same reference are summed into single expense. Empty for bank fees, general costs, insurance. | REF-2025-0042 |
| Val./Devise objet | Decimal | Yes | Expense amount in EUR | 12500.00 |
| Date de la pièce | Date | Yes | Date of expense. ISO 8601 format: YYYY-MM-DD | 2025-01-15 |
| Texte de la commande d'achat | String | No | Description text. Only filled for purchase entries. | Serveurs Dell PowerEdge R750 (x2) |
| Groupe d'origine | String | No | Origin group. **Not used - ignore during import**. | GRP-ADMIN |
| Référence | String | No | Purchase order reference for purchases. Empty for time tracking. | PO-2025-0023 |

**Data Validation Rules:**

- **VAL-EXP-001**: `Exercice comptable` must be valid year (2000-2100)
- **VAL-EXP-002**: `Période` must be between 1 and 12
- **VAL-EXP-003**: `Val./Devise objet` must be non-negative decimal (>=0)
- **VAL-EXP-004**: `Date de la pièce` must be valid ISO 8601 date
- **VAL-EXP-005**: If `Document d'achat` is empty, `Nom Matricule` is required (time tracking)
- **VAL-EXP-006**: If `Document d'achat` is not empty, `Nom 1` is required (purchase)
- **VAL-EXP-007**: `Elément d'OTP` must match pattern `^[A-Z0-9]+-[A-Z0-9]+(-[A-Z0-9]+)?$`
- **VAL-EXP-008**: `Désign.nat.comptable` must not be empty

**Grouping Logic:**

Expenses with same `Nº pièce référence` (non-empty) are grouped:
- Sum `Val./Devise objet` amounts
- Use first row's values for all other fields
- Create single expense entry in wfp-poc

**Milestone Assignment:**

Expenses are assigned to milestones by **date matching** (handled by wfp-poc service).

**Import Mode:** ADD only (historical data).

---

### 7.2. RAE Excel Schema

**Sheet Name**: "RAE Forecast"

**Required Columns:**

| Column Name | Type | Required | Description |
|-------------|------|----------|-------------|
| milestone_name | String | Yes | Exact name matching existing milestone |
| remaining_amount | Decimal | Yes | Remaining budget forecast |
| forecast_date | Date | Yes | Forecast date (ISO 8601) |
| task_breakdown | JSON/String | Optional | Task allocation breakdown |

**Data Validation Rules:**

- **VAL-RAE-001**: `milestone_name` must match existing milestone (case-sensitive)
- **VAL-RAE-002**: `remaining_amount` must be non-negative
- **VAL-RAE-003**: `forecast_date` must be valid ISO 8601 date
- **VAL-RAE-004**: If `task_breakdown` provided, sum must equal `remaining_amount`

**Import Mode:** UPSERT (update if exists, create if new).


## 8. Data Schemas - MS Project XML

### 8.1. MS Project XML Structure

poc-import parses Microsoft Project 2010+ XML files following the official schema.

**Root Element**: `<Project>`

**Key Sections:**
- `<Project>`: Metadata
- `<Tasks><Task>`: Task list
- `<Resources><Resource>`: Resource list
- `<Assignments><Assignment>`: Assignment list
- `<PredecessorLink>`: Dependencies (nested in Task)

---

### 8.2. Project Element

| Field | XPath | Type | Imported | Description |
|-------|-------|------|----------|-------------|
| Name | `/Project/Name` | String | Yes | Project name |
| GUID | `/Project/GUID` | UUID | Yes | Project GUID |
| StartDate | `/Project/StartDate` | DateTime | Yes | Start date (ISO 8601) |
| FinishDate | `/Project/FinishDate` | DateTime | Yes | Finish date |
| SaveVersion | `/Project/SaveVersion` | Integer | Yes | MS Project version (conflict detection) |
| wfp_project_id | ExtendedAttribute | UUID | Yes | wfp-poc project ID (from export) |
| wfp_version | ExtendedAttribute | Integer | Yes | wfp-poc version (conflict detection) |

---

### 8.3. Task Element

| Field | XPath | Type | Imported | Description |
|-------|-------|------|----------|-------------|
| UID | `UID` | Integer | Yes | Task UID (can change on renumber) |
| GUID | `GUID` | UUID | Yes | **Stable identifier for UUID cycle** |
| Name | `Name` | String | Yes | Task name |
| WBS | `WBS` | String | Yes | Work Breakdown Structure |
| OutlineLevel | `OutlineLevel` | Integer | Yes | Hierarchy depth |
| Start | `Start` | DateTime | Yes | Start date (ISO 8601) |
| Finish | `Finish` | DateTime | Yes | Finish date |
| Duration | `Duration` | Duration | Yes | ISO 8601 duration (PT192H0M0S = 24 days) |
| PercentComplete | `PercentComplete` | Integer | Yes | 0-100 |
| Milestone | `Milestone` | Boolean | Yes | True if milestone |
| Summary | `Summary` | Boolean | Yes | True if summary task |
| Critical | `Critical` | Boolean | Yes | True if on critical path |

**Color Coding**: Green = imported, Gray = display-only

**Milestone Detection**: `<Milestone>1</Milestone>` OR `<Duration>PT0H0M0S</Duration>`

**UUID Reconciliation**: Check GUID exists in wfp-poc → UPDATE if yes, CREATE if no

---

### 8.4. Resource Element

| Field | XPath | Type | Imported | Description |
|-------|-------|------|----------|-------------|
| UID | `UID` | Integer | Yes | Resource UID |
| GUID | `GUID` | UUID | Yes | Stable identifier |
| Name | `Name` | String | Yes | Resource name |
| Type | `Type` | Integer | Yes | 1=Work, 2=Material, 3=Cost |
| StandardRate | `StandardRate` | Decimal | Yes | Hourly rate |
| OvertimeRate | `OvertimeRate` | Decimal | Yes | Overtime rate |

---

### 8.5. Assignment Element

| Field | XPath | Type | Imported | Description |
|-------|-------|------|----------|-------------|
| UID | `UID` | Integer | Yes | Assignment UID |
| TaskUID | `TaskUID` | Integer | Yes | Reference to Task |
| ResourceUID | `ResourceUID` | Integer | Yes | Reference to Resource |
| Work | `Work` | Duration | Yes | Total work (PT80H0M0S = 80h) |
| Units | `Units` | Decimal | Yes | 1.0=100%, 0.5=50% |

---

### 8.6. Dependency (PredecessorLink)

Nested inside `<Task>` element.

| Field | XPath | Type | Imported | Description |
|-------|-------|------|----------|-------------|
| PredecessorUID | `PredecessorUID` | Integer | Yes | Predecessor task UID |
| Type | `Type` | Integer | Yes | 0=FF, 1=FS, 2=SF, 3=SS |
| LinkLag | `LinkLag` | Integer | Yes | Lag in tenths of minutes |

**Dependency Types:**
- FF (0): Finish-to-Finish
- FS (1): Finish-to-Start (most common)
- SF (2): Start-to-Finish
- SS (3): Start-to-Start

**Lag Conversion**: `lag_days = (LinkLag / 10) / 60 / 8`

Example: `LinkLag=9600` → 9600/10=960 min → 960/60=16h → 16/8=2 days


## 9. Validation Rules

### 9.1. Circular Dependency Detection

**VAL-001**: poc-import SHALL detect circular dependencies before import

**Algorithm**: Depth-First Search (DFS)
- Build dependency graph from PredecessorLink elements
- For each task, traverse predecessors recursively
- If task encounters itself in traversal → circular dependency detected

**Error Message**:
```
ERROR: Circular dependency detected involving tasks: #42 → #45 → #48 → #42 (line 1234)
```

---

### 9.2. Date Validation

**VAL-002**: Milestone without date
- Check: `IsMilestone=true AND (Start is null OR Finish is null)`
- Error: `ERROR: Milestone "#5 - Foundation Complete" has no date (line 234)`

**VAL-003**: End date < start date
- Check: `Finish < Start`
- Error: `ERROR: Task #42 end date (2026-01-10) < start date (2026-01-15) (line 567)`

**VAL-004**: Invalid ISO 8601 date format
- Check: Date fields match pattern `YYYY-MM-DDTHH:MM:SS`
- Error: `ERROR: Invalid date format "15/01/2026" for task #42 (line 567). Expected ISO 8601: YYYY-MM-DD`

---

### 9.3. Reference Validation

**VAL-005**: Reference to non-existent task
- Check: All PredecessorUID values exist in task list
- Error: `ERROR: Task #42 references non-existent predecessor #99 (line 567)`

**VAL-006**: Reference to non-existent resource
- Check: All ResourceUID in assignments exist in resource list
- Error: `ERROR: Assignment references non-existent resource #88 (line 890)`

---

### 9.4. Version Conflict Detection

**VAL-007**: MS Project version mismatch
- Check: `XML.SaveVersion != wfp_poc_project.ms_project_save_version`
- Error: `ERROR: Version conflict detected. XML version: 14, Database version: 15. Project modified after export. Re-export before import.`

**Notes**:
- wfp-poc Project schema exposes `ms_project_save_version` (OpenAPI: Project.ms_project_save_version). poc-import SHALL use this field name.
- If `ms_project_save_version` is missing or null in the API response, poc-import SHALL skip VAL-007 and emit a WARNING indicating version conflict detection is unavailable.

---

### 9.5. Assignment & Resource Validation

**VAL-008**: Assignment units exceeds 100%
- **Check**: `assignment.units > 1.0`
- **Severity**: WARNING
- **Message**: `Assignment units=1.50 exceeds 100% (task_uid=42, resource_uid=5). Will be capped to 100% during import.`
- **Rationale**: MS Project allows units > 1.0 for over-allocation, but wfp-poc API expects percent_allocation between 0-100. Import will automatically cap to 100%.
- **Action**: User should review MS Project resource allocation and correct if needed before re-import.

**VAL-009**: Assignment units is negative
- **Check**: `assignment.units < 0`
- **Severity**: ERROR
- **Message**: `Assignment units=-0.50 is negative (task_uid=42, resource_uid=5).`
- **Rationale**: Negative allocation is invalid and will cause import failure.
- **Action**: User must fix the assignment in MS Project before import.

**VAL-010**: Assignment exceeds resource max_units
- **Check**: `assignment.units > resource.max_units`
- **Severity**: WARNING
- **Message**: `Assignment units=2.00 exceeds resource max_units=1.50 (resource='John Doe', task_uid=42).`
- **Rationale**: Resource over-allocated beyond their maximum availability.
- **Action**: Review resource allocation strategy in MS Project.

---

### 9.6. EVM-Specific Validation (Future)

**VAL-011**: Milestone deletion with declared pose
- Check: Milestone exists in wfp-poc with pose_date set, but missing in XML
- Error: `ERROR: Cannot delete milestone "Foundation Complete" with declared pose date 2026-03-31`

**VAL-012**: Milestone date shift > threshold
- Check: `abs(XML.milestone_date - wfp_poc.milestone_date) > 7 days`
- Warning: `WARNING: Milestone "Phase 1" date shifted by 15 days (2026-03-31 → 2026-04-15). Review impact on EVM calculations.`

---

## 10. Error Handling

### 10.1. Exit Codes

| Code | Meaning | Usage |
|------|---------|-------|
| 0 | Success | All operations completed successfully |
| 1 | Runtime Error | File not found, API error, network error, parse error |
| 2 | Validation Failed | Business rule validation errors detected |

**Examples**:
```bash
$ ./poc-import.py  # Interactive shell
(shell) xml load missing.xml
ERROR: File not found: missing.xml
(shell) exit
$ echo $?
1

$ ./poc-import.py
(shell) xml load invalid.xml
ERROR: Circular dependency detected
(shell) exit
$ echo $?
2
```

---

### 10.2. Error Message Format

**Template**: `ERROR: [context] message (line X)`

**Components**:
- **Severity**: ERROR, WARNING, INFO
- **Context**: [Task #42], [Resource #5], [Assignment #12], [File], [API]
- **Message**: Human-readable description
- **Line number**: XML line number (if applicable)

**Examples**:
```
ERROR: [Task #42] End date < start date (line 567)
WARNING: [Milestone #5] Date shifted by 15 days since last export (line 234)
ERROR: [API] Connection timeout after 30s. Check network and wfp-poc availability.
ERROR: [File] XML parse error at line 1234: Unexpected closing tag </Task>
```

---

### 10.3. Rollback Strategy

**Trigger**: Import fails after creating one or more entities

**Process**:
1. Capture all entity UUIDs created during import session
2. On error, call DELETE endpoint for each created entity (reverse order)
3. Display rollback progress: `Rolling back... Deleted 45/98 entities`
4. If rollback fails, display list of orphaned entities for manual cleanup

**Example Output**:
```
Importing tasks...
 ████████░░░░░░░░░░░░░░░░░░░░ 45/156 (29%)
ERROR: [Task #67] Invalid date format (line 890)

✗ Import failed. Rolling back changes...
 ████████████████████████████ 45/45 (100%)
✓ Rollback completed. Database restored to previous state.

No entities were modified.
```

---

### 10.4. Validation Report Format

**Console Output**:
```
Running validation checks...

✓ XML structure valid
✓ All task dates valid (end >= start)
✓ No circular dependencies detected
✗ 3 tasks missing resource assignments (#23, #45, #67)
⚠ 5 tasks have duration > 30 days (consider breaking down)
✗ Task #89: References non-existent predecessor #99 (line 1234)
⚠ Milestone #12: Date changed by 15 days since last export

Validation Summary:
  ✓ Passed: 42
  ⚠ Warnings: 6
  ✗ Errors: 2

Recommendation: Fix 2 errors before importing. Use 'xml show task <id>' for details.
```

**JSON Output** (with `--output json`):
```json
{
  "status": "failed",
  "summary": {
    "passed": 42,
    "warnings": 6,
    "errors": 2
  },
  "checks": [
    {
      "id": "VAL-001",
      "severity": "error",
      "message": "Task #89: References non-existent predecessor #99",
      "line": 1234,
      "context": {"task_id": 89, "predecessor_id": 99}
    },
    {
      "id": "VAL-009",
      "severity": "warning",
      "message": "Milestone #12: Date changed by 15 days since last export",
      "line": 567,
      "context": {"milestone_id": 12, "old_date": "2026-03-31", "new_date": "2026-04-15"}
    }
  ]
}
```

---

## 11. Acceptance Criteria

### 11.1. XML Commands (AC-001 to AC-010)

**AC-001**: Given XML file exists, When `xml load <file>` executed, Then display summary with project name, task count, resource count, dependency count

**AC-002**: Given XML loaded, When `xml list tasks` executed, Then display table with all tasks sorted by WBS

**AC-003**: Given XML loaded, When `xml show task <id>` executed, Then display all fields with color coding (green=imported, gray=display-only)

**AC-004**: Given XML loaded, When `xml validate` executed, Then detect circular dependencies, date errors, reference errors

**AC-005**: Given XML loaded and project selected, When `xml import project` executed, Then create/update all entities via wfp-poc API

**AC-006**: Given import fails at task 45/156, When rollback triggered, Then delete all 44 created tasks and restore database state

**AC-007**: Given XML with validation errors, When `xml validate` executed, Then exit with code 2 and display error report

**AC-008**: Given XML loaded, When `xml import task <id>` executed, Then import single task only (for debugging)

**AC-009**: Given large XML (1000 tasks), When parsing, Then complete in <5 seconds

**AC-010**: Given XML with circular dependency, When `xml validate` executed, Then detect and report cycle path

---

### 11.2. Service Commands (AC-011 to AC-020)

**AC-011**: Given valid JWT, When `service list projects` executed, Then display table with all accessible projects

**AC-012**: Given project ID, When `service select <id>` executed, Then set active project and display confirmation

**AC-013**: Given project selected, When `service show project` executed, Then display full project metadata including version

**AC-014**: Given project selected, When `service list tasks` executed, Then display tasks for selected project only

**AC-015**: Given task ID, When `service show task <id>` executed, Then display task with dependencies and assignments

**AC-016**: Given no project selected, When `xml import project` executed, Then reject with error "No project selected. Use 'service select <id>' first."

**AC-017**: Given API timeout (30s), When service command executed, Then display error and exit code 1

**AC-018**: Given invalid JWT, When service command executed, Then display authentication error

**AC-019**: Given network disconnected, When service command executed, Then display connection error and retry suggestion

**AC-020**: Given project selected, When user exits shell, Then session state lost (no persistent state file)

---

### 11.3. Excel Commands (AC-021 to AC-030)

**AC-021**: Given expenses Excel file, When `excel load <file> --type expenses` executed, Then validate columns and display summary

**AC-022**: Given expenses with same reference, When loading, Then group by reference and sum amounts

**AC-023**: Given expenses loaded, When `excel list expenses` executed, Then display table with grouped entries

**AC-024**: Given expenses loaded and project selected, When `excel import expenses` executed, Then create expenses in ADD mode

**AC-025**: Given RAE Excel file, When `excel load <file> --type rae` executed, Then validate milestone names exist in wfp-poc

**AC-026**: Given RAE with task breakdown, When validating, Then verify sum equals remaining_amount

**AC-027**: Given expenses with missing required column, When loading, Then reject with validation error

**AC-028**: Given Excel file with 342 rows, When parsing, Then complete in <3 seconds

**AC-029**: Given expenses import in progress, When failure occurs, Then rollback created expenses

**AC-030**: Given RAE import, When milestone already has RAE, Then update (UPSERT mode)

---

### 11.4. Validation Rules (AC-031 to AC-040)

**AC-031**: Given XML with task A→B→C→A, When validating, Then detect circular dependency A→B→C→A

**AC-032**: Given milestone with no date, When validating, Then report error with task ID and line number

**AC-033**: Given task with Finish < Start, When validating, Then report date error

**AC-034**: Given XML version 14 and DB version 15, When validating, Then detect version conflict and reject import

**AC-035**: Given task referencing non-existent predecessor, When validating, Then report reference error

**AC-036**: Given 1000-task project, When validating, Then complete in <10 seconds

**AC-037**: Given validation with 2 errors and 5 warnings, When reporting, Then display summary "2 errors, 5 warnings"

**AC-038**: Given validation errors, When `--strict` flag used, Then treat warnings as errors

**AC-039**: Given milestone date shift > 7 days, When validating, Then display warning (not error)

**AC-040**: Given all validations pass, When `xml validate` executed, Then exit with code 0

---

### 11.5. Error Handling (AC-041 to AC-050)

**AC-041**: Given import fails, When rollback executes, Then delete all entities created in current session only

**AC-042**: Given file not found, When loading, Then display error "File not found: <path>" and exit code 1

**AC-043**: Given API returns 500, When importing, Then display error "API server error. Contact administrator."

**AC-044**: Given import with `--continue-on-error`, When error occurs, Then skip failed entity and continue

**AC-045**: Given import without `--continue-on-error`, When error occurs, Then stop and rollback

**AC-046**: Given malformed XML, When loading, Then display parse error with line number

**AC-047**: Given long import (>1 min), When executing, Then display progress bar with percentage

**AC-048**: Given validation report, When errors found, Then include line numbers for all errors

**AC-049**: Given JWT expired, When API call made, Then display authentication error and suggest token refresh

**AC-050**: Given network timeout, When retrying, Then attempt 3 times before failing

---

## 12. Test Automation Strategy

### 12.1. Test Levels

**Unit Tests** (`tests/unit/`):
- Mock wfp-poc API responses
- Test parsers (MS Project XML, Excel)
- Test validators (circular dependency, dates, references)
- Test models (pydantic schemas)
- Framework: pytest
- Coverage target: >80% for parsers and validators

**Integration Tests** (`tests/integration/`):
- Real wfp-poc service (via docker-compose)
- Test full import workflows
- Test rollback scenarios
- Test multi-entity operations
- Framework: pytest with real API calls

---

### 12.2. Test Fixtures

**Location**: `tests/fixtures/`

**Required Fixtures**:
- `simple_project.xml`: 10 tasks, 3 resources, 5 dependencies (happy path)
- `large_project.xml`: 1000 tasks (performance test)
- `circular_dependency.xml`: Tasks with A→B→C→A cycle
- `invalid_dates.xml`: Tasks with Finish < Start
- `missing_references.xml`: Dependencies to non-existent tasks
- `expenses_valid.xlsx`: 50 expenses, mixed purchases/time tracking
- `expenses_grouped.xlsx`: Multiple rows with same reference
- `rae_valid.xlsx`: 5 milestones with task breakdowns
- `rae_invalid_sum.xlsx`: Task breakdown sum ≠ remaining_amount

---

### 12.3. CI/CD Integration

**GitHub Actions Workflow**:
```yaml
name: poc-import Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python 3.11
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: pip install -e .[dev]
      - name: Run unit tests
        run: pytest tests/unit/ -v --cov=poc_import
      - name: Start wfp-poc service
        run: docker-compose up -d
      - name: Run integration tests
        run: pytest tests/integration/ -v
      - name: Check coverage
        run: coverage report --fail-under=80
```

---

### 12.4. Mock Strategy

**Unit Tests** - Mock `WfpApiClient`:
```python
@pytest.fixture
def mock_api_client(mocker):
    client = mocker.Mock(spec=WfpApiClient)
    client.list_projects.return_value = [
        {"id": "123e...", "name": "Project A", "task_count": 156}
    ]
    return client
```

**Integration Tests** - Use real API:
```python
@pytest.fixture(scope="session")
def wfp_api_client():
    # Wait for service to be ready
    wait_for_service("http://localhost:5000/health", timeout=30)
    return WfpApiClient(base_url="http://localhost:5000")
```

---

## 13. Dependencies & External Integrations

### 13.1. External Systems - wfp-poc API

**EXT-001**: wfp-poc API
- **Purpose**: Target system for data import
- **Authentication**: JWT Bearer token in `Authorization: Bearer <token>` header
- **Base URL**: Configurable via `--env` flag (dev: http://localhost:5000, staging/prod: https://wfp-poc.waterfall-services.io)
- **SLA**: <500ms response time (p95), 99.9% uptime
- **Rate Limits**: 100 requests/minute (standard), 10 requests/minute (bulk endpoints)

#### V1 Endpoints (Implemented/Required by poc-import V1)

The tables below list endpoints that poc-import V1 SHALL rely on.

##### Create Operations (Import)

| Endpoint | Method | Purpose | Used By |
|----------|--------|---------|----------|
| `/{version}/projects` | POST | Create project | `xml import create-project` (V1) |
| `/{version}/projects/{project_id}/tasks` | POST | Create task | `xml import project`, `xml import task <id>` |
| `/{version}/resources` | POST | Create resource | `xml import project` |
| `/{version}/projects/{project_id}/assignments` | POST | Create assignment | `xml import project` |
| `/{version}/projects/{project_id}/milestones` | POST | Create milestone | `xml import project` |
| `/{version}/projects/{project_id}/expenses` | POST | Create expense | `excel import expenses` |
| `/{version}/milestones/{milestone_id}/rae` | POST | Update milestone RAE | `excel import rae` |

##### Read Operations (Query)

| Endpoint | Method | Purpose | Used By |
|----------|--------|---------|----------|
| `/{version}/projects` | GET | List projects | `service list projects` |
| `/{version}/projects/{id}` | GET | Get project details | `service show project` |
| `/{version}/projects/{project_id}/tasks` | GET | List tasks | `service list tasks` |
| `/{version}/projects/{project_id}/tasks/{id}` | GET | Get task details | `service show task <id>` |
| `/{version}/resources` | GET | List resources (company-scoped) | `service list resources` |
| `/{version}/resources/{id}` | GET | Get resource details | `service show resource <id>` |
| `/{version}/projects/{project_id}/assignments` | GET | List assignments | `service list assignments` |
| `/{version}/projects/{project_id}/assignments/{id}` | GET | Get assignment details | `service show assignment <id>` |

##### Delete Operations (Rollback)

| Endpoint | Method | Purpose | Used By |
|----------|--------|---------|----------|
| `/{version}/projects/{id}` | DELETE | Delete project (no related entities) | Rollback on failed import |
| `/{version}/projects/{project_id}/tasks/{id}` | DELETE | Delete task (cascades to assignments) | Rollback on failed import |
| `/{version}/resources/{id}` | DELETE | Delete resource (no active assignments) | Rollback on failed import |
| `/{version}/projects/{project_id}/assignments/{id}` | DELETE | Delete assignment | Rollback on failed import |
| `/{version}/projects/{project_id}/milestones/{id}` | DELETE | Delete milestone (no expenses/RAE) | Rollback on failed import |
| `/{version}/projects/{project_id}/expenses/{id}` | DELETE | Delete expense | Rollback on failed import |

#### Out of V1 Scope (Future/Optional Endpoints)

The endpoints below SHALL be treated as **out of V1 scope** even if available in the API. They MAY be implemented in a later version of poc-import.

| Endpoint | Method | Purpose | Planned Use |
|----------|--------|---------|-------------|
| `/{version}/projects/{project_id}/tasks/bulk` | POST | Bulk create tasks | V3 optimization to reduce rate-limit impact |
| `/{version}/projects/{project_id}/tasks/sync` | PUT | Sync tasks (re-import / upsert) | V2 re-import mode |
| `/{version}/projects/{project_id}/expenses/bulk` | POST | Bulk create expenses | V3 optimization |
| `/{version}/projects/{project_id}/milestones` | GET | List milestones | V2 service query convenience |
| `/{version}/projects/{project_id}/expenses` | GET | List expenses | V2 service query convenience |

**Note on Rollback**: poc-import tracks all entity UUIDs created during import session. On failure, DELETE requests are sent in reverse order (assignments → tasks → resources → project) to maintain referential integrity.

#### Response Format

All endpoints follow Waterfall standard response format:

**Single Resource (201 Created, 200 OK):**
```json
{
  "data": {
    "id": "a1b2c3d4-e5f6-4a5b-8c9d-0e1f2a3b4c5d",
    "name": "Project Name",
    "created_at": "2026-01-18T10:30:00Z",
    "updated_at": "2026-01-18T10:30:00Z"
  },
  "message": "Project created successfully"
}
```

**Collection (200 OK):**
```json
{
  "data": [
    {"id": "...", "name": "Project A"},
    {"id": "...", "name": "Project B"}
  ],
  "page": 1,
  "per_page": 20,
  "total": 150,
  "total_pages": 8
}
```

**Error (4xx, 5xx):**
```json
{
  "message": "Validation failed",
  "errors": {
    "name": ["Field is required"],
    "start_date": ["Invalid date format"]
  },
  "correlation_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479"
}
```

---

### 13.1.1. JSON Output Examples

All `service list` and `service show` commands support `--output json` flag.

**`service list projects --output json`:**
```json
{
  "data": [
    {
      "id": "a1b2c3d4-e5f6-4a5b-8c9d-0e1f2a3b4c5d",
      "company_id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "Waterfall Platform Development",
      "code": "G.PRJ.12345",
      "start_date": "2026-01-15T09:00:00Z",
      "finish_date": "2026-12-31T18:00:00Z",
      "status": "active",
      "budget": 1500000.00,
      "currency_code": "EUR",
      "ms_project_save_version": 14,
      "created_at": "2026-01-10T10:00:00Z",
      "updated_at": "2026-01-18T09:15:00Z"
    },
    {
      "id": "b2c3d4e5-f6a7-4b5c-9d0e-1f2a3b4c5d6e",
      "company_id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "Mobile App Redesign",
      "code": "G.PRJ.98765",
      "start_date": "2025-11-01T09:00:00Z",
      "finish_date": "2026-06-30T18:00:00Z",
      "status": "active",
      "budget": 750000.00,
      "currency_code": "EUR",
      "ms_project_save_version": 8,
      "created_at": "2025-10-15T10:00:00Z",
      "updated_at": "2026-01-12T14:20:00Z"
    }
  ],
  "page": 1,
  "per_page": 20,
  "total": 12,
  "total_pages": 1
}
```

**`service show project --output json`:**
```json
{
  "data": {
    "id": "a1b2c3d4-e5f6-4a5b-8c9d-0e1f2a3b4c5d",
    "company_id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "Waterfall Platform Development",
    "code": "G.PRJ.12345",
    "title": "Infrastructure Modernization",
    "description": "Complete platform rewrite with microservices architecture",
    "start_date": "2026-01-15T09:00:00Z",
    "finish_date": "2026-12-31T18:00:00Z",
    "status": "active",
    "budget": 1500000.00,
    "currency_code": "EUR",
    "ms_project_uid": "1",
    "ms_project_guid": "{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}",
    "ms_project_save_version": 14,
    "creation_date": "2025-12-01T10:00:00Z",
    "last_saved_date": "2026-01-17T15:30:00Z",
    "minutes_per_day": 420,
    "minutes_per_week": 2100,
    "days_per_month": 20,
    "created_at": "2026-01-10T10:00:00Z",
    "updated_at": "2026-01-18T09:15:00Z"
  }
}
```

**`service list tasks --output json`:**
```json
{
  "data": [
    {
      "id": "c3d4e5f6-a7b8-4c5d-0e1f-2a3b4c5d6e7f",
      "project_id": "a1b2c3d4-e5f6-4a5b-8c9d-0e1f2a3b4c5d",
      "parent_id": null,
      "ms_project_uid": 1,
      "ms_project_guid": "{42ABC123-4567-890A-BCDE-F12345678901}",
      "wbs": "1",
      "name": "Waterfall Platform",
      "start": "2026-01-15T09:00:00Z",
      "finish": "2026-12-31T18:00:00Z",
      "duration_minutes": 105000,
      "percent_complete": 23,
      "is_milestone": false,
      "is_summary": true,
      "is_critical": false,
      "status": "in_progress",
      "created_at": "2026-01-10T11:00:00Z",
      "updated_at": "2026-01-18T09:30:00Z"
    },
    {
      "id": "d4e5f6a7-b8c9-4d5e-1f2a-3b4c5d6e7f8a",
      "project_id": "a1b2c3d4-e5f6-4a5b-8c9d-0e1f2a3b4c5d",
      "parent_id": "c3d4e5f6-a7b8-4c5d-0e1f-2a3b4c5d6e7f",
      "ms_project_uid": 2,
      "ms_project_guid": "{5DEF6789-0ABC-4567-89AB-CDEF01234567}",
      "wbs": "1.1",
      "name": "Phase 1: Foundation",
      "start": "2026-01-15T09:00:00Z",
      "finish": "2026-03-31T18:00:00Z",
      "duration_minutes": 31920,
      "percent_complete": 45,
      "is_milestone": false,
      "is_summary": false,
      "is_critical": true,
      "status": "in_progress",
      "created_at": "2026-01-10T11:05:00Z",
      "updated_at": "2026-01-18T09:35:00Z"
    }
  ],
  "page": 1,
  "per_page": 20,
  "total": 156,
  "total_pages": 8
}
```

**`service show task <id> --output json`:**
```json
{
  "data": {
    "id": "d4e5f6a7-b8c9-4d5e-1f2a-3b4c5d6e7f8a",
    "project_id": "a1b2c3d4-e5f6-4a5b-8c9d-0e1f2a3b4c5d",
    "parent_id": "c3d4e5f6-a7b8-4c5d-0e1f-2a3b4c5d6e7f",
    "ms_project_uid": 42,
    "ms_project_guid": "{42ABC123-4567-890A-BCDE-F12345678901}",
    "wbs": "1.2.3.1",
    "name": "Backend API - Authentication Module",
    "outline_level": 4,
    "start": "2026-02-15T09:00:00Z",
    "finish": "2026-03-10T18:00:00Z",
    "duration_minutes": 10080,
    "percent_complete": 35,
    "is_milestone": false,
    "is_summary": false,
    "is_critical": true,
    "status": "in_progress",
    "actual_start": "2026-02-15T09:00:00Z",
    "actual_finish": null,
    "actual_duration_minutes": 3528,
    "predecessors": [
      {
        "predecessor_task_id": "e5f6a7b8-c9d0-4e5f-2a3b-4c5d6e7f8a9b",
        "predecessor_wbs": "1.2.3",
        "predecessor_name": "Backend API - Core Framework",
        "link_type": "FS",
        "lag_minutes": 0
      },
      {
        "predecessor_task_id": "f6a7b8c9-d0e1-4f5a-3b4c-5d6e7f8a9b0c",
        "predecessor_wbs": "1.2.2",
        "predecessor_name": "Database Schema Design",
        "link_type": "FS",
        "lag_minutes": 840
      }
    ],
    "successors": [
      {
        "successor_task_id": "a7b8c9d0-e1f2-4a5b-4c5d-6e7f8a9b0c1d",
        "successor_wbs": "1.2.4",
        "successor_name": "API Testing",
        "link_type": "FS",
        "lag_minutes": 0
      }
    ],
    "assignments": [
      {
        "id": "b8c9d0e1-f2a3-4b5c-5d6e-7f8a9b0c1d2e",
        "resource_id": "f6a7b8c9-d0e1-4f5a-3b4c-5d6e7f8a9b0c",
        "resource_name": "John Doe",
        "work_hours": "PT80H0M0S",
        "percent_allocation": 100,
        "cost": 6800.00
      },
      {
        "id": "c9d0e1f2-a3b4-4c5d-6e7f-8a9b0c1d2e3f",
        "resource_id": "a1b2c3d4-e5f6-4a5b-8c9d-0e1f2a3b4c5d",
        "resource_name": "Jane Smith",
        "work_hours": "PT40H0M0S",
        "percent_allocation": 50,
        "cost": 3800.00
      }
    ],
    "created_at": "2026-01-10T11:45:00Z",
    "updated_at": "2026-01-18T10:15:00Z"
  }
}
```

**`excel list expenses --output json`:**
```json
{
  "data": [
    {
      "id": 1,
      "reference_number": "4500123456",
      "date": "2025-01-15",
      "amount": 12500.00,
      "category": "procurement",
      "description": "Serveurs Dell PowerEdge R750 (x2)",
      "vendor_name": "Dell Technologies France",
      "otp_element": "G.PRJ.12345/INFRA",
      "fiscal_year": 2025,
      "period": 1
    },
    {
      "id": 2,
      "reference_number": "4500123457",
      "date": "2025-01-20",
      "amount": 3450.00,
      "category": "procurement",
      "description": "Licences logicielles Microsoft",
      "vendor_name": "Microsoft France",
      "otp_element": "G.PRJ.12345/INFRA",
      "fiscal_year": 2025,
      "period": 1
    },
    {
      "id": 3,
      "reference_number": null,
      "date": "2025-01-25",
      "amount": 850.00,
      "category": "labor",
      "description": "John Doe (80h)",
      "resource_name": "John Doe",
      "resource_matricule": "EMP-12345",
      "otp_element": "G.PRJ.12345/DEV",
      "fiscal_year": 2025,
      "period": 1
    }
  ],
  "total": 342,
  "total_amount": 1245678.50,
  "currency": "EUR",
  "unique_references": 298,
  "grouped_count": 44
}
```

**`excel list rae --output json`:**
```json
{
  "data": [
    {
      "id": 1,
      "milestone_name": "Phase 1: Foundation",
      "remaining_amount": 125000.00,
      "forecast_date": "2026-03-31",
      "task_breakdown": [
        {"task_name": "Infrastructure Setup", "amount": 45000.00},
        {"task_name": "Database Implementation", "amount": 32500.00},
        {"task_name": "API Core", "amount": 28000.00},
        {"task_name": "Testing", "amount": 19500.00}
      ],
      "task_count": 12,
      "breakdown_sum": 125000.00
    },
    {
      "id": 2,
      "milestone_name": "Phase 2: Core Development",
      "remaining_amount": 345000.00,
      "forecast_date": "2026-06-30",
      "task_breakdown": [
        {"task_name": "Backend API Framework", "amount": 45000.00},
        {"task_name": "Database Implementation", "amount": 32500.00},
        {"task_name": "Authentication Module", "amount": 28000.00},
        {"task_name": "Frontend Core", "amount": 55000.00}
      ],
      "task_count": 28,
      "breakdown_sum": 345000.00
    }
  ],
  "total": 12,
  "total_rae": 854321.50,
  "currency": "EUR"
}
```

---

### 13.2. Technology Platform Dependencies

**PLT-001**: Python 3.11+
- **Rationale**: Type hints with `|` union syntax, improved performance
- **Installation**: `sudo apt install python3.11` or `brew install python@3.11`

**PLT-002**: Core Libraries
- **lxml>=4.9.0**: XML parsing with XPath support
- **openpyxl>=3.1.0**: Excel .xlsx file parsing
- **click>=8.1.0**: CLI framework
- **click-shell>=2.1**: Interactive REPL
- **rich>=13.0.0**: Terminal formatting (tables, progress bars, colors)
- **requests>=2.31.0**: HTTP API client
- **pydantic>=2.5.0**: Data validation and models

---

### 13.3. Development Roadmap

**V1 (MVP) - Current Specification**:
- xml load/list/show commands
- xml validate (dry-run)
- xml import project (full import) + rollback on failure
- xml import task <id> (debugging) + --dry-run
- `--continue-on-error` flag
- service list/select/show commands
- Excel load/list/show/import for expenses and RAE
- Circular dependency detection
- Date validation
- Reference validation
- Version conflict detection (best-effort; requires Project.ms_project_save_version)
- Multi-environment support (dev/staging/prod)

**Future (Post-V1) - Advanced Import & Performance**:
- Re-import mode (upsert/sync) using `/{version}/projects/{project_id}/tasks/sync`
- Bulk API calls using `/{version}/projects/{project_id}/tasks/bulk` and `/{version}/projects/{project_id}/expenses/bulk`
- Selective import flags (e.g., `--with-dependencies`, `--with-assignments`)
- Additional service query convenience commands (e.g., list milestones/expenses)
- EVM-specific validation rules (milestone pose constraints, shift thresholds)

**V4 - Production Readiness**:
- Hardened environment configuration (packaging, deployment defaults)
- Enhanced error recovery
- Detailed audit logging
- Performance optimization (>10000 tasks)
- Comprehensive test coverage (>90%)

**Phase 2 - Service Mode** (Future):
- REST API endpoints for programmatic access
- Guardian integration (RBAC)
- Identity service integration
- MCP (Model Context Protocol) server for AI integration
- Web UI for file uploads
- Scheduled/automated imports

---

### 13.4. Performance Benchmarks

Targeted performance benchmarks to validate during implementation and testing.

#### XML Parsing Performance

| Task Count | File Size | Expected Parse Time | Max Memory Usage | Test Status |
|------------|-----------|---------------------|------------------|-------------|
| 10 | ~50 KB | <0.1s | 20 MB | ✓ Pass |
| 100 | ~500 KB | <0.5s | 50 MB | ✓ Pass |
| 500 | ~2.5 MB | <2s | 150 MB | ⚠ Monitor |
| 1000 | ~5 MB | <5s | 250 MB | Target (PERF-005) |
| 5000 | ~25 MB | <25s | 1 GB | ⚠ Degraded |
| 10000 | ~50 MB | <60s | 2 GB | ❌ Out of scope (V1) |

**Notes**:
- Includes parsing Project, Tasks, Resources, Assignments, Dependencies
- Memory includes lxml tree + pydantic models
- Tested on: Intel Core i7-10750H, 16GB RAM, Python 3.11

#### Excel Parsing Performance

| Row Count | File Size | Expected Parse Time | Max Memory Usage | Test Status |
|-----------|-----------|---------------------|------------------|-------------|
| 50 | ~30 KB | <0.1s | 15 MB | ✓ Pass |
| 100 | ~50 KB | <0.2s | 25 MB | ✓ Pass |
| 500 | ~200 KB | <1s | 80 MB | ✓ Pass |
| 1000 | ~400 KB | <3s | 150 MB | Target (AC-028) |
| 5000 | ~2 MB | <15s | 500 MB | ⚠ Monitor |
| 10000 | ~4 MB | <30s | 1 GB | ❌ Out of scope (V1) |

**Notes**:
- Includes column validation, type conversion, grouping logic
- Memory includes openpyxl workbook + pydantic models

#### Validation Performance

| Validation Type | Task Count | Expected Time | Test Status |
|-----------------|------------|---------------|-------------|
| Circular dependency (DFS) | 100 | <0.5s | ✓ Pass |
| Circular dependency (DFS) | 1000 | <5s | Target |
| Date validations | 1000 | <1s | ✓ Pass |
| Reference validations | 1000 | <2s | ✓ Pass |
| Full validation suite | 100 | <1s | ✓ Pass |
| Full validation suite | 1000 | <10s | Target (PERF-006) |

**Notes**:
- Circular dependency uses depth-first search (worst case: O(V+E))
- Reference validation uses hash lookups (O(1) per check)

#### Import Performance (V1: 1 API call per entity)

| Entity Count | Expected Time | API Calls | Network Impact | Test Status |
|--------------|---------------|-----------|----------------|-------------|
| 10 tasks | <5s | 10 | Low | ✓ Pass |
| 100 tasks | <30s | 100 | Medium | Target |
| 500 tasks | <2.5min | 500 | High | ⚠ Monitor |
| 1000 tasks | <5min | 1000 | Very High | Target (V1 max) |

**Assumptions**:
- Average API response time: 300ms (p50)
- Sequential API calls in V1 (no parallelization)
- Progress bar updates every 10 entities

**Future Optimization Target (Bulk API calls; out of V1 scope)**:

| Entity Count | Bulk Size | Expected Time | API Calls | Improvement |
|--------------|-----------|---------------|-----------|-------------|
| 1000 tasks | 50 | <30s | 20 | 10x faster |
| 1000 tasks | 100 | <20s | 10 | 15x faster |

#### End-to-End Workflow Performance

| Workflow | Task Count | Expected Total Time | Steps | Test Status |
|----------|------------|---------------------|-------|-------------|
| **Complete Import (V1)** | 100 | <45s | Load (0.5s) + Validate (1s) + Import (30s) + Verify (5s) | Target |
| **Complete Import (V1)** | 1000 | <6min | Load (5s) + Validate (10s) + Import (5min) + Verify (10s) | Target |
| **Re-import (Future)** | 100 | <40s | Load + Validate + Sync (update mode) + Verify | Future |
| **Debug Single Task (V1)** | 1 | <3s | Load + Validate (optional) + Import (single task) + Verify | Target |

#### Memory Usage Guidelines

| Scenario | Expected Memory | Max Acceptable | Notes |
|----------|-----------------|----------------|-------|
| CLI idle | <50 MB | 100 MB | Python runtime + libraries |
| XML loaded (100 tasks) | <100 MB | 200 MB | lxml tree + models |
| XML loaded (1000 tasks) | <300 MB | 500 MB | Target (PERF) |
| Excel loaded (1000 rows) | <200 MB | 400 MB | openpyxl workbook |
| Import in progress | +100 MB | +200 MB | Rollback tracking |

#### Rate Limiting Impact

**wfp-poc API Limits**:
- Standard endpoints: 100 requests/minute
- Bulk endpoints: 10 requests/minute

**V1 Sequential Import** (1 call per entity):
- 100 tasks → 100 calls → 1 minute (hitting rate limit)
- 1000 tasks → 1000 calls → 10 minutes (rate limited)

**Future Bulk Import** (100 entities per call):
- 1000 tasks → 10 calls → <1 minute (within limit)

**Mitigation Strategies**:
- V1: Display rate limit warnings, suggest smaller batches
- Future: Implement exponential backoff on 429 errors
- Future: Use bulk endpoints to reduce API calls

#### Performance Degradation Thresholds

| Metric | Good | Acceptable | Degraded | Action |
|--------|------|------------|----------|--------|
| Parse time (1000 tasks) | <3s | <5s | >5s | Optimize XML parser |
| Validation time (1000 tasks) | <5s | <10s | >10s | Optimize validation algorithms |
| Import time (100 tasks, V1) | <20s | <30s | >30s | Document in limitations |
| Memory usage (1000 tasks) | <200 MB | <300 MB | >500 MB | Implement streaming |
| API latency (p95) | <300ms | <500ms | >1s | Check network/wfp-poc health |

---

### 13.5. Logging Strategy

**LOG-001**: poc-import SHALL use Python `logging` module with rich handler for formatted console output

**LOG-002**: poc-import SHALL support `--log-level` CLI flag with values: debug, info, warning, error, critical (default: info)

**LOG-003**: poc-import SHALL write logs to console (stdout for info/debug, stderr for warning/error/critical)

**LOG-004**: poc-import SHALL NOT write logs to file in V1 (console only)

#### Log Levels

| Level | When to Use | Example |
|-------|-------------|----------|
| DEBUG | Internal details for troubleshooting | "Parsing XML element: <Task UID='42'>" |
| INFO | Normal operations | "✓ XML loaded: 156 tasks, 23 resources" |
| WARNING | Unexpected but recoverable | "⚠ Task #42 has no resource assignments" |
| ERROR | Operation failed | "✗ Import failed: API returned 500" |
| CRITICAL | System failure | "✗ Fatal error: Out of memory" |

#### What to Log

**Command Execution:**
```python
LOG.info("Executing command: xml load %s", filepath)
LOG.info("✓ XML loaded: %s (156 tasks, 23 resources)", filepath)
```

**API Requests (DEBUG level):**
```python
LOG.debug("API Request: POST %s", url)
LOG.debug("Request headers: %s", headers)  # Mask Authorization token
LOG.debug("Request body: %s", body[:200])  # Truncate to 200 chars
LOG.debug("API Response: %d %s (%.2fs)", status_code, reason, elapsed)
```

**Validation Results:**
```python
LOG.info("Running validation checks...")
LOG.warning("VAL-002: Milestone #5 has no date (line 234)")
LOG.error("VAL-001: Circular dependency detected: #42 → #45 → #48 → #42")
LOG.info("Validation Summary: 42 passed, 6 warnings, 2 errors")
```

**Import Progress:**
```python
LOG.info("Starting import: 156 tasks, 23 resources, 89 assignments")
LOG.info("Importing tasks... 45/156 (29%)")  # Every 10 entities
LOG.info("✓ Import completed: 156 tasks, 23 resources, 89 assignments")
```

**Errors:**
```python
LOG.error("File not found: %s", filepath)
LOG.error("API error: %s (correlation_id: %s)", error_message, correlation_id)
LOG.error("Rollback initiated: deleting %d created entities", len(created_uuids))
```

#### What NOT to Log

**SEC-009**: poc-import SHALL NOT log sensitive data:
- ❌ JWT tokens (full or partial)
- ❌ API secret keys
- ❌ User passwords
- ❌ Full request/response bodies containing PII (names, emails)

**Examples of Safe Logging:**
```python
# ✓ GOOD: Mask token
LOG.debug("Authorization: Bearer %s...", token[:8])

# ✗ BAD: Full token
LOG.debug("Authorization: Bearer %s", token)

# ✓ GOOD: Correlation ID only
LOG.error("API error 500 (correlation_id: %s)", correlation_id)

# ✗ BAD: Full error response with PII
LOG.error("API error: %s", full_response_body)
```

#### Correlation ID Tracking

**LOG-005**: poc-import SHALL generate correlation_id (UUID v4) for each command execution

**LOG-006**: poc-import SHALL include correlation_id in all log messages

**LOG-007**: poc-import SHALL send correlation_id to wfp-poc API via `X-Correlation-ID` header

**Format:**
```
2026-01-18 10:30:45 [INFO] [corr:f47ac10b-58cc] Executing command: xml load project.xml
2026-01-18 10:30:46 [DEBUG] [corr:f47ac10b-58cc] API Request: POST /v0/projects
2026-01-18 10:30:47 [INFO] [corr:f47ac10b-58cc] ✓ Project created: Waterfall Platform (id: a1b2c3d4...)
```

#### Log Formatting

**Console Output (rich handler):**
- Color coding: INFO (blue), WARNING (yellow), ERROR (red)
- Timestamps: ISO 8601 format
- Correlation ID: `[corr:uuid-prefix]`
- Progress bars: Separate from logs (rich.progress)

**Example:**
```
2026-01-18 10:30:45 [INFO] Executing command: xml load project.xml
2026-01-18 10:30:46 [INFO] ✓ XML loaded: Waterfall Platform Development
2026-01-18 10:30:46 [INFO]   - Tasks: 156 (12 milestones)
2026-01-18 10:30:46 [INFO]   - Resources: 23
2026-01-18 10:30:46 [INFO]   - Dependencies: 134
2026-01-18 10:30:47 [WARNING] ⚠ 2 tasks have no resource assignments (#23, #45)
2026-01-18 10:30:48 [INFO] Use 'xml validate' to check for errors
```

#### Debug Mode Details

**`--log-level debug` outputs:**
- XML element parsing details
- Excel row processing
- API request/response details (masked)
- Validation check execution
- State changes (project selected, file loaded)
- Memory usage stats

**Example:**
```
2026-01-18 10:30:45 [DEBUG] Parsing XML: /path/to/project.xml
2026-01-18 10:30:45 [DEBUG] Found Project element: Name=Waterfall Platform
2026-01-18 10:30:45 [DEBUG] Parsing Tasks: found 156 <Task> elements
2026-01-18 10:30:45 [DEBUG] Task[0]: UID=1, Name=Waterfall Platform, WBS=1
2026-01-18 10:30:45 [DEBUG] Task[1]: UID=2, Name=Phase 1: Foundation, WBS=1.1
...
2026-01-18 10:30:46 [DEBUG] Memory usage: 145 MB (lxml: 85 MB, models: 60 MB)
2026-01-18 10:30:47 [DEBUG] API Request: POST https://wfp-poc.waterfall.io/v0/projects
2026-01-18 10:30:47 [DEBUG] Request headers: {"Authorization": "Bearer eyJhbGc...", "X-Correlation-ID": "f47ac10b..."}
2026-01-18 10:30:47 [DEBUG] Request body (truncated): {"name": "Waterfall Platform", "start_date": ...}
2026-01-18 10:30:48 [DEBUG] API Response: 201 Created (0.35s)
2026-01-18 10:30:48 [DEBUG] Response body: {"data": {"id": "a1b2c3d4...", ...}
```

#### Performance Logging

**LOG-008**: poc-import SHALL log operation durations for operations >1s

**Example:**
```
2026-01-18 10:30:45 [INFO] Parsing XML... (1000 tasks)
2026-01-18 10:30:49 [INFO] ✓ Parsing completed in 4.2s
2026-01-18 10:30:49 [INFO] Running validation checks...
2026-01-18 10:30:58 [INFO] ✓ Validation completed in 8.7s (42 passed, 2 errors)
2026-01-18 10:30:58 [INFO] Starting import...
2026-01-18 10:35:23 [INFO] ✓ Import completed in 4m 25s (1000 entities created)
```

---

## 14. Related Specifications

- [architecture-project-management-evm.md](../architecture-project-management-evm.md): EVM calculation methodology
- [integration-wfp-services.md](../integration-wfp-services.md): Waterfall services integration patterns
- [wfp-poc OpenAPI Specification](../../openapi/wfp-poc-api-bundle.yaml): wfp-poc API contract
- [poc-export Specification](../poc-export/): Complementary export tool specification (to be created)

---

## 15. Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-18 | Waterfall Team | Initial specification created from brainstorming session |

---

**End of Specification**
