---
title: poc-export - MS Project Export and EVM Reporting Service Specification
version: 1.0
date_created: 2026-01-10
last_updated: 2026-01-10
owner: Waterfall Team
tags: [tool, poc-export, ms-project, excel, reporting, blueprints, visualization]
---

# poc-export - MS Project Export and EVM Reporting Service Specification

## 1. Purpose & Scope

### Purpose

`poc-export` is a Flask-based export and reporting service that generates MS Project XML snapshots, Excel EVM reports, and Blueprint-based chart visualizations from wfp-poc data. It provides both a command-line interface (CLI) for batch exports and a web interface (Blueprints) for interactive chart viewing, serving as the primary data extraction and visualization tool for the Waterfall project management ecosystem.

### Scope

**In Scope:**
- **MS Project XML Export**: Generate MS Project 2010+ XML from wfp-poc data (tasks, milestones, resources, assignments)
- **Excel EVM Export**: Generate Excel spreadsheets with EVM metrics (BAC, PV, AC, EV, CV, SV, CPI, SPI, forecasts)
- **Blueprint Visualization**: Flask Blueprint-based web pages displaying charts (Earned Value curves, milestone status, expense breakdown)
- Preserve GUID/UID mappings for round-trip compatibility (import → export → edit → reimport)
- Support CLI for automated exports (CI/CD, scheduled jobs)
- Support web interface for interactive chart viewing
- Provide detailed export reports and summaries

**Out of Scope:**
- MS Project binary .mpp file generation (export XML only, convert with MS Project if needed)
- Real-time synchronization (batch export only)
- Data import (handled by poc-import service)
- Full-featured dashboard/SPA (lightweight Blueprint views only)
- Authentication/authorization (delegates to wfp-poc API via JWT)

### Intended Audience

- Project Managers exporting planning data to MS Project
- Executives viewing EVM charts and reports
- Financial Controllers exporting expense data to Excel
- System Administrators automating export workflows
- Developers integrating poc-export into pipelines

### Assumptions

- wfp-poc API is accessible and responsive
- User has valid JWT token with appropriate Guardian permissions (READ)
- Exported MS Project XML can be opened in MS Project 2010+
- Excel files target Microsoft Excel 2016+ or compatible (LibreOffice Calc)
- Charts rendered server-side (no JavaScript frameworks, use matplotlib/plotly)

## 2. Definitions

| Term | Definition |
|------|------------|
| **Snapshot Export** | Point-in-time export of project data (tasks, resources, dates, actuals) |
| **Round-Trip Compatibility** | Exported XML can be imported back into wfp-poc without data loss |
| **GUID Preservation** | ms_project_guid values maintained in export for reconciliation |
| **UID Preservation** | ms_project_uid values maintained in export for MS Project display consistency |
| **EVM Snapshot** | Historical EVM metrics at a specific date (from evm_snapshots table) |
| **Blueprint** | Flask Blueprint for organizing web routes and views |
| **Server-Side Rendering** | HTML generated on server (not SPA, minimal JavaScript) |
| **Chart Generation** | matplotlib or plotly generating PNG/SVG images or HTML plots |
| **Baseline Preservation** | Original planned dates (baseline) vs current planned dates vs actuals |
| **Excel Template** | Pre-formatted Excel with formulas and charts (populated with data) |

## 3. Requirements, Constraints & Guidelines

### Functional Requirements (REQ-xxx)

#### MS Project XML Export

- **REQ-001**: poc-export SHALL generate MS Project 2010+ XML format compatible with MS Project desktop
- **REQ-002**: poc-export SHALL retrieve project data from wfp-poc via GET /v0/projects/{project_id} API
- **REQ-003**: poc-export SHALL retrieve tasks with GET /v0/projects/{project_id}/tasks API
- **REQ-004**: poc-export SHALL retrieve milestones with GET /v0/projects/{project_id}/milestones API
- **REQ-005**: poc-export SHALL retrieve resources with GET /v0/resources API (global resources, filter by project locally)
- **REQ-006**: poc-export SHALL retrieve assignments with GET /v0/projects/{project_id}/assignments API
- **REQ-007**: poc-export SHALL preserve ms_project_guid for task reconciliation
- **REQ-008**: poc-export SHALL preserve ms_project_uid for MS Project display consistency
- **REQ-009**: poc-export SHALL export planned dates to <Start>/<Finish> elements
- **REQ-010**: poc-export SHALL export actual dates to <ActualStart>/<ActualFinish> elements
- **REQ-011**: poc-export SHALL export percent_complete to <PercentComplete> element
- **REQ-012**: poc-export SHALL export task dependencies as <PredecessorLink> elements
- **REQ-013**: poc-export SHALL export milestones as tasks with Duration=0 and Milestone=1
- **REQ-014**: poc-export SHALL export task budgets to <Cost> element
- **REQ-015**: poc-export SHALL validate generated XML against MS Project schema

