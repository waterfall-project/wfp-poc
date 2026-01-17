---
title: OpenAPI Modular Specification Completeness Audit (Global)
version: 1.0
date_created: 2026-01-17
last_updated: 2026-01-17
owner: API Platform / Project Management EVM
tags: [process, openapi, validation, documentation]
---

# Introduction

This document records a global audit of the modular OpenAPI specification to ensure it is not under-documented and remains coherent with the narrative Markdown specification.

## 1. Purpose & Scope

- **Purpose**: Provide a repeatable, explicit checklist-based audit of documentation completeness for the OpenAPI contract.
- **Scope**:
  - In scope: Modular OpenAPI sources under `openapi/wfp-poc-api-modular.yaml`, `openapi/paths/`, and `openapi/components/`.
  - Out of scope: `openapi/wfp-poc-api-bundle.yaml` (generated artifact produced by Redocly).
  - Coherence checks include: defaults consistency, response schemas, request schemas, standard errors, and authentication representation.
- **Audience**: API maintainers and engineers updating contract and implementation.

## 2. Definitions

- **OpenAPI (OAS)**: OpenAPI Specification, YAML contract defining HTTP endpoints.
- **Modular OpenAPI**: OpenAPI split into multiple YAML fragments (paths/components), referenced from an entrypoint.
- **Bundle**: A single-file OpenAPI output generated from modular sources (e.g., Redocly).
- **Under-documented**: A contract gap where an operation lacks schemas, parameters, responses, security definition, or clear descriptions.
- **RAE**: Reste À Engager.

## 3. Requirements, Constraints & Guidelines

### Functional Requirements (REQ-AUD-xxx)

- **REQ-AUD-001**: The audit SHALL evaluate every operation in `openapi/paths/*.yaml`.
- **REQ-AUD-002**: For every operation, the audit SHALL verify presence of `summary`, `description`, `operationId`, and `tags`.
- **REQ-AUD-003**: For operations with request bodies (POST/PUT/PATCH), the audit SHALL verify a JSON `schema` exists under `requestBody.content.application/json`.
- **REQ-AUD-004**: For 2xx responses with a body (e.g., 200/201), the audit SHALL verify a JSON `schema` exists under `responses.<code>.content.application/json`.
- **REQ-AUD-005**: For 204 responses, the audit SHALL verify `description` exists and no JSON body schema is required.
- **REQ-AUD-006**: The audit SHALL verify common error responses reference shared components where possible (400/401/403/404/409/422/429/500), and that error shapes include correlation IDs.
- **REQ-AUD-007**: The audit SHALL verify list endpoints document pagination parameters and defaults, and sorting parameters and defaults where applicable.

### Security Requirements (SEC-AUD-xxx)

**Authentication:**
- **SEC-AUD-001**: Protected endpoints SHALL be representable with either:
  - `Authorization: Bearer <JWT>` header (`bearerAuth`), OR
  - `access_token=<JWT>` cookie (`cookieAuth`).

**Authorization:**
- **SEC-AUD-002**: Endpoints intended to be public SHALL explicitly set `security: []`.

### Constraints (CON-AUD-xxx)

- **CON-AUD-001**: The modular OpenAPI contract is the source of truth; any inconsistencies in other artifacts SHOULD be resolved to match it.
- **CON-AUD-002**: The bundled OpenAPI file is generated and SHALL NOT be manually edited as part of this audit.

### Guidelines (GUD-AUD-xxx)

- **GUD-AUD-001**: Prefer `$ref` to shared parameters/responses to keep defaults consistent.
- **GUD-AUD-002**: Prefer including at least one example for key POST endpoints where it materially improves consumer understanding.

### Patterns (PAT-AUD-xxx)

- **PAT-AUD-001**: Standardize error responses via `openapi/components/responses.yaml` and the shared error schema.

## 4. Interfaces & Data Contracts

### OpenAPI Entry Point

- **Document**: `openapi/wfp-poc-api-modular.yaml`
- **Path fragments**: `openapi/paths/*.yaml`
- **Shared components**: `openapi/components/*.yaml` and `openapi/components/schemas/*.yaml`

## 5. Acceptance Criteria

- **AC-AUD-001**: Given any operation in `openapi/paths/*.yaml`, when inspected, then it has `summary`, `description`, `operationId`, and `tags`.
- **AC-AUD-002**: Given any POST/PUT/PATCH operation, when inspected, then the request body contains an explicit JSON schema.
- **AC-AUD-003**: Given any 200/201 response that returns JSON, when inspected, then a response JSON schema is present.
- **AC-AUD-004**: Given any protected operation, when inspected, then it is compatible with `bearerAuth` or `cookieAuth` (unless intentionally overridden).

## 6. Test Automation Strategy

- **Unit-level contract checks** (recommended): Add a CI step that lints and validates the OpenAPI entrypoint and resolves `$ref`s.
- **Static checks** (recommended): Add automated checks for:
  - 2xx schemas present for non-204 responses
  - required metadata (`summary`, `description`, `operationId`, `tags`)
  - consistent pagination/sort defaults via shared parameter refs

## 7. Rationale & Context

This audit reduces consumer confusion and prevents drift between narrative docs and the contract. The modular OpenAPI is treated as source of truth because it is the most precise and directly drives generated documentation.

## 8. Dependencies & External Integrations

### External Systems
- **EXT-001**: Redocly (or equivalent) - bundles modular OpenAPI into an HTML site/artifact.

### Infrastructure Dependencies
- **INF-001**: CI pipeline - SHOULD run OpenAPI validation to prevent regressions.

## 9. Examples & Edge Cases

- **204 responses**: `DELETE` operations commonly return 204 with no body; this is considered complete if the response has a description.
- **Public endpoints**: Health endpoints remain public and should explicitly set `security: []`.

## 10. Validation Criteria

### Audit Coverage (Reviewed)

The following modular path fragments were reviewed for documentation completeness:

- `openapi/paths/assignments.yaml`
- `openapi/paths/evm.yaml`
- `openapi/paths/expenses.yaml`
- `openapi/paths/health.yaml`
- `openapi/paths/metrics.yaml`
- `openapi/paths/milestones.yaml`
- `openapi/paths/progress.yaml`
- `openapi/paths/projects.yaml`
- `openapi/paths/rae.yaml`
- `openapi/paths/resources.yaml`
- `openapi/paths/statistics.yaml`
- `openapi/paths/tasks.yaml`

### Findings

- **FND-001 (Fixed)**: Sorting default inconsistency for task listing
  - Observed: `sort_order` default differed from shared convention.
  - Resolution: Updated `openapi/paths/tasks.yaml` list tasks `sort_order` default to `desc`.

- **FND-002 (Fixed)**: Narrative spec deletion semantics inconsistent with OpenAPI
  - Observed: The Markdown narrative described project deletion as cascade-delete, while OpenAPI specifies deletion is blocked with `409 Conflict` when related entities exist.
  - Resolution: Updated the Markdown narrative section “Delete Rules” and business rule `BR-PRJ-002` to match OpenAPI.

### Outcome

- **STATUS**: PASS (no remaining under-documentation gaps identified in the modular OpenAPI files during this audit).

## 11. Related Specifications / Further Reading

- `spec/wfp-poc/schema-api-project-management-evm.md` (narrative API specification)
- `openapi/wfp-poc-api-modular.yaml` (contract source of truth)
- `openapi/components/responses.yaml` (standard error responses)
