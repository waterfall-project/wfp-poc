---
title: WFP-POC - Project Management & EVM API Specification
version: 1.0
date_created: 2026-01-10
last_updated: 2026-01-10
owner: Waterfall Project Team
tags: [api, schema, evm, project-management, planning, poc]
---

# Introduction

The **wfp-poc** service is a proof-of-concept microservice that provides comprehensive project management and Earned Value Management (EVM) capabilities for the Waterfall suite. This service enables project tracking, financial monitoring, and performance forecasting through industry-standard EVM metrics.

**wfp-poc** serves as the central data repository and calculation engine for:
- **Project planning data** imported from Microsoft Project XML files (tasks, predecessors, resources, assignments)
- **Financial data** imported from ERP Excel exports (expenses categorized by type: labor, procurement, subcontracting, overhead)
- **EVM indicators** calculated and exposed for visualization in frontend dashboards using Apache ECharts
- **Performance forecasts** using multiple projection methods (CPI, CPI×SPI, plan-based)

This service is designed to validate the feasibility and relevance of the Waterfall project management approach before building production-grade services with broader scope.

**Architecture Position:**
- **Upstream**: Consumes data from `poc-import` service (XML/Excel transformation to JSON)
- **Downstream**: Provides data to `poc-export` service (Excel report generation) and frontend visualization layer
- **Standalone**: Exposes REST API for direct CRUD operations and indicator queries

## 1. Purpose & Scope

### Purpose

The primary purpose of **wfp-poc** is to:

1. **Store and manage project planning data** including projects, tasks, milestones, resources, and their relationships in a structured database
2. **Calculate Earned Value Management (EVM) indicators** to provide real-time visibility into project cost and schedule performance
3. **Generate financial statistics** for expense analysis (breakdown by category, labor distribution by resource, monthly trends)
4. **Forecast project outcomes** using multiple EVM projection methods to anticipate budget overruns and schedule delays
5. **Support time-series analysis** by maintaining historical data for RAE (Reste À Engager) updates and progress tracking
6. **Enable integration** with import/export services and future frontend applications through a well-defined REST API

### Scope

**In Scope:**

- **Project Management**: CRUD operations for projects, tasks (with hierarchical WBS structure), milestones, resources, and assignments
- **Financial Tracking**: Expense recording with categorization (labor, procurement, subcontracting, overhead) and milestone-based allocation
- **EVM Calculations**: Monthly-granularity calculation of PV (Planned Value), AC (Actual Cost), EV (Earned Value), and derived metrics (CV, SV, CPI, SPI, EAC, ETC, VAC)
- **Dual EV Methods**: Physical progress method (RAE-based) and milestone completion method
- **Critical Path Analysis**: Task scheduling with predecessor relationships (FS, SS, FF, SF) and lag/lead times
- **Statistics & Reporting**: Expense breakdown, labor distribution, monthly trends optimized for chart visualization
- **Multi-Tenant Support**: Data isolation by company_id for secure multi-company operations
- **Bulk Operations**: Bulk import endpoints for efficient data loading from poc-import service
- **Historical Tracking**: RAE update history, progress snapshots, and time-series data retention

**Out of Scope (Future Enhancements):**

- **Authentication/Authorization**: Real Guardian and Identity service integration (mocked for POC)
- **Performance Optimization**: Caching strategies, query optimization, indexing tuning
- **Real-Time ERP Integration**: Direct API connections to ERP systems (Excel import only for POC)
- **Advanced Resource Management**: Resource calendars, availability tracking, capacity planning
- **Baseline Management**: Multiple project baselines and variance analysis
- **Risk Management**: Risk identification, mitigation tracking, impact analysis
- **Change Management**: Change request workflow and approval processes
- **Advanced Reporting**: Custom report builder, PDF generation, email notifications
- **Collaborative Features**: Comments, notifications, task assignments, approval workflows

**Assumptions:**

- **Data Volume**: ~100 projects, ~500 tasks per project, ~25 resources per project (POC scale)
- **Calculation Frequency**: Monthly granularity for EVM indicators (not real-time)
- **Milestone Coverage**: All expenses fall between defined milestones (validation enforced)
- **Non-Overlapping Milestones**: Milestones do not overlap in time (simplifies AC allocation)
- **Linear PV Distribution**: Planned value is distributed linearly across task duration
- **Mock Services**: Guardian and Identity services return permissive mocks during POC phase

## 2. Definitions

### Project Management Terms

- **WBS (Work Breakdown Structure)**: Hierarchical decomposition of project work into smaller, manageable components. Each task has an outline number (e.g., "1.2.3") and optional parent task, forming a tree structure. Summary tasks aggregate child task data.

- **Critical Path**: The longest sequence of dependent tasks that determines the minimum project duration. Tasks on the critical path have zero total slack; any delay impacts the project end date. Calculated using forward/backward pass algorithms considering predecessor relationships.

- **Milestone**: A zero-duration marker representing a significant project checkpoint or decision point (e.g., "Requirements Approved", "Testing Complete"). Milestones are used to track progress and allocate expenses in this system. In MS Project XML, milestones are tasks with `<Milestone>1</Milestone>` and zero duration.

- **Deliverable**: A tangible or intangible output produced by project work (e.g., document, code module, trained system). Deliverables are associated with milestones. In this POC, deliverables may be represented as tasks with an `is_deliverable` flag or as separate entities linked to milestones.

- **Predecessor**: A task dependency relationship defining the order in which tasks must be executed. Types:
  - **FS (Finish-to-Start)**: Successor starts when predecessor finishes (most common)
  - **SS (Start-to-Start)**: Both tasks start simultaneously
  - **FF (Finish-to-Finish)**: Both tasks finish simultaneously
  - **SF (Start-to-Finish)**: Successor finishes when predecessor starts (rare)
  
  Relationships may include lag (delay) or lead (overlap) time.

- **RAE (Reste À Engager)**: "Remaining to be Committed" - The estimated cost remaining to complete a task or milestone, updated monthly based on actual progress. Used to calculate EV via physical progress method: `Progress = AC / (AC + RAE)`. Historical RAE values are tracked for time-series analysis.

- **Assignment**: The allocation of a resource (person, equipment, material) to a task, specifying the amount of work or percentage allocation. One task can have multiple assignments; one resource can be assigned to multiple tasks.

- **Resource**: An entity that performs work or incurs costs (e.g., engineer, consultant, server, materials). Resources have attributes like type (labor, material, cost), hourly rate, and availability.

- **Task Status**: Current state of a task:
  - **not_started**: Task has not begun
  - **in_progress**: Task is actively being worked on
  - **completed**: Task is finished
  - **cancelled**: Task will not be executed

- **Summary Task**: A parent task that aggregates child task data (dates, costs, work). Summary tasks have `<Summary>1</Summary>` in MS Project XML and are identified by having child tasks in the WBS hierarchy.

- **Lag/Lead**: Time offset in a predecessor relationship. Positive lag = delay (successor waits after predecessor completes). Negative lag (lead) = overlap (successor starts before predecessor completes).

- **Total Slack/Float**: The amount of time a task can be delayed without impacting the project end date. Zero slack indicates the task is on the critical path.

### Earned Value Management (EVM) Terms

- **BAC (Budget At Completion)**: The total planned budget for the project or task. Represents the baseline cost assuming all work is completed as planned. `BAC = Sum of all planned task costs`.

- **PV (Planned Value / BCWS)**: The authorized budget assigned to scheduled work. Represents what you **planned to spend** by a given date. Calculated by distributing task budgets linearly across their scheduled duration, respecting predecessor constraints. Also called Budgeted Cost of Work Scheduled (BCWS).

- **AC (Actual Cost / ACWP)**: The actual costs incurred for work performed. Represents what you **actually spent** by a given date. Calculated by summing expense records from ERP imports, allocated to milestones based on expense date. Also called Actual Cost of Work Performed (ACWP).

- **EV (Earned Value / BCWP)**: The value of work actually completed. Represents what you **should have spent** for the work done. Calculated using two methods:
  1. **Physical Progress Method**: `EV = BAC × (AC / (AC + RAE))` - Based on remaining cost estimates
  2. **Milestone Completion Method**: `EV = Sum of BAC for completed milestones` - Based on milestone achievement
  
  Also called Budgeted Cost of Work Performed (BCWP).

