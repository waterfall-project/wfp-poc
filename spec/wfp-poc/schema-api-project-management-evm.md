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

### Requirements Overview

The wfp-poc API specification defines 105 requirements across 10 functional categories, plus security, performance, and architectural constraints.

#### Diagram 1: Hierarchical Mind Map

This mind map provides a **comprehensive catalog** of all requirements organized by domain. Each branch shows the detailed functional capabilities, security controls, performance targets, and constraints. Use this diagram to:
- Understand the breadth of the specification (what features are included)
- Explore specific capabilities within each domain (e.g., what EVM calculations are supported)
- Identify gaps or missing functionality during requirements review

**Legend:**
- **Central Node**: Overall requirements container (wfp-poc Requirements)
- **Primary Branches**: Five main requirement categories (Functional, Security, Performance, Constraints, Guidelines)
- **Secondary Branches**: Specific requirement domains (REQ-PM, REQ-TM, SEC-AUTH, etc.)
- **Leaf Nodes**: Individual capabilities or constraints within each domain

```mermaid
mindmap
  root((wfp-poc<br/>Requirements))
    Functional Requirements
      REQ-PM: Project Management
        CRUD operations
        Multi-tenant isolation
        MS Project metadata
        Bulk import support
      REQ-TM: Task Management
        Task hierarchy WBS
        Predecessor relationships
        Summary task aggregation
        Critical path data
      REQ-RM: Resource Management
        Labor, Material, Cost types
        Cost rates and units
        Resource calendars
      REQ-AS: Assignment Management
        Task-resource allocation
        Work hours tracking
        Cost calculation
      REQ-MD: Milestones & Deliverables
        Milestone tracking
        Budget weight allocation
        Deliverable management
        Target date constraints
      REQ-ET: Expense Tracking
        ERP import support
        Milestone allocation
        Category classification
        Multi-currency support
      REQ-RAE: Reste À Engager
        Monthly RAE updates
        Historical tracking
        Physical progress calculation
      REQ-EVM: EVM Calculations
        Dual EV methods
        PV/AC/EV computation
        CPI/SPI indicators
        Three EAC projections
      REQ-ST: Statistics & Reporting
        Time-series data
        ECharts format
        Expense breakdown
        Resource utilization
      REQ-PU: Progress Updates
        Task completion tracking
        Milestone achievement
        RAE estimation
    Security Requirements
      SEC-AUTH: Authentication
        JWT validation
        Required claims
        Token expiration
      SEC-AUTHZ: Authorization
        Guardian integration
        RBAC permissions
        Company isolation
      SEC-INPUT: Input Validation
        Schema validation
        SQL injection prevention
        XSS protection
      SEC-RATE: Rate Limiting
        10 req/min per endpoint
        429 responses
        X-RateLimit headers
    Performance Requirements
      PERF-RESPONSE: Response Time
        <200ms list endpoints
        <500ms EVM calculations
        95th percentile SLA
      PERF-SCALE: Scalability
        100 concurrent users
        500 tasks per project
        Indexed queries
      PERF-PAGINATION: Pagination
        20 items per page default
        100 items maximum
        Cursor-based option
    Architectural Constraints
      CON-SCOPE: POC Limitations
        Monthly granularity
        Mock authentication
        No caching
        Single baseline
      CON-DATA: Data Constraints
        Non-overlapping milestones
        Task date ranges
        Budget weight sum=1.0
        Expense date validation
      CON-TECH: Technical Constraints
        Synchronous operations
        Fixed resource capacity
        Linear PV distribution
    Guidelines & Patterns
      GUD: Development Guidelines
        Waterfall template adherence
        Standard response formats
        ISO 8601 dates
        UUID identifiers
      PAT: Design Patterns
        Layered architecture
        Repository pattern
        DTO pattern
        Decorator pattern
```


#### Diagram 2: Dependency and Risk Analysis Graph

This directed graph shows **formal relationships between requirements** and highlights implementation priorities through color-coded risk levels. Use this diagram to:
- Identify critical path requirements (high-risk items that block others)
- Understand requirement dependencies (which must be implemented first)
- Plan implementation order based on derivation relationships
- Assess risk concentration (e.g., EVM depends on 4 high/medium risk domains)

**Legend:**

*Node Colors (Risk Levels):*
- 🔴 **Red (High Risk)**: Complex algorithms, critical security, high implementation effort
  - Examples: REQ-TM (task hierarchy), REQ-EVM (dual calculation methods), SEC-AUTH (JWT validation)
- 🟡 **Yellow (Medium Risk)**: Moderate complexity, integration with external systems
  - Examples: REQ-PM (multi-tenant isolation), REQ-ET (expense allocation), PERF-RESPONSE
- 🟢 **Green (Low Risk)**: Simple CRUD, straightforward logic, standard patterns
  - Examples: REQ-RM (resource management), REQ-ST (statistics), GUD-DEV (guidelines)
- 🔵 **Blue (Categories)**: Requirement group containers (non-implementable)
  - Examples: REQ-FUNC, REQ-SEC, REQ-PERF, CON-ALL, GUIDE-ALL

*Edge Types (Relationships):*
- **Solid arrows (→)**: Containment - parent contains child requirements
- **Dotted arrows (-.->)**: 
  - `derives` - requirement depends on another for implementation (e.g., REQ-EVM derives from REQ-PM)
  - `refines` - constraint refines a requirement (e.g., CON-DATA refines REQ-MD)
  - `traces` - guideline traces back to requirements (e.g., GUD-DEV traces to REQ-FUNC)

```mermaid
graph TB
    REQ-FUNC[Functional Requirements<br/>REQ-FUNC]
    REQ-PM[Project Management<br/>REQ-PM-001-007<br/>Risk: Medium]
    REQ-TM[Task Management<br/>REQ-TM-001-013<br/>Risk: High]
    REQ-RM[Resource Management<br/>REQ-RM-001-005<br/>Risk: Low]
    REQ-AS[Assignment Management<br/>REQ-AS-001-004<br/>Risk: Medium]
    REQ-MD[Milestones & Deliverables<br/>REQ-MD-001-007<br/>Risk: Medium]
    REQ-ET[Expense Tracking<br/>REQ-ET-001-006<br/>Risk: Medium]
    REQ-RAE[Reste À Engager<br/>REQ-RAE-001-005<br/>Risk: High]
    REQ-EVM[EVM Calculations<br/>REQ-EVM-001-011<br/>Risk: High]
    REQ-ST[Statistics & Reporting<br/>REQ-ST-001-005<br/>Risk: Low]
    REQ-PU[Progress Updates<br/>REQ-PU-001-003<br/>Risk: Medium]
    
    REQ-SEC[Security Requirements<br/>REQ-SEC]
    SEC-AUTH[Authentication<br/>SEC-001-003<br/>Risk: High]
    SEC-AUTHZ[Authorization<br/>SEC-004-006<br/>Risk: High]
    SEC-INPUT[Input Validation<br/>SEC-007-009<br/>Risk: High]
    SEC-RATE[Rate Limiting<br/>SEC-010<br/>Risk: Medium]
    
    REQ-PERF[Performance Requirements<br/>REQ-PERF]
    PERF-RESPONSE[Response Time<br/>PERF-001-003<br/>Risk: Medium]
    PERF-SCALE[Scalability<br/>PERF-004-006<br/>Risk: Medium]
    PERF-PAGINATION[Pagination<br/>PERF-007<br/>Risk: Low]
    
    CON-ALL[Architectural Constraints<br/>CON-ALL]
    CON-SCOPE[POC Limitations<br/>CON-001-009<br/>Risk: Low]
    CON-DATA[Data Constraints<br/>CON-003-004<br/>Risk: Medium]
    CON-TECH[Technical Constraints<br/>CON-005-008<br/>Risk: Low]
    
    GUIDE-ALL[Guidelines & Patterns<br/>GUIDE-ALL]
    GUD-DEV[Development Guidelines<br/>GUD-001-014<br/>Risk: Low]
    PAT-ARCH[Design Patterns<br/>PAT-001-010<br/>Risk: Low]
    
    %% Containment relationships
    REQ-FUNC --> REQ-PM
    REQ-FUNC --> REQ-TM
    REQ-FUNC --> REQ-RM
    REQ-FUNC --> REQ-AS
    REQ-FUNC --> REQ-MD
    REQ-FUNC --> REQ-ET
    REQ-FUNC --> REQ-RAE
    REQ-FUNC --> REQ-EVM
    REQ-FUNC --> REQ-ST
    REQ-FUNC --> REQ-PU
    
    REQ-SEC --> SEC-AUTH
    REQ-SEC --> SEC-AUTHZ
    REQ-SEC --> SEC-INPUT
    REQ-SEC --> SEC-RATE
    
    REQ-PERF --> PERF-RESPONSE
    REQ-PERF --> PERF-SCALE
    REQ-PERF --> PERF-PAGINATION
    
    CON-ALL --> CON-SCOPE
    CON-ALL --> CON-DATA
    CON-ALL --> CON-TECH
    
    GUIDE-ALL --> GUD-DEV
    GUIDE-ALL --> PAT-ARCH
    
    %% Derivation relationships (dependencies)
    REQ-EVM -.derives.-> REQ-PM
    REQ-EVM -.derives.-> REQ-TM
    REQ-EVM -.derives.-> REQ-ET
    REQ-EVM -.derives.-> REQ-RAE
    
    REQ-TM -.derives.-> REQ-PM
    REQ-AS -.derives.-> REQ-TM
    REQ-AS -.derives.-> REQ-RM
    REQ-ET -.derives.-> REQ-MD
    REQ-RAE -.derives.-> REQ-PM
    
    REQ-ST -.derives.-> REQ-EVM
    REQ-PU -.derives.-> REQ-TM
    REQ-PU -.derives.-> REQ-MD
    
    SEC-AUTHZ -.derives.-> SEC-AUTH
    
    %% Refinement relationships
    CON-DATA -.refines.-> REQ-MD
    CON-DATA -.refines.-> REQ-ET
    
    %% Tracing relationships
    GUD-DEV -.traces.-> REQ-FUNC
    PAT-ARCH -.traces.-> REQ-FUNC
    
    %% Styling
    classDef highRisk fill:#ffcccc,stroke:#cc0000,stroke-width:2px
    classDef mediumRisk fill:#ffffcc,stroke:#cccc00,stroke-width:2px
    classDef lowRisk fill:#ccffcc,stroke:#00cc00,stroke-width:2px
    classDef category fill:#cce5ff,stroke:#0066cc,stroke-width:3px
    
    class REQ-TM,REQ-RAE,REQ-EVM,SEC-AUTH,SEC-AUTHZ,SEC-INPUT highRisk
    class REQ-PM,REQ-AS,REQ-MD,REQ-ET,REQ-PU,SEC-RATE,PERF-RESPONSE,PERF-SCALE,CON-DATA mediumRisk
    class REQ-RM,REQ-ST,PERF-PAGINATION,CON-SCOPE,CON-TECH,GUD-DEV,PAT-ARCH lowRisk
    class REQ-FUNC,REQ-SEC,REQ-PERF,CON-ALL,GUIDE-ALL category
```

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

This section defines all HTTP endpoints, request/response schemas, and data models for the wfp-poc API. Complete specifications for 46 endpoints across 11 categories are provided below.

### 4.1. Data Models

#### Entity Relationship Diagram

The following diagram illustrates the relationships between all data entities in the wfp-poc system:

```mermaid
erDiagram
    Project ||--o{ Task : "contains"
    Project ||--o{ Milestone : "tracks"
    Project ||--o{ Deliverable : "produces"
    Project ||--o{ Resource : "uses"
    Project ||--o{ Expense : "incurs"
    Project ||--o{ RAEHistory : "forecasts"
    
    Task ||--o{ Task : "parent_of"
    Task ||--o{ Assignment : "assigned_to"
    Task }o--o{ Task : "predecessor_of"
    
    Milestone ||--o{ Deliverable : "delivers_at"
    Milestone ||--o{ Expense : "allocates_to"
    
    Resource ||--o{ Assignment : "works_on"
    
    Project {
        uuid id PK
        uuid company_id FK
        string name
        string code
        date planned_start_date
        date planned_finish_date
        decimal budget
        enum status
        string ms_project_uid
        timestamp created_at
        timestamp updated_at
    }
    
    Task {
        uuid id PK
        uuid project_id FK
        uuid parent_task_id FK
        string name
        string wbs_code
        boolean is_summary
        date planned_start_date
        date planned_finish_date
        integer duration
        decimal budget
        integer percent_complete
        boolean is_critical
        enum type
        string ms_project_uid
    }
    
    Milestone {
        uuid id PK
        uuid project_id FK
        string name
        date target_date
        date actual_date
        decimal budget_weight
        enum status
        string description
    }
    
    Deliverable {
        uuid id PK
        uuid project_id FK
        uuid milestone_id FK
        string name
        string description
        date due_date
        enum status
        string document_reference
    }
    
    Resource {
        uuid id PK
        uuid company_id FK
        string name
        string code
        enum type
        decimal cost_per_hour
        decimal cost_per_unit
        decimal max_units
        string email
    }
    
    Assignment {
        uuid id PK
        uuid task_id FK
        uuid resource_id FK
        decimal work_hours
        decimal remaining_work
        decimal allocation_percent
        date start_date
        date finish_date
    }
    
    Expense {
        uuid id PK
        uuid project_id FK
        uuid milestone_id FK
        string description
        decimal amount
        date expense_date
        enum category
        string invoice_number
        string payment_reference
    }
    
    RAEHistory {
        uuid id PK
        uuid project_id FK
        date date
        decimal rae_value
        string comment
        uuid updated_by FK
        timestamp created_at
    }
```

**Key Relationships:**
- **Project-centric**: All entities link to Project (multi-tenant isolation via `company_id`)
- **Task Hierarchy**: Tasks reference `parent_task_id` for WBS structure (self-referencing)
- **Task Dependencies**: Tasks can have multiple predecessors (many-to-many via predecessor table)
- **Milestone-Expense**: Expenses allocated to milestones for AC calculation
- **Milestone-Deliverable**: Deliverables tied to milestone achievements
- **Task-Assignment-Resource**: Many-to-many relationship through Assignment join table
- **RAE History**: Time-series tracking of Reste À Engager for physical progress EV

**Cascade Delete Rules:**
- Delete Project → cascades to Tasks, Milestones, Deliverables, Expenses, RAE History
- Delete Task → cascades to Assignments, child Tasks
- Delete Milestone → nullifies Expense.milestone_id, cascades to Deliverables
- Delete Resource → prevents deletion if Assignments exist (constraint violation)

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

**Endpoint:** `POST /v0/projects`

**Description:** Create a new project

**Request Headers:**
- `Authorization: Bearer <JWT>` (required)
- `Content-Type: application/json` (required)

**Request Body:**
```json
{
  "name": "string (required, 1-255 chars)",
  "code": "string (optional, max 50 chars)",
  "title": "string (optional, max 255 chars)",
  "start_date": "datetime ISO 8601 (required)",
  "finish_date": "datetime ISO 8601 (required, must be > start_date)",
  "budget": "decimal (optional, >= 0)",
  "currency_code": "string (optional, default: EUR)",
  "status": "string (optional, default: active, enum: [active, completed, cancelled, on_hold])",
  "ms_project_guid": "string (optional)",
  "ms_project_save_version": "integer (optional)",
  "creation_date": "datetime ISO 8601 (optional)",
  "last_saved_date": "datetime ISO 8601 (optional)",
  "calendar_uid": "integer (optional)",
  "minutes_per_day": "integer (optional, default: 420)",
  "minutes_per_week": "integer (optional, default: 2100)",
  "days_per_month": "integer (optional, default: 20)",
  "week_start_day": "integer (optional, default: 1)",
  "default_start_time": "string HH:MM:SS (optional, default: 09:00:00)",
  "default_finish_time": "string HH:MM:SS (optional, default: 18:00:00)"
}
```

**Response:** `201 Created`
```json
{
  "data": {
    "id": "uuid",
    "company_id": "uuid (from JWT)",
    "name": "string",
    "code": "string",
    ...
    "created_at": "datetime",
    "updated_at": "datetime"
  },
  "message": "Project created successfully"
}
```

**Error Responses:**
- `400 Bad Request`: Validation errors (start_date >= finish_date, invalid currency_code)
- `401 Unauthorized`: Missing or invalid JWT
- `403 Forbidden`: Insufficient Guardian permissions
- `422 Unprocessable Entity`: Business logic error

**Example Request:**
```json
{
  "name": "Planning BAGUERA 2025",
  "code": "G.DED.22966",
  "title": "Planning RCD",
  "start_date": "2024-11-25T09:00:00Z",
  "finish_date": "2027-02-19T18:00:00Z",
  "budget": 1500000.00,
  "currency_code": "EUR"
}
```

---

#### List Projects

**Endpoint:** `GET /v0/projects`

**Description:** Retrieve paginated list of projects for the authenticated user's company

**Request Headers:**
- `Authorization: Bearer <JWT>` (required)

**Query Parameters:**
- `page` (integer, optional, default: 1): Page number
- `per_page` (integer, optional, default: 20, max: 100): Items per page
- `status` (string, optional): Filter by status (active, completed, cancelled, on_hold)
- `start_date_from` (datetime, optional): Filter projects starting after date
- `start_date_to` (datetime, optional): Filter projects starting before date
- `search` (string, optional): Search in name, code, title fields
- `sort_by` (string, optional, default: created_at): Field to sort by (name, code, start_date, created_at)
- `sort_order` (string, optional, default: desc): Sort direction (asc, desc)

**Response:** `200 OK`
```json
{
  "data": [
    {
      "id": "uuid",
      "company_id": "uuid",
      "name": "string",
      "code": "string",
      "start_date": "datetime",
      "finish_date": "datetime",
      "budget": "decimal",
      "status": "string",
      ...
    }
  ],
  "page": 1,
  "per_page": 20,
  "total": 100,
  "total_pages": 5
}
```