#### Excel EVM Export

- **REQ-016**: poc-export SHALL generate Excel workbook with multiple sheets (Summary, Metrics, Expenses, RAE)
- **REQ-017**: poc-export SHALL retrieve EVM data with GET /v0/projects/{project_id}/evm/timeseries API
- **REQ-018**: poc-export SHALL retrieve expenses with GET /v0/projects/{project_id}/expenses API
- **REQ-019**: poc-export SHALL retrieve RAE data using GET /v0/projects/{project_id}/rae/summary API (which aggregates RAE from all milestones)
- **REQ-020**: poc-export SHALL create "Summary" sheet with project overview (BAC, dates, status)
- **REQ-021**: poc-export SHALL create "Metrics" sheet with EVM time-series (date, BAC, PV, AC, EV, CV, SV, CPI, SPI, EAC, etc.)
- **REQ-022**: poc-export SHALL create "Expenses" sheet with expense details (date, description, amount, category, milestone)
- **REQ-023**: poc-export SHALL create "RAE" sheet with RAE history per milestone
- **REQ-024**: poc-export SHALL format numbers as currency (€ or $) with 2 decimal places
- **REQ-025**: poc-export SHALL format percentages with 1 decimal place
- **REQ-026**: poc-export SHALL apply Excel formulas for derived metrics (e.g., ETC = EAC - AC)
- **REQ-027**: poc-export SHALL create Excel charts (line chart for EV curves, pie chart for expenses)

#### Blueprint Visualization

- **REQ-028**: poc-export SHALL provide Flask Blueprint with routes for chart viewing
- **REQ-029**: poc-export SHALL generate route GET /charts/project/{id}/overview for project summary dashboard
- **REQ-030**: poc-export SHALL generate route GET /charts/project/{id}/evm for Earned Value charts
- **REQ-031**: poc-export SHALL generate route GET /charts/project/{id}/milestones for milestone status
- **REQ-032**: poc-export SHALL generate route GET /charts/project/{id}/expenses for expense breakdown
- **REQ-033**: poc-export SHALL render charts server-side using matplotlib or plotly
- **REQ-034**: poc-export SHALL generate responsive HTML with embedded charts (PNG/SVG or plotly HTML)
- **REQ-035**: poc-export SHALL display EV curve chart (BAC, PV, AC, EV_physical, EV_milestone over time)
- **REQ-036**: poc-export SHALL display milestone status chart (Gantt-style or timeline)
- **REQ-037**: poc-export SHALL display expense breakdown pie chart (by category: labor, procurement, etc.)
- **REQ-038**: poc-export SHALL display RAE trend chart (RAE per milestone over time)
- **REQ-039**: poc-export SHALL authenticate chart access via JWT token (delegated to wfp-poc)
- **REQ-040**: poc-export SHALL check Guardian READ permissions before displaying charts

#### CLI Interface

- **REQ-041**: poc-export SHALL support CLI command `export msproject <project-id>` for XML generation
- **REQ-042**: poc-export SHALL support CLI command `export excel <project-id>` for Excel generation
- **REQ-043**: poc-export SHALL support `--output` flag to specify output file path
- **REQ-044**: poc-export SHALL support `--format` flag for chart format (png, svg, html)
- **REQ-045**: poc-export SHALL generate export summary report (file size, record counts)
- **REQ-046**: poc-export SHALL log all operations with timestamps and correlation IDs

### Security Requirements (SEC-xxx)

- **SEC-001**: poc-export SHALL require valid JWT token for all wfp-poc API requests
- **SEC-002**: poc-export SHALL validate JWT token before starting export (401 → abort immediately)
- **SEC-003**: poc-export SHALL use HTTPS for all API communication in production
- **SEC-004**: poc-export SHALL NOT store JWT tokens in log files
- **SEC-005**: poc-export SHALL check Guardian READ permissions via wfp-poc (403 → abort with permission error)
- **SEC-006**: poc-export Blueprint routes SHALL require authentication (JWT in cookie or Authorization header)
- **SEC-007**: poc-export SHALL sanitize project IDs to prevent injection attacks

### Performance Requirements (PERF-xxx)

- **PERF-001**: poc-export SHALL generate MS Project XML for 1000 tasks within 30 seconds
- **PERF-002**: poc-export SHALL generate Excel EVM report within 10 seconds
- **PERF-003**: poc-export SHALL render Blueprint charts within 2 seconds (server-side generation)
- **PERF-004**: poc-export SHALL cache chart images for 5 minutes (configurable)
- **PERF-005**: poc-export SHALL paginate large datasets (e.g., expenses > 1000 rows)