- **CV (Cost Variance)**: Difference between earned value and actual cost. Formula: `CV = EV - AC`
  - **Positive CV**: Under budget (good)
  - **Negative CV**: Over budget (bad)

- **SV (Schedule Variance)**: Difference between earned value and planned value. Formula: `SV = EV - PV`
  - **Positive SV**: Ahead of schedule (good)
  - **Negative SV**: Behind schedule (bad)

- **CPI (Cost Performance Index)**: Efficiency ratio for cost performance. Formula: `CPI = EV / AC`
  - **CPI > 1.0**: Cost efficiency is good (getting more value per dollar)
  - **CPI < 1.0**: Cost overrun (spending more than value delivered)
  - **CPI = 1.0**: On budget

- **SPI (Schedule Performance Index)**: Efficiency ratio for schedule performance. Formula: `SPI = EV / PV`
  - **SPI > 1.0**: Ahead of schedule
  - **SPI < 1.0**: Behind schedule
  - **SPI = 1.0**: On schedule

- **EAC (Estimate At Completion)**: Forecasted total project cost at completion. Calculated using multiple methods:
  1. **CPI Method**: `EAC = BAC / CPI` - Assumes current cost performance continues
  2. **CPI×SPI Method**: `EAC = AC + (BAC - EV) / (CPI × SPI)` - Considers both cost and schedule performance
  3. **Plan-Based Method**: `EAC = AC + Remaining_PV` - Assumes future work follows original plan

- **ETC (Estimate To Complete)**: Forecasted cost to finish remaining work. Formula: `ETC = EAC - AC`

- **VAC (Variance At Completion)**: Expected variance at project completion. Formula: `VAC = BAC - EAC`
  - **Positive VAC**: Expected to finish under budget
  - **Negative VAC**: Expected to finish over budget

- **Time-Series Data**: Historical monthly snapshots of EVM indicators (PV, AC, EV) used to generate trend charts in Apache ECharts. Each data point represents cumulative values at month-end.

### Technical Terms

- **Company ID**: Unique identifier for a tenant in multi-tenant architecture. All project data is scoped to a company_id to ensure data isolation.

- **Bulk Import**: Endpoint accepting arrays of entities for efficient batch creation, used by poc-import service to load large datasets from MS Project XML files.

- **MS Project UID**: Microsoft Project's unique identifier for tasks, resources, and assignments. Preserved during import to enable round-trip export via poc-export service.