**Error Responses:**
- `401 Unauthorized`: Missing or invalid JWT
- `403 Forbidden`: Insufficient Guardian permissions

---

#### Get Project

**Endpoint:** `GET /v0/projects/{id}`

**Description:** Retrieve a single project by ID

**Request Headers:**
- `Authorization: Bearer <JWT>` (required)

**Path Parameters:**
- `id` (uuid, required): Project unique identifier

**Response:** `200 OK`
```json
{
  "data": {
    "id": "uuid",
    "company_id": "uuid",
    "name": "string",
    "code": "string",
    "title": "string",
    "start_date": "datetime",
    "finish_date": "datetime",
    "budget": "decimal",
    "currency_code": "string",
    "status": "string",
    "ms_project_guid": "string",
    ...
    "created_at": "datetime",
    "updated_at": "datetime"
  }
}
```

**Error Responses:**
- `401 Unauthorized`: Missing or invalid JWT
- `403 Forbidden`: Insufficient Guardian permissions
- `404 Not Found`: Project does not exist or belongs to different company

---

#### Update Project

**Endpoint:** `PATCH /v0/projects/{id}`

**Description:** Update an existing project (partial update)

**Request Headers:**
- `Authorization: Bearer <JWT>` (required)
- `Content-Type: application/json` (required)

**Path Parameters:**
- `id` (uuid, required): Project unique identifier

**Request Body:** (all fields optional)
```json
{
  "name": "string (1-255 chars)",
  "code": "string (max 50 chars)",
  "title": "string (max 255 chars)",
  "start_date": "datetime ISO 8601",
  "finish_date": "datetime ISO 8601",
  "budget": "decimal (>= 0)",
  "currency_code": "string",
  "status": "string (enum: [active, completed, cancelled, on_hold])",
  "last_saved_date": "datetime ISO 8601",
  ...
}
```

**Response:** `200 OK`
```json
{
  "data": {
    "id": "uuid",
    ...updated fields...,
    "updated_at": "datetime (new timestamp)"
  },
  "message": "Project updated successfully"
}
```

**Error Responses:**
- `400 Bad Request`: Validation errors
- `401 Unauthorized`: Missing or invalid JWT
- `403 Forbidden`: Insufficient Guardian permissions
- `404 Not Found`: Project does not exist
- `422 Unprocessable Entity`: Business logic error (e.g., start_date >= finish_date)

---

#### Delete Project

**Endpoint:** `DELETE /v0/projects/{id}`

**Description:** Delete a project (cascade or soft delete based on implementation)

**Request Headers:**
- `Authorization: Bearer <JWT>` (required)

**Path Parameters:**
- `id` (uuid, required): Project unique identifier

**Response:** `204 No Content`

**Error Responses:**
- `401 Unauthorized`: Missing or invalid JWT
- `403 Forbidden`: Insufficient Guardian permissions
- `404 Not Found`: Project does not exist
- `409 Conflict`: Cannot delete project with associated tasks, milestones, or expenses

### 4.3. Task Endpoints

#### Create Task

**Endpoint:** `POST /v0/projects/{project_id}/tasks`

**Description:** Create a new task within a project

**Request Headers:**
- `Authorization: Bearer <JWT>` (required)
- `Content-Type: application/json` (required)

**Path Parameters:**
- `project_id` (uuid, required): Parent project identifier

**Request Body:**
```json
{
  "parent_id": "uuid (optional, for WBS hierarchy)",
  "ms_project_uid": "integer (optional)",
  "ms_project_id": "integer (optional)",
  "ms_project_guid": "string (optional)",
  "name": "string (required, 1-255 chars)",
  "wbs": "string (optional, e.g., '5.6')",
  "outline_number": "string (optional)",
  "outline_level": "integer (optional, >= 0)",
  "start": "datetime ISO 8601 (required)",
  "finish": "datetime ISO 8601 (required)",
  "duration": "string ISO 8601 duration (optional, e.g., 'PT8H0M0S')",
  "work": "string ISO 8601 duration (optional)",
  "cost": "decimal (optional, >= 0)",
  "fixed_cost": "decimal (optional, default: 0)",
  "is_milestone": "boolean (optional, default: false)",
  "is_summary": "boolean (optional, default: false)",
  "is_deliverable": "boolean (optional, default: false)",
  "status": "string (optional, default: not_started)",
  "percent_complete": "integer (optional, 0-100)",
  "manual_scheduling": "boolean (optional, default: false)",
  "predecessors": "array of {predecessor_task_id: uuid, type: FS|SS|FF|SF, lag: integer} (optional)"
}
```

**Response:** `201 Created`
```json
{
  "data": {
    "id": "uuid",
    "project_id": "uuid",
    "name": "string",
    ...
    "created_at": "datetime",
    "updated_at": "datetime"
  },
  "message": "Task created successfully"
}
```

**Error Responses:**
- `400 Bad Request`: Validation errors (start >= finish for non-milestones, invalid WBS)
- `401 Unauthorized`: Missing or invalid JWT
- `403 Forbidden`: Insufficient Guardian permissions
- `404 Not Found`: Project or parent_id not found
- `409 Conflict`: Circular dependency in predecessors
- `422 Unprocessable Entity`: Business logic error (child dates outside parent range)

---

#### Bulk Create Tasks

**Endpoint:** `POST /v0/projects/{project_id}/tasks/bulk`

**Description:** Create multiple tasks in a single request (for efficient import from poc-import service)

**Request Headers:**
- `Authorization: Bearer <JWT>` (required)
- `Content-Type: application/json` (required)

**Path Parameters:**
- `project_id` (uuid, required): Parent project identifier

**Request Body:**
```json
{
  "tasks": [
    {
      "name": "string",
      "start": "datetime",
      "finish": "datetime",
      ...
    },
    {
      "name": "string",
      "start": "datetime",
      "finish": "datetime",
      ...
    }
  ]
}
```

**Response:** `201 Created`
```json
{
  "data": {
    "created_count": 150,
    "failed_count": 2,
    "tasks": [
      {
        "id": "uuid",
        "name": "string",
        ...
      }
    ],
    "errors": [
      {
        "index": 42,
        "task_name": "Invalid Task",
        "errors": {"start": ["Must be before finish"]}
      }
    ]
  },
  "message": "150 tasks created, 2 failed"
}
```

**Error Responses:**
- `400 Bad Request`: Array validation errors (empty array, too many items)
- `401 Unauthorized`: Missing or invalid JWT
- `403 Forbidden`: Insufficient Guardian permissions
- `404 Not Found`: Project not found
- `429 Too Many Requests`: Rate limit exceeded (10 req/min for bulk endpoints)

**Note:** Bulk operations use database transactions for atomicity. If critical errors occur, entire batch is rolled back.

---

#### List Tasks

**Endpoint:** `GET /v0/projects/{project_id}/tasks`

**Description:** Retrieve paginated list of tasks for a project

**Request Headers:**
- `Authorization: Bearer <JWT>` (required)

**Path Parameters:**
- `project_id` (uuid, required): Parent project identifier

**Query Parameters:**
- `page` (integer, optional, default: 1): Page number
- `per_page` (integer, optional, default: 20, max: 100): Items per page
- `parent_id` (uuid, optional): Filter by parent task (use "null" for top-level tasks)
- `is_milestone` (boolean, optional): Filter milestones only
- `is_summary` (boolean, optional): Filter summary tasks only
- `is_critical` (boolean, optional): Filter critical path tasks only
- `status` (string, optional): Filter by status
- `search` (string, optional): Search in name field
- `sort_by` (string, optional, default: wbs): Sort field (wbs, name, start, finish)
- `sort_order` (string, optional, default: asc): Sort direction

**Response:** `200 OK`
```json
{
  "data": [
    {
      "id": "uuid",
      "project_id": "uuid",
      "parent_id": "uuid or null",
      "name": "string",
      "wbs": "string",
      "start": "datetime",
      "finish": "datetime",
      "is_milestone": "boolean",
      "is_critical": "boolean",
      "status": "string",
      "percent_complete": "integer",
      ...
    }
  ],
  "page": 1,
  "per_page": 20,
  "total": 500,
  "total_pages": 25
}
```

**Error Responses:**
- `401 Unauthorized`: Missing or invalid JWT
- `403 Forbidden`: Insufficient Guardian permissions
- `404 Not Found`: Project not found

---

#### Get Task

**Endpoint:** `GET /v0/projects/{project_id}/tasks/{id}`

**Description:** Retrieve a single task by ID

**Request Headers:**
- `Authorization: Bearer <JWT>` (required)

**Path Parameters:**
- `project_id` (uuid, required): Parent project identifier
- `id` (uuid, required): Task unique identifier

**Response:** `200 OK`
```json
{
  "data": {
    "id": "uuid",
    "project_id": "uuid",
    "parent_id": "uuid or null",
    "ms_project_uid": "integer",
    "ms_project_id": "integer",
    "ms_project_guid": "string",
    "name": "string",
    "wbs": "string",
    "outline_number": "string",
    "outline_level": "integer",
    "start": "datetime",
    "finish": "datetime",
    "duration": "string",
    "work": "string",
    "cost": "decimal",
    "fixed_cost": "decimal",
    "is_milestone": "boolean",
    "is_summary": "boolean",
    "is_deliverable": "boolean",
    "is_critical": "boolean",
    "status": "string",
    "percent_complete": "integer",
    "percent_work_complete": "integer",
    "early_start": "datetime",
    "early_finish": "datetime",
    "late_start": "datetime",
    "late_finish": "datetime",
    "total_slack": "integer",
    "free_slack": "integer",
    "manual_scheduling": "boolean",
    "actual_start": "datetime or null",
    "actual_finish": "datetime or null",
    "actual_cost": "decimal",
    "actual_work": "string",
    "remaining_cost": "decimal",
    "remaining_work": "string",
    "predecessors": [
      {
        "predecessor_task_id": "uuid",
        "type": "FS",
        "lag": 0
      }
    ],
    "created_at": "datetime",
    "updated_at": "datetime"
  }
}
```

**Error Responses:**
- `401 Unauthorized`: Missing or invalid JWT
- `403 Forbidden`: Insufficient Guardian permissions
- `404 Not Found`: Task or project not found

---

#### Update Task

**Endpoint:** `PATCH /v0/projects/{project_id}/tasks/{id}`

**Description:** Update an existing task (partial update)

**Request Headers:**
- `Authorization: Bearer <JWT>` (required)
- `Content-Type: application/json` (required)

**Path Parameters:**
- `project_id` (uuid, required): Parent project identifier
- `id` (uuid, required): Task unique identifier

**Request Body:** (all fields optional)
```json
{
  "name": "string",
  "start": "datetime",
  "finish": "datetime",
  "status": "string",
  "percent_complete": "integer",
  "actual_start": "datetime",
  "actual_finish": "datetime",
  "remaining_cost": "decimal",
  "predecessors": "array",
  ...
}
```

**Response:** `200 OK`
```json
{
  "data": {
    "id": "uuid",
    ...updated fields...,
    "updated_at": "datetime"
  },
  "message": "Task updated successfully"
}
```

**Error Responses:**
- `400 Bad Request`: Validation errors
- `401 Unauthorized`: Missing or invalid JWT
- `403 Forbidden`: Insufficient Guardian permissions
- `404 Not Found`: Task or project not found
- `409 Conflict`: Circular dependency in predecessors
- `422 Unprocessable Entity`: Business logic error

---

#### Delete Task

**Endpoint:** `DELETE /v0/projects/{project_id}/tasks/{id}`

**Description:** Delete a task (cascade deletes assignments, but may fail if referenced by other tasks as predecessor)

**Request Headers:**
- `Authorization: Bearer <JWT>` (required)

**Path Parameters:**
- `project_id` (uuid, required): Parent project identifier
- `id` (uuid, required): Task unique identifier

**Response:** `204 No Content`

**Error Responses:**
- `401 Unauthorized`: Missing or invalid JWT
- `403 Forbidden`: Insufficient Guardian permissions
- `404 Not Found`: Task or project not found
- `409 Conflict`: Task is referenced as predecessor by other tasks or has child tasks

### 4.4. Milestone Endpoints

#### Create Milestone

**Endpoint:** `POST /v0/projects/{project_id}/milestones`

**Request Body:**
```json
{
  "task_id": "uuid (optional)",
  "name": "string (required, 1-255 chars)",
  "description": "string (optional, max 1000 chars)",
  "target_date": "datetime ISO 8601 (required)",
  "planned_date": "datetime ISO 8601 (optional)",
  "budget": "decimal (optional, >= 0)"
}
```

**Response:** `201 Created`

**Error Responses:**
- `400 Bad Request`: Validation errors
- `409 Conflict`: Milestone overlaps with existing milestone (non-overlapping constraint)
- `422 Unprocessable Entity`: target_date outside project date range

---

#### List Milestones

**Endpoint:** `GET /v0/projects/{project_id}/milestones`

**Query Parameters:**
- `page`, `per_page`, `sort_by`, `sort_order` (standard pagination)
- `status` (optional): Filter by status (upcoming, achieved, missed)
- `date_from`, `date_to` (optional): Filter by target_date range

**Response:** `200 OK` (paginated list)

---

#### Get Milestone

**Endpoint:** `GET /v0/projects/{project_id}/milestones/{id}`

**Response:** `200 OK` (single milestone with planned_date_history)

---

#### Update Milestone

**Endpoint:** `PATCH /v0/projects/{project_id}/milestones/{id}`

**Request Body:** (all fields optional)
```json
{
  "name": "string",
  "target_date": "datetime",
  "actual_date": "datetime",
  "budget": "decimal"
}
```

**Note:** Updating `planned_date` appends to `planned_date_history` for time/time analysis.

**Response:** `200 OK`

---

#### Delete Milestone

**Endpoint:** `DELETE /v0/projects/{project_id}/milestones/{id}`

**Response:** `204 No Content`

**Error Responses:**
- `409 Conflict`: Cannot delete milestone with associated expenses or deliverables

### 4.5. Resource Endpoints

**Note:** Resources are company-scoped, not project-scoped (can be shared across projects).

#### Create Resource

**Endpoint:** `POST /v0/resources`

**Request Body:**
```json
{
  "ms_project_uid": "integer (optional)",
  "name": "string (required, 1-255 chars)",
  "type": "string (optional, default: labor, enum: [labor, material, cost])",
  "standard_rate": "decimal (optional, >= 0)",
  "overtime_rate": "decimal (optional, >= 0)",
  "email": "string (optional, valid email format)",
  "is_active": "boolean (optional, default: true)"
}
```

**Response:** `201 Created`

---

#### List Resources

**Endpoint:** `GET /v0/resources`

**Query Parameters:**
- Standard pagination (`page`, `per_page`)
- `type` (optional): Filter by type
- `is_active` (optional): Filter active/inactive resources
- `search` (optional): Search in name, email fields

**Response:** `200 OK` (paginated list filtered by company_id from JWT)

---

#### Get Resource

**Endpoint:** `GET /v0/resources/{id}`

**Response:** `200 OK`

---

#### Update Resource

**Endpoint:** `PATCH /v0/resources/{id}`

**Request Body:** (all fields optional)
```json
{
  "name": "string",
  "standard_rate": "decimal",
  "overtime_rate": "decimal",
  "is_active": "boolean"
}
```

**Response:** `200 OK`

---

#### Delete Resource

**Endpoint:** `DELETE /v0/resources/{id}`

**Response:** `204 No Content`

**Error Responses:**
- `409 Conflict`: Cannot delete resource with active assignments

### 4.6. Assignment Endpoints

#### Create Assignment

**Endpoint:** `POST /v0/projects/{project_id}/assignments`

**Request Body:**
```json
{
  "task_id": "uuid (required)",
  "resource_id": "uuid (required)",
  "ms_project_uid": "integer (optional)",
  "work_hours": "string ISO 8601 duration (optional, e.g., 'PT40H0M0S')",
  "percent_allocation": "integer (optional, 0-100, default: 100)",
  "cost": "decimal (optional, >= 0)"
}
```

**Response:** `201 Created`

**Error Responses:**
- `404 Not Found`: Task or resource not found
- `409 Conflict`: Duplicate assignment (same task + resource)
- `422 Unprocessable Entity`: Resource and task belong to different companies

---

#### List Assignments

**Endpoint:** `GET /v0/projects/{project_id}/assignments`

**Query Parameters:**
- Standard pagination
- `task_id` (optional): Filter by task
- `resource_id` (optional): Filter by resource

**Response:** `200 OK` (paginated list)

---

#### Get Assignment

**Endpoint:** `GET /v0/projects/{project_id}/assignments/{id}`

**Response:** `200 OK`

---

#### Update Assignment

**Endpoint:** `PATCH /v0/projects/{project_id}/assignments/{id}`

**Request Body:** (all fields optional)
```json
{
  "work_hours": "string",
  "percent_allocation": "integer",
  "cost": "decimal",
  "actual_work": "string",
  "actual_cost": "decimal"
}
```

**Response:** `200 OK`

---

#### Delete Assignment

**Endpoint:** `DELETE /v0/projects/{project_id}/assignments/{id}`

**Response:** `204 No Content`

### 4.7. Expense Endpoints

#### Create Expense

**Endpoint:** `POST /v0/projects/{project_id}/expenses`

**Request Body:**
```json
{
  "resource_id": "uuid (optional, for labor expenses)",
  "date": "datetime ISO 8601 (required)",
  "amount": "decimal (required, >= 0)",
  "category": "string (required, enum: [labor, procurement, subcontracting, overhead])",
  "description": "string (optional, max 500 chars)",
  "reference_number": "string (optional, max 50 chars)",
  "purchase_document": "string (optional)",
  "fiscal_year": "integer (optional)",
  "period": "integer (optional)",
  "otp_element": "string (optional)",
  "accounting_nature": "string (optional)",
  "vendor_name": "string (optional)",
  "origin_group": "string (optional)"
}
```