### Constraints (CON-xxx)

- **CON-001**: poc-export SHALL only generate MS Project 2010+ XML format (not 2007 or binary .mpp)
- **CON-002**: poc-export SHALL only generate .xlsx Excel format (not .xls or .csv)
- **CON-003**: poc-export SHALL require Python 3.9+ runtime environment
- **CON-004**: poc-export SHALL NOT modify wfp-poc data (read-only operations)
- **CON-005**: poc-export SHALL limit Excel file size to 50MB (reject if exceeds)
- **CON-006**: poc-export Blueprint SHALL NOT use JavaScript frameworks (server-side rendering only)

### Guidelines (GUD-xxx)

- **GUD-001**: Use lxml library for MS Project XML generation with schema validation
- **GUD-002**: Use openpyxl or xlsxwriter for Excel file generation
- **GUD-003**: Use matplotlib or plotly for chart generation (prefer plotly for interactive HTML)
- **GUD-004**: Implement caching for chart images (avoid regenerating on every request)
- **GUD-005**: Provide verbose logging mode (--verbose) for debugging
- **GUD-006**: Use structured logging (JSON format) for production deployments
- **GUD-007**: Generate correlation ID once per export session, use for all API calls
- **GUD-008**: Provide actionable error messages with resolution steps

## 4. Interfaces & Data Contracts

### 4.1. Command-Line Interface

#### Export MS Project XML

```bash
poc-export msproject <project-id> \
  --token=<jwt_token> \
  --api-url=https://wfp-poc.example.com \
  --output=project_export.xml \
  [--verbose] \
  [--validate]
```

**Parameters:**
- `<project-id>`: UUID of project to export (required)
- `--token`: JWT authentication token (required, can use env var WFP_JWT_TOKEN)
- `--api-url`: wfp-poc API base URL (required, can use env var WFP_API_URL)
- `--output`: Output file path (default: `project_{id}_{date}.xml`)
- `--verbose`: Enable detailed logging (optional)
- `--validate`: Validate XML against MS Project schema after generation (optional)

**Exit Codes:**
- `0`: Success (XML generated)
- `1`: Validation errors (invalid data, schema violation)
- `2`: API errors (4xx client errors, permission denied)
- `3`: System errors (network failure, disk full)

#### Export Excel EVM Report

```bash
poc-export excel <project-id> \
  --token=<jwt_token> \
  --api-url=https://wfp-poc.example.com \
  --output=evm_report.xlsx \
  [--verbose] \
  [--include-charts]
```

**Parameters:**
- `<project-id>`: UUID of project to export (required)
- `--token`: JWT authentication token (required)
- `--api-url`: wfp-poc API base URL (required)
- `--output`: Output file path (default: `evm_report_{id}_{date}.xlsx`)
- `--verbose`: Enable detailed logging (optional)
- `--include-charts`: Embed Excel charts in workbook (optional, default: false)

#### Generate Chart Images (CLI)

```bash
poc-export charts <project-id> \
  --token=<jwt_token> \
  --api-url=https://wfp-poc.example.com \
  --output-dir=./charts \
  --format=png \
  [--chart-type=evm,milestones,expenses] \
  [--verbose]
```

**Parameters:**
- `<project-id>`: UUID of project (required)
- `--token`: JWT authentication token (required)
- `--api-url`: wfp-poc API base URL (required)
- `--output-dir`: Directory for chart images (default: `./charts`)
- `--format`: Image format: `png`, `svg`, `html` (default: `png`)
- `--chart-type`: Comma-separated chart types to generate (default: all)
- `--verbose`: Enable detailed logging (optional)

### 4.2. Blueprint Web Interface

#### Routes

| Route | Method | Description | Response |
|-------|--------|-------------|----------|
| `/charts/` | GET | List available projects with charts | HTML page with project list |
| `/charts/project/{id}/overview` | GET | Project summary dashboard | HTML page with overview charts |
| `/charts/project/{id}/evm` | GET | Earned Value Management charts | HTML page with EV curves |
| `/charts/project/{id}/milestones` | GET | Milestone status and timeline | HTML page with milestone chart |
| `/charts/project/{id}/expenses` | GET | Expense breakdown and trends | HTML page with expense charts |
| `/charts/project/{id}/rae` | GET | RAE trends per milestone | HTML page with RAE charts |

#### Authentication

**JWT in Cookie:**
```http
GET /charts/project/a1b2c3d4-e5f6-4a5b-8c9d-0e1f2a3b4c5d/evm
Cookie: access_token=<jwt_token>
```

**JWT in Authorization Header:**
```http
GET /charts/project/a1b2c3d4-e5f6-4a5b-8c9d-0e1f2a3b4c5d/evm
Authorization: Bearer <jwt_token>
```

