# poc-import Specification

## Current Specification

**[spec-tool-poc-import-cli.md](spec-tool-poc-import-cli.md)** - Interactive CLI Tool (V1.0)
- **Status**: Complete (2185 lines)
- **Type**: CLI-only interactive REPL tool
- **Technology**: Python 3.11+ with click-shell
- **Features**:
  - MS Project XML import (tasks, resources, dependencies, assignments)
  - Excel import (expenses, RAE/remaining-to-engage)
  - Interactive commands: xml, service, excel groups
  - Validation engine (circular dependencies, dates, references, version conflicts)
  - Rollback on failure
  - UUID-based reconciliation cycle (import→export→re-import)

## Planning Document

**[TODO-spec-cli.md](TODO-spec-cli.md)** - Requirements Capture & Writing Plan
- Business context (3 user roles: migration, debug, dev)
- 28 Q&A from requirements discovery session
- 14-step specification writing plan
- Excel column definitions from ERP exports
- Validation rules summary

## Archived Specifications

**[schema-tool-poc-import-service.OLD.md](schema-tool-poc-import-service.OLD.md)** - Previous Flask Service Design
- **Status**: Archived (replaced by CLI-only approach)
- **Reason**: Too complex for initial use case; CLI more appropriate for migration/debug workflows

## Quick Reference

### Specification Sections
1. Introduction
2. Purpose & Scope
3. Definitions (25 terms)
4. Rationale & Context
5. Requirements (96 total: REQ-001 to REQ-060, SEC-001 to SEC-011, PERF-001 to PERF-007, CON-001 to CON-018)
6. CLI Commands (32 commands: xml/service/excel groups)
7. Excel Data Schemas (Expenses: 14 columns, RAE: 4 columns)
8. MS Project XML Schemas (Project/Task/Resource/Assignment/Dependency)
9. Validation Rules (VAL-001 to VAL-009)
10. Error Handling (exit codes, rollback strategy)
11. Acceptance Criteria (AC-001 to AC-050)
12. Test Automation Strategy (unit/integration tests, fixtures, CI/CD)
13. Dependencies & External Integrations (wfp-poc API, Python 3.11+)
14. Related Specifications
15. Document History

### Key Design Decisions

**Why CLI-only (no batch mode)?**
- UUID reconciliation requires context from wfp-poc project
- Import decisions cannot be fully automated (version conflicts, validation errors)
- Migration users need visibility and control (task-by-task review)

**Why click-shell REPL?**
- Preserve session state (loaded files, selected project)
- Interactive validation and debugging
- Better UX than repeated CLI invocations

**Why UUID reconciliation cycle?**
- MS Project GUIDs enable import→export→re-import workflow
- Avoid duplicate entity creation
- Support incremental updates

**Why version conflict detection?**
- Prevent concurrent modification (multiple PM exports)
- MS Project `SaveVersion` field tracks export versions
- wfp-poc stores `ms_project_version` for comparison

### Development Roadmap

- **V1 (MVP)**: Basic import, validation, rollback
- **V2**: Excel support, EVM validations
- **V3**: Selective import, performance optimization
- **V4**: Production readiness, audit logging
- **Phase 2**: Service mode (REST API, Guardian/Identity integration, MCP server)

## Usage Example

```bash
$ ./poc-import.py
poc-import> xml load ~/projects/project-alpha.xml
✓ Loaded: Project Alpha (156 tasks, 12 resources, 98 dependencies)

poc-import> xml validate
✓ No validation errors found

poc-import> service list projects
ID                                    Name            Tasks  Status
123e4567-e89b-12d3-a456-426614174000  Project Alpha   142    Active

poc-import> service select 123e4567-e89b-12d3-a456-426614174000
✓ Selected project: Project Alpha

poc-import> xml import project
Importing tasks... ████████████████████████████ 156/156 (100%)
Importing resources... ████████████████████████████ 12/12 (100%)
✓ Import completed successfully

poc-import> exit
```

## Next Steps

1. **Implementation**: Create Python project structure in `tools/poc-import/`
2. **Fixtures**: Create test fixtures in `tests/fixtures/`
3. **Unit Tests**: Implement parser and validator tests
4. **Integration Tests**: Test against real wfp-poc service
5. **Documentation**: Add user guide and examples