**Response:** `201 Created`

**Note:** `milestone_id` is auto-assigned based on expense date falling between milestone target dates.

**Error Responses:**
- `400 Bad Request`: Validation errors (amount < 0, invalid category)
- `422 Unprocessable Entity`: Expense date before first milestone or after last milestone
- `409 Conflict`: Duplicate expense (based on reference_number + date + amount)

---

#### Bulk Create Expenses

**Endpoint:** `POST /v0/projects/{project_id}/expenses/bulk`

**Request Body:**
```json
{
  "expenses": [
    {
      "date": "datetime",
      "amount": "decimal",
      "category": "string",
      ...
    }
  ]
}
```

**Response:** `201 Created`
```json
{
  "data": {
    "created_count": 250,
    "failed_count": 3,
    "expenses": [...],
    "errors": [...]
  },
  "message": "250 expenses created, 3 failed"
}
```

**Error Responses:**
- `429 Too Many Requests`: Rate limit exceeded (10 req/min for bulk)

---

#### List Expenses

**Endpoint:** `GET /v0/projects/{project_id}/expenses`

**Query Parameters:**
- Standard pagination
- `category` (optional): Filter by category
- `milestone_id` (optional): Filter by milestone
- `resource_id` (optional): Filter by resource
- `date_from`, `date_to` (optional): Date range filter
- `sort_by` (optional, default: date): Sort field
- `sort_order` (optional, default: asc)

**Response:** `200 OK` (paginated list)

---

#### Get Expense

**Endpoint:** `GET /v0/projects/{project_id}/expenses/{id}`

**Response:** `200 OK`

---

#### Update Expense

**Endpoint:** `PATCH /v0/projects/{project_id}/expenses/{id}`

**Request Body:** (all fields optional)
```json
{
  "date": "datetime",
  "amount": "decimal",
  "category": "string",
  "description": "string"
}
```

**Note:** Updating `date` may trigger milestone_id reassignment.

**Response:** `200 OK`

---

#### Delete Expense

**Endpoint:** `DELETE /v0/projects/{project_id}/expenses/{id}`

**Response:** `204 No Content`

### 4.8. RAE (Reste À Engager) Endpoints

#### Update Task RAE

**Endpoint:** `POST /v0/projects/{project_id}/tasks/{task_id}/rae`

**Description:** Record a new RAE (Remaining to be Committed) value for a task. Creates historical record.

**Request Headers:**
- `Authorization: Bearer <JWT>` (required)
- `Content-Type: application/json` (required)

**Path Parameters:**
- `project_id` (uuid, required): Parent project identifier
- `task_id` (uuid, required): Task identifier

**Request Body:**
```json
{
  "date": "datetime ISO 8601 (required, typically month-end)",
  "remaining_cost": "decimal (required, >= 0)",
  "comment": "string (optional, max 500 chars)"
}
```

**Response:** `201 Created`
```json
{
  "data": {
    "id": "uuid",
    "task_id": "uuid",
    "date": "datetime",
    "remaining_cost": "decimal",
    "comment": "string",
    "updated_by": "uuid (from JWT)",
    "created_at": "datetime"
  },
  "message": "RAE updated successfully"
}
```

**Side Effect:** Also updates `task.remaining_cost` field with latest value.

**Error Responses:**
- `400 Bad Request`: Validation errors (remaining_cost < 0)
- `404 Not Found`: Task or project not found

---

#### Get RAE History

**Endpoint:** `GET /v0/projects/{project_id}/tasks/{task_id}/rae/history`

**Description:** Retrieve historical RAE values for a task (time series)

**Request Headers:**
- `Authorization: Bearer <JWT>` (required)

**Path Parameters:**
- `project_id` (uuid, required): Parent project identifier
- `task_id` (uuid, required): Task identifier

**Query Parameters:**
- `page` (integer, optional, default: 1): Page number
- `per_page` (integer, optional, default: 20, max: 100): Items per page
- `date_from` (datetime, optional): Filter from date
- `date_to` (datetime, optional): Filter to date
- `sort_order` (string, optional, default: asc): Sort by date (asc, desc)

**Response:** `200 OK`
```json
{
  "data": [
    {
      "id": "uuid",
      "task_id": "uuid",
      "date": "datetime",
      "remaining_cost": "decimal",
      "comment": "string",
      "updated_by": "uuid",
      "created_at": "datetime"
    },
    {
      "id": "uuid",
      "task_id": "uuid",
      "date": "2026-02-28T23:59:59Z",
      "remaining_cost": 10000.00,
      "comment": "Updated based on Q2 progress",
      "updated_by": "uuid",
      "created_at": "2026-03-01T10:00:00Z"
    }
  ],
  "page": 1,
  "per_page": 20,
  "total": 12,
  "total_pages": 1
}
```

**Error Responses:**
- `404 Not Found`: Task or project not found

### 4.9. EVM Indicators Endpoints

#### Get Project EVM Indicators

**Endpoint:** `GET /v0/projects/{project_id}/evm`

**Description:** Calculate and retrieve current EVM indicators for a project (snapshot at specified date)

**Request Headers:**
- `Authorization: Bearer <JWT>` (required)

**Path Parameters:**
- `project_id` (uuid, required): Project identifier

**Query Parameters:**
- `as_of_date` (datetime, optional, default: current date): Analysis date for calculations
- `ev_method` (string, optional, default: both): EV calculation method
  - `physical`: Physical progress method (RAE-based)
  - `milestone`: Milestone completion method
  - `both`: Return both methods for comparison

**Response:** `200 OK`
```json
{
  "data": {
    "project_id": "uuid",
    "as_of_date": "2026-01-10T00:00:00Z",
    "bac": 1500000.00,
    "pv": 750000.00,
    "ac": 820000.00,
    "ev_physical": 680000.00,
    "ev_milestone": 700000.00,
    "cv_physical": -140000.00,
    "cv_milestone": -120000.00,
    "sv_physical": -70000.00,
    "sv_milestone": -50000.00,
    "cpi_physical": 0.829,
    "cpi_milestone": 0.854,
    "spi_physical": 0.907,
    "spi_milestone": 0.933,
    "eac_cpi_physical": 1809178.74,
    "eac_cpi_milestone": 1756432.69,
    "eac_cpi_spi_physical": 1912456.33,
    "eac_cpi_spi_milestone": 1842190.21,
    "eac_plan_based": 1570000.00,
    "etc_cpi_physical": 989178.74,
    "etc_cpi_milestone": 936432.69,
    "etc_cpi_spi_physical": 1092456.33,
    "etc_cpi_spi_milestone": 1022190.21,
    "etc_plan_based": 750000.00,
    "vac_cpi_physical": -309178.74,
    "vac_cpi_milestone": -256432.69,
    "vac_cpi_spi_physical": -412456.33,
    "vac_cpi_spi_milestone": -342190.21,
    "vac_plan_based": -70000.00,
    "percent_complete_physical": 45.33,
    "percent_complete_milestone": 46.67,
    "calculation_timestamp": "2026-01-10T12:30:00Z"
  }
}
```

**Field Descriptions:**
- `bac`: Budget At Completion (total planned budget)
- `pv`: Planned Value (what should be spent by as_of_date)
- `ac`: Actual Cost (what was actually spent)
- `ev_physical`: Earned Value using physical progress method
- `ev_milestone`: Earned Value using milestone completion method
- `cv`: Cost Variance (EV - AC), negative = over budget
- `sv`: Schedule Variance (EV - PV), negative = behind schedule
- `cpi`: Cost Performance Index (EV / AC), < 1.0 = cost overrun
- `spi`: Schedule Performance Index (EV / PV), < 1.0 = behind schedule
- `eac_*`: Estimate At Completion (forecasted total cost) using different methods
- `etc_*`: Estimate To Complete (remaining cost forecast)
- `vac_*`: Variance At Completion (BAC - EAC), negative = expected overrun
- `percent_complete_*`: Project completion percentage

**Error Responses:**
- `401 Unauthorized`: Missing or invalid JWT
- `403 Forbidden`: Insufficient Guardian permissions
- `404 Not Found`: Project not found
- `422 Unprocessable Entity`: Cannot calculate EVM (no milestones, no expenses, etc.)
- `429 Too Many Requests`: Rate limit exceeded (20 req/min for EVM endpoints)

**Notes:**
- Calculation is performed on-demand (not cached for POC)
- If AC=0 or PV=0, CPI/SPI return null to avoid division by zero
- EAC methods provide different forecasts based on performance assumptions

---

#### Get EVM Time Series

**Endpoint:** `GET /v0/projects/{project_id}/evm/timeseries`

**Description:** Retrieve monthly EVM indicators for trend analysis and charting (Apache ECharts format)

**Request Headers:**
- `Authorization: Bearer <JWT>` (required)

**Path Parameters:**
- `project_id` (uuid, required): Project identifier

**Query Parameters:**
- `start_date` (datetime, optional, default: project start): Time series start date
- `end_date` (datetime, optional, default: current date): Time series end date
- `granularity` (string, optional, default: month): Data point frequency
  - `month`: Monthly data points (POC default)
  - `week`: Weekly data points (future enhancement)
  - `day`: Daily data points (future enhancement)
- `ev_method` (string, optional, default: physical): EV calculation method (physical, milestone)
- `cumulative` (boolean, optional, default: true): Cumulative values (true) or period values (false)

**Response:** `200 OK`
```json
{
  "data": {
    "project_id": "uuid",
    "start_date": "2024-11-01T00:00:00Z",
    "end_date": "2026-01-01T00:00:00Z",
    "granularity": "month",
    "ev_method": "physical",
    "cumulative": true,
    "series": [
      {
        "date": "2024-11-30T23:59:59Z",
        "pv": 50000.00,
        "ac": 48000.00,
        "ev": 45000.00,
        "cv": -3000.00,
        "sv": -5000.00,
        "cpi": 0.938,
        "spi": 0.900
      },
      {
        "date": "2024-12-31T23:59:59Z",
        "pv": 120000.00,
        "ac": 125000.00,
        "ev": 110000.00,
        "cv": -15000.00,
        "sv": -10000.00,
        "cpi": 0.880,
        "spi": 0.917
      },
      {
        "date": "2026-01-31T23:59:59Z",
        "pv": 750000.00,
        "ac": 820000.00,
        "ev": 680000.00,
        "cv": -140000.00,
        "sv": -70000.00,
        "cpi": 0.829,
        "spi": 0.907
      }
    ],
    "echarts_format": {
      "xAxis": {
        "type": "category",
        "data": ["2024-11", "2024-12", "2025-01", "...", "2026-01"]
      },
      "series": [
        {
          "name": "PV",
          "type": "line",
          "data": [50000.00, 120000.00, 200000.00, "...", 750000.00]
        },
        {
          "name": "AC",
          "type": "line",
          "data": [48000.00, 125000.00, 210000.00, "...", 820000.00]
        },
        {
          "name": "EV",
          "type": "line",
          "data": [45000.00, 110000.00, 195000.00, "...", 680000.00]
        }
      ]
    }
  }
}
```

**Error Responses:**
- `400 Bad Request`: Invalid date range (start_date > end_date)
- `404 Not Found`: Project not found
- `429 Too Many Requests`: Rate limit exceeded

**Notes:**
- Response includes both raw `series` array and `echarts_format` for direct chart rendering
- Data points calculated at month-end (23:59:59 on last day of month)
- Missing months (no expenses) still included with PV values

---

#### Get EVM Forecasts

**Endpoint:** `GET /v0/projects/{project_id}/evm/forecasts`

**Description:** Retrieve EVM forecast values using all three projection methods

**Request Headers:**
- `Authorization: Bearer <JWT>` (required)

**Path Parameters:**
- `project_id` (uuid, required): Project identifier

**Query Parameters:**
- `as_of_date` (datetime, optional, default: current date): Forecast baseline date
- `ev_method` (string, optional, default: physical): EV calculation method

**Response:** `200 OK`
```json
{
  "data": {
    "project_id": "uuid",
    "as_of_date": "2026-01-10T00:00:00Z",
    "bac": 1500000.00,
    "current_ac": 820000.00,
    "current_ev": 680000.00,
    "current_pv": 750000.00,
    "remaining_pv": 750000.00,
    "cpi": 0.829,
    "spi": 0.907,
    "forecasts": [
      {
        "method": "cpi",
        "description": "CPI Method: Assumes current cost performance continues",
        "formula": "EAC = BAC / CPI",
        "eac": 1809178.74,
        "etc": 989178.74,
        "vac": -309178.74,
        "confidence": "low",
        "use_case": "Pessimistic scenario, cost issues persist"
      },
      {
        "method": "cpi_spi",
        "description": "CPI×SPI Method: Considers both cost and schedule performance",
        "formula": "EAC = AC + (BAC - EV) / (CPI × SPI)",
        "eac": 1912456.33,
        "etc": 1092456.33,
        "vac": -412456.33,
        "confidence": "medium",
        "use_case": "Realistic scenario, performance improvement unlikely"
      },
      {
        "method": "plan_based",
        "description": "Plan-Based: Assumes future work follows original plan",
        "formula": "EAC = AC + Remaining_PV",
        "eac": 1570000.00,
        "etc": 750000.00,
        "vac": -70000.00,
        "confidence": "high",
        "use_case": "Optimistic scenario, team corrects course"
      }
    ],
    "recommended_method": "cpi_spi",
    "recommendation_reason": "Balanced view considering both cost and schedule issues"
  }
}
```

**Error Responses:**
- `404 Not Found`: Project not found
- `422 Unprocessable Entity`: Cannot calculate forecasts (insufficient data)

**Notes:**
- Three methods provide range of outcomes: optimistic (plan), realistic (CPI×SPI), pessimistic (CPI)
- `recommended_method` selected based on project performance patterns
- `confidence` levels guide decision-making

### 4.10. Statistics Endpoints

#### Get Expense Breakdown by Category

**Endpoint:** `GET /v0/projects/{project_id}/statistics/expenses/by-category`

**Description:** Retrieve expense distribution by category for pie/donut chart visualization

**Request Headers:**
- `Authorization: Bearer <JWT>` (required)

**Path Parameters:**
- `project_id` (uuid, required): Project identifier

**Query Parameters:**
- `start_date` (datetime, optional): Filter from date
- `end_date` (datetime, optional): Filter to date
- `milestone_id` (uuid, optional): Filter by milestone

**Response:** `200 OK`
```json
{
  "data": {
    "project_id": "uuid",
    "total_expenses": 820000.00,
    "breakdown": [
      {
        "category": "labor",
        "amount": 450000.00,
        "percentage": 54.88,
        "count": 156
      },
      {
        "category": "subcontracting",
        "amount": 220000.00,
        "percentage": 26.83,
        "count": 42
      },
      {
        "category": "procurement",
        "amount": 120000.00,
        "percentage": 14.63,
        "count": 68
      },
      {
        "category": "overhead",
        "amount": 30000.00,
        "percentage": 3.66,
        "count": 24
      }
    ],
    "echarts_format": {
      "series": [
        {
          "name": "Expenses by Category",
          "type": "pie",
          "radius": ["40%", "70%"],
          "data": [
            {"value": 450000.00, "name": "Labor (54.88%)"},
            {"value": 220000.00, "name": "Subcontracting (26.83%)"},
            {"value": 120000.00, "name": "Procurement (14.63%)"},
            {"value": 30000.00, "name": "Overhead (3.66%)"}
          ]
        }
      ]
    }
  }
}
```

**Error Responses:**
- `404 Not Found`: Project not found

---

#### Get Labor Cost by Resource

**Endpoint:** `GET /v0/projects/{project_id}/statistics/labor/by-resource`

**Description:** Retrieve labor cost distribution by resource for bar chart visualization

**Request Headers:**
- `Authorization: Bearer <JWT>` (required)

**Path Parameters:**
- `project_id` (uuid, required): Project identifier

**Query Parameters:**
- `start_date` (datetime, optional): Filter from date
- `end_date` (datetime, optional): Filter to date
- `limit` (integer, optional, default: 20): Max resources to return (top N)
- `sort_order` (string, optional, default: desc): Sort by amount (asc, desc)

**Response:** `200 OK`
```json
{
  "data": {
    "project_id": "uuid",
    "total_labor_cost": 450000.00,
    "resource_count": 25,
    "breakdown": [
      {
        "resource_id": "uuid",
        "resource_name": "Jean Dupont",
        "amount": 85000.00,
        "percentage": 18.89,
        "hours": 1000.0,
        "average_rate": 85.00
      },
      {
        "resource_id": "uuid",
        "resource_name": "Marie Martin",
        "amount": 72000.00,
        "percentage": 16.00,
        "hours": 900.0,
        "average_rate": 80.00
      },
      {
        "resource_id": "uuid",
        "resource_name": "Pierre Bernard",
        "amount": 65000.00,
        "percentage": 14.44,
        "hours": 850.0,
        "average_rate": 76.47
      }
    ],
    "echarts_format": {
      "xAxis": {
        "type": "category",
        "data": ["Jean Dupont", "Marie Martin", "Pierre Bernard", "..."]
      },
      "yAxis": {
        "type": "value",
        "name": "Cost (€)"
      },
      "series": [
        {
          "name": "Labor Cost",
          "type": "bar",
          "data": [85000.00, 72000.00, 65000.00, "..."]
        }
      ]
    }
  }
}
```

**Error Responses:**
- `404 Not Found`: Project not found

---

#### Get Monthly Expense Distribution

**Endpoint:** `GET /v0/projects/{project_id}/statistics/expenses/monthly`

**Description:** Retrieve monthly expense trends for line/bar chart visualization

**Request Headers:**
- `Authorization: Bearer <JWT>` (required)

**Path Parameters:**
- `project_id` (uuid, required): Project identifier