### 4.3. MS Project XML Output Schema

#### Project Element

```xml
<Project>
  <Name>Project Baguera Phase 1</Name>
  <Title>Infrastructure Modernization</Title>
  <StartDate>2026-01-15T08:00:00</StartDate>
  <FinishDate>2027-12-31T17:00:00</FinishDate>
  <CurrentDate>2026-06-30T12:00:00</CurrentDate>
  <GUID>42DA3870-5DF4-EF11-9360-F4EE08B24B68</GUID>
  <Tasks>...</Tasks>
  <Resources>...</Resources>
  <Assignments>...</Assignments>
</Project>
```

**Mapping from wfp-poc API:**
- `<Name>` ← project.name
- `<Title>` ← project.title
- `<StartDate>` ← project.start_date
- `<FinishDate>` ← project.finish_date
- `<CurrentDate>` ← current timestamp
- `<GUID>` ← project.ms_project_project_guid

#### Task Element

```xml
<Task>
  <UID>1</UID>
  <GUID>A1B2C3D4-E5F6-4A5B-8C9D-0E1F2A3B4C5D</GUID>
  <ID>1</ID>
  <Name>Requirements Analysis</Name>
  <WBS>1.1.1</WBS>
  <Start>2026-01-15T08:00:00</Start>
  <Finish>2026-02-15T17:00:00</Finish>
  <ActualStart>2026-01-16T09:00:00</ActualStart>
  <ActualFinish>2026-02-14T16:00:00</ActualFinish>
  <Duration>PT240H0M0S</Duration>
  <PercentComplete>100</PercentComplete>
  <Critical>1</Critical>
  <Milestone>0</Milestone>
  <Cost>50000</Cost>
  <PredecessorLink>
    <PredecessorUID>0</PredecessorUID>
    <Type>1</Type>
  </PredecessorLink>
</Task>
```

**Mapping from wfp-poc API:**
- `<UID>` ← task.ms_project_uid
- `<GUID>` ← task.ms_project_guid
- `<Name>` ← task.name
- `<WBS>` ← task.wbs_code
- `<Start>` ← task.planned_start_date
- `<Finish>` ← task.planned_finish_date
- `<ActualStart>` ← task.actual_start_date (if exists)
- `<ActualFinish>` ← task.actual_finish_date (if exists)
- `<PercentComplete>` ← task.percent_complete
- `<Cost>` ← task.budget
- `<PredecessorLink>` ← task.predecessors (array of UIDs)

### 4.4. Excel EVM Report Structure

#### Sheet 1: Summary

| Field | Value | Source |
|-------|-------|--------|
| Project Name | Project Baguera Phase 1 | project.name |
| Project Code | G.DED.22966 | project.code |
| Start Date | 2026-01-15 | project.start_date |
| Finish Date | 2027-12-31 | project.finish_date |
| Status | In Progress | project.status |
| BAC | €500,000.00 | project.budget |
| Current Date | 2026-06-30 | evm_snapshot.snapshot_date |
| PV | €450,000.00 | evm_snapshot.pv |
| AC | €330,000.00 | evm_snapshot.ac |
| EV (Physical) | €340,000.00 | evm_snapshot.ev_physical |
| EV (Milestone) | €330,000.00 | evm_snapshot.ev_milestone |
| CV | €10,000.00 | evm_snapshot.cv_physical |
| SV | -€110,000.00 | evm_snapshot.sv_physical |
| CPI | 1.03 | evm_snapshot.cpi_physical |
| SPI | 0.76 | evm_snapshot.spi_physical |
| EAC (CPI) | €485,437.00 | evm_snapshot.eac_cpi_physical |
| ETC | €155,437.00 | evm_snapshot.etc_physical |
| VAC | €14,563.00 | evm_snapshot.vac_physical |
| % Complete | 68.0% | evm_snapshot.percent_complete |

#### Sheet 2: EVM Metrics (Time-Series)

| Date | BAC | PV | AC | EV (Physical) | EV (Milestone) | CV | SV | CPI | SPI | EAC | ETC | VAC |
|------|-----|----|----|---------------|----------------|----|----|-----|-----|-----|-----|-----|
| 2026-03-31 | 500,000 | 150,000 | 145,000 | 148,000 | 145,000 | 3,000 | -2,000 | 1.02 | 0.99 | 490,196 | 345,196 | 9,804 |
| 2026-06-30 | 500,000 | 450,000 | 330,000 | 340,000 | 330,000 | 10,000 | -110,000 | 1.03 | 0.76 | 485,437 | 155,437 | 14,563 |
| ... | ... | ... | ... | ... | ... | ... | ... | ... | ... | ... | ... | ... |

**Source**: `GET /v0/projects/{project_id}/evm/timeseries`

#### Sheet 3: Expenses