- **Expense Category**: Classification of expenses from ERP system:
  - **Labor (MO - Main d'Oeuvre)**: Personnel costs (salaries, contractors)
  - **Procurement (Achat)**: Material and equipment purchases
  - **Subcontracting (ST - Sous-Traitance)**: External vendor services
  - **Overhead (Frais)**: Indirect costs (travel, facilities, administrative)

## 3. Requirements, Constraints & Guidelines

### Functional Requirements (REQ-xxx)

#### Project Management (REQ-PM-xxx)

- **REQ-PM-001**: System SHALL support full CRUD operations for projects (Create, Read, Update, Delete)
- **REQ-PM-002**: System SHALL store project attributes including: name, code, start_date, finish_date, budget, company_id, and MS Project metadata (GUID, SaveVersion, Title, CreationDate, LastSaved, Currency)
- **REQ-PM-003**: System SHALL enforce multi-tenant data isolation by company_id for all project operations
- **REQ-PM-004**: System SHALL support project listing with pagination (page, per_page parameters)
- **REQ-PM-005**: System SHALL allow filtering projects by company_id, status, and date ranges
- **REQ-PM-006**: System SHALL prevent deletion of projects with associated tasks, milestones, or expenses (cascading delete or soft delete pattern)
- **REQ-PM-007**: System SHALL validate that project start_date is before finish_date
- **REQ-PM-008**: System SHALL store MS Project calendar settings (MinutesPerDay, MinutesPerWeek, DaysPerMonth, WeekStartDay, DefaultStartTime, DefaultFinishTime)

#### Task Management (REQ-TM-xxx)

- **REQ-TM-001**: System SHALL support full CRUD operations for tasks (Create, Read, Update, Delete)
- **REQ-TM-002**: System SHALL preserve MS Project identifiers (UID, ID, GUID) for round-trip export compatibility
- **REQ-TM-003**: System SHALL store task hierarchy using parent_id references to support WBS (Work Breakdown Structure)
- **REQ-TM-004**: System SHALL calculate and store WBS outline numbers (e.g., "1.2.3") based on task hierarchy
- **REQ-TM-005**: System SHALL support task types: normal, summary (parent), and milestone (zero duration)
- **REQ-TM-006**: System SHALL store task status: not_started, in_progress, completed, cancelled
- **REQ-TM-007**: System SHALL store task attributes: name, start, finish, duration, work (hours), cost, percent_complete, is_deliverable
- **REQ-TM-008**: System SHALL store MS Project scheduling fields: manual scheduling flag, early_start, early_finish, late_start, late_finish, total_slack, free_slack, critical path flag
- **REQ-TM-009**: System SHALL support predecessor relationships with types: FS (Finish-to-Start), SS (Start-to-Start), FF (Finish-to-Finish), SF (Start-to-Finish)
- **REQ-TM-010**: System SHALL store lag/lead time for predecessor relationships (positive = delay, negative = overlap)
- **REQ-TM-011**: System SHALL detect and reject circular dependencies in predecessor relationships
- **REQ-TM-012**: System SHALL calculate critical path using forward/backward pass algorithms considering all predecessor relationships
- **REQ-TM-013**: System SHALL support bulk task creation via POST /projects/{id}/tasks/bulk endpoint for efficient import
- **REQ-TM-014**: System SHALL validate that task start date is before finish date (except milestones with zero duration)
- **REQ-TM-015**: System SHALL validate that child task dates fall within parent summary task date range
- **REQ-TM-016**: System SHALL automatically aggregate summary task attributes (dates, costs, work) from child tasks

#### Resource Management (REQ-RM-xxx)

- **REQ-RM-001**: System SHALL support full CRUD operations for resources (Create, Read, Update, Delete)
- **REQ-RM-002**: System SHALL store resource attributes: name, type (labor, material, cost), standard_rate (hourly), company_id
- **REQ-RM-003**: System SHALL preserve MS Project resource UID for round-trip compatibility
- **REQ-RM-004**: System SHALL enforce multi-tenant isolation for resources by company_id
- **REQ-RM-005**: System SHALL support resource assignment to tasks via Assignment entity
- **REQ-RM-006**: System SHALL prevent deletion of resources with active task assignments
- **REQ-RM-007**: System SHALL validate that standard_rate is non-negative for labor resources

#### Assignment Management (REQ-AS-xxx)

- **REQ-AS-001**: System SHALL support full CRUD operations for assignments (linking resources to tasks)
- **REQ-AS-002**: System SHALL store assignment attributes: resource_id, task_id, work_hours, percent_allocation, cost
- **REQ-AS-003**: System SHALL preserve MS Project assignment UID for round-trip compatibility
- **REQ-AS-004**: System SHALL validate that resource and task belong to the same project/company
- **REQ-AS-005**: System SHALL prevent duplicate assignments (same resource + task combination)
- **REQ-AS-006**: System SHALL validate that percent_allocation is between 0 and 100

#### Milestone & Deliverables (REQ-MD-xxx)

- **REQ-MD-001**: System SHALL support full CRUD operations for milestones
- **REQ-MD-002**: System SHALL store milestone attributes: name, target_date, actual_date, planned_date, status (upcoming, achieved, missed), budget
- **REQ-MD-003**: System SHALL maintain historical planned_date values for time-based variance analysis (time/time diagrams)
- **REQ-MD-004**: System SHALL link milestones to tasks marked with is_milestone flag
- **REQ-MD-005**: System SHALL support multiple deliverables per milestone
- **REQ-MD-006**: System SHALL store deliverable attributes: name, description, type (document, code, system), status (planned, in_progress, delivered, accepted)
- **REQ-MD-007**: System SHALL validate that milestones do not overlap in time (non-overlapping constraint for expense allocation)
- **REQ-MD-008**: System SHALL validate that project has at least one milestone before accepting expenses
- **REQ-MD-009**: System SHALL automatically update milestone status based on actual_date (upcoming if null, achieved if filled)

#### Expense Tracking (REQ-ET-xxx)

- **REQ-ET-001**: System SHALL support full CRUD operations for expenses
- **REQ-ET-002**: System SHALL store expense attributes: date, amount, category (labor, procurement, subcontracting, overhead), description, reference_number
- **REQ-ET-003**: System SHALL automatically allocate expenses to milestones based on expense date falling between milestone target dates
- **REQ-ET-004**: System SHALL reject expenses with dates before the first project milestone
- **REQ-ET-005**: System SHALL reject expenses with dates after the last project milestone
- **REQ-ET-006**: System SHALL support bulk expense creation via POST /projects/{id}/expenses/bulk endpoint for ERP imports
- **REQ-ET-007**: System SHALL validate expense amount is non-negative
- **REQ-ET-008**: System SHALL enforce uniqueness constraints to prevent duplicate expense imports (based on reference_number + date + amount combination)
- **REQ-ET-009**: System SHALL support expense filtering by date range, category, and milestone
- **REQ-ET-010**: System SHALL link expenses to resources when labor category is used (optional)

#### RAE (Reste À Engager) Management (REQ-RAE-xxx)

- **REQ-RAE-001**: System SHALL store RAE (Remaining to be Committed) values at task level
- **REQ-RAE-002**: System SHALL maintain complete historical record of RAE updates with timestamps
- **REQ-RAE-003**: System SHALL support RAE updates via POST /projects/{project_id}/tasks/{task_id}/rae endpoint
- **REQ-RAE-004**: System SHALL validate that RAE values are non-negative
- **REQ-RAE-005**: System SHALL use RAE history for physical progress EV calculations
- **REQ-RAE-006**: System SHALL support monthly RAE update frequency (typical use case)
- **REQ-RAE-007**: System SHALL return RAE history with pagination for long-running projects

#### EVM Calculations (REQ-EVM-xxx)

- **REQ-EVM-001**: System SHALL calculate PV (Planned Value) by distributing task budgets linearly across scheduled duration, respecting predecessor constraints
- **REQ-EVM-002**: System SHALL calculate AC (Actual Cost) by summing expenses allocated to milestones up to the analysis date
- **REQ-EVM-003**: System SHALL calculate EV (Earned Value) using two methods:
  - **Physical Progress Method**: `EV = BAC × (AC / (AC + RAE))` based on latest RAE values
  - **Milestone Completion Method**: `EV = Sum of BAC for achieved milestones`
- **REQ-EVM-004**: System SHALL expose both EV calculation methods in API responses for comparison
- **REQ-EVM-005**: System SHALL calculate derived metrics: CV (EV - AC), SV (EV - PV), CPI (EV / AC), SPI (EV / PV)
- **REQ-EVM-006**: System SHALL calculate EAC (Estimate At Completion) using three forecasting methods:
  - **CPI Method**: `EAC = BAC / CPI`
  - **CPI×SPI Method**: `EAC = AC + (BAC - EV) / (CPI × SPI)`
  - **Plan-Based Method**: `EAC = AC + Remaining_PV` (where Remaining_PV is based on original plan RAE, not updated RAE)
- **REQ-EVM-007**: System SHALL calculate ETC (EAC - AC) and VAC (BAC - EAC) for all three EAC methods
- **REQ-EVM-008**: System SHALL provide monthly granularity for EVM time-series data
- **REQ-EVM-009**: System SHALL handle division by zero cases (AC=0, PV=0) by returning null or appropriate default values
- **REQ-EVM-010**: System SHALL support cumulative and period-based EVM indicator views
- **REQ-EVM-011**: System SHALL recalculate EVM indicators on-demand (not pre-cached for POC simplicity)
- **REQ-EVM-012**: System SHALL support EVM calculations at project level (aggregating all tasks/milestones)

#### Statistics & Reporting (REQ-ST-xxx)

- **REQ-ST-001**: System SHALL provide expense breakdown by category (labor, procurement, subcontracting, overhead) for pie chart visualization
- **REQ-ST-002**: System SHALL provide labor cost distribution by resource for bar chart visualization
- **REQ-ST-003**: System SHALL provide monthly expense trends for line chart visualization
- **REQ-ST-004**: System SHALL format statistics responses for Apache ECharts consumption (series format with labels and data arrays)
- **REQ-ST-005**: System SHALL support date range filtering for all statistics endpoints
- **REQ-ST-006**: System SHALL aggregate statistics at project level

#### Progress Updates (REQ-PU-xxx)

- **REQ-PU-001**: System SHALL support bulk progress updates via POST /projects/{project_id}/progress endpoint
- **REQ-PU-002**: System SHALL accept progress updates as array of {task_id, percent_complete, date} objects
- **REQ-PU-003**: System SHALL validate percent_complete values are between 0 and 100
- **REQ-PU-004**: System SHALL automatically update task status based on percent_complete (0=not_started, 1-99=in_progress, 100=completed)
- **REQ-PU-005**: System SHALL maintain progress update history with timestamps
- **REQ-PU-006**: System SHALL support querying progress history for trend analysis

### Security Requirements (SEC-xxx)

**Authentication:**
- **SEC-001**: Endpoints SHALL require valid JWT token in `access_token` cookie (following Waterfall template pattern)
- **SEC-002**: JWT SHALL contain required claims: `user_id`, `company_id`, `email`
- **SEC-003**: JWT validation SHALL use Identity service public key (mocked for POC)
- **SEC-004**: Unauthenticated requests SHALL return 401 Unauthorized status

**Authorization:**
- **SEC-005**: Endpoints SHALL check Guardian permissions using `@access_required` decorator (mocked for POC to allow all)
- **SEC-006**: Guardian operations SHALL map to: LIST (GET collections), READ (GET single), CREATE (POST), UPDATE (PATCH), DELETE (DELETE)
- **SEC-007**: Guardian context SHALL include `company_id`, `project_id`, `resource_id` as applicable
- **SEC-008**: Forbidden requests SHALL return 403 Forbidden status with reason

**Input Validation:**
- **SEC-009**: All inputs SHALL be validated against Marshmallow schemas before processing
- **SEC-010**: System SHALL sanitize string inputs to prevent SQL injection (SQLAlchemy ORM protection)
- **SEC-011**: System SHALL reject requests with invalid UUIDs for ID parameters
- **SEC-012**: System SHALL validate date formats (ISO 8601) and reject malformed dates
- **SEC-013**: System SHALL validate numeric ranges (non-negative costs, 0-100 percentages)
- **SEC-014**: Validation errors SHALL return 400 Bad Request with detailed error messages

**Data Isolation:**
- **SEC-015**: All queries SHALL filter by company_id from JWT claims to enforce multi-tenant isolation
- **SEC-016**: Cross-company data access attempts SHALL return 404 Not Found (not 403 to avoid information disclosure)
- **SEC-017**: System SHALL prevent company_id tampering in request bodies (override with JWT claim)

**Rate Limiting:**
- **SEC-018**: Bulk import endpoints SHALL enforce rate limit of 10 requests per minute per user
- **SEC-019**: Standard endpoints SHALL enforce rate limit of 100 requests per minute per user
- **SEC-020**: EVM calculation endpoints SHALL enforce rate limit of 20 requests per minute per user (computationally expensive)
- **SEC-021**: Rate limit exceeded requests SHALL return 429 Too Many Requests with Retry-After header

### Performance Requirements (PERF-xxx)

- **PERF-001**: Standard CRUD operations SHOULD complete within 200ms at 95th percentile (not enforced for POC)
- **PERF-002**: EVM calculations SHOULD complete within 2 seconds at 95th percentile for projects with 500 tasks (not enforced for POC)
- **PERF-003**: Bulk import operations SHALL process at least 100 tasks per second (not enforced for POC)
- **PERF-004**: System SHOULD support pagination for all collection endpoints (page, per_page with default 20, max 100)
- **PERF-005**: System SHOULD use database indexes on company_id, project_id, task_id, date fields (implementation detail)
- **PERF-006**: Critical path calculation SHOULD use efficient algorithms (topological sort + forward/backward pass)

### Constraints (CON-xxx)

- **CON-001**: POC scope - Performance optimization is not a priority; focus on functionality and correctness
- **CON-002**: Monthly granularity - EVM calculations are monthly, not real-time or daily
- **CON-003**: Non-overlapping milestones - Milestones must not overlap in time for expense allocation algorithm
- **CON-004**: Linear PV distribution - Planned value is distributed linearly across task duration (no custom curves)
- **CON-005**: Single baseline - Only one project baseline is supported (no multiple baseline comparisons)
- **CON-006**: Fixed capacity - Resource calendars and availability not modeled; fixed capacity assumed
- **CON-007**: No workflow - No approval workflows or state transitions beyond basic status updates
- **CON-008**: Synchronous operations - All calculations are synchronous (no background jobs or queues)
- **CON-009**: Mock auth - Guardian and Identity integrations use permissive mocks for POC phase

### Guidelines (GUD-xxx)

- **GUD-001**: Follow Waterfall template layered architecture: Resources (HTTP) → Schemas (validation) → Models (database)
- **GUD-002**: Use SQLAlchemy models with UUIDMixin and TimestampMixin for consistency
- **GUD-003**: Use Marshmallow schemas with SQLAlchemyAutoSchema for serialization/deserialization
- **GUD-004**: Use Flask-RESTful Resource classes for endpoint implementation
- **GUD-005**: Return standard Waterfall response format: `{data: {...}, message: "optional"}` for single resources
- **GUD-006**: Return paginated format for collections: `{data: [...], page: 1, per_page: 20, total: 100, total_pages: 5}`
- **GUD-007**: Return error format: `{message: "error", errors: {field: ["messages"]}, correlation_id: "uuid"}`
- **GUD-008**: Use ISO 8601 format for all dates (e.g., "2026-01-10T10:30:00Z")
- **GUD-009**: Use UUID v4 for all entity identifiers
- **GUD-010**: Preserve MS Project UIDs/GUIDs in separate fields (not as primary keys)
- **GUD-011**: Use snake_case for JSON field names (Python convention)
- **GUD-012**: Include X-Correlation-ID header in all responses for tracing
- **GUD-013**: Log all errors with correlation ID for debugging
- **GUD-014**: Use database transactions for bulk operations to ensure atomicity

### Patterns (PAT-xxx)

- **PAT-001**: Layered architecture: Resources → Schemas → Models (Waterfall template pattern)
- **PAT-002**: Repository pattern: Encapsulate database queries in model methods or service layer
- **PAT-003**: DTO pattern: Use schemas for data transfer between layers
- **PAT-004**: Decorator pattern: Use `@require_jwt_auth` and `@access_required` for cross-cutting concerns
- **PAT-005**: Factory pattern: Use application factory pattern for Flask app creation
- **PAT-006**: Migration pattern: Use Alembic for database schema migrations
- **PAT-007**: Soft delete pattern: Consider using is_deleted flag instead of hard deletes for audit trail (optional)
- **PAT-008**: Aggregate pattern: Summary tasks aggregate child task data using computed properties
- **PAT-009**: Time-series pattern: Store historical snapshots with timestamps for trend analysis
- **PAT-010**: Bulk operation pattern: Accept arrays in POST endpoints with validation for each item

## 4. Interfaces & Data Contracts

[À COMPLÉTER - Définition complète de tous les endpoints et schémas de données]

### 4.1. Data Models

#### Project Model

```json
{
  "id": {
    "type": "uuid",
    "required": true,
    "description": "Unique identifier (UUID v4), auto-generated"
  },
  "company_id": {
    "type": "uuid",
    "required": true,
    "description": "Tenant identifier for multi-tenant isolation"
  },
  "name": {
    "type": "string",
    "required": true,
    "minLength": 1,
    "maxLength": 255,
    "description": "Project name"
  },
  "code": {
    "type": "string",
    "required": false,
    "maxLength": 50,
    "description": "Project code or identifier (e.g., G.DED.22966)"
  },
  "title": {
    "type": "string",
    "required": false,
    "maxLength": 255,
    "description": "MS Project Title field"
  },
  "start_date": {
    "type": "datetime",
    "required": true,
    "format": "ISO 8601",
    "description": "Project start date (YYYY-MM-DDTHH:MM:SSZ)",
    "validation": "Must be before finish_date"
  },
  "finish_date": {
    "type": "datetime",
    "required": true,
    "format": "ISO 8601",
    "description": "Project finish date (YYYY-MM-DDTHH:MM:SSZ)",
    "validation": "Must be after start_date"
  },
  "budget": {
    "type": "decimal",
    "required": false,
    "precision": "2 decimal places",
    "minimum": 0,
    "description": "Total project budget (BAC)"
  },
  "currency_code": {
    "type": "string",
    "required": false,
    "default": "EUR",
    "maxLength": 3,
    "description": "ISO 4217 currency code (e.g., EUR, USD)"
  },
  "status": {
    "type": "string",
    "required": false,
    "default": "active",
    "enum": ["active", "completed", "cancelled", "on_hold"],
    "description": "Project status"
  },
  "ms_project_guid": {
    "type": "string",
    "required": false,
    "maxLength": 50,
    "description": "MS Project GUID for round-trip compatibility"
  },
  "ms_project_save_version": {
    "type": "integer",
    "required": false,
    "description": "MS Project SaveVersion field"
  },
  "creation_date": {
    "type": "datetime",
    "required": false,
    "format": "ISO 8601",
    "description": "Original MS Project creation date"
  },
  "last_saved_date": {
    "type": "datetime",
    "required": false,
    "format": "ISO 8601",
    "description": "MS Project last saved date"
  },
  "calendar_uid": {
    "type": "integer",
    "required": false,
    "description": "MS Project calendar UID"
  },
  "minutes_per_day": {
    "type": "integer",
    "required": false,
    "default": 420,
    "description": "Working minutes per day (420 = 7 hours)"
  },
  "minutes_per_week": {
    "type": "integer",
    "required": false,
    "default": 2100,
    "description": "Working minutes per week (2100 = 35 hours)"
  },
  "days_per_month": {
    "type": "integer",
    "required": false,
    "default": 20,
    "description": "Working days per month"
  },
  "week_start_day": {
    "type": "integer",
    "required": false,
    "default": 1,
    "description": "First day of week (0=Sunday, 1=Monday)"
  },
  "default_start_time": {
    "type": "string",
    "required": false,
    "default": "09:00:00",
    "format": "HH:MM:SS",
    "description": "Default task start time"
  },
  "default_finish_time": {
    "type": "string",
    "required": false,
    "default": "18:00:00",
    "format": "HH:MM:SS",
    "description": "Default task finish time"
  },
  "created_at": {
    "type": "datetime",
    "required": true,
    "format": "ISO 8601",
    "description": "Record creation timestamp (auto-generated)"
  },
  "updated_at": {
    "type": "datetime",
    "required": true,
    "format": "ISO 8601",
    "description": "Record last update timestamp (auto-updated)"
  }
}
```

**Example:**
```json
{
  "id": "a1b2c3d4-e5f6-4a5b-8c9d-0e1f2a3b4c5d",
  "company_id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Planning BAGUERA 2025",
  "code": "G.DED.22966",
  "title": "Planning RCD",
  "start_date": "2024-11-25T09:00:00Z",
  "finish_date": "2027-02-19T18:00:00Z",
  "budget": 1500000.00,
  "currency_code": "EUR",
  "status": "active",
  "ms_project_guid": "264A1861-0FAB-EF11-934B-F4EE08B24B68",
  "ms_project_save_version": 14,
  "creation_date": "2024-11-25T09:00:00Z",
  "last_saved_date": "2026-01-10T09:21:00Z",
  "calendar_uid": 1,
  "minutes_per_day": 420,
  "minutes_per_week": 2100,
  "days_per_month": 20,
  "week_start_day": 1,
  "default_start_time": "09:00:00",
  "default_finish_time": "18:00:00",
  "created_at": "2026-01-10T10:00:00Z",
  "updated_at": "2026-01-10T10:00:00Z"
}
```

#### Task Model

```json
{
  "id": {
    "type": "uuid",
    "required": true,
    "description": "Unique identifier (UUID v4), auto-generated"
  },
  "project_id": {
    "type": "uuid",
    "required": true,
    "description": "Parent project reference"
  },
  "parent_id": {
    "type": "uuid",
    "required": false,
    "nullable": true,
    "description": "Parent task for WBS hierarchy (null for top-level tasks)"
  },
  "ms_project_uid": {
    "type": "integer",
    "required": false,
    "description": "MS Project UID (unique within project)"
  },
  "ms_project_id": {
    "type": "integer",
    "required": false,
    "description": "MS Project ID (display order)"
  },
  "ms_project_guid": {
    "type": "string",
    "required": false,
    "maxLength": 50,
    "description": "MS Project GUID"
  },
  "name": {
    "type": "string",
    "required": true,
    "minLength": 1,
    "maxLength": 255,
    "description": "Task name"
  },
  "wbs": {
    "type": "string",
    "required": false,
    "maxLength": 50,
    "description": "Work Breakdown Structure code (e.g., 5.6, 1.2.3)"
  },
  "outline_number": {
    "type": "string",
    "required": false,
    "maxLength": 50,
    "description": "MS Project OutlineNumber (e.g., 5.6)"
  },
  "outline_level": {
    "type": "integer",
    "required": false,
    "minimum": 0,
    "description": "Hierarchical level (0=top, 1=child, 2=grandchild...)"
  },
  "start": {
    "type": "datetime",
    "required": true,
    "format": "ISO 8601",
    "description": "Task start date/time",
    "validation": "Must be before finish (except milestones)"
  },
  "finish": {
    "type": "datetime",
    "required": true,
    "format": "ISO 8601",
    "description": "Task finish date/time"
  },
  "duration": {
    "type": "string",
    "required": false,
    "format": "ISO 8601 duration (e.g., PT8H0M0S for 8 hours)",
    "description": "Task duration in ISO 8601 format"
  },
  "work": {
    "type": "string",
    "required": false,
    "format": "ISO 8601 duration",
    "description": "Total work effort (hours) in ISO 8601 format"
  },
  "cost": {
    "type": "decimal",
    "required": false,
    "precision": "2 decimal places",
    "minimum": 0,
    "description": "Planned task cost"
  },
  "fixed_cost": {
    "type": "decimal",
    "required": false,
    "default": 0,
    "precision": "2 decimal places",
    "description": "Fixed cost not related to resources"
  },
  "is_milestone": {
    "type": "boolean",
    "required": false,
    "default": false,
    "description": "True if task is a milestone (zero duration)"
  },
  "is_summary": {
    "type": "boolean",
    "required": false,
    "default": false,
    "description": "True if task is a summary (parent) task"
  },
  "is_deliverable": {
    "type": "boolean",
    "required": false,
    "default": false,
    "description": "True if task produces a deliverable"
  },
  "is_critical": {
    "type": "boolean",
    "required": false,
    "default": false,
    "description": "True if task is on critical path"
  },
  "status": {
    "type": "string",
    "required": false,
    "default": "not_started",
    "enum": ["not_started", "in_progress", "completed", "cancelled"],
    "description": "Task status"
  },
  "percent_complete": {
    "type": "integer",
    "required": false,
    "default": 0,
    "minimum": 0,
    "maximum": 100,
    "description": "Percentage complete (0-100)"
  },
  "percent_work_complete": {
    "type": "integer",
    "required": false,
    "default": 0,
    "minimum": 0,
    "maximum": 100,
    "description": "Work percentage complete (0-100)"
  },
  "early_start": {
    "type": "datetime",
    "required": false,
    "format": "ISO 8601",
    "description": "Earliest possible start (critical path calculation)"
  },
  "early_finish": {
    "type": "datetime",
    "required": false,
    "format": "ISO 8601",
    "description": "Earliest possible finish"
  },
  "late_start": {
    "type": "datetime",
    "required": false,
    "format": "ISO 8601",
    "description": "Latest allowable start without delaying project"
  },
  "late_finish": {
    "type": "datetime",
    "required": false,
    "format": "ISO 8601",
    "description": "Latest allowable finish"
  },
  "total_slack": {
    "type": "integer",
    "required": false,
    "default": 0,
    "description": "Total slack/float in minutes"
  },
  "free_slack": {
    "type": "integer",
    "required": false,
    "default": 0,
    "description": "Free slack in minutes (delay without affecting successors)"
  },
  "manual_scheduling": {
    "type": "boolean",
    "required": false,
    "default": false,
    "description": "True if task uses manual scheduling (MS Project)"
  },
  "actual_start": {
    "type": "datetime",
    "required": false,
    "nullable": true,
    "format": "ISO 8601",
    "description": "Actual start date (when work began)"
  },
  "actual_finish": {
    "type": "datetime",
    "required": false,
    "nullable": true,
    "format": "ISO 8601",
    "description": "Actual finish date (when completed)"
  },
  "actual_cost": {
    "type": "decimal",
    "required": false,
    "default": 0,
    "precision": "2 decimal places",
    "description": "Actual cost incurred (from expenses)"
  },
  "actual_work": {
    "type": "string",
    "required": false,
    "format": "ISO 8601 duration",
    "description": "Actual work performed"
  },
  "remaining_cost": {
    "type": "decimal",
    "required": false,
    "precision": "2 decimal places",
    "description": "RAE - Remaining cost to complete (latest value)"
  },
  "remaining_work": {
    "type": "string",
    "required": false,
    "format": "ISO 8601 duration",
    "description": "Remaining work to complete"
  },
  "predecessors": {
    "type": "array",
    "required": false,
    "items": {
      "type": "object",
      "properties": {
        "predecessor_task_id": {
          "type": "uuid",
          "description": "Predecessor task reference"
        },
        "type": {
          "type": "string",
          "enum": ["FS", "SS", "FF", "SF"],
          "description": "Relationship type (FS=Finish-to-Start, SS=Start-to-Start, FF=Finish-to-Finish, SF=Start-to-Finish)"
        },
        "lag": {
          "type": "integer",
          "description": "Lag time in minutes (positive=delay, negative=lead)"
        }
      }
    },
    "description": "Array of predecessor relationships"
  },
  "created_at": {
    "type": "datetime",
    "required": true,
    "format": "ISO 8601",
    "description": "Record creation timestamp"
  },
  "updated_at": {
    "type": "datetime",
    "required": true,
    "format": "ISO 8601",
    "description": "Record last update timestamp"
  }
}
```

**Example:**
```json
{
  "id": "b2c3d4e5-f6a7-4b5c-9d0e-1f2a3b4c5d6e",
  "project_id": "a1b2c3d4-e5f6-4a5b-8c9d-0e1f2a3b4c5d",
  "parent_id": null,
  "ms_project_uid": 42,
  "ms_project_id": 39,
  "ms_project_guid": "7225FBCF-D0AC-EF11-934C-F4EE08B24B68",
  "name": "RQF",
  "wbs": "5.6",
  "outline_number": "5.6",
  "outline_level": 2,
  "start": "2027-01-22T18:00:00Z",
  "finish": "2027-01-22T18:00:00Z",
  "duration": "PT0H0M0S",
  "work": "PT0H0M0S",
  "cost": 0.00,
  "fixed_cost": 0.00,
  "is_milestone": true,
  "is_summary": false,
  "is_deliverable": false,
  "is_critical": true,
  "status": "not_started",
  "percent_complete": 0,
  "percent_work_complete": 0,
  "early_start": "2027-01-22T18:00:00Z",
  "early_finish": "2027-01-22T18:00:00Z",
  "late_start": "2027-01-25T09:00:00Z",
  "late_finish": "2027-01-25T09:00:00Z",
  "total_slack": 0,
  "free_slack": 0,
  "manual_scheduling": false,
  "actual_start": null,
  "actual_finish": null,
  "actual_cost": 0.00,
  "actual_work": "PT0H0M0S",
  "remaining_cost": 0.00,
  "remaining_work": "PT0H0M0S",
  "predecessors": [
    {
      "predecessor_task_id": "c3d4e5f6-a7b8-4c5d-0e1f-2a3b4c5d6e7f",
      "type": "FS",
      "lag": 0
    }
  ],
  "created_at": "2026-01-10T10:00:00Z",
  "updated_at": "2026-01-10T10:00:00Z"
}
```

#### Milestone Model

```json
{
  "id": {
    "type": "uuid",
    "required": true,
    "description": "Unique identifier (UUID v4), auto-generated"
  },
  "project_id": {
    "type": "uuid",
    "required": true,
    "description": "Parent project reference"
  },
  "task_id": {
    "type": "uuid",
    "required": false,
    "nullable": true,
    "description": "Associated task (if milestone originates from MS Project task)"
  },
  "name": {
    "type": "string",
    "required": true,
    "minLength": 1,
    "maxLength": 255,
    "description": "Milestone name"
  },
  "description": {
    "type": "string",
    "required": false,
    "maxLength": 1000,
    "description": "Milestone description"
  },
  "target_date": {
    "type": "datetime",
    "required": true,
    "format": "ISO 8601",
    "description": "Target completion date",
    "validation": "Must not overlap with other milestones"
  },
  "planned_date": {
    "type": "datetime",
    "required": false,
    "format": "ISO 8601",
    "description": "Original planned date (for time/time diagrams)"
  },
  "actual_date": {
    "type": "datetime",
    "required": false,
    "nullable": true,
    "format": "ISO 8601",
    "description": "Actual completion date (null if not achieved)"
  },
  "status": {
    "type": "string",
    "required": false,
    "default": "upcoming",
    "enum": ["upcoming", "achieved", "missed"],
    "description": "Milestone status (auto-updated based on actual_date)"
  },
  "budget": {
    "type": "decimal",
    "required": false,
    "precision": "2 decimal places",
    "minimum": 0,
    "description": "Budget allocated to milestone (for EV calculation)"
  },
  "planned_date_history": {
    "type": "array",
    "required": false,
    "items": {
      "type": "object",
      "properties": {
        "date": {"type": "datetime", "format": "ISO 8601"},
        "planned_date": {"type": "datetime", "format": "ISO 8601"},
        "updated_at": {"type": "datetime", "format": "ISO 8601"}
      }
    },
    "description": "Historical planned dates for variance tracking"
  },
  "created_at": {
    "type": "datetime",
    "required": true,
    "format": "ISO 8601",
    "description": "Record creation timestamp"
  },
  "updated_at": {
    "type": "datetime",
    "required": true,
    "format": "ISO 8601",
    "description": "Record last update timestamp"
  }
}
```

**Example:**
```json
{
  "id": "d4e5f6a7-b8c9-4d5e-1f2a-3b4c5d6e7f8a",
  "project_id": "a1b2c3d4-e5f6-4a5b-8c9d-0e1f2a3b4c5d",
  "task_id": "b2c3d4e5-f6a7-4b5c-9d0e-1f2a3b4c5d6e",
  "name": "RQF",
  "description": "Requirements Qualification Review",
  "target_date": "2027-01-22T18:00:00Z",
  "planned_date": "2027-01-22T18:00:00Z",
  "actual_date": null,
  "status": "upcoming",
  "budget": 50000.00,
  "planned_date_history": [
    {
      "date": "2026-01-10T00:00:00Z",
      "planned_date": "2027-01-22T18:00:00Z",
      "updated_at": "2026-01-10T10:00:00Z"
    }
  ],
  "created_at": "2026-01-10T10:00:00Z",
  "updated_at": "2026-01-10T10:00:00Z"
}
```

#### Deliverable Model

```json
{
  "id": {
    "type": "uuid",
    "required": true,
    "description": "Unique identifier (UUID v4), auto-generated"
  },
  "project_id": {
    "type": "uuid",
    "required": true,
    "description": "Parent project reference"
  },
  "milestone_id": {
    "type": "uuid",
    "required": true,
    "description": "Associated milestone"
  },
  "task_id": {
    "type": "uuid",
    "required": false,
    "nullable": true,
    "description": "Associated task (if deliverable is task-based)"
  },
  "name": {
    "type": "string",
    "required": true,
    "minLength": 1,
    "maxLength": 255,
    "description": "Deliverable name"
  },
  "description": {
    "type": "string",
    "required": false,
    "maxLength": 2000,
    "description": "Detailed description"
  },
  "type": {
    "type": "string",
    "required": false,
    "enum": ["document", "code", "system", "training", "hardware", "other"],
    "description": "Deliverable type/category"
  },
  "status": {
    "type": "string",
    "required": false,
    "default": "planned",
    "enum": ["planned", "in_progress", "delivered", "accepted", "rejected"],
    "description": "Deliverable status"
  },
  "planned_delivery_date": {
    "type": "datetime",
    "required": false,
    "format": "ISO 8601",
    "description": "Planned delivery date"
  },
  "actual_delivery_date": {
    "type": "datetime",
    "required": false,
    "nullable": true,
    "format": "ISO 8601",
    "description": "Actual delivery date"
  },
  "acceptance_date": {
    "type": "datetime",
    "required": false,
    "nullable": true,
    "format": "ISO 8601",
    "description": "Acceptance/approval date"
  },
  "created_at": {
    "type": "datetime",
    "required": true,
    "format": "ISO 8601",
    "description": "Record creation timestamp"
  },
  "updated_at": {
    "type": "datetime",
    "required": true,
    "format": "ISO 8601",
    "description": "Record last update timestamp"
  }
}
```

**Example:**
```json
{
  "id": "e5f6a7b8-c9d0-4e5f-2a3b-4c5d6e7f8a9b",
  "project_id": "a1b2c3d4-e5f6-4a5b-8c9d-0e1f2a3b4c5d",
  "milestone_id": "d4e5f6a7-b8c9-4d5e-1f2a-3b4c5d6e7f8a",
  "task_id": null,
  "name": "Requirements Specification Document",
  "description": "Complete requirements specification including functional, non-functional, and technical requirements",
  "type": "document",
  "status": "planned",
  "planned_delivery_date": "2027-01-22T18:00:00Z",
  "actual_delivery_date": null,
  "acceptance_date": null,
  "created_at": "2026-01-10T10:00:00Z",
  "updated_at": "2026-01-10T10:00:00Z"
}
```

#### Resource Model

```json
{
  "id": {
    "type": "uuid",
    "required": true,
    "description": "Unique identifier (UUID v4), auto-generated"
  },
  "company_id": {
    "type": "uuid",
    "required": true,
    "description": "Tenant identifier for multi-tenant isolation"
  },
  "ms_project_uid": {
    "type": "integer",
    "required": false,
    "description": "MS Project resource UID"
  },
  "name": {
    "type": "string",
    "required": true,
    "minLength": 1,
    "maxLength": 255,
    "description": "Resource name"
  },
  "type": {
    "type": "string",
    "required": false,
    "default": "labor",
    "enum": ["labor", "material", "cost"],
    "description": "Resource type (labor=personnel, material=equipment/supplies, cost=fixed cost)"
  },
  "standard_rate": {
    "type": "decimal",
    "required": false,
    "default": 0,
    "precision": "2 decimal places",
    "minimum": 0,
    "description": "Standard hourly rate for labor resources"
  },
  "overtime_rate": {
    "type": "decimal",
    "required": false,
    "default": 0,
    "precision": "2 decimal places",
    "minimum": 0,
    "description": "Overtime hourly rate"
  },
  "email": {
    "type": "string",
    "required": false,
    "maxLength": 255,
    "format": "email",
    "description": "Resource email address"
  },
  "is_active": {
    "type": "boolean",
    "required": false,
    "default": true,
    "description": "True if resource is currently active/available"
  },
  "created_at": {
    "type": "datetime",
    "required": true,
    "format": "ISO 8601",
    "description": "Record creation timestamp"
  },
  "updated_at": {
    "type": "datetime",
    "required": true,
    "format": "ISO 8601",
    "description": "Record last update timestamp"
  }
}
```

**Example:**
```json
{
  "id": "f6a7b8c9-d0e1-4f5a-3b4c-5d6e7f8a9b0c",
  "company_id": "550e8400-e29b-41d4-a716-446655440000",
  "ms_project_uid": 1,
  "name": "Jean Dupont",
  "type": "labor",
  "standard_rate": 85.00,
  "overtime_rate": 127.50,
  "email": "jean.dupont@example.com",
  "is_active": true,
  "created_at": "2026-01-10T10:00:00Z",
  "updated_at": "2026-01-10T10:00:00Z"
}
```

#### Assignment Model

```json
{
  "id": {
    "type": "uuid",
    "required": true,
    "description": "Unique identifier (UUID v4), auto-generated"
  },
  "project_id": {
    "type": "uuid",
    "required": true,
    "description": "Parent project reference"
  },
  "task_id": {
    "type": "uuid",
    "required": true,
    "description": "Assigned task reference"
  },
  "resource_id": {
    "type": "uuid",
    "required": true,
    "description": "Assigned resource reference"
  },
  "ms_project_uid": {
    "type": "integer",
    "required": false,
    "description": "MS Project assignment UID"
  },
  "work_hours": {
    "type": "string",
    "required": false,
    "format": "ISO 8601 duration",
    "description": "Planned work hours for this assignment (e.g., PT40H0M0S)"
  },
  "percent_allocation": {
    "type": "integer",
    "required": false,
    "default": 100,
    "minimum": 0,
    "maximum": 100,
    "description": "Resource allocation percentage (100 = full-time on this task)"
  },
  "cost": {
    "type": "decimal",
    "required": false,
    "precision": "2 decimal places",
    "minimum": 0,
    "description": "Planned cost for this assignment (calculated from work_hours × rate)"
  },
  "actual_work": {
    "type": "string",
    "required": false,
    "format": "ISO 8601 duration",
    "description": "Actual work performed"
  },
  "actual_cost": {
    "type": "decimal",
    "required": false,
    "default": 0,
    "precision": "2 decimal places",
    "description": "Actual cost incurred"
  },
  "created_at": {
    "type": "datetime",
    "required": true,
    "format": "ISO 8601",
    "description": "Record creation timestamp"
  },
  "updated_at": {
    "type": "datetime",
    "required": true,
    "format": "ISO 8601",
    "description": "Record last update timestamp"
  }
}
```

**Example:**
```json
{
  "id": "a7b8c9d0-e1f2-4a5b-4c5d-6e7f8a9b0c1d",
  "project_id": "a1b2c3d4-e5f6-4a5b-8c9d-0e1f2a3b4c5d",
  "task_id": "b2c3d4e5-f6a7-4b5c-9d0e-1f2a3b4c5d6e",
  "resource_id": "f6a7b8c9-d0e1-4f5a-3b4c-5d6e7f8a9b0c",
  "ms_project_uid": 100,
  "work_hours": "PT40H0M0S",
  "percent_allocation": 50,
  "cost": 3400.00,
  "actual_work": "PT0H0M0S",
  "actual_cost": 0.00,
  "created_at": "2026-01-10T10:00:00Z",
  "updated_at": "2026-01-10T10:00:00Z"
}
```

#### Expense Model

```json
{
  "id": {
    "type": "uuid",
    "required": true,
    "description": "Unique identifier (UUID v4), auto-generated"
  },
  "project_id": {
    "type": "uuid",
    "required": true,
    "description": "Parent project reference"
  },
  "milestone_id": {
    "type": "uuid",
    "required": false,
    "nullable": true,
    "description": "Allocated milestone (auto-assigned based on expense date)"
  },
  "resource_id": {
    "type": "uuid",
    "required": false,
    "nullable": true,
    "description": "Associated resource (for labor expenses)"
  },
  "date": {
    "type": "datetime",
    "required": true,
    "format": "ISO 8601",
    "description": "Expense date (Date de la pièce from ERP)",
    "validation": "Must fall between project milestone dates"
  },
  "amount": {
    "type": "decimal",
    "required": true,
    "precision": "2 decimal places",
    "minimum": 0,
    "description": "Expense amount"
  },
  "category": {
    "type": "string",
    "required": true,
    "enum": ["labor", "procurement", "subcontracting", "overhead"],
    "description": "Expense category (labor=MO, procurement=Achat, subcontracting=ST, overhead=Frais)"
  },
  "description": {
    "type": "string",
    "required": false,
    "maxLength": 500,
    "description": "Expense description"
  },
  "reference_number": {
    "type": "string",
    "required": false,
    "maxLength": 50,
    "description": "ERP reference number (Nº pièce référence)"
  },
  "purchase_document": {
    "type": "string",
    "required": false,
    "maxLength": 50,
    "description": "Document d'achat from ERP"
  },
  "fiscal_year": {
    "type": "integer",
    "required": false,
    "description": "Exercice comptable from ERP"
  },
  "period": {
    "type": "integer",
    "required": false,
    "description": "Période from ERP (month)"
  },
  "otp_element": {
    "type": "string",
    "required": false,
    "maxLength": 50,
    "description": "Elément d'OTP from ERP (project code)"
  },
  "accounting_nature": {
    "type": "string",
    "required": false,
    "maxLength": 50,
    "description": "Nature comptable from ERP"
  },
  "vendor_name": {
    "type": "string",
    "required": false,
    "maxLength": 255,
    "description": "Nom 1 from ERP (vendor or resource name)"
  },
  "origin_group": {
    "type": "string",
    "required": false,
    "maxLength": 50,
    "description": "Groupe d'origine from ERP"
  },
  "created_at": {
    "type": "datetime",
    "required": true,
    "format": "ISO 8601",
    "description": "Record creation timestamp"
  },
  "updated_at": {
    "type": "datetime",
    "required": true,
    "format": "ISO 8601",
    "description": "Record last update timestamp"
  }
}
```

**Example:**
```json
{
  "id": "b8c9d0e1-f2a3-4b5c-5d6e-7f8a9b0c1d2e",
  "project_id": "a1b2c3d4-e5f6-4a5b-8c9d-0e1f2a3b4c5d",
  "milestone_id": "d4e5f6a7-b8c9-4d5e-1f2a-3b4c5d6e7f8a",
  "resource_id": null,
  "date": "2025-04-25T00:00:00Z",
  "amount": 3820.00,
  "category": "subcontracting",
  "description": "REMISE EN ETAT ET RETOUR DES TIROIRS",
  "reference_number": "5129412025",
  "purchase_document": "24337010",
  "fiscal_year": 2025,
  "period": 5,
  "otp_element": "G.DED.22966/13984",
  "accounting_nature": "60510000",
  "vendor_name": "ARELIS",
  "origin_group": "STOR",
  "created_at": "2026-01-10T10:00:00Z",
  "updated_at": "2026-01-10T10:00:00Z"
}
```

#### RAE History Model

```json
{
  "id": {
    "type": "uuid",
    "required": true,
    "description": "Unique identifier (UUID v4), auto-generated"
  },
  "task_id": {
    "type": "uuid",
    "required": true,
    "description": "Associated task reference"
  },
  "date": {
    "type": "datetime",
    "required": true,
    "format": "ISO 8601",
    "description": "RAE update date (typically month-end)"
  },
  "remaining_cost": {
    "type": "decimal",
    "required": true,
    "precision": "2 decimal places",
    "minimum": 0,
    "description": "Remaining cost to complete task (RAE value)"
  },
  "comment": {
    "type": "string",
    "required": false,
    "maxLength": 500,
    "description": "Optional comment explaining RAE update"
  },
  "updated_by": {
    "type": "uuid",
    "required": false,
    "description": "User ID who made the update (from JWT)"
  },
  "created_at": {
    "type": "datetime",
    "required": true,
    "format": "ISO 8601",
    "description": "Record creation timestamp"
  }
}
```

**Example:**
```json
{
  "id": "c9d0e1f2-a3b4-4c5d-6e7f-8a9b0c1d2e3f",
  "task_id": "b2c3d4e5-f6a7-4b5c-9d0e-1f2a3b4c5d6e",
  "date": "2026-01-31T23:59:59Z",
  "remaining_cost": 12500.00,
  "comment": "Updated based on Q1 progress review",
  "updated_by": "550e8400-e29b-41d4-a716-446655440000",
  "created_at": "2026-01-10T10:00:00Z"
}
```

### 4.2. Project Endpoints

#### Create Project
[À COMPLÉTER - POST /v0/projects]

#### List Projects
[À COMPLÉTER - GET /v0/projects]

#### Get Project
[À COMPLÉTER - GET /v0/projects/{id}]

#### Update Project
[À COMPLÉTER - PATCH /v0/projects/{id}]

#### Delete Project
[À COMPLÉTER - DELETE /v0/projects/{id}]

### 4.3. Task Endpoints

#### Create Task
[À COMPLÉTER - POST /v0/projects/{project_id}/tasks]

#### Bulk Create Tasks
[À COMPLÉTER - POST /v0/projects/{project_id}/tasks/bulk]

#### List Tasks
[À COMPLÉTER - GET /v0/projects/{project_id}/tasks]

#### Get Task
[À COMPLÉTER - GET /v0/projects/{project_id}/tasks/{id}]

#### Update Task
[À COMPLÉTER - PATCH /v0/projects/{project_id}/tasks/{id}]

#### Delete Task
[À COMPLÉTER - DELETE /v0/projects/{project_id}/tasks/{id}]

### 4.4. Milestone Endpoints

#### Create Milestone
[À COMPLÉTER - POST /v0/projects/{project_id}/milestones]

#### List Milestones
[À COMPLÉTER - GET /v0/projects/{project_id}/milestones]

#### Get Milestone
[À COMPLÉTER - GET /v0/projects/{project_id}/milestones/{id}]

#### Update Milestone
[À COMPLÉTER - PATCH /v0/projects/{project_id}/milestones/{id}]

#### Delete Milestone
[À COMPLÉTER - DELETE /v0/projects/{project_id}/milestones/{id}]

### 4.5. Resource Endpoints

#### Create Resource
[À COMPLÉTER - POST /v0/resources]

#### List Resources
[À COMPLÉTER - GET /v0/resources]

#### Get Resource
[À COMPLÉTER - GET /v0/resources/{id}]

#### Update Resource
[À COMPLÉTER - PATCH /v0/resources/{id}]

#### Delete Resource
[À COMPLÉTER - DELETE /v0/resources/{id}]

### 4.6. Assignment Endpoints

#### Create Assignment
[À COMPLÉTER - POST /v0/projects/{project_id}/assignments]

#### List Assignments
[À COMPLÉTER - GET /v0/projects/{project_id}/assignments]

#### Get Assignment
[À COMPLÉTER - GET /v0/projects/{project_id}/assignments/{id}]

#### Update Assignment
[À COMPLÉTER - PATCH /v0/projects/{project_id}/assignments/{id}]

#### Delete Assignment
[À COMPLÉTER - DELETE /v0/projects/{project_id}/assignments/{id}]

### 4.7. Expense Endpoints

#### Create Expense
[À COMPLÉTER - POST /v0/projects/{project_id}/expenses]

#### Bulk Create Expenses
[À COMPLÉTER - POST /v0/projects/{project_id}/expenses/bulk]

#### List Expenses
[À COMPLÉTER - GET /v0/projects/{project_id}/expenses]

#### Get Expense
[À COMPLÉTER - GET /v0/projects/{project_id}/expenses/{id}]

#### Update Expense
[À COMPLÉTER - PATCH /v0/projects/{project_id}/expenses/{id}]

#### Delete Expense
[À COMPLÉTER - DELETE /v0/projects/{project_id}/expenses/{id}]

### 4.8. RAE (Reste À Engager) Endpoints

#### Update Task RAE
[À COMPLÉTER - POST /v0/projects/{project_id}/tasks/{task_id}/rae]

#### Get RAE History
[À COMPLÉTER - GET /v0/projects/{project_id}/tasks/{task_id}/rae/history]

### 4.9. EVM Indicators Endpoints

#### Get Project EVM Indicators
[À COMPLÉTER - GET /v0/projects/{project_id}/evm]

#### Get EVM Time Series
[À COMPLÉTER - GET /v0/projects/{project_id}/evm/timeseries]

#### Get EVM Forecasts
[À COMPLÉTER - GET /v0/projects/{project_id}/evm/forecasts]

### 4.10. Statistics Endpoints

#### Get Expense Breakdown by Category
[À COMPLÉTER - GET /v0/projects/{project_id}/statistics/expenses/by-category]

#### Get Labor Cost by Resource
[À COMPLÉTER - GET /v0/projects/{project_id}/statistics/labor/by-resource]

#### Get Monthly Expense Distribution
[À COMPLÉTER - GET /v0/projects/{project_id}/statistics/expenses/monthly]

### 4.11. Progress Update Endpoints

#### Update Project Progress
[À COMPLÉTER - POST /v0/projects/{project_id}/progress]

#### Get Progress History
[À COMPLÉTER - GET /v0/projects/{project_id}/progress/history]

### Standard Response Headers

| Header | Description |
|--------|-------------|
| X-Correlation-ID | Request correlation ID for tracing |
| X-RateLimit-Limit | Maximum requests per window |
| X-RateLimit-Remaining | Remaining requests in window |
| X-RateLimit-Reset | Unix timestamp when limit resets |

### Standard Status Codes

| Code | Description | When to Use |
|------|-------------|-------------|
| 200 | OK | Successful GET/PATCH/DELETE |
| 201 | Created | Successful POST |
| 204 | No Content | Successful DELETE with no body |
| 400 | Bad Request | Validation errors |
| 401 | Unauthorized | Invalid/missing JWT token |
| 403 | Forbidden | Insufficient permissions |
| 404 | Not Found | Resource not found |
| 409 | Conflict | Duplicate resource or constraint violation |
| 422 | Unprocessable Entity | Business logic validation error |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Unexpected server error |

## 5. Acceptance Criteria

[À COMPLÉTER - Critères d'acceptation testables]

### Project Management (AC-PM-xxx)
- **AC-PM-001**: [À COMPLÉTER]

### Task Management (AC-TM-xxx)
- **AC-TM-001**: [À COMPLÉTER]

### EVM Calculations (AC-EVM-xxx)
- **AC-EVM-001**: [À COMPLÉTER]

## 6. Test Automation Strategy

[À COMPLÉTER - Stratégie de test]

- **Test Levels**: Unit, Integration, End-to-End
- **Frameworks**: pytest, pytest-flask, pytest-mock
- **Test Data Management**: [À COMPLÉTER]
- **CI/CD Integration**: GitHub Actions with test suite execution
- **Coverage Requirements**: Minimum 80% code coverage
- **Performance Testing**: [À COMPLÉTER]

## 7. Rationale & Context

[À COMPLÉTER - Justification des choix de conception]

### Design Decisions

#### Milestone-Based AC Allocation
[À COMPLÉTER - Pourquoi allouer les dépenses par jalon plutôt que par tâche]

#### Dual EV Calculation Methods
[À COMPLÉTER - Pourquoi proposer 2 méthodes de calcul EV]

#### Task Hierarchy Structure
[À COMPLÉTER - Arborescence vs plat pour les tâches]

#### RAE History Tracking
[À COMPLÉTER - Pourquoi historiser le RAE]

## 8. Dependencies & External Integrations

### External Systems
- **EXT-001**: MS Project XML format - Microsoft Project 2010+ XML schema
- **EXT-002**: Excel ERP exports - Monthly expense data

### Third-Party Services
- **SVC-001**: Guardian service - Authorization and access control (mocked for POC)
- **SVC-002**: Identity service - JWT authentication (mocked for POC)

### Infrastructure Dependencies
- **INF-001**: PostgreSQL 13+ - Relational database with JSON support
- **INF-002**: Redis - Optional caching for EVM calculations (future)

### Data Dependencies
- **DAT-001**: poc-import service - MS Project XML and Excel imports
- **DAT-002**: poc-export service - Excel report generation

### Technology Platform Dependencies
- **PLT-001**: Python 3.11+ - Runtime environment
- **PLT-002**: Flask 3.0+ - Web framework
- **PLT-003**: SQLAlchemy 2.0+ - ORM layer
- **PLT-004**: Marshmallow 3.0+ - Schema validation and serialization

### Compliance Dependencies
- **COM-001**: Multi-tenant data isolation - Company-based data segregation

## 9. Examples & Edge Cases

[À COMPLÉTER - Exemples concrets et cas limites]

### Example: Create Project with Tasks
```json
[À COMPLÉTER]
```

### Example: EVM Calculation Response
```json
[À COMPLÉTER]
```

### Edge Case: Expense Before First Milestone
[À COMPLÉTER]

### Edge Case: Task with Circular Dependencies
[À COMPLÉTER]

### Edge Case: RAE Update with Negative Value
[À COMPLÉTER]

## 10. Validation Criteria

[À COMPLÉTER - Critères de validation de la conformité]

- **VAL-001**: All endpoints SHALL return responses conforming to schemas defined in section 4
- **VAL-002**: EVM calculations SHALL produce results within 0.01% margin of reference calculations
- **VAL-003**: Critical path calculation SHALL match MS Project output
- **VAL-004**: Multi-tenant isolation SHALL prevent cross-company data access
- **VAL-005**: [À COMPLÉTER]

## 11. Related Specifications / Further Reading

- [Health Endpoints Specification](./schema-api-health-endpoints.md)
- [Metrics Endpoint Specification](./schema-api-metrics-endpoint.md)
- [POC Import Service Specification](../poc-import/) (to be created)
- [POC Export Service Specification](../poc-export/) (to be created)
- [MS Project XML Schema Reference](https://docs.microsoft.com/en-us/previous-versions/office/developer/office-2010/bb968652(v=office.14))
- [Earned Value Management Guide (PMI)](https://www.pmi.org/)