**Query Parameters:**
- `start_date` (datetime, optional): Filter from date
- `end_date` (datetime, optional): Filter to date
- `category` (string, optional): Filter by category
- `cumulative` (boolean, optional, default: false): Cumulative (true) or period (false) values

**Response:** `200 OK`
```json
{
  "data": {
    "project_id": "uuid",
    "start_date": "2024-11-01T00:00:00Z",
    "end_date": "2026-01-31T23:59:59Z",
    "cumulative": false,
    "monthly_data": [
      {
        "month": "2024-11",
        "total": 48000.00,
        "labor": 25000.00,
        "subcontracting": 15000.00,
        "procurement": 6000.00,
        "overhead": 2000.00
      },
      {
        "month": "2024-12",
        "total": 77000.00,
        "labor": 42000.00,
        "subcontracting": 20000.00,
        "procurement": 12000.00,
        "overhead": 3000.00
      },
      {
        "month": "2025-01",
        "total": 85000.00,
        "labor": 45000.00,
        "subcontracting": 25000.00,
        "procurement": 11000.00,
        "overhead": 4000.00
      }
    ],
    "echarts_format": {
      "xAxis": {
        "type": "category",
        "data": ["2024-11", "2024-12", "2025-01", "..."]
      },
      "yAxis": {
        "type": "value",
        "name": "Expenses (€)"
      },
      "series": [
        {"name": "Labor", "type": "bar", "stack": "total", "data": [25000, 42000, 45000, "..."]},
        {"name": "Subcontracting", "type": "bar", "stack": "total", "data": [15000, 20000, 25000, "..."]},
        {"name": "Procurement", "type": "bar", "stack": "total", "data": [6000, 12000, 11000, "..."]},
        {"name": "Overhead", "type": "bar", "stack": "total", "data": [2000, 3000, 4000, "..."]}
      ]
    }
  }
}
```

**Error Responses:**
- `404 Not Found`: Project not found

### 4.11. Progress Update Endpoints

#### Update Project Progress

**Endpoint:** `POST /v0/projects/{project_id}/progress`

**Description:** Bulk update progress (percent_complete) for multiple tasks with timestamp

**Request Headers:**
- `Authorization: Bearer <JWT>` (required)
- `Content-Type: application/json` (required)

**Path Parameters:**
- `project_id` (uuid, required): Project identifier

**Request Body:**
```json
{
  "date": "datetime ISO 8601 (required, progress reporting date)",
  "updates": [
    {
      "task_id": "uuid (required)",
      "percent_complete": "integer (required, 0-100)",
      "comment": "string (optional, max 255 chars)"
    },
    {
      "task_id": "uuid",
      "percent_complete": 75,
      "comment": "Design phase completed, moving to implementation"
    },
    {
      "task_id": "uuid",
      "percent_complete": 100,
      "comment": "Testing completed successfully"
    }
  ]
}
```

**Response:** `200 OK`
```json
{
  "data": {
    "project_id": "uuid",
    "date": "2026-01-10T10:00:00Z",
    "updated_count": 3,
    "failed_count": 0,
    "updates": [
      {
        "task_id": "uuid",
        "task_name": "Design Phase",
        "previous_percent_complete": 50,
        "new_percent_complete": 75,
        "status_changed": true,
        "new_status": "in_progress"
      },
      {
        "task_id": "uuid",
        "task_name": "Testing",
        "previous_percent_complete": 90,
        "new_percent_complete": 100,
        "status_changed": true,
        "new_status": "completed"
      }
    ],
    "errors": []
  },
  "message": "Progress updated successfully for 3 tasks"
}
```

**Side Effects:**
- Updates `task.percent_complete` field
- Auto-updates `task.status` based on percent_complete:
  - 0% → `not_started`
  - 1-99% → `in_progress`
  - 100% → `completed`
- Records progress update in history for trend analysis
- Triggers recalculation of summary task percentages (if parent tasks exist)

**Error Responses:**
- `400 Bad Request`: Validation errors (percent_complete not in 0-100 range)
- `404 Not Found`: Project or task not found
- `422 Unprocessable Entity`: Business logic error (cannot update completed task)

**Notes:**
- Partial success supported: some updates may succeed while others fail
- Use database transaction for atomicity within single update
- `date` field allows backdated progress reporting for historical tracking

---

#### Get Progress History

**Endpoint:** `GET /v0/projects/{project_id}/progress/history`

**Description:** Retrieve progress update history for trend analysis

**Request Headers:**
- `Authorization: Bearer <JWT>` (required)

**Path Parameters:**
- `project_id` (uuid, required): Project identifier

**Query Parameters:**
- `task_id` (uuid, optional): Filter by specific task
- `start_date` (datetime, optional): Filter from date
- `end_date` (datetime, optional): Filter to date
- `page` (integer, optional, default: 1): Page number
- `per_page` (integer, optional, default: 20, max: 100): Items per page
- `sort_order` (string, optional, default: desc): Sort by date (asc, desc)

**Response:** `200 OK`
```json
{
  "data": [
    {
      "id": "uuid",
      "project_id": "uuid",
      "task_id": "uuid",
      "task_name": "Design Phase",
      "date": "2026-01-10T10:00:00Z",
      "previous_percent_complete": 50,
      "new_percent_complete": 75,
      "delta": 25,
      "comment": "Design phase completed, moving to implementation",
      "updated_by": "uuid (user_id from JWT)",
      "created_at": "2026-01-10T10:05:00Z"
    },
    {
      "id": "uuid",
      "project_id": "uuid",
      "task_id": "uuid",
      "task_name": "Testing",
      "date": "2026-01-10T10:00:00Z",
      "previous_percent_complete": 90,
      "new_percent_complete": 100,
      "delta": 10,
      "comment": "Testing completed successfully",
      "updated_by": "uuid",
      "created_at": "2026-01-10T10:05:00Z"
    }
  ],
  "page": 1,
  "per_page": 20,
  "total": 156,
  "total_pages": 8
}
```

**Error Responses:**
- `404 Not Found`: Project not found

**Notes:**
- Progress history enables trend analysis and S-curve generation
- `delta` field shows progress increment for quick scanning
- Filter by `task_id` to see specific task progress over time

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

### 4.12. EVM Calculation Algorithms

This section defines the algorithms and formulas for calculating Earned Value Management (EVM) indicators. All calculations SHALL operate at **monthly granularity** for POC scope.

#### 4.12.1. Budget At Completion (BAC)

**Formula:**
```
BAC = Σ(task.budget) for all project tasks
```

**Algorithm:**
1. Query all tasks for project where `is_summary = false` (leaf tasks only)
2. Sum the `budget` field of all leaf tasks
3. BAC is static unless project structure changes

**Implementation Notes:**
- Summary tasks do NOT contribute to BAC (they aggregate child tasks)
- BAC is cached at project level and recalculated on task budget changes
- Task budgets default to 0 if not specified

**Example:**
```python
# Project with 3 leaf tasks
Task A: budget = 10,000 EUR
Task B: budget = 15,000 EUR  
Task C: budget = 5,000 EUR
BAC = 10,000 + 15,000 + 5,000 = 30,000 EUR
```

#### 4.12.2. Planned Value (PV) Calculation

**Formula (Project Level):**
```
PV(t) = Σ PV_task(t) for all tasks

Where:
PV_task(t) = task.budget × planned_progress_at(t)
planned_progress_at(t) = min(1.0, days_from_start / task_duration_days)
```

**Algorithm:**
1. For each task, calculate days from planned start to reference date `t`
2. If `t < planned_start`: `planned_progress = 0%`
3. If `t > planned_finish`: `planned_progress = 100%`
4. Otherwise: `planned_progress = (t - planned_start) / (planned_finish - planned_start)`
5. Task PV = `task.budget × planned_progress`
6. Project PV = Sum of all task PV values

**Monthly Aggregation:**
- For monthly report at date `t`, use last day of month as reference date
- PV represents the planned budget that SHOULD have been earned by date `t`

**Predecessor Handling:**
- **Assumption**: Critical path and dependencies affect `planned_start` and `planned_finish` dates during project scheduling
- PV calculation uses the resulting scheduled dates (already incorporating predecessor constraints)
- No runtime critical path calculation during PV computation

**Implementation Notes:**
- PV follows linear distribution assumption (work progresses uniformly over task duration)
- For tasks with `percent_complete > 0`, PV still uses planned dates (not actual)
- Store monthly PV snapshots for timeseries queries

**Example:**
```python
# Task with budget 10,000 EUR
# Planned: 2026-01-01 to 2026-01-31 (31 days)
# Query PV at 2026-01-15 (halfway through)

days_from_start = 15 - 1 = 14 days
task_duration = 31 days
planned_progress = 14 / 31 = 0.45 (45%)
PV = 10,000 × 0.45 = 4,500 EUR
```

#### 4.12.3. Actual Cost (AC) Calculation

**Formula:**
```
AC(t) = Σ(expense.amount) for all expenses with expense_date ≤ t
```

**Algorithm (Milestone-Based Allocation):**
1. Query all expenses for project with `expense_date ≤ reference_date`
2. For each expense:
   - Identify associated milestone via `milestone_id` (direct link)
   - OR allocate to milestone by date range (if `milestone_id` is null):
     * Find milestone where `expense_date` is between `milestone.target_date` and next milestone's `target_date`
     * **Constraint**: Milestones MUST NOT overlap in target dates (enforced by **CON-004**)
3. Sum all expense amounts

**Monthly Aggregation:**
- AC for month M = Sum of expenses with `expense_date` in month M
- Cumulative AC at date `t` = Sum of all expenses from project start to date `t`

**Implementation Notes:**
- Expenses without `milestone_id` are allocated using date-based logic
- If no milestone covers the expense date, expense is **unallocated** (excluded from AC)
- Expense validation ensures `expense_date` is within project date range
- Store monthly AC snapshots for timeseries queries

**Example:**
```python
# Project with expenses
Expense 1: 2026-01-05, 2,000 EUR (Milestone: Kick-off, target: 2026-01-07)
Expense 2: 2026-01-15, 3,000 EUR (Milestone: Design Complete, target: 2026-01-31)
Expense 3: 2026-02-10, 1,500 EUR (Milestone: Testing, target: 2026-02-28)

# AC at 2026-01-31
AC = 2,000 + 3,000 = 5,000 EUR (Expense 3 not included, future date)

# AC at 2026-02-28  
AC = 2,000 + 3,000 + 1,500 = 6,500 EUR
```

#### 4.12.4. Earned Value (EV) Calculation - Dual Methods

The system provides TWO methods for calculating Earned Value, enabling cross-validation and comparison:

##### Method 1: Physical Progress (RAE-Based)

**Formula:**
```
EV_physical = BAC × physical_progress
physical_progress = AC / (AC + RAE)

Where:
- AC = Actual Cost (cumulative expenses to date)
- RAE = Reste À Engager (remaining budget to commit)
```

**Algorithm:**
1. Query latest RAE value from `rae_history` table for project at reference date
2. If no RAE history: `RAE = BAC` (no spend yet)
3. Calculate `physical_progress = AC / (AC + RAE)`
4. Calculate `EV_physical = BAC × physical_progress`

**Use Case:**
- Preferred when RAE is regularly updated by project managers
- Reflects actual physical work progress independent of planned schedule
- Useful for projects with variable work rates

**Example:**
```python
# Project: BAC = 100,000 EUR
# At 2026-02-28:
# - AC = 40,000 EUR (actual expenses)
# - RAE = 50,000 EUR (remaining budget, updated by PM on 2026-02-25)

physical_progress = 40,000 / (40,000 + 50,000) = 40,000 / 90,000 = 0.444 (44.4%)
EV_physical = 100,000 × 0.444 = 44,400 EUR

# Note: AC + RAE = 90,000 EUR < BAC (10,000 EUR forecasted savings)
```

##### Method 2: Milestone Completion

**Formula:**
```
EV_milestone = Σ(milestone.budget_weight × BAC) for all achieved milestones

Where:
- milestone.budget_weight = percentage of BAC allocated to milestone (0.0 to 1.0)
- Achieved milestone: status = 'achieved' AND actual_date ≤ reference_date
```

**Algorithm:**
1. Query all milestones for project with `status = 'achieved'` AND `actual_date ≤ reference_date`
2. For each achieved milestone:
   - Validate `budget_weight` is between 0.0 and 1.0
   - Calculate milestone value = `milestone.budget_weight × BAC`
3. Sum all milestone values to get `EV_milestone`

**Constraint:**
- **CON-005**: Sum of all milestone `budget_weight` values for a project MUST equal 1.0 (100%)
- Validation enforced at milestone creation/update

**Use Case:**
- Preferred for gate-based projects with clear deliverable milestones
- Aligns with Agile sprint completions or waterfall phase gates
- Less sensitive to RAE update frequency

**Example:**
```python
# Project: BAC = 100,000 EUR
# Milestones:
# - Kick-off: 5% weight, achieved 2026-01-07
# - Design: 25% weight, achieved 2026-01-31  
# - Development: 50% weight, planned 2026-03-31 (not achieved)
# - Testing: 15% weight, planned 2026-04-30 (not achieved)
# - Deployment: 5% weight, planned 2026-05-15 (not achieved)

# At 2026-02-28:
EV_milestone = (0.05 × 100,000) + (0.25 × 100,000)
             = 5,000 + 25,000
             = 30,000 EUR

# Only Kick-off and Design milestones achieved by reference date
```

##### EV Method Comparison and Selection

**API Response:**
- EVM endpoints return BOTH `ev_physical` and `ev_milestone` values
- Frontend can display both for comparison or select one as primary
- `ev_delta = ev_physical - ev_milestone` shows variance between methods

**Guidelines:**
- **GUD-012**: Use physical progress method when RAE is updated weekly/monthly
- **GUD-013**: Use milestone method for projects with binary deliverables
- **GUD-014**: Investigate if `ev_delta > 10% BAC` (methods diverge significantly)

**Example JSON Response:**
```json
{
  "date": "2026-02-28",
  "bac": 100000,
  "pv": 50000,
  "ac": 40000,
  "ev_physical": 44400,
  "ev_milestone": 30000,
  "ev_delta": 14400,
  "cv_physical": 4400,
  "sv_physical": -5600,
  "cpi_physical": 1.11,
  "spi_physical": 0.888,
  "cpi_milestone": 0.75,
  "spi_milestone": 0.6
}
```

#### 4.12.5. Cost Variance (CV) and Schedule Variance (SV)

**Formulas:**
```
CV = EV - AC
SV = EV - PV

Where:
- Positive CV: Under budget (good)
- Negative CV: Over budget (bad)
- Positive SV: Ahead of schedule (good)
- Negative SV: Behind schedule (bad)
```

**Algorithm:**
1. Calculate EV using selected method (physical or milestone)
2. Calculate AC (cumulative expenses)
3. Calculate PV (planned value at reference date)
4. Compute variances: `CV = EV - AC`, `SV = EV - PV`

**Both Methods:**
- System calculates CV and SV for both EV methods
- Response includes: `cv_physical`, `sv_physical`, `cv_milestone`, `sv_milestone`

**Example:**
```python
# Using physical progress method:
EV_physical = 44,400 EUR
AC = 40,000 EUR
PV = 50,000 EUR

CV_physical = 44,400 - 40,000 = 4,400 EUR (under budget by 4.4K)
SV_physical = 44,400 - 50,000 = -5,600 EUR (behind schedule by 5.6K)

# Using milestone method:
EV_milestone = 30,000 EUR
CV_milestone = 30,000 - 40,000 = -10,000 EUR (over budget by 10K)
SV_milestone = 30,000 - 50,000 = -20,000 EUR (behind schedule by 20K)
```

#### 4.12.6. Cost Performance Index (CPI) and Schedule Performance Index (SPI)

**Formulas:**
```
CPI = EV / AC
SPI = EV / PV

Where:
- CPI > 1.0: Under budget (good cost performance)
- CPI < 1.0: Over budget (poor cost performance)
- CPI = 1.0: On budget
- SPI > 1.0: Ahead of schedule (good schedule performance)
- SPI < 1.0: Behind schedule (poor schedule performance)  
- SPI = 1.0: On schedule
```

**Algorithm:**
1. Calculate EV, AC, PV as per previous sections
2. Compute ratios: `CPI = EV / AC`, `SPI = EV / PV`
3. Handle edge cases:
   - If `AC = 0`: `CPI = undefined` (project not started)
   - If `PV = 0`: `SPI = undefined` (no work planned yet)
   - Return `null` for undefined indices in JSON response

**Both Methods:**
- System calculates CPI and SPI for both EV methods
- Response includes: `cpi_physical`, `spi_physical`, `cpi_milestone`, `spi_milestone`

**Example:**
```python
# Using physical progress method:
CPI_physical = 44,400 / 40,000 = 1.11 (11% under budget)
SPI_physical = 44,400 / 50,000 = 0.888 (11.2% behind schedule)

# Using milestone method:
CPI_milestone = 30,000 / 40,000 = 0.75 (25% over budget)
SPI_milestone = 30,000 / 50,000 = 0.6 (40% behind schedule)

# Interpretation:
# - Physical method shows better cost performance (1.11 vs 0.75)
# - Both methods show schedule delays
# - Large divergence suggests milestone achievements lagging physical progress
```

#### 4.12.7. Estimate At Completion (EAC) - Three Projection Methods

The system provides THREE methods for forecasting final project cost (EAC), each with different assumptions:

##### EAC Method 1: CPI-Based Projection

**Formula:**
```
EAC_CPI = BAC / CPI

Assumption: Current cost performance will continue for remaining work
```

**Algorithm:**
1. Calculate CPI = EV / AC
2. If `CPI = 0`: `EAC_CPI = undefined` (cannot project)
3. Otherwise: `EAC_CPI = BAC / CPI`

**Use Case:**
- Default method for most projects
- Assumes cost efficiency trends will persist
- Best when cost variances are due to systemic factors (e.g., labor rates, productivity)