| Date | Description | Amount | Category | Milestone | Invoice Number |
|------|-------------|--------|----------|-----------|----------------|
| 2026-04-15 | Backend Dev Team | €85,000.00 | labor | Phase 2 Complete | INV-2026-0234 |
| 2026-04-20 | Server Hardware | €12,000.00 | procurement | Phase 2 Complete | INV-2026-0245 |
| ... | ... | ... | ... | ... | ... |

**Source**: `GET /v0/projects/{project_id}/expenses`

#### Sheet 4: RAE (Reste À Engager)

| Date | Milestone | RAE Amount | Comment |
|------|-----------|------------|---------|
| 2026-06-30 | Phase 1 Complete | €0.00 | Completed |
| 2026-06-30 | Phase 2 Complete | €85,000.00 | Backend delay |
| 2026-06-30 | Phase 3 Complete | €150,000.00 | Not started |
| ... | ... | ... | ... |

**Source**: `GET /v0/projects/{project_id}/rae/summary`

### 4.5. Blueprint Chart Views

#### Overview Dashboard

**Route:** `/charts/project/{id}/overview`

**Layout:**
```
┌─────────────────────────────────────────────┐
│ Project: Baguera Phase 1                    │
│ Status: In Progress | BAC: €500K | CPI: 1.03│
├─────────────────────────────────────────────┤
│ [EV Curve Chart]        [Milestone Status]  │
│                                              │
│ [Expense Breakdown]     [KPI Summary]       │
└─────────────────────────────────────────────┘
```

#### Earned Value Chart

**Route:** `/charts/project/{id}/evm`

**Chart:** Line chart with 4 curves:
- BAC (horizontal line at budget)
- PV (Planned Value - S-curve based on task dates)
- AC (Actual Cost - accumulated expenses)
- EV Physical (Earned Value based on AC/(AC+RAE))
- EV Milestone (Earned Value based on milestone weights)

**X-axis:** Date (monthly intervals)
**Y-axis:** Cost (€)
**Legend:** Top-right with color coding

#### Milestone Status Chart

**Route:** `/charts/project/{id}/milestones`

**Chart:** Gantt-style timeline showing:
- Planned date (vertical line)
- Actual date (marker if achieved)
- Status color: Green (achieved on time), Yellow (achieved late), Red (missed/at risk)

#### Expense Breakdown Chart

**Route:** `/charts/project/{id}/expenses`

**Charts:**
1. **Pie Chart:** Expenses by category (labor, procurement, subcontracting, overhead)
2. **Bar Chart:** Monthly expense trend
3. **Table:** Top 10 largest expenses

### 4.6. Output - Export Report

**Success Report (JSON):**
```json
{
  "status": "success",
  "correlation_id": "e5f6a7b8-c9d0-4e5f-2a3b-4c5d6e7f8a9b",
  "export_type": "msproject_xml",
  "project": {
    "id": "a1b2c3d4-e5f6-4a5b-8c9d-0e1f2a3b4c5d",
    "name": "Project Baguera Phase 1"
  },
  "output_file": "/path/to/project_export.xml",
  "file_size_bytes": 2457600,
  "timestamp": "2026-06-30T18:00:00Z",
  "duration_seconds": 12.5,
  "summary": {
    "tasks": 150,
    "milestones": 5,
    "resources": 25,
    "assignments": 300,
    "guid_preserved": true,
    "uid_preserved": true
  },
  "validation": {
    "xml_schema_valid": true,
    "warnings": [
      "Task 'Testing' has no ActualStart (not started yet)"
    ]
  }
}
```

**Excel Export Report:**
```json
{
  "status": "success",
  "correlation_id": "f6a7b8c9-d0e1-4f5a-2b3c-4d5e6f7a8b9c",
  "export_type": "excel_evm",
  "project": {
    "id": "a1b2c3d4-e5f6-4a5b-8c9d-0e1f2a3b4c5d",
    "name": "Project Baguera Phase 1"
  },
  "output_file": "/path/to/evm_report.xlsx",
  "file_size_bytes": 1048576,
  "timestamp": "2026-06-30T18:05:00Z",
  "duration_seconds": 3.8,
  "summary": {
    "sheets": 4,
    "evm_snapshots": 12,
    "expenses": 125,
    "rae_records": 15,
    "charts_embedded": true
  }
}
```

## 5. Acceptance Criteria

### MS Project XML Export

- **AC-001**: Given a project with 100 tasks, When I run `poc-export msproject <id>`, Then XML file SHALL be generated with all 100 tasks
- **AC-002**: Given tasks with ms_project_guid, When exported, Then <GUID> elements SHALL match source GUIDs
- **AC-003**: Given tasks with actual_start_date, When exported, Then <ActualStart> SHALL be populated
- **AC-004**: Given tasks with dependencies, When exported, Then <PredecessorLink> SHALL reference correct UIDs
- **AC-005**: Given generated XML, When validated, Then SHALL pass MS Project 2010+ schema validation
- **AC-006**: Given exported XML, When imported to MS Project, Then SHALL open without errors