**Example:**
```python
BAC = 100,000 EUR
CPI = 1.11 (from physical progress method)

EAC_CPI = 100,000 / 1.11 = 90,090 EUR

# Interpretation: Project forecasted to finish 9,910 EUR under budget
# if current 11% cost efficiency continues
```

##### EAC Method 2: CPI×SPI Combined Projection

**Formula:**
```
EAC_CPISPI = AC + [(BAC - EV) / (CPI × SPI)]

Assumption: Both cost AND schedule performance affect remaining work
```

**Algorithm:**
1. Calculate CPI = EV / AC
2. Calculate SPI = EV / PV
3. If `CPI = 0` OR `SPI = 0`: `EAC_CPISPI = undefined`
4. Otherwise: `EAC_CPISPI = AC + [(BAC - EV) / (CPI × SPI)]`

**Use Case:**
- Used when schedule delays correlate with cost overruns
- More conservative than CPI-only method
- Reflects reality that rushing to catch up costs money

**Example:**
```python
BAC = 100,000 EUR
AC = 40,000 EUR
EV_physical = 44,400 EUR
CPI_physical = 1.11
SPI_physical = 0.888

EAC_CPISPI = 40,000 + [(100,000 - 44,400) / (1.11 × 0.888)]
           = 40,000 + [55,600 / 0.986]
           = 40,000 + 56,389
           = 96,389 EUR

# Interpretation: Despite good cost performance (CPI=1.11),
# schedule delay (SPI=0.888) increases forecasted final cost
```

##### EAC Method 3: Plan-Based Projection

**Formula:**
```
EAC_PLAN = AC + (BAC - EV)

Assumption: Remaining work will proceed exactly as originally planned
```

**Algorithm:**
1. Calculate EV (using selected method)
2. Calculate AC (cumulative expenses)
3. Compute: `EAC_PLAN = AC + (BAC - EV)`
4. Equivalent to: `EAC_PLAN = AC + ETC_planned`

**Use Case:**
- Optimistic scenario (assumes no more issues)
- Used when past variances are isolated incidents (e.g., one-time delays)
- Baseline for comparing performance-based projections

**Example:**
```python
BAC = 100,000 EUR
AC = 40,000 EUR
EV_physical = 44,400 EUR

EAC_PLAN = 40,000 + (100,000 - 44,400)
         = 40,000 + 55,600
         = 95,600 EUR

# Interpretation: If remaining work goes perfectly as planned,
# project will finish 4,400 EUR under budget
```

##### EAC Method Comparison

**API Response:**
- EVM endpoints return ALL THREE EAC projections
- Each projection calculated using the selected EV method (physical or milestone)
- Total of 6 EAC values: 3 methods × 2 EV methods

**Example JSON Response:**
```json
{
  "eac_cpi_physical": 90090,
  "eac_cpispi_physical": 96389,
  "eac_plan_physical": 95600,
  "eac_cpi_milestone": 133333,
  "eac_cpispi_milestone": 155556,
  "eac_plan_milestone": 110000
}
```

**Guidelines:**
- **GUD-015**: Use CPI method as primary EAC when CPI is stable (±10% over 3 months)
- **GUD-016**: Use CPI×SPI method when schedule and cost are correlated
- **GUD-017**: Use Plan method as optimistic scenario or when corrective actions implemented
- **GUD-018**: If EAC methods diverge > 20%, investigate root causes

#### 4.12.8. Estimate To Complete (ETC) and Variance At Completion (VAC)

**Formulas:**
```
ETC = EAC - AC
VAC = BAC - EAC

Where:
- ETC: Forecasted cost for remaining work
- VAC: Forecasted final budget variance (positive = under budget, negative = over budget)
```

**Algorithm:**
1. Calculate EAC using one of the three methods
2. Compute: `ETC = EAC - AC`
3. Compute: `VAC = BAC - EAC`

**Implementation Notes:**
- ETC and VAC calculated for all three EAC methods
- Response includes: `etc_cpi`, `etc_cpispi`, `etc_plan`, `vac_cpi`, `vac_cpispi`, `vac_plan`
- VAC helps executive decision-making (e.g., cancel if `VAC < -50% BAC`)

**Example:**
```python
# Using CPI method with physical progress:
EAC_CPI = 90,090 EUR
AC = 40,000 EUR
BAC = 100,000 EUR

ETC_CPI = 90,090 - 40,000 = 50,090 EUR (forecasted remaining cost)
VAC_CPI = 100,000 - 90,090 = 9,910 EUR (forecasted savings)

# Using CPI×SPI method:
EAC_CPISPI = 96,389 EUR
ETC_CPISPI = 96,389 - 40,000 = 56,389 EUR
VAC_CPISPI = 100,000 - 96,389 = 3,611 EUR (smaller forecasted savings)
```

#### 4.12.9. Critical Path Calculation (Optional for POC)

**Status:** OUT OF SCOPE for POC MVP (per **Section 1.3**)

**Future Implementation Notes:**
- Critical path determines longest task chain from project start to finish
- Algorithm: Forward pass (early start/finish) + Backward pass (late start/finish)
- Predecessor types: Finish-to-Start (FS), Start-to-Start (SS), Finish-to-Finish (FF), Start-to-Finish (SF)
- Lag/Lead: Time offset between predecessor and successor tasks
- Critical tasks: `slack = 0` (late_start - early_start = 0)

**POC Workaround:**
- Import critical path flags from MS Project XML (`is_critical = true`)
- Do not recalculate critical path in POC service
- Display imported critical path visually in Gantt chart

#### 4.12.10. Monthly Snapshot Storage

**Requirement:** Store monthly EVM snapshots for timeseries analysis (**REQ-EVM-010**)

**Algorithm:**
1. At end of each month, calculate all EVM indicators for project:
   - PV, AC, EV (both methods), CV, SV, CPI, SPI, EAC (all methods), ETC, VAC
2. Store snapshot in `evm_snapshots` table (to be defined) with:
   - `project_id`, `snapshot_date`, `pv`, `ac`, `ev_physical`, `ev_milestone`, etc.
3. Timeseries endpoint queries snapshots for date range

**Schema (Future):**
```json
{
  "id": "uuid",
  "project_id": "uuid",
  "snapshot_date": "2026-02-28",
  "pv": 50000,
  "ac": 40000,
  "ev_physical": 44400,
  "ev_milestone": 30000,
  "cv_physical": 4400,
  "sv_physical": -5600,
  "cpi_physical": 1.11,
  "spi_physical": 0.888,
  "eac_cpi_physical": 90090,
  "etc_cpi_physical": 50090,
  "vac_cpi_physical": 9910,
  "created_at": "2026-02-28T23:59:59Z"
}
```

**Implementation Notes:**
- Snapshots generated via scheduled job (cron) or manual trigger
- Historical snapshots immutable (no updates after creation)
- Enables S-curve visualization: PV, AC, EV over time

## 5. Acceptance Criteria

Defines testable acceptance criteria for each functional requirement using Given-When-Then format where applicable.

### Project Management (AC-PM-xxx)

- **AC-PM-001**: Given a valid JWT with `company_id`, When creating a project with all required fields, Then the system SHALL return 201 with project `id` and set `company_id` from JWT
- **AC-PM-002**: Given a project exists, When updating with `name` exceeding 255 characters, Then the system SHALL return 400 with validation error
- **AC-PM-003**: Given a project with `planned_start_date > planned_finish_date`, When creating/updating, Then the system SHALL return 400 with error "finish date must be after start date"
- **AC-PM-004**: Given a project with tasks, When deleting the project, Then the system SHALL cascade delete all child tasks, milestones, assignments, expenses, and RAE history
- **AC-PM-005**: Given user from company A, When attempting to access project from company B, Then the system SHALL return 404 (not 403 to avoid data leakage)
- **AC-PM-006**: Given a project with `ms_project_uid`, When importing again with same UID, Then the system SHALL update existing project (not create duplicate)
- **AC-PM-007**: Given project list request, When filtering by `status=active`, Then the system SHALL return only projects with status "active"
- **AC-PM-008**: Given project list request with `sort_by=created_at&sort_order=desc`, Then the system SHALL return projects ordered by creation date descending
- **AC-PM-009**: Given a project, When calculating BAC, Then the system SHALL sum only leaf task budgets (exclude summary tasks)
- **AC-PM-010**: Given a project, When querying via GET /projects/{id}, Then response SHALL include computed `total_budget` field matching BAC calculation

### Task Management (AC-TM-xxx)

- **AC-TM-001**: Given a project, When creating a task with `wbs_code` "1.2.3", Then the system SHALL validate WBS format (dot-separated integers)
- **AC-TM-002**: Given a task with `is_summary=true`, When creating child tasks, Then the system SHALL auto-calculate summary task dates from child min/max dates
- **AC-TM-003**: Given a task, When updating `percent_complete` to 50%, Then the system SHALL record progress update in history with `delta`, `updated_by`, and timestamp
- **AC-TM-004**: Given a task with `percent_complete=100`, When attempting to update to 95%, Then the system SHALL allow it (progress can regress)
- **AC-TM-005**: Given a task with `type=milestone`, When validating, Then `duration` SHALL equal 0
- **AC-TM-006**: Given a task, When creating with `planned_start_date < project.planned_start_date`, Then the system SHALL return 422 with error "task dates outside project dates"
- **AC-TM-007**: Given task list request for project, When querying with `is_critical=true`, Then the system SHALL return only tasks on critical path
- **AC-TM-008**: Given a task with predecessors, When importing from MS Project, Then the system SHALL preserve `predecessor_type` (FS/SS/FF/SF) and `lag_days`
- **AC-TM-009**: Given tasks at different WBS levels, When querying, Then the system SHALL support filtering by `wbs_level` (depth in hierarchy)
- **AC-TM-010**: Given a summary task, When calculating `percent_complete`, Then the system SHALL use weighted average of child task progress

### Resource Management (AC-RM-xxx)

- **AC-RM-001**: Given a company, When creating a resource with duplicate `code` within same company, Then the system SHALL return 409 Conflict
- **AC-RM-002**: Given a resource with `cost_per_hour=150.50`, When creating assignment, Then the system SHALL use this rate for cost calculations
- **AC-RM-003**: Given a resource with `type=material`, When creating assignment, Then `cost_per_unit` SHALL be validated (required for material resources)
- **AC-RM-004**: Given resources list request, When filtering by `type=labor`, Then the system SHALL return only labor resources
- **AC-RM-005**: Given a resource, When deleting with active assignments, Then the system SHALL return 409 with error "resource has active assignments" (prevent orphaned data)
- **AC-RM-006**: Given a resource with `max_units=2.0` (200%), When calculating availability, Then the system SHALL support over-allocation detection
- **AC-RM-007**: Given resource list request with `sort_by=cost_per_hour`, Then the system SHALL order by cost ascending (or descending if `sort_order=desc`)

### Assignment Management (AC-AS-xxx)

- **AC-AS-001**: Given a task and resource, When creating assignment with `allocation_percent=150`, Then the system SHALL validate it does not exceed `resource.max_units`
- **AC-AS-002**: Given an assignment, When updating `remaining_work`, Then the system SHALL recalculate task ETC based on `resource.cost_per_hour`
- **AC-AS-003**: Given a task with multiple assignments, When calculating task cost, Then the system SHALL sum `(resource.cost_per_hour * assignment.work_hours)`
- **AC-AS-004**: Given assignments for a task, When task `planned_start_date` changes, Then the system SHALL automatically adjust assignment dates to match
- **AC-AS-005**: Given an assignment, When resource is deleted, Then the system SHALL cascade delete assignment OR return 409 (based on referential integrity policy)
- **AC-AS-006**: Given assignment list request for project, When filtering by `resource_id`, Then the system SHALL return all assignments for that resource across all project tasks

### Milestone & Deliverable Management (AC-MD-xxx)

- **AC-MD-001**: Given a project, When creating milestones with `budget_weight` summing to 0.95, Then the system SHALL return 400 with error "milestone weights must sum to 1.0"
- **AC-MD-002**: Given a milestone with `target_date`, When marking as achieved with `actual_date`, Then the system SHALL validate `actual_date` is within project date range
- **AC-MD-003**: Given milestones with overlapping target date ranges, When creating/updating, Then the system SHALL return 400 with error "milestones must not overlap" (CON-004)
- **AC-MD-004**: Given a milestone with `status=achieved`, When calculating EV_milestone, Then the system SHALL include `budget_weight × BAC` in EV total
- **AC-MD-005**: Given a milestone, When associating deliverable, Then the system SHALL validate deliverable `due_date` aligns with milestone `target_date` (within ±7 days tolerance)
- **AC-MD-006**: Given a deliverable with `status=delivered`, When querying project statistics, Then the system SHALL include it in "deliverables delivered" count
- **AC-MD-007**: Given milestones list, When sorting by `target_date`, Then the system SHALL order chronologically for Gantt chart rendering

### Expense Tracking (AC-ET-xxx)

- **AC-ET-001**: Given a project, When creating expense with `expense_date` outside project date range, Then the system SHALL return 422 with error "expense date outside project dates"
- **AC-ET-002**: Given an expense with `amount=5000` and `category=Labor`, When recording, Then the system SHALL increment project AC by 5000 for that month
- **AC-ET-003**: Given an expense with `milestone_id=null`, When calculating AC allocation, Then the system SHALL assign to milestone based on `expense_date` falling between milestone target dates
- **AC-ET-004**: Given expenses with `invoice_number` duplicate within project, Then the system SHALL allow it (same invoice can have multiple line items)
- **AC-ET-005**: Given expense list request, When filtering by `category=Equipment`, Then the system SHALL return only equipment expenses
- **AC-ET-006**: Given expenses for a month, When querying statistics, Then the system SHALL provide breakdown by category with echarts_format for pie chart
- **AC-ET-007**: Given an expense with `description` exceeding 500 characters, Then the system SHALL return 400 with validation error

### Reste À Engager (AC-RAE-xxx)

- **AC-RAE-001**: Given a project at month end, When PM updates RAE to 50000, Then the system SHALL create RAE history entry with `date`, `rae_value`, `comment`, `updated_by`
- **AC-RAE-002**: Given RAE history, When calculating physical progress, Then the system SHALL use latest RAE value for reference date via `physical_progress = AC / (AC + RAE)`
- **AC-RAE-003**: Given a project with no RAE history, When calculating EV_physical, Then the system SHALL default `RAE = BAC` (no spend yet)
- **AC-RAE-004**: Given RAE update with `rae_value < 0`, Then the system SHALL return 400 with error "RAE cannot be negative"
- **AC-RAE-005**: Given RAE history request, When querying timeseries, Then the system SHALL return ordered by date ascending for trend visualization

### EVM Calculations (AC-EVM-xxx)

- **AC-EVM-001**: Given a project with BAC=100000, PV=50000, AC=40000, RAE=50000, When calculating EV_physical, Then the system SHALL return `EV = 100000 × (40000/(40000+50000)) = 44444`
- **AC-EVM-002**: Given a project with 2 achieved milestones (weights 0.2 and 0.3), BAC=100000, When calculating EV_milestone, Then the system SHALL return `EV = (0.2 + 0.3) × 100000 = 50000`
- **AC-EVM-003**: Given EV=44000, AC=40000, When calculating CV, Then the system SHALL return `CV = 44000 - 40000 = 4000` (under budget)
- **AC-EVM-004**: Given EV=44000, PV=50000, When calculating SV, Then the system SHALL return `SV = 44000 - 50000 = -6000` (behind schedule)
- **AC-EVM-005**: Given EV=44000, AC=40000, When calculating CPI, Then the system SHALL return `CPI = 44000 / 40000 = 1.1`
- **AC-EVM-006**: Given EV=44000, PV=50000, When calculating SPI, Then the system SHALL return `SPI = 44000 / 50000 = 0.88`
- **AC-EVM-007**: Given BAC=100000, CPI=1.1, When calculating EAC_CPI, Then the system SHALL return `EAC = 100000 / 1.1 = 90909`
- **AC-EVM-008**: Given AC=40000, BAC=100000, EV=44000, CPI=1.1, SPI=0.88, When calculating EAC_CPISPI, Then the system SHALL return `EAC = 40000 + (100000-44000)/(1.1×0.88)`
- **AC-EVM-009**: Given AC=40000, BAC=100000, EV=44000, When calculating EAC_PLAN, Then the system SHALL return `EAC = 40000 + (100000-44000) = 96000`
- **AC-EVM-010**: Given EAC=90909, AC=40000, When calculating ETC, Then the system SHALL return `ETC = 90909 - 40000 = 50909`
- **AC-EVM-011**: Given BAC=100000, EAC=90909, When calculating VAC, Then the system SHALL return `VAC = 100000 - 90909 = 9091` (forecasted savings)
- **AC-EVM-012**: Given EVM snapshot request for date range, When querying timeseries, Then the system SHALL return monthly snapshots with PV, AC, EV arrays for S-curve rendering
- **AC-EVM-013**: Given `ev_physical=44000` and `ev_milestone=30000`, When calculating delta, Then the system SHALL return `ev_delta = 44000 - 30000 = 14000` and flag divergence if `|delta| > 0.1 × BAC`
- **AC-EVM-014**: Given AC=0 (project not started), When calculating CPI, Then the system SHALL return `null` (undefined)
- **AC-EVM-015**: Given PV=0 (no work planned yet), When calculating SPI, Then the system SHALL return `null` (undefined)

### Statistics (AC-ST-xxx)

- **AC-ST-001**: Given expense statistics request, When querying by category, Then the system SHALL return expenses grouped by category with echarts_format for pie chart
- **AC-ST-002**: Given resource statistics request, When querying by allocation, Then the system SHALL return total_work_hours per resource with echarts_format for bar chart
- **AC-ST-003**: Given monthly statistics request, When querying project costs, Then the system SHALL return time series with dates and amounts for line chart
- **AC-ST-004**: Given statistics with no data (empty project), When querying, Then the system SHALL return empty arrays `{data: [], echarts_format: {series: [{data: []}]}}`

### Progress Updates (AC-PU-xxx)

- **AC-PU-001**: Given bulk progress update with 50 task updates, When submitting via POST /progress, Then the system SHALL process all updates atomically (all or none)
- **AC-PU-002**: Given progress update for task not in project, When validating, Then the system SHALL return 400 with error for invalid `task_id`
- **AC-PU-003**: Given progress update with `percent_complete=150`, When validating, Then the system SHALL return 400 with error "percent must be 0-100"
- **AC-PU-004**: Given progress history request, When querying with pagination, Then the system SHALL support `page`, `per_page`, and return `total_pages`
- **AC-PU-005**: Given progress history, When filtering by date range, Then the system SHALL support `from_date` and `to_date` query parameters
- **AC-PU-006**: Given progress update, When recording, Then the system SHALL capture `updated_by` from JWT `user_id` claim automatically

### Security (AC-SEC-xxx)

- **AC-SEC-001**: Given request without JWT token, When accessing any protected endpoint, Then the system SHALL return 401 Unauthorized
- **AC-SEC-002**: Given JWT token with invalid signature, When validating, Then the system SHALL return 401 with error "invalid token"
- **AC-SEC-003**: Given JWT token missing `company_id` claim, When validating, Then the system SHALL return 401 with error "missing required claim"
- **AC-SEC-004**: Given user from company A, When listing projects, Then the system SHALL filter results to only company A projects (implicit WHERE company_id = user.company_id)
- **AC-SEC-005**: Given malicious input `<script>alert('xss')</script>` in project name, When creating, Then the system SHALL sanitize or escape HTML entities
- **AC-SEC-006**: Given SQL injection attempt in search query, When processing, Then the system SHALL use parameterized queries (SQLAlchemy ORM prevents injection)
- **AC-SEC-007**: Given 11 requests in 10 seconds to same endpoint, When rate limit is 10/min, Then the system SHALL return 429 on 11th request
- **AC-SEC-008**: Given rate limit exceeded response, When returning 429, Then response SHALL include `X-RateLimit-Reset` header with Unix timestamp
- **AC-SEC-009**: Given Guardian check-access returns `access_granted=false`, When enforcing @access_required decorator, Then the system SHALL return 403 Forbidden
- **AC-SEC-010**: Given mock Guardian service (POC), When checking access, Then the system SHALL bypass actual Guardian calls and return `access_granted=true` for development

### Performance (AC-PERF-xxx)

- **AC-PERF-001**: Given project list request with 100 projects, When querying, Then response time SHALL be < 200ms at 95th percentile
- **AC-PERF-002**: Given EVM calculation request, When calculating all indicators, Then response time SHALL be < 500ms at 95th percentile
- **AC-PERF-003**: Given pagination request with `per_page=100`, When querying tasks, Then the system SHALL limit maximum per_page to 100 (prevent abuse)
- **AC-PERF-004**: Given concurrent requests from 10 users, When accessing different projects, Then the system SHALL handle without deadlocks or race conditions
- **AC-PERF-005**: Given database query with N+1 problem potential, When loading projects with tasks, Then the system SHALL use eager loading (`joinedload` or `selectinload`)
- **AC-PERF-006**: Given monthly snapshot generation, When processing 100 projects, Then batch job SHALL complete within 5 minutes

## 6. Test Automation Strategy

Defines comprehensive testing approach to ensure API reliability, correctness, and performance.

### Test Levels

#### Unit Tests (`tests/unit/`)
- **Scope**: Individual functions, methods, and classes in isolation
- **Mocking**: Mock all external dependencies (database, Guardian, Identity services)
- **Focus Areas**:
  - EVM calculation functions (PV, AC, EV, CPI, SPI, EAC algorithms)
  - Schema validation (Marshmallow schemas for all DTOs)
  - Decorator logic (`@require_jwt_auth`, `@access_required`, `@limiter`)
  - Model methods (BAC calculation, summary task aggregation)
  - JWT token parsing and validation
- **Execution**: Fast (<1 second total), no external dependencies
- **Coverage Target**: 85% for business logic modules

**Example:**
```python
def test_calculate_bac_excludes_summary_tasks():
    """Test that BAC calculation sums only leaf task budgets."""
    project = Project(id=uuid4(), name="Test Project")
    task1 = Task(project_id=project.id, budget=10000, is_summary=False)
    task2 = Task(project_id=project.id, budget=15000, is_summary=False)
    summary = Task(project_id=project.id, budget=25000, is_summary=True)
    
    bac = calculate_bac([task1, task2, summary])
    assert bac == 25000  # Summary task excluded
```

#### Integration Tests (`tests/integration/`)
- **Scope**: API endpoints with real database (PostgreSQL via docker-compose)
- **Database**: Clean database per test using fixtures, transactions rolled back after each test
- **Focus Areas**:
  - Full CRUD workflows (create project → add tasks → add expenses → calculate EVM)
  - Multi-tenant isolation validation (user from company A cannot access company B data)
  - Database constraints (foreign keys, unique constraints, check constraints)
  - Pagination, filtering, sorting on list endpoints
  - Error handling and status code validation (400, 404, 409, 422, 500)
  - Guardian service integration (mocked with controlled responses)
- **Execution**: Moderate speed (10-30 seconds), requires `make compose-up`
- **Coverage Target**: 90% for resource endpoints

**Example:**
```python
def test_project_crud_workflow(authenticated_client, api_url):
    """Test complete project lifecycle: create → read → update → delete."""
    # Create
    payload = {"name": "Test Project", "planned_start_date": "2026-01-01", ...}
    response = authenticated_client.post(api_url("projects"), json=payload)
    assert response.status_code == 201
    project_id = response.json["data"]["id"]
    
    # Read
    response = authenticated_client.get(api_url(f"projects/{project_id}"))
    assert response.status_code == 200
    assert response.json["data"]["name"] == "Test Project"
    
    # Update
    response = authenticated_client.patch(api_url(f"projects/{project_id}"), 
                                          json={"name": "Updated Name"})
    assert response.status_code == 200
    
    # Delete
    response = authenticated_client.delete(api_url(f"projects/{project_id}"))
    assert response.status_code == 204
```

#### End-to-End Tests (Future)
- **Scope**: Multi-service workflows (wfp-poc + poc-import + poc-export)
- **Focus**: Import MS Project XML → Calculate EVM → Export to Excel
- **Status**: OUT OF SCOPE for POC MVP

### Frameworks & Tools

- **pytest 8.0+**: Test runner with fixtures, parametrization, markers
- **pytest-flask**: Flask app testing utilities (`client`, `authenticated_client` fixtures)
- **pytest-mock**: Mocking with `mocker` fixture (wraps `unittest.mock`)
- **pytest-cov**: Code coverage measurement with branch coverage
- **Faker**: Generate realistic test data (names, dates, addresses)
- **factory_boy**: Test data factories for models (ProjectFactory, TaskFactory)
- **responses**: Mock HTTP calls to external services (Guardian, Identity)

### Test Data Management

#### Fixtures Strategy
```python
@pytest.fixture
def sample_project(db_session):
    """Create a sample project for testing."""
    project = Project(
        id=uuid4(),
        company_id=COMPANY_A_ID,
        name="Sample Project",
        planned_start_date=date(2026, 1, 1),
        planned_finish_date=date(2026, 6, 30),
        budget=100000
    )
    db_session.add(project)
    db_session.commit()
    return project

@pytest.fixture
def sample_tasks(db_session, sample_project):
    """Create sample tasks for a project."""
    tasks = [
        Task(project_id=sample_project.id, name="Design", budget=30000, ...),
        Task(project_id=sample_project.id, name="Development", budget=50000, ...),
        Task(project_id=sample_project.id, name="Testing", budget=20000, ...),
    ]
    db_session.add_all(tasks)
    db_session.commit()
    return tasks
```

#### Factory Pattern
```python
class ProjectFactory(factory.Factory):
    class Meta:
        model = Project
    
    id = factory.LazyFunction(uuid4)
    company_id = COMPANY_A_ID
    name = factory.Faker('catch_phrase')
    planned_start_date = factory.Faker('date_between', start_date='today', end_date='+30d')
    planned_finish_date = factory.Faker('date_between', start_date='+31d', end_date='+365d')
    budget = factory.Faker('random_int', min=10000, max=1000000)
```

#### Database Reset
- **Integration tests**: Use `@pytest.fixture(scope="function")` for `db_session`
- Rollback transaction after each test to ensure isolation
- Alternatively, use `TRUNCATE TABLE` in teardown for faster cleanup

#### Test Data Constants
```python
# tests/conftest.py
COMPANY_A_ID = uuid4()  # Fixed UUID for tenant A
COMPANY_B_ID = uuid4()  # Fixed UUID for tenant B
USER_A_ID = uuid4()     # User belonging to company A
USER_B_ID = uuid4()     # User belonging to company B
```

### CI/CD Integration

#### GitHub Actions Workflow
```yaml
name: Test Suite

on: [push, pull_request]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python 3.11
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: make install-dev
      - name: Run unit tests
        run: make test-unit
      - name: Upload coverage
        uses: codecov/codecov-action@v4
  
  integration-tests:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python 3.11
        uses: actions/setup-python@v5
      - name: Install dependencies
        run: make install-dev
      - name: Run integration tests
        run: make test-integration
        env:
          DATABASE_URL: postgresql://postgres:postgres@localhost:5432/testdb
```

#### Makefile Targets
```makefile
test-unit:  ## Run unit tests only
	pytest tests/unit/ -v --cov=app --cov-report=term --cov-report=html

test-integration:  ## Run integration tests (requires compose-up)
	pytest tests/integration/ -v --cov=app --cov-append

test-all:  ## Run all tests
	make compose-up
	pytest tests/ -v --cov=app --cov-report=term --cov-report=html
	make compose-down
```

### Coverage Requirements

- **Minimum Overall Coverage**: 80% line coverage, 75% branch coverage
- **Critical Modules** (must achieve 90%+):
  - `app/resources/` (all endpoints)
  - `app/models/` (calculation methods)
  - `app/schemas/` (validation logic)
  - EVM calculation algorithms
- **Excluded from Coverage**:
  - `app/cli.py` (CLI commands, tested manually)
  - Migration scripts (`migrations/versions/*`)
  - Configuration files (`app/config.py`)

#### Coverage Report
```bash
# Generate HTML coverage report
pytest --cov=app --cov-report=html
open htmlcov/index.html

# Check coverage threshold
pytest --cov=app --cov-fail-under=80
```

### Performance Testing

#### Load Testing with Locust
```python
# tests/performance/locustfile.py
from locust import HttpUser, task, between

class ProjectAPIUser(HttpUser):
    wait_time = between(1, 3)
    
    def on_start(self):
        """Authenticate and get JWT token."""
        self.client.headers['Authorization'] = f'Bearer {get_test_jwt()}'
    
    @task(3)
    def list_projects(self):
        self.client.get("/v0/projects?page=1&per_page=20")
    
    @task(1)
    def get_project_evm(self):
        project_id = self.project_ids[random.randint(0, len(self.project_ids)-1)]
        self.client.get(f"/v0/projects/{project_id}/evm")
```

**Execution:**
```bash
locust -f tests/performance/locustfile.py --host=http://localhost:5000
# Open browser to http://localhost:8089
# Configure: 100 users, spawn rate 10/sec
```

**Performance Targets:**
- **Throughput**: 100 req/sec sustained for 5 minutes
- **Response Time**: 95th percentile < 500ms for EVM calculations
- **Database Connections**: Max 20 concurrent connections (pgBouncer pool)

#### Profiling
```python
# Use pytest-profiling or cProfile for slow tests
pytest tests/integration/test_evm_api.py --profile
```

### Test Organization

```
tests/
├── __init__.py
├── conftest.py                    # Shared fixtures (app, client, db_session)
├── unit/
│   ├── __init__.py
│   ├── conftest.py                # Unit-specific fixtures
│   ├── test_models/
│   │   ├── test_project_model.py
│   │   ├── test_task_model.py
│   │   └── test_evm_calculations.py
│   ├── test_schemas/
│   │   ├── test_project_schema.py
│   │   └── test_task_schema.py
│   ├── test_resources/
│   │   └── test_project_resource.py
│   └── test_utils/
│       ├── test_jwt_decorators.py
│       └── test_rate_limiting.py
├── integration/
│   ├── __init__.py
│   ├── conftest.py                # Integration-specific fixtures
│   ├── test_project_api.py
│   ├── test_task_api.py
│   ├── test_evm_api.py
│   ├── test_statistics_api.py
│   └── test_multi_tenant_isolation.py
├── performance/
│   └── locustfile.py
└── fixtures/
    ├── sample_projects.json
    └── ms_project_xml_samples/
```

### Test Execution Workflow

1. **Local Development**: `make test-unit` (fast feedback loop)
2. **Pre-Commit**: `make test-all` (full suite before pushing)
3. **CI Pipeline**: Automated on every push/PR
4. **Pre-Release**: Load testing with Locust (manual)

### Assertions & Validation

#### Use Descriptive Assertions
```python
# Bad
assert response.status_code == 200

# Good
assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.json}"
```

#### Validate Complete Response Structure
```python
response = client.get(api_url("projects/123/evm"))
assert response.status_code == 200
data = response.json["data"]

# Validate all required fields present
required_fields = ["bac", "pv", "ac", "ev_physical", "ev_milestone", "cpi_physical", "spi_physical"]
for field in required_fields:
    assert field in data, f"Missing required field: {field}"

# Validate data types
assert isinstance(data["bac"], (int, float))
assert isinstance(data["cpi_physical"], (float, type(None)))  # Can be null

# Validate business logic
assert data["cv_physical"] == data["ev_physical"] - data["ac"], "CV calculation incorrect"
```

### Mocking External Services

#### Guardian Service Mock
```python
@pytest.fixture
def mock_guardian_allow(mocker):
    """Mock Guardian service to always allow access."""
    return mocker.patch(
        'app.services.guardian_service.GuardianService.check_access',
        return_value={"access_granted": True, "reason": "granted"}
    )

@pytest.fixture
def mock_guardian_deny(mocker):
    """Mock Guardian service to deny access."""
    return mocker.patch(
        'app.services.guardian_service.GuardianService.check_access',
        return_value={"access_granted": False, "reason": "no_permission"}
    )
```

#### Identity Service Mock
```python
@pytest.fixture
def mock_jwt_validation(mocker):
    """Mock JWT validation to return test user claims."""
    return mocker.patch(
        'app.utils.jwt_decorators.validate_jwt',
        return_value={
            "user_id": str(USER_A_ID),
            "company_id": str(COMPANY_A_ID),
            "email": "test@example.com",
            "roles": ["project_manager"]
        }
    )
```

## 7. Rationale & Context

Explains the reasoning behind key architectural and functional design decisions in the wfp-poc API.

### Design Decisions

#### Milestone-Based AC Allocation

**Decision**: Expenses are allocated to milestones (not tasks) for AC calculation.

**Rationale**:
1. **Milestone-Driven Financial Control**: In large projects, financial approvals and budget releases typically align with milestone achievements (e.g., design approval, phase completion), not individual tasks.
2. **Simplified Accounting**: ERP systems and accounting workflows often track expenses at the milestone/phase level. Forcing task-level expense tracking adds granularity that finance teams may not use.
3. **Non-Overlapping Constraint**: By requiring milestones to have non-overlapping target dates (**CON-004**), expenses can be unambiguously allocated by date (expense falls between milestone M1 and M2 target dates → allocated to M1).
4. **Avoids Micro-Management**: Task-level expense tracking encourages over-detailed tracking (e.g., tracking coffee expenses per task), which adds overhead without value for POC scope.
5. **MS Project Compatibility**: MS Project uses milestone-based cost tracking by default (costs assigned at baseline/milestone dates).

**Trade-offs**:
- **Loss of Granularity**: Cannot directly answer "How much did Task X cost?" without aggregating milestone expenses.
- **Workaround**: For task-level cost estimation, use assignments (resource allocations with cost_per_hour × work_hours).

**Alternative Considered**: Task-level expense tracking was rejected due to increased complexity and limited value for POC scope (100 projects, ~500 tasks each = 50,000 potential expense allocations).

#### Dual EV Calculation Methods

**Decision**: Provide two EV calculation methods (physical progress via RAE + milestone completion) in parallel.

**Rationale**:
1. **Cross-Validation**: Comparing `ev_physical` and `ev_milestone` reveals discrepancies between physical work progress and deliverable completion. Large divergence (`|ev_delta| > 10% BAC`) signals potential issues:
   - Physical progress high, milestone low → Work done but deliverables not accepted (quality issues?)
   - Milestone high, physical progress low → Milestones achieved but unexpected costs (scope creep?)
2. **Flexibility**: Different project types benefit from different methods:
   - **R&D projects**: Physical progress method aligns with iterative development (RAE updated monthly based on work completed)
   - **Waterfall projects**: Milestone method aligns with gate-based approvals (payment upon deliverable acceptance)
3. **Stakeholder Preferences**: Finance prefers physical progress (cash flow tracking), PMO prefers milestones (deliverable tracking). Providing both satisfies all stakeholders.
4. **Audit Trail**: Having both methods creates audit checkpoints. If methods diverge, project manager must reconcile (e.g., update RAE, revise milestone weights).
5. **PMI Best Practices**: PMI EVM guidelines recommend comparing multiple EV methods for validation.

**Trade-offs**:
- **Complexity**: Two calculations instead of one increases testing surface and user confusion.
- **Mitigation**: API returns both; frontend defaults to one method but allows toggle for comparison.

**Alternative Considered**: Single EV method (physical progress only) was rejected because milestone-based tracking is standard in French public sector contracts (e.g., "tranche ferme", "tranche conditionnelle" payments tied to deliverables).

#### Task Hierarchy Structure

**Decision**: Support hierarchical task structure (WBS with parent/child via `parent_task_id`) but store as flat table with adjacency list.