### Excel EVM Export

- **AC-007**: Given a project with EVM snapshots, When I run `poc-export excel <id>`, Then Excel file SHALL contain 4 sheets
- **AC-008**: Given EVM snapshots, When exported, Then "Metrics" sheet SHALL have time-series with all dates
- **AC-009**: Given expenses, When exported, Then "Expenses" sheet SHALL have all expense rows
- **AC-010**: Given RAE data, When exported, Then "RAE" sheet SHALL have milestone breakdown
- **AC-011**: Given numeric values, When exported, Then SHALL be formatted as currency with 2 decimals
- **AC-012**: Given --include-charts flag, When exported, Then Excel SHALL contain embedded charts

### Blueprint Charts

- **AC-013**: Given authenticated user, When I access `/charts/project/{id}/evm`, Then SHALL display EV curve chart
- **AC-014**: Given EVM snapshots, When chart rendered, Then SHALL show BAC, PV, AC, EV curves
- **AC-015**: Given milestones, When I access `/charts/project/{id}/milestones`, Then SHALL display Gantt-style timeline
- **AC-016**: Given expenses, When I access `/charts/project/{id}/expenses`, Then SHALL display pie chart by category
- **AC-017**: Given invalid JWT, When accessing chart route, Then SHALL return 401 Unauthorized
- **AC-018**: Given insufficient permissions, When accessing chart, Then SHALL return 403 Forbidden
- **AC-019**: Given large dataset, When chart rendered, Then SHALL complete within 2 seconds
- **AC-020**: Given chart request, When rendered, Then SHALL cache image for 5 minutes

### Error Handling

- **AC-021**: Given invalid project ID, When export executed, Then SHALL fail with "Project not found" error
- **AC-022**: Given network timeout, When API call fails, Then SHALL retry up to 3 times
- **AC-023**: Given project with no EVM snapshots, When Excel export, Then SHALL warn "No EVM data available"
- **AC-024**: Given disk full error, When writing file, Then SHALL abort with clear error message

## 6. Rationale & Context

### Why Flask Service with Blueprints?

**Architecture Decision: Flask Service with CLI + Blueprint Views**

| Approach | Pros | Cons | Decision |
|----------|------|------|----------|
| **Pure CLI Tool** | Simple, no server, easy deployment | No interactive charts, must export files to view | ❌ Rejected |
| **Flask + Blueprints** ✅ | CLI for automation + web UI for interactive viewing, consistent with wfp-poc | Requires server for web access | ✅ **Chosen** |
| **Separate Frontend SPA** | Rich interactivity | Complex setup, JavaScript frameworks, API duplication | ❌ Rejected (too complex) |

**Chosen Architecture Benefits:**
- ✅ **Reusable Generators**: `app/generators/` used by both CLI and Blueprint routes
- ✅ **Server-Side Rendering**: No JavaScript frameworks, fast page loads
- ✅ **Consistent Stack**: Same Flask patterns as wfp-poc and poc-import
- ✅ **Future-Proof**: Can enhance with REST API endpoints if needed
- ✅ **Lightweight**: matplotlib/plotly generates charts, minimal dependencies

**Layered Architecture:**
```
┌─────────────────────────────────────┐
│         CLI Interface               │ ← Flask Click commands
├─────────────────────────────────────┤
│      Blueprint Routes               │ ← Flask Blueprint (chart views)
├─────────────────────────────────────┤
│         Services Layer              │ ← Orchestration logic
│  • ExportService                    │
│  • WfpApiClient                     │
├─────────────────────────────────────┤
│         Generators Layer            │ ← Pure logic (reusable)
│  • MSProjectXMLGenerator            │
│  • ExcelReportGenerator             │
│  • ChartGenerator                   │
└─────────────────────────────────────┘
```