**Rationale**:
1. **MS Project Compatibility**: MS Project uses Work Breakdown Structure (WBS) with multi-level nesting (project → phases → tasks → subtasks). Preserving hierarchy ensures round-trip import/export without data loss.
2. **Summary Task Aggregation**: Parent tasks (summary tasks) auto-compute dates, budget, progress from child tasks. Storing hierarchy enables recursive aggregation queries.
3. **Flat Table Performance**: Storing in single `tasks` table (not separate `phases`, `tasks`, `subtasks` tables) simplifies queries:
   - Single JOIN for task data
   - Use `is_summary` flag to distinguish summary vs leaf tasks
   - Use `wbs_code` (e.g., "1.2.3") for display ordering
4. **Flexible Depth**: Adjacency list pattern (`parent_task_id` FK to `tasks.id`) supports arbitrary nesting depth (1-10 levels typical in MS Project).
5. **Critical Path Calculation**: Hierarchical structure required for forward/backward pass algorithm (respects parent-child constraints).

**Trade-offs**:
- **Recursive Queries**: Computing full hierarchy (all descendants of task X) requires recursive CTE in SQL or multiple queries. For POC scope (500 tasks/project), performance acceptable.
- **Summary Task Consistency**: Must ensure summary task `budget` = SUM(child budgets). Enforced via validation at creation/update.

**Alternative Considered**: Materialized path (store full path as "1.2.3" string) was rejected because it complicates updates when moving tasks in hierarchy.

#### RAE History Tracking

**Decision**: Store all RAE updates in separate `rae_history` table (not just latest value in `projects` table).

**Rationale**:
1. **Trend Analysis**: RAE evolution over time reveals project health trends:
   - RAE decreasing → Work progressing, budget consumed (good)
   - RAE increasing → Scope creep, additional work discovered (warning)
   - RAE stable while AC increases → Work done but RAE not updated (PM not engaged)
2. **EV Physical Progress Validation**: Physical progress formula `EV = BAC × AC / (AC + RAE)` uses latest RAE. Historical RAE enables recalculating EV for past months (e.g., regenerate S-curves with corrected RAE).
3. **Audit Compliance**: French public sector contracts require "Reste À Engager" reporting at month-end. History table provides audit trail for financial inspections.
4. **Forecast Improvement**: RAE rate of change (dRAE/dt) improves EAC forecasts. Example: If RAE decreases by 10K/month, project will complete in RAE/10K months.
5. **Commenting**: RAE updates include optional `comment` field explaining changes (e.g., "Added 5K for unplanned server migration"). Comments provide context for variance analysis.

**Trade-offs**:
- **Storage**: ~12 RAE entries per project per year (monthly updates). For 100 projects over 2 years = 2,400 records (negligible).
- **Query Complexity**: Must lookup latest RAE via `ORDER BY date DESC LIMIT 1` instead of direct `projects.rae` field.
- **Mitigation**: Add index on `(project_id, date DESC)` for fast latest-RAE queries.

**Alternative Considered**: Storing only latest RAE in `projects.rae_current` field was rejected due to loss of historical data (cannot reconstruct past EVM snapshots).

#### Monthly Granularity for EVM

**Decision**: Calculate and store EVM indicators at monthly intervals (not daily/weekly).

**Rationale**:
1. **POC Scope**: Simplifies implementation by reducing calculation frequency (12 snapshots/year vs 365 daily snapshots).
2. **Business Alignment**: Financial reporting cycles are monthly (month-end close). Aligning EVM with accounting simplifies reconciliation.
3. **Data Stability**: Daily EVM fluctuates wildly due to expense timing (e.g., large invoice on day 15 spikes AC). Monthly aggregation smooths noise.
4. **Resource Constraints**: POC team lacks capacity for real-time EVM calculation (would require event-driven architecture with message queues).
5. **MS Project Standard**: MS Project status reports are typically monthly.

**Trade-offs**:
- **Delayed Visibility**: Cannot detect mid-month issues until month-end calculation.
- **Workaround**: Support on-demand EVM calculation via `GET /projects/{id}/evm?date=2026-01-15` for ad-hoc analysis.

**Future Enhancement**: Add weekly snapshots for high-priority projects (>1M EUR budget).

#### Three EAC Projection Methods

**Decision**: Calculate EAC using three different methods (CPI, CPI×SPI, Plan-based) and return all three in API response.