**File Structure:**
```
poc-export/
├── app/
│   ├── __init__.py           # Flask app factory
│   ├── config.py             # Configuration classes
│   ├── cli.py                # CLI commands (flask export msproject ...)
│   ├── generators/           # 🔧 REUSABLE GENERATION LOGIC
│   │   ├── __init__.py
│   │   ├── msproject_xml_generator.py   # Python objects → MS Project XML
│   │   ├── excel_report_generator.py    # EVM data → Excel workbook
│   │   └── chart_generator.py           # Data → matplotlib/plotly charts
│   ├── services/             # 🎯 ORCHESTRATION LOGIC
│   │   ├── __init__.py
│   │   ├── export_service.py            # High-level export workflows
│   │   └── wfp_api_client.py            # wfp-poc API wrapper
│   ├── blueprints/           # 🌐 WEB ROUTES (chart viewing)
│   │   ├── __init__.py
│   │   ├── charts_blueprint.py          # Routes for chart pages
│   │   └── templates/
│   │       ├── base.html
│   │       ├── overview.html
│   │       ├── evm_chart.html
│   │       └── milestones_chart.html
│   └── utils/
│       ├── logger.py
│       └── cache.py
├── tests/
│   ├── unit/
│   │   ├── test_msproject_generator.py
│   │   ├── test_excel_generator.py
│   │   └── test_chart_generator.py
│   └── integration/
│       └── test_export_workflows.py
├── run.py                    # CLI entry point + dev server
├── pyproject.toml
└── README.md
```

### Why Preserve GUID/UID?

**Round-Trip Compatibility**: Export → Edit in MS Project → Reimport
- ✅ GUIDs ensure reimport updates correct tasks (stable reconciliation)
- ✅ UIDs maintain display order in MS Project
- ✅ No duplicate tasks created

### Why Server-Side Chart Rendering?

**Alternatives Considered:**
1. **JavaScript Charts (Chart.js, D3)**: Requires frontend framework, client-side processing
2. **Server-Side (matplotlib/plotly)**: Faster initial load, no JS dependencies, SEO-friendly
3. **Hybrid**: API returns JSON, client renders charts

**Chosen: Server-Side Rendering**
- ✅ Simpler deployment (no build step)
- ✅ Faster perceived performance (charts ready on page load)
- ✅ Works without JavaScript
- ✅ Easy caching (image files or HTML)
- ✅ Consistent with lightweight Blueprint approach

### Why Excel + Charts?

**Executive Reporting**: Excel familiar to non-technical users, supports pivot tables, formulas, sharing

**Chart Options:**
- **CLI export**: Generate chart images separately (PNG/SVG)
- **Excel embedded**: Charts in Excel workbook (requires xlsxwriter)
- **Blueprint web**: Interactive viewing without Excel

## 7. Dependencies & External Integrations

### External Systems

- **EXT-001**: wfp-poc REST API - Source for all project data
- **EXT-002**: Identity Service (via wfp-poc) - JWT token validation
- **EXT-003**: Guardian Service (via wfp-poc) - Permission checking (READ)

### Technology Platform Dependencies

- **PLT-001**: Python 3.9+ - Runtime environment
- **PLT-002**: Flask - Web framework (CLI, Blueprints)
- **PLT-003**: lxml library - MS Project XML generation with schema validation
- **PLT-004**: openpyxl or xlsxwriter - Excel file generation (.xlsx format)
- **PLT-005**: requests library - HTTP client for wfp-poc API
- **PLT-006**: Click - CLI framework (Flask built-in CLI support)
- **PLT-007**: matplotlib or plotly - Chart generation
- **PLT-008**: Jinja2 - HTML templating (Flask built-in)
- **PLT-009**: Flask-Caching - Chart image caching

### Infrastructure Dependencies

- **INF-001**: Network connectivity - HTTP/HTTPS access to wfp-poc API
- **INF-002**: File system access - Write export files, read templates
- **INF-003**: Web server - For Blueprint routes (Flask dev server or gunicorn)

### Compliance Dependencies

- **COM-001**: MS Project 2010+ XML Schema - Vendor-defined schema compliance
- **COM-002**: Excel OpenXML Format - ECMA-376 specification

## 8. Examples & Edge Cases

### Example 1: MS Project XML Export

```bash
# Export project to MS Project XML
poc-export msproject a1b2c3d4-e5f6-4a5b-8c9d-0e1f2a3b4c5d \
  --token=$WFP_JWT_TOKEN \
  --api-url=https://wfp-poc.example.com \
  --output=baguera_export.xml \
  --validate

# Output:
# ✅ Fetching project data from wfp-poc...
# ✅ Retrieved: 150 tasks, 5 milestones, 25 resources
# ✅ Generating MS Project XML...
# ✅ Preserving GUIDs for round-trip compatibility
# ✅ Exporting planned dates to <Start>/<Finish>
# ✅ Exporting actual dates to <ActualStart>/<ActualFinish>
# ✅ Exporting dependencies (127 predecessor links)
# ✅ Validating XML against MS Project schema...
# ✅ Export completed in 12.5 seconds
# 📄 File: baguera_export.xml (2.4 MB)
# 📊 Summary: 150 tasks, 5 milestones, 25 resources, 300 assignments
```

### Example 2: Excel EVM Report

```bash
# Generate Excel report with charts
poc-export excel a1b2c3d4-e5f6-4a5b-8c9d-0e1f2a3b4c5d \
  --token=$WFP_JWT_TOKEN \
  --api-url=https://wfp-poc.example.com \
  --output=evm_report.xlsx \
  --include-charts

# Output:
# ✅ Fetching EVM data from wfp-poc...
# ✅ Retrieved: 12 EVM snapshots, 125 expenses, 15 RAE records
# ✅ Generating Excel workbook...
# ✅ Sheet 1: Summary (project overview)
# ✅ Sheet 2: Metrics (EVM time-series, 12 rows)
# ✅ Sheet 3: Expenses (125 rows)
# ✅ Sheet 4: RAE (15 rows)
# ✅ Embedding charts (EV curve, expense breakdown)...
# ✅ Export completed in 3.8 seconds
# 📄 File: evm_report.xlsx (1.0 MB)
```

### Example 3: Access Blueprint Chart (Web)

```bash
# Start Flask server
flask --app poc_export run --port=5002

# Access chart in browser
# URL: http://localhost:5002/charts/project/a1b2c3d4-e5f6-4a5b-8c9d-0e1f2a3b4c5d/evm
# (JWT in cookie from previous wfp-poc login)

# Server log:
# INFO: GET /charts/project/.../evm - 200 OK (1.5s)
# INFO: Generated EV curve chart (cached for 5 minutes)
# INFO: Chart dimensions: 1200x600, format: PNG
```

### Example 4: Chart Export via CLI

```bash
# Generate chart images for all chart types
poc-export charts a1b2c3d4-e5f6-4a5b-8c9d-0e1f2a3b4c5d \
  --token=$WFP_JWT_TOKEN \
  --api-url=https://wfp-poc.example.com \
  --output-dir=./charts \
  --format=png

# Output:
# ✅ Generating charts for project Baguera Phase 1...
# ✅ EV Curve Chart → charts/evm_curve_2026-06-30.png (120 KB)
# ✅ Milestone Status → charts/milestones_2026-06-30.png (85 KB)
# ✅ Expense Breakdown → charts/expenses_breakdown_2026-06-30.png (95 KB)
# ✅ RAE Trend Chart → charts/rae_trend_2026-06-30.png (78 KB)
# ✅ Export completed in 5.2 seconds
```

### Example 5: Export Error - Permission Denied

```bash
poc-export msproject a1b2c3d4-e5f6-4a5b-8c9d-0e1f2a3b4c5d \
  --token=$WFP_JWT_TOKEN \
  --api-url=https://wfp-poc.example.com

# Output:
# ✅ Fetching project data from wfp-poc...
# ❌ API Error: 403 Forbidden
# 
# Error Details:
#   Guardian Permission Check Failed
#   Required: READ permission on resource "projects"
#   User: john.doe@example.com
#   Company: ACME Corp
# 
# Resolution:
#   Contact your administrator to request READ access to this project.
# 
# Exit code: 2 (Permission denied)
```

## 9. Validation Criteria

### MS Project XML Validation

- **VAL-001**: Generated XML SHALL validate against MS Project 2010+ XML schema
- **VAL-002**: All <GUID> elements SHALL be valid UUID v4 format
- **VAL-003**: All dates SHALL be ISO 8601 format with timezone
- **VAL-004**: <PredecessorLink> UIDs SHALL reference existing tasks

### Excel Report Validation

- **VAL-005**: Excel file SHALL be valid .xlsx OpenXML format
- **VAL-006**: All sheets SHALL have headers in row 1
- **VAL-007**: Numeric columns SHALL be formatted as currency or percentage
- **VAL-008**: Embedded charts SHALL be valid Excel chart objects

### Blueprint Chart Validation

- **VAL-009**: Chart images SHALL be valid PNG/SVG format
- **VAL-010**: HTML pages SHALL pass W3C HTML5 validation
- **VAL-011**: JWT authentication SHALL be checked before rendering charts
- **VAL-012**: Chart dimensions SHALL be responsive (min 800px width)

## 10. Related Specifications / Further Reading

- [Integration Specification - Waterfall Project Management Services](../integration-wfp-services.md)
- [WFP-POC REST API Specification](../wfp-poc/schema-api-project-management-evm.md)
- [POC-Import Service Specification](../poc-import/schema-tool-poc-import-service.md)
- [Microsoft Project XML Schema Reference](https://docs.microsoft.com/en-us/office-project/xml-data-interchange/project-xml-data-interchange-schema-reference)
- [OpenXML Excel Format Specification](https://www.ecma-international.org/publications-and-standards/standards/ecma-376/)
- [Flask Blueprints Documentation](https://flask.palletsprojects.com/en/latest/blueprints/)
- [matplotlib Documentation](https://matplotlib.org/stable/contents.html)
- [Plotly Python Documentation](https://plotly.com/python/)

---

**End of Specification**