**Rationale**:
1. **Uncertainty Quantification**: Each method represents different assumption:
   - **EAC_CPI**: Optimistic (assumes schedule delays won't cost extra)
   - **EAC_CPISPI**: Realistic (assumes catching up requires overtime/additional resources)
   - **EAC_PLAN**: Best-case (assumes no more issues)
2. **Risk Management**: Spread between methods quantifies forecast uncertainty. Example:
   - EAC_CPI = 90K, EAC_CPISPI = 105K, EAC_PLAN = 95K → 15K range suggests moderate risk
   - Narrow spread (<5% BAC) → High confidence in forecast
   - Wide spread (>20% BAC) → High uncertainty, investigate causes
3. **Decision Support**: Executive dashboards can show EAC range as error bars on charts ("Project will finish between 90K-105K").
4. **PMI Standard**: PMI Practice Standard for EVM recommends comparing multiple EAC methods.
5. **No Single Right Answer**: Project context determines best method:
   - Fixed-price contracts → Use EAC_CPI (schedule delays don't change price)
   - Time-and-materials → Use EAC_CPISPI (delays increase cost)
   - Corrective actions implemented → Use EAC_PLAN (past doesn't predict future)

**Trade-offs**:
- **Cognitive Load**: Three numbers confuse non-EVM experts.
- **Mitigation**: Frontend highlights one primary method (user-configurable) but shows others in expandable detail.

**Alternative Considered**: Single EAC method (CPI only) was rejected because it oversimplifies and loses valuable risk information.

#### Apache ECharts Integration

**Decision**: Include `echarts_format` objects in statistics endpoint responses.

**Rationale**:
1. **Frontend Simplification**: Frontend can directly pass `echarts_format` to ECharts library without transformation logic. Reduces frontend complexity.
2. **Consistency**: Ensures all frontends (web, mobile) render identical charts (same colors, labels, formatting).
3. **Backend Control**: Chart configuration (e.g., color scheme for expense categories) managed in backend, not hardcoded in frontend.
4. **POC Scope**: Tight integration acceptable for POC (single frontend). For production, consider GraphQL or HATEOAS for flexible data fetching.

**Trade-offs**:
- **Coupling**: API couples to specific charting library (ECharts). Switching to Chart.js requires backend changes.
- **Payload Size**: Increases response size by ~30% (data + chart config).
- **Mitigation**: Return both `data` (raw) and `echarts_format` (UI-specific). Clients can use either.

#### Multi-Tenant Isolation via company_id

**Decision**: All entities have `company_id` FK, enforced at database and API layers.

**Rationale**:
1. **Data Segregation**: Prevents accidental data leakage between companies (critical for compliance).
2. **Shared Infrastructure**: Single database instance supports multiple tenants, reducing operational costs vs tenant-per-database.
3. **Implicit Filtering**: Middleware injects `company_id` filter on all queries based on JWT claim. Developers cannot forget to add WHERE clause.
4. **Performance**: Composite indexes `(company_id, id)` enable fast queries within tenant.
5. **Waterfall Pattern**: Consistent with other Waterfall services (Identity, Guardian use same pattern).

**Trade-offs**:
- **Schema Denormalization**: `company_id` duplicated in every table increases storage.
- **Cross-Company Queries**: Cannot easily query "all companies' projects" (requires admin override).
- **Mitigation**: Admin endpoints with special permission bypass company filter.

### Technology Choices

#### PostgreSQL 13+
- **Rationale**: Mature relational DB with JSON support (for flexible fields), CTEs (for recursive queries), strong ACID guarantees.
- **Alternative Considered**: MongoDB rejected due to lack of JOIN support (needed for task-resource assignments).

#### Flask 3.0+
- **Rationale**: Lightweight web framework, mature ecosystem, team familiarity.
- **Alternative Considered**: FastAPI rejected due to learning curve (async programming).

#### Marshmallow 3.0+
- **Rationale**: Declarative schema validation, automatic OpenAPI generation, nested schema support.
- **Alternative Considered**: Pydantic rejected due to tight coupling with FastAPI.

#### SQLAlchemy 2.0+
- **Rationale**: Powerful ORM with eager loading, relationship management, migration support (Alembic).
- **Alternative Considered**: Raw SQL rejected due to maintenance burden and SQL injection risk.

### POC Simplifications

**Documented simplifications for MVP scope:**
1. **Mock Authentication**: Guardian and Identity services mocked (no real JWT validation)
2. **No Critical Path Calculation**: Import from MS Project, don't recalculate
3. **Monthly Granularity**: No daily/weekly EVM snapshots
4. **No Caching**: EVM calculated on-demand (acceptable for 100 projects)
5. **No Async Processing**: Synchronous API calls (no background jobs)
6. **Limited Validation**: Basic constraints only (e.g., no resource over-allocation detection)
7. **No Soft Deletes**: Hard deletes with cascade (no audit trail for deleted entities)
8. **No Versioning**: No entity versioning (cannot rollback changes)
9. **No Notifications**: No email/webhook alerts for budget overruns
10. **No File Attachments**: Cannot attach documents to tasks/deliverables

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

Provides concrete examples and documents edge case handling for complex scenarios.

### Example 1: Complete Project Creation Workflow

**Scenario**: Create project "Website Redesign" with 3 phases, 8 tasks, 2 milestones, 3 resources.

#### Step 1: Create Project
```http
POST /v0/projects
Authorization: Bearer <JWT with company_id=abc123>
Content-Type: application/json

{
  "name": "Website Redesign",
  "description": "Complete redesign of corporate website",
  "planned_start_date": "2026-02-01",
  "planned_finish_date": "2026-06-30",
  "budget": 150000,
  "status": "planned",
  "ms_project_uid": "WR-2026-001"
}
```

**Response:**
```json
{
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "company_id": "abc123-company-uuid",
    "name": "Website Redesign",
    "description": "Complete redesign of corporate website",
    "planned_start_date": "2026-02-01",
    "planned_finish_date": "2026-06-30",
    "budget": 150000,
    "status": "planned",
    "ms_project_uid": "WR-2026-001",
    "created_at": "2026-01-10T14:30:00Z",
    "updated_at": "2026-01-10T14:30:00Z"
  },
  "message": "Project created successfully"
}
```

#### Step 2: Create Tasks (Hierarchical)
```http
POST /v0/projects/550e8400-e29b-41d4-a716-446655440000/tasks

{
  "tasks": [
    {
      "name": "Phase 1: Discovery",
      "wbs_code": "1",
      "is_summary": true,
      "planned_start_date": "2026-02-01",
      "planned_finish_date": "2026-02-28"
    },
    {
      "name": "Requirements Gathering",
      "wbs_code": "1.1",
      "parent_task_id": null,
      "is_summary": false,
      "planned_start_date": "2026-02-01",
      "planned_finish_date": "2026-02-14",
      "duration": 10,
      "budget": 15000,
      "type": "task"
    },
    {
      "name": "Design Mockups",
      "wbs_code": "1.2",
      "is_summary": false,
      "planned_start_date": "2026-02-15",
      "planned_finish_date": "2026-02-28",
      "duration": 10,
      "budget": 20000,
      "predecessors": [{"predecessor_task_id": "<task-1.1-id>", "type": "FS"}]
    },
    {
      "name": "Phase 2: Development",
      "wbs_code": "2",
      "is_summary": true,
      "planned_start_date": "2026-03-01",
      "planned_finish_date": "2026-05-31"
    },
    {
      "name": "Frontend Development",
      "wbs_code": "2.1",
      "is_summary": false,
      "planned_start_date": "2026-03-01",
      "planned_finish_date": "2026-04-30",
      "duration": 40,
      "budget": 60000
    },
    {
      "name": "Backend API Development",
      "wbs_code": "2.2",
      "is_summary": false,
      "planned_start_date": "2026-03-15",
      "planned_finish_date": "2026-05-15",
      "duration": 40,
      "budget": 50000
    },
    {
      "name": "Phase 3: Deployment",
      "wbs_code": "3",
      "is_summary": true,
      "planned_start_date": "2026-06-01",
      "planned_finish_date": "2026-06-30"
    },
    {
      "name": "Production Deployment",
      "wbs_code": "3.1",
      "is_summary": false,
      "planned_start_date": "2026-06-01",
      "planned_finish_date": "2026-06-15",
      "duration": 10,
      "budget": 5000
    }
  ]
}
```

#### Step 3: Create Milestones
```http
POST /v0/projects/550e8400-e29b-41d4-a716-446655440000/milestones

{
  "milestones": [
    {
      "name": "Design Approved",
      "target_date": "2026-02-28",
      "budget_weight": 0.25,
      "description": "Design mockups approved by stakeholders"
    },
    {
      "name": "Development Complete",
      "target_date": "2026-05-31",
      "budget_weight": 0.65,
      "description": "All frontend and backend development finished"
    },
    {
      "name": "Go Live",
      "target_date": "2026-06-30",
      "budget_weight": 0.10,
      "description": "Website live in production"
    }
  ]
}
```

**Note**: Milestone weights sum to 1.0 (0.25 + 0.65 + 0.10 = 1.00)

#### Step 4: Create Resources
```http
POST /v0/projects/550e8400-e29b-41d4-a716-446655440000/resources

{
  "resources": [
    {
      "name": "John Smith",
      "code": "JS-001",
      "type": "labor",
      "cost_per_hour": 120.00,
      "max_units": 1.0,
      "email": "john.smith@company.com"
    },
    {
      "name": "Sarah Johnson",
      "code": "SJ-002",
      "type": "labor",
      "cost_per_hour": 150.00,
      "max_units": 1.0,
      "email": "sarah.johnson@company.com"
    },
    {
      "name": "Cloud Hosting",
      "code": "AWS-001",
      "type": "material",
      "cost_per_unit": 500.00,
      "unit": "month"
    }
  ]
}
```

#### Step 5: Record Expenses
```http
POST /v0/projects/550e8400-e29b-41d4-a716-446655440000/expenses

{
  "expenses": [
    {
      "description": "Design phase labor - John Smith",
      "amount": 12000,
      "expense_date": "2026-02-28",
      "category": "Labor",
      "milestone_id": "<design-approved-milestone-id>",
      "invoice_number": "INV-2026-001"
    },
    {
      "description": "Frontend development - Sarah Johnson",
      "amount": 30000,
      "expense_date": "2026-04-30",
      "category": "Labor",
      "milestone_id": "<development-complete-milestone-id>",
      "invoice_number": "INV-2026-002"
    },
    {
      "description": "AWS hosting Q1",
      "amount": 1500,
      "expense_date": "2026-03-31",
      "category": "Equipment",
      "milestone_id": null,
      "invoice_number": "AWS-2026-Q1"
    }
  ]
}
```

#### Step 6: Calculate EVM (2026-04-30)
```http
GET /v0/projects/550e8400-e29b-41d4-a716-446655440000/evm?date=2026-04-30
```

**Response:**
```json
{
  "data": {
    "project_id": "550e8400-e29b-41d4-a716-446655440000",
    "project_name": "Website Redesign",
    "date": "2026-04-30",
    "bac": 150000,
    "pv": 105000,
    "ac": 43500,
    "ev_physical": 48000,
    "ev_milestone": 37500,
    "ev_delta": 10500,
    "cv_physical": 4500,
    "sv_physical": -57000,
    "cv_milestone": -6000,
    "sv_milestone": -67500,
    "cpi_physical": 1.10,
    "spi_physical": 0.457,
    "cpi_milestone": 0.862,
    "spi_milestone": 0.357,
    "eac_cpi_physical": 136364,
    "eac_cpispi_physical": 158000,
    "eac_plan_physical": 145500,
    "eac_cpi_milestone": 173913,
    "eac_cpispi_milestone": 198000,
    "eac_plan_milestone": 156000,
    "etc_cpi_physical": 92864,
    "vac_cpi_physical": 13636,
    "percent_complete_physical": 32.0,
    "percent_complete_milestone": 25.0
  },
  "message": "EVM indicators calculated successfully"
}
```

**Analysis:**
- Project 32% complete (physical) but only 25% by milestones (delta = 7%)
- Under budget (CPI = 1.10) but severely behind schedule (SPI = 0.457)
- Forecast: Finish between 136K-158K (best to worst case)
- Action: Investigate schedule delays, consider adding resources

### Example 2: EVM Timeseries for S-Curve

```http
GET /v0/projects/550e8400-e29b-41d4-a716-446655440000/evm/timeseries?from_date=2026-02-01&to_date=2026-06-30
```

**Response:**
```json
{
  "data": {
    "project_id": "550e8400-e29b-41d4-a716-446655440000",
    "project_name": "Website Redesign",
    "snapshots": [
      {"date": "2026-02-28", "pv": 35000, "ac": 12000, "ev_physical": 15000, "ev_milestone": 37500},
      {"date": "2026-03-31", "pv": 70000, "ac": 28500, "ev_physical": 32000, "ev_milestone": 37500},
      {"date": "2026-04-30", "pv": 105000, "ac": 43500, "ev_physical": 48000, "ev_milestone": 37500},
      {"date": "2026-05-31", "pv": 140000, "ac": 65000, "ev_physical": 72000, "ev_milestone": 135000},
      {"date": "2026-06-30", "pv": 150000, "ac": 80000, "ev_physical": 85000, "ev_milestone": 150000}
    ],
    "echarts_format": {
      "xAxis": {"type": "category", "data": ["2026-02", "2026-03", "2026-04", "2026-05", "2026-06"]},
      "yAxis": {"type": "value", "name": "Cost (EUR)"},
      "series": [
        {"name": "PV", "type": "line", "data": [35000, 70000, 105000, 140000, 150000], "lineStyle": {"color": "#5470C6"}},
        {"name": "AC", "type": "line", "data": [12000, 28500, 43500, 65000, 80000], "lineStyle": {"color": "#EE6666"}},
        {"name": "EV (Physical)", "type": "line", "data": [15000, 32000, 48000, 72000, 85000], "lineStyle": {"color": "#91CC75"}}
      ]
    }
  }
}
```

### Edge Case 1: Expense Before First Milestone

**Scenario**: Expense recorded with `expense_date` before first milestone's `target_date`.

**Example:**
- First milestone: "Kick-off", target_date = 2026-02-15
- Expense: "Pre-project setup", expense_date = 2026-02-01, amount = 5000

**Behavior**:
- **Option A (Strict)**: Return 400 Bad Request with error "Expense date before first milestone"
- **Option B (Lenient)**: Allocate expense to first milestone (accepted approach for POC)

**Implementation**: Use lenient approach. Query milestones ordered by `target_date ASC`, assign expense to first milestone if `expense_date < first_milestone.target_date`.

**Rationale**: Project setup costs (e.g., kickoff meeting, tooling setup) occur before formal milestones. Rejecting these expenses forces artificial milestone creation ("Project Start" at day 1).

### Edge Case 2: Expense After Last Milestone

**Scenario**: Expense recorded after last milestone's `target_date`.

**Example:**
- Last milestone: "Go Live", target_date = 2026-06-30
- Expense: "Post-launch bug fix", expense_date = 2026-07-15, amount = 2000

**Behavior**:
- Return 422 Unprocessable Entity with error "Expense date outside project date range"
- **Constraint**: `expense_date` must be ≤ `project.planned_finish_date` (**CON-002**)

**Workaround**: Extend project finish date to accommodate post-launch expenses, OR create "Warranty" milestone at project end date.

### Edge Case 3: Task with Circular Dependencies

**Scenario**: Task A depends on Task B, Task B depends on Task C, Task C depends on Task A (circular).

**Validation**:
```python
def validate_no_circular_dependencies(task_id, predecessors):
    visited = set()
    stack = [task_id]
    
    while stack:
        current = stack.pop()
        if current in visited:
            raise ValidationError("Circular dependency detected")
        visited.add(current)
        
        # Add all predecessors of current task to stack
        for pred in get_predecessors(current):
            stack.append(pred.predecessor_task_id)
```

**Response**: 400 Bad Request with error "Circular task dependency detected: Task A → Task B → Task C → Task A"

**Import Behavior**: If MS Project XML contains circular dependencies (shouldn't happen, but MS Project allows with warnings), import process rejects file with validation error.

### Edge Case 4: RAE Greater Than BAC

**Scenario**: PM updates RAE to 180,000 when BAC = 150,000 (suggests massive scope creep).

**Validation**:
- **Warning** (not error): Allow RAE > BAC but log warning
- Response includes `"warning": "RAE exceeds BAC by 30000 (20%). Consider revising project budget."`

**Rationale**: RAE > BAC is legitimate when:
1. Scope creep discovered mid-project
2. PM estimates additional work needed
3. BAC not yet formally updated (pending change request approval)

**Consequence**: Physical progress calculation may exceed 100%:
```
physical_progress = AC / (AC + RAE)
If AC = 100K, RAE = 180K, then progress = 100/(100+180) = 35.7%
```
Formula remains valid.

### Edge Case 5: Multiple Milestones on Same Date

**Scenario**: Two milestones with identical `target_date` = 2026-03-31.

**Behavior**:
- **Allowed**: Non-overlapping constraint (**CON-004**) checks for date **ranges**, not single dates
- Expenses on 2026-03-31 allocated to first milestone (ordered by `created_at` or `id`)

**Recommendation**: Avoid same-date milestones by offsetting by 1 day (e.g., 2026-03-30 and 2026-03-31) for unambiguous expense allocation.

### Edge Case 6: Zero Duration Milestone Tasks

**Scenario**: Task with `type=milestone` and `duration=0`.

**Validation**: Enforced at schema level. Milestones MUST have `duration=0` (**CON-003**).

**MS Project Compatibility**: MS Project represents milestones as tasks with duration=0. Import preserves this.

### Edge Case 7: Summary Task Budget Mismatch

**Scenario**: Summary task budget = 50K, but child tasks sum to 60K.

**Validation**:
- **On Creation**: Return 400 with error "Summary task budget (50000) does not match sum of child budgets (60000)"
- **On Update**: Recalculate summary task budget automatically from children (ignore user-provided summary budget)

**Implementation**: Use computed property for summary tasks:
```python
@property
def budget(self):
    if self.is_summary:
        return sum(child.budget for child in self.children if not child.is_summary)
    return self._budget
```

### Edge Case 8: Concurrent RAE Updates

**Scenario**: Two PMs update RAE simultaneously (race condition).

**Mitigation**:
- Use database-level locking (SELECT FOR UPDATE) during RAE update
- OR use optimistic locking with `version` field
- Return 409 Conflict if concurrent update detected

**POC Scope**: No locking (acceptable risk with 2-3 concurrent users)

### Edge Case 9: Negative Cost Variance

**Scenario**: CV = EV - AC = -10,000 (over budget).

**Interpretation**: Negative CV is valid (project over budget). Display as "-10,000 EUR (10% over budget)" in UI.

**Alert**: Trigger warning if `CV < -0.1 × BAC` (10% over budget threshold).

### Edge Case 10: Division by Zero in CPI/SPI

**Scenario**: CPI = EV / AC when AC = 0 (project not started).

**Handling**:
```python
def calculate_cpi(ev, ac):
    if ac == 0:
        return None  # Return null in JSON
    return ev / ac
```

**JSON Response**: `{"cpi_physical": null, "cpi_milestone": null}`

**UI Display**: Show "N/A" or "—" instead of numeric value.

## 10. Validation Criteria

Defines criteria and tests for verifying compliance with this specification.

### Schema Conformance

- **VAL-001**: All endpoints SHALL return responses conforming to JSON schemas defined in section 4
  - **Test**: Use JSON Schema validator (e.g., `jsonschema` Python library) to validate all responses
  - **Pass Criteria**: 100% of responses pass schema validation
  - **Tools**: Automated via integration tests with `pytest-json-schema`

- **VAL-002**: All endpoints SHALL accept requests conforming to input schemas in section 4
  - **Test**: Submit valid and invalid payloads, verify 400/422 for invalid schemas
  - **Pass Criteria**: Invalid schemas rejected with descriptive error messages

### EVM Calculation Accuracy

- **VAL-003**: EVM calculations SHALL produce results within 0.01% margin of reference calculations
  - **Test**: Use reference dataset with pre-calculated EVM indicators (Excel or manual calculation)
  - **Pass Criteria**: `|calculated - reference| / reference < 0.0001` for all indicators (PV, AC, EV, CPI, SPI, EAC, ETC, VAC)
  - **Reference Dataset**: 10 projects with varying complexity (5-50 tasks, 2-10 milestones, 10-100 expenses)

- **VAL-004**: BAC calculation SHALL sum only leaf task budgets (exclude summary tasks)
  - **Test**: Create project with summary tasks having non-zero budget, verify BAC excludes them
  - **Pass Criteria**: `BAC = SUM(budget WHERE is_summary=false)`

- **VAL-005**: Physical progress EV calculation SHALL use formula `EV = BAC × AC / (AC + RAE)`
  - **Test**: Set BAC=100K, AC=40K, RAE=60K, verify EV = 40K (40%)
  - **Pass Criteria**: Exact match (no rounding errors beyond floating-point precision)

- **VAL-006**: Milestone-based EV calculation SHALL sum achieved milestone weights
  - **Test**: Create project with 3 milestones (weights 0.2, 0.5, 0.3), mark first two as achieved
  - **Pass Criteria**: `EV_milestone = (0.2 + 0.5) × BAC = 0.7 × BAC`

- **VAL-007**: Three EAC methods SHALL produce distinct results matching formulas in section 4.12.7
  - **Test**: Verify `EAC_CPI = BAC / CPI`, `EAC_CPISPI = AC + (BAC-EV)/(CPI×SPI)`, `EAC_PLAN = AC + (BAC-EV)`
  - **Pass Criteria**: All three formulas produce correct results

### Multi-Tenant Isolation

- **VAL-008**: Multi-tenant isolation SHALL prevent cross-company data access
  - **Test**: Authenticate as Company A user, attempt to access Company B project via API
  - **Pass Criteria**: Return 404 Not Found (not 403 to avoid data leakage)
  - **Security Test**: Attempt direct database query bypassing API (should fail at ORM level)

- **VAL-009**: All entities SHALL inherit `company_id` from JWT claim, not request payload
  - **Test**: Submit project creation with `company_id=B` in payload while JWT has `company_id=A`
  - **Pass Criteria**: Created project has `company_id=A` (JWT overrides payload)

- **VAL-010**: List endpoints SHALL implicitly filter by JWT `company_id`
  - **Test**: Authenticate as Company A, call `GET /projects`, verify all results have `company_id=A`
  - **Pass Criteria**: No results from other companies returned

### MS Project Compatibility

- **VAL-011**: Imported MS Project data SHALL preserve UID, ID, GUID fields for round-trip compatibility
  - **Test**: Import MS Project XML, export to XML, verify UIDs/IDs unchanged
  - **Pass Criteria**: `ms_project_uid`, `ms_project_id`, `ms_project_guid` preserved exactly
  - **Note**: Full round-trip testing requires poc-import and poc-export services

- **VAL-012**: Task hierarchy SHALL support arbitrary nesting depth (1-10 levels)
  - **Test**: Create project with 10-level task hierarchy (project → phase → stage → task → subtask → ...)
  - **Pass Criteria**: All levels stored correctly, summary tasks aggregate child data

- **VAL-013**: Predecessor relationships SHALL support all four types (FS, SS, FF, SF) with lag
  - **Test**: Create tasks with each predecessor type and positive/negative lag
  - **Pass Criteria**: Predecessor data stored and retrieved correctly

### Data Integrity Constraints

- **VAL-014**: Milestone budget weights SHALL sum to 1.0 per project
  - **Test**: Attempt to create milestones with weights summing to 0.95 or 1.05
  - **Pass Criteria**: Return 400 Bad Request with error "milestone weights must sum to 1.0"

- **VAL-015**: Milestones SHALL NOT have overlapping target dates
  - **Test**: Create milestones with target_date = 2026-03-15 and 2026-03-10 (overlap)
  - **Pass Criteria**: Return 400 with error "milestones must not overlap"

- **VAL-016**: Task dates SHALL fall within project date range
  - **Test**: Create task with `planned_start_date` before `project.planned_start_date`
  - **Pass Criteria**: Return 422 with error "task dates outside project dates"

- **VAL-017**: Expense dates SHALL fall within project date range
  - **Test**: Record expense with `expense_date` after `project.planned_finish_date`
  - **Pass Criteria**: Return 422 with error "expense date outside project dates"

- **VAL-018**: Summary tasks SHALL have `is_summary=true` and computed budget from children
  - **Test**: Create summary task with manual budget, verify it's overridden by child sum
  - **Pass Criteria**: Summary task budget auto-calculated, user-provided value ignored

### Security & Authorization

- **VAL-019**: JWT authentication SHALL be required for all endpoints except health/metrics
  - **Test**: Call protected endpoints without Authorization header
  - **Pass Criteria**: Return 401 Unauthorized

- **VAL-020**: JWT validation SHALL verify signature, expiration, and required claims
  - **Test**: Submit expired JWT, invalid signature, missing `company_id` claim
  - **Pass Criteria**: Return 401 with descriptive error for each failure mode

- **VAL-021**: Rate limiting SHALL enforce 10 requests per minute per endpoint
  - **Test**: Send 15 requests in 10 seconds to same endpoint
  - **Pass Criteria**: Requests 1-10 succeed (200), requests 11-15 return 429 with `X-RateLimit-Reset` header

- **VAL-022**: Input validation SHALL prevent SQL injection attacks
  - **Test**: Submit malicious input `' OR '1'='1` in search query
  - **Pass Criteria**: Query returns empty results (not all projects), no error

- **VAL-023**: Input validation SHALL prevent XSS attacks
  - **Test**: Submit `<script>alert('xss')</script>` in project name
  - **Pass Criteria**: Stored with escaped entities `&lt;script&gt;...` or sanitized entirely

### Performance & Scalability

- **VAL-024**: Project list endpoint SHALL respond within 200ms at 95th percentile
  - **Test**: Load 100 projects per company, query with pagination
  - **Pass Criteria**: Response time < 200ms for 95% of requests (measure with Locust)

- **VAL-025**: EVM calculation SHALL complete within 500ms for projects with 500 tasks
  - **Test**: Create project with 500 tasks, 50 expenses, query `GET /projects/{id}/evm`
  - **Pass Criteria**: Response time < 500ms (95th percentile)

- **VAL-026**: Database queries SHALL use indexes efficiently (no full table scans)
  - **Test**: Run EXPLAIN ANALYZE on critical queries (project list, EVM calculation)
  - **Pass Criteria**: All queries use indexes, no sequential scans on large tables

- **VAL-027**: API SHALL handle 100 concurrent requests without errors
  - **Test**: Use Locust to simulate 100 concurrent users querying different projects
  - **Pass Criteria**: All requests succeed (200), no 500 errors, no database deadlocks

### Compliance & Auditability

- **VAL-028**: All create/update operations SHALL record `created_by` / `updated_by` from JWT
  - **Test**: Create project, verify `created_by` = JWT `user_id`
  - **Pass Criteria**: User tracking fields populated automatically

- **VAL-029**: All entities SHALL have `created_at` and `updated_at` timestamps
  - **Test**: Create and update entity, verify timestamps
  - **Pass Criteria**: `created_at` set on creation, `updated_at` updated on modification

- **VAL-030**: RAE history SHALL be append-only (no updates or deletes)
  - **Test**: Attempt to update or delete RAE history entry
  - **Pass Criteria**: Operation rejected (405 Method Not Allowed or 403 Forbidden)

### API Documentation & OpenAPI Compliance

- **VAL-031**: OpenAPI specification SHALL be auto-generated from code (future)
  - **Test**: Generate OpenAPI YAML from Marshmallow schemas, verify completeness
  - **Pass Criteria**: All endpoints documented with request/response schemas
  - **Note**: Manual OpenAPI spec acceptable for POC

- **VAL-032**: API SHALL follow RESTful conventions (resource-oriented URLs, standard HTTP verbs)
  - **Test**: Review all endpoint paths and verbs
  - **Pass Criteria**: No non-RESTful patterns (e.g., `/getProject?id=123` instead of `GET /projects/123`)

### Error Handling

- **VAL-033**: All errors SHALL return consistent JSON format with `message`, `errors`, `correlation_id`
  - **Test**: Trigger validation error, 404, 500, verify response format
  - **Pass Criteria**: All error responses match standard format

- **VAL-034**: Validation errors SHALL include field-specific error messages
  - **Test**: Submit invalid payload with multiple field errors
  - **Pass Criteria**: Response includes `{"errors": {"field1": ["error1"], "field2": ["error2"]}}`

- **VAL-035**: 500 errors SHALL NOT leak sensitive information (stack traces, database errors)
  - **Test**: Trigger unhandled exception (e.g., database connection failure)
  - **Pass Criteria**: Response contains generic message, no stack trace (logged server-side only)

### Regression Testing

- **VAL-036**: All acceptance criteria (AC-xxx) SHALL have corresponding automated tests
  - **Test**: Map each AC-xxx to test case, verify coverage
  - **Pass Criteria**: 100% of acceptance criteria covered by tests

- **VAL-037**: Test suite SHALL achieve minimum 80% code coverage
  - **Test**: Run `pytest --cov=app --cov-report=term`
  - **Pass Criteria**: Line coverage ≥ 80%, branch coverage ≥ 75%

- **VAL-038**: Integration tests SHALL use clean database per test (isolation)
  - **Test**: Run integration tests with database state inspection
  - **Pass Criteria**: No test data leakage between tests (each test starts with empty DB)

### Validation Process

**Phase 1: Unit Testing (Developer)**
- Run `make test-unit` after each code change
- Verify VAL-001 to VAL-007 (calculation accuracy)
- Fix failing tests before committing

**Phase 2: Integration Testing (CI Pipeline)**
- Run `make test-integration` on every push
- Verify VAL-008 to VAL-030 (data integrity, security, performance)
- Block merge if tests fail

**Phase 3: Manual Testing (QA)**
- Test VAL-011 (MS Project round-trip) with poc-import/export
- Test VAL-024 to VAL-027 (performance) with Locust
- Exploratory testing for edge cases

**Phase 4: Acceptance Testing (Product Owner)**
- Verify all acceptance criteria (AC-xxx) met
- Review EVM calculation outputs with reference data
- Sign off on specification compliance

**Validation Sign-Off:**

| Criterion | Status | Verified By | Date |
|-----------|--------|----------------|------|
| VAL-001 to VAL-007 | ☐ Pending | Developer | |
| VAL-008 to VAL-018 | ☐ Pending | QA Team | |
| VAL-019 to VAL-023 | ☐ Pending | Security Team | |
| VAL-024 to VAL-027 | ☐ Pending | Performance Team | |
| VAL-028 to VAL-038 | ☐ Pending | QA Team | |

**Note**: This table should be filled during implementation and testing phases.

## 11. Related Specifications / Further Reading

- [Health Endpoints Specification](./schema-api-health-endpoints.md)
- [Metrics Endpoint Specification](./schema-api-metrics-endpoint.md)
- [POC Import Service Specification](../poc-import/) (to be created)
- [POC Export Service Specification](../poc-export/) (to be created)
- [MS Project XML Schema Reference](https://docs.microsoft.com/en-us/previous-versions/office/developer/office-2010/bb968652(v=office.14))
- [Earned Value Management Guide (PMI)](https://www.pmi.org/)
