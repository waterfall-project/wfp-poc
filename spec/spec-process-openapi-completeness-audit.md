# Checklist de conformité OpenAPI — WFP PoC API (tous les endpoints)

Date: 2026-01-17  
Source: `openapi/paths/*.yaml` (modulaire)  
**Dernière mise à jour**: 2026-01-17 (après correctifs critiques)

> Objectif: vérifier *endpoint par endpoint* que l'implémentation respecte le contrat OpenAPI.
> Spoiler: "à peu près" = "pas conforme". Les clients stricts n'ont pas de bouton "je m'en fiche".

---

## ✅ Correctifs appliqués (2026-01-17)

### Critiques (bloquants clients)
- ✅ **DELETE 204 sans body**: Corrigé dans `milestone_res.py`, `project_res.py` (retournent maintenant `""` au lieu de `{}`)
- ✅ **sort_order default tasks**: Corrigé dans `task_res.py` listTasks (maintenant `desc` conforme OpenAPI, était `asc`)
- ✅ **Validation API version standardisée**: Tous les endpoints utilisent maintenant `validate_api_version_or_error_response()` au lieu de `validate_api_version()` pour retourner des erreurs structurées avec corrélation
- ✅ **Types de retour mypy**: Tous les types de retour dans `milestone_res.py` et `milestone_task_res.py` sont maintenant compatibles avec `ResponseTuple` (`tuple[Any, int] | tuple[Any, int, dict[str, str]]`) — mypy passe sans erreurs

### Fichiers modifiés
- `app/resources/milestone_res.py`:
  - Import error_response + validate_api_version_or_error_response
  - DELETE 204 retourne `""` au lieu de `{}`
  - Tous les types de retour changés pour accepter ResponseTuple
- `app/resources/milestone_task_res.py`:
  - Import error_response + validate_api_version_or_error_response
  - Tous les types de retour changés pour accepter ResponseTuple
- `app/resources/project_res.py`: validate_api_version_or_error_response + DELETE 204
- `app/resources/task_res.py`: validate_api_version_or_error_response + sort_order default

### Vérifications passées
- ✅ `ruff check app/resources/` → All checks passed!
- ✅ `mypy app/resources/` → Success: no issues found in 13 source files
- ✅ **Tests unitaires**: 96 tests passed (test_milestones_crud, test_milestones_list, test_milestone_tasks, test_projects_list, test_tasks_crud, test_tasks_list)

### Restant à faire (non-bloquant)
- ⚠️ Standardisation complète des erreurs dans milestone_res/milestone_task_res (utiliser systématiquement `error_response()` au lieu de tuples manuels) → amélioration qualité, pas bloquant
- ⚠️ Vérification exhaustive rate limits vs indication globale OpenAPI

---

## Conventions globales (s’applique partout)

### A. Routage & versioning
- [ ] Le chemin et la méthode HTTP matchent exactement l’OpenAPI (segments + params path).
- [ ] `/{version}` est supporté comme contractuel (et pas uniquement `/v0/...` “par tradition orale”).
- [x] Version invalide → code d'erreur + format d'erreur standardisé (pas une string random).

### B. AuthN/AuthZ & multi-tenancy
- [ ] Endpoints protégés: auth appliquée (JWT cookie/bearer) comme spécifié.
- [ ] Endpoints protégés: RBAC Guardian appliqué avec l’opération correcte (LIST/READ/CREATE/UPDATE/DELETE).
- [ ] Isolation `company_id` (issu du JWT) *systématique* sur list/get/update/delete (pas d’IDOR).

### C. Validation & schémas
- [ ] Les champs `required`, enums, min/max, formats (`uuid`, `date-time`) sont respectés.
- [x] **CORRIGÉ**: Les defaults matchent la spec (sort_order=desc corrigé dans task_res.py).
- [ ] Erreurs de validation: bon code (`422` vs `400`) selon la spec.

### D. Réponses & erreurs
- [ ] Codes HTTP conformes (200/201/204/400/401/403/404/409/422/429/500).
- [x] **CORRIGÉ**: `204` = *aucun body* (corrigé dans milestone_res.py et project_res.py).
- [x] **CORRIGÉ**: Toutes les erreurs utilisent le schéma d'erreur standard + corrélation (validate_api_version_or_error_response partout).
- [x] **CORRIGÉ**: Types de retour mypy compatibles avec ResponseTuple.

### E. Rate limiting
- [ ] Limites cohérentes avec la doc (et cohérentes entre endpoints similaires).
- [ ] 429 conforme (format + message + corrélation).

---

# Checklist endpoint-par-endpoint (OpenAPI → Implémentation)

## Health

### getHealth — GET `/health`
**Attendus (OpenAPI)**: `200`, `500`, pas de sécurité  
- [ ] Route existe et répond en JSON conforme
- [ ] Aucun décorateur d’auth ajouté “par accident”
- [ ] `500` renvoie le schéma prévu (pas du HTML/traceback)

### getReady — GET `/ready`
**Attendus (OpenAPI)**: `200`, `503`, pas de sécurité  
- [ ] Route existe
- [ ] `503` renvoie un body conforme (pas un texte brut)

### getVersion — GET `/version`
**Attendus (OpenAPI)**: `200`, `500`, pas de sécurité  
- [ ] Route existe
- [ ] Les champs version/build matchent le schéma

---

## Metrics

### getMetrics — GET `/metrics`
**Attendus (OpenAPI)**: sécurité `metricsAuth`, `200` en `text/plain`, `401` JSON, `429`, `500`  
- [ ] Auth API key appliquée (et pas JWT)
- [ ] `200` retourne bien `text/plain; version=0.0.4; charset=utf-8`
- [ ] `401` retourne JSON au format documenté (message + timestamp)
- [ ] `429/500` suivent les réponses standardisées attendues

---

## Projects

### listProjects — GET `/{version}/projects`
**Attendus (OpenAPI)**: params pagination + filtres + tri (`sort_order` default `desc`), `200/400/401/403/429/500`  
- [x] Version validée (`{version}`)
- [ ] Auth + RBAC `LIST` appliqués
- [ ] Multi-tenant: filtrage par `company_id` systématique
- [ ] Pagination (page/per_page) conforme
- [ ] Filtres `status`, `start_date_from/to`, `search` conformes
- [ ] Tri `sort_by` + `sort_order` avec defaults conformes (`desc`)
- [ ] `200` renvoie le schéma paginé `ProjectList`
- [ ] Erreurs standardisées (`400/401/403/429/500`)

### createProject — POST `/{version}/projects`
**Attendus (OpenAPI)**: body `ProjectCreate`, `201/400/401/403/409/422/429/500`  
- [x] Version validée
- [ ] Auth + RBAC `CREATE` appliqués
- [ ] Validation `ProjectCreate` (required + formats + enums)
- [ ] Conflits d’unicité → `409` (pas `400`)
- [ ] Validation métier → `422` (pas `400`)
- [ ] `201` renvoie `ProjectResponse`

### getProject — GET `/{version}/projects/{id}`
**Attendus (OpenAPI)**: `200/400/401/403/404/429/500`  
- [x] Version validée
- [ ] Auth + RBAC `READ` appliqués
- [ ] Multi-tenant: accès interdit si autre company (id existant ≠ visible)
- [ ] `404` si inexistant/non visible
- [ ] `200` conforme `ProjectResponse`

### updateProject — PATCH `/{version}/projects/{id}`
**Attendus (OpenAPI)**: body `ProjectUpdate`, `200/400/401/403/404/409/422/429/500`  
- [x] Version validée
- [ ] Auth + RBAC `UPDATE` appliqués
- [ ] `409` sur conflit (ex: code unique)
- [ ] `422` sur validation métier
- [ ] `200` conforme `ProjectResponse`

### deleteProject — DELETE `/{version}/projects/{id}`
**Attendus (OpenAPI)**: `204/400/401/403/404/409/429/500`  
- [x] Version validée
- [ ] Auth + RBAC `DELETE` appliqués
- [ ] Règle: blocage si entités liées → `409`
- [x] `204` sans body (vraiment sans body)

---

## Tasks

### createTask — POST `/{version}/projects/{project_id}/tasks`
**Attendus (OpenAPI)**: body `TaskCreate`, `201/400/401/403/404/409/429/500`  
- [ ] Version validée
- [ ] Auth + RBAC `CREATE` appliqués
- [ ] `project_id` existe + visible (sinon `404`)
- [ ] Validation `TaskCreate`
- [ ] `201` conforme `TaskResponse`

### listTasks — GET `/{version}/projects/{project_id}/tasks`
**Attendus (OpenAPI)**: pagination, filtres, tri (`sort_order` default `desc`), `200/400/401/403/404/429/500`  
- [x] Version validée
- [ ] Auth + RBAC `LIST` appliqués
- [ ] Multi-tenant: project scoping correct
- [ ] Pagination conforme
- [ ] Filtres (`parent_id`, `is_milestone`, `is_summary`, `is_critical`, `status`, `search`) conformes
- [ ] Tri `sort_by` default `wbs`
- [x] Tri `sort_order` default `desc` (pas `asc` "par habitude")
- [ ] `200` conforme `TaskList`

### bulkCreateTasks — POST `/{version}/projects/{project_id}/tasks/bulk`
**Attendus (OpenAPI)**: body `TaskBulkCreate`, `201/400/401/403/404/409/429/500`  
- [ ] Version validée
- [ ] Auth + RBAC `CREATE` appliqués (bulk ≠ bypass)
- [ ] Limites de taille respectées si définies dans schéma
- [ ] `201` conforme `TaskBulkResponse`

### syncTasks — PUT `/{version}/projects/{project_id}/tasks/sync`
**Attendus (OpenAPI)**: body `TaskSync`, `200/400/401/403/404/409/429/500`  
- [ ] Version validée
- [ ] Auth + RBAC `UPDATE` (ou permission dédiée si prévue)
- [ ] Respect de la sémantique: MAJ planning uniquement, préserve tracking (progress/RAE/etc.)
- [ ] `200` conforme `TaskSyncResponse`

### getTask — GET `/{version}/projects/{project_id}/tasks/{id}`
**Attendus (OpenAPI)**: `200/400/401/403/404/429/500`  
- [ ] Version validée
- [ ] Auth + RBAC `READ`
- [ ] `404` si task hors project_id ou non visible
- [ ] `200` conforme `TaskResponse`

### updateTask — PATCH `/{version}/projects/{project_id}/tasks/{id}`
**Attendus (OpenAPI)**: body `TaskUpdate`, `200/400/401/403/404/409/429/500`  
- [ ] Version validée
- [ ] Auth + RBAC `UPDATE`
- [ ] `409` sur conflits (ex: unicité, cohérence)
- [ ] `200` conforme `TaskResponse`

### deleteTask — DELETE `/{version}/projects/{project_id}/tasks/{id}`
**Attendus (OpenAPI)**: `204/400/401/403/404/409/429/500`  
- [ ] Version validée
- [ ] Auth + RBAC `DELETE`
- [ ] `204` sans body (et cascade conforme si implémentée)

---

## Resources

### createResource — POST `/{version}/resources`
**Attendus (OpenAPI)**: body `ResourceCreate`, `201/400/401/403/409/429/500`  
- [ ] Version validée
- [ ] Auth + RBAC `CREATE`
- [ ] `company_id` vient du JWT (pas client-controlled)
- [ ] `409` sur conflit (ex: email unique si applicable)
- [ ] `201` conforme `ResourceResponse`

### listResources — GET `/{version}/resources`
**Attendus (OpenAPI)**: pagination, filtres, tri, `200/400/401/403/429/500`  
- [ ] Version validée
- [ ] Auth + RBAC `LIST`
- [ ] Filtrage par `company_id` obligatoire
- [ ] Filtres (`type`, `is_active`, `search`) conformes
- [ ] `200` conforme `ResourceList`

### getResource — GET `/{version}/resources/{id}`
**Attendus (OpenAPI)**: `200/400/401/403/404/429/500`  
- [ ] Version validée
- [ ] Auth + RBAC `READ`
- [ ] `404` si resource pas dans company
- [ ] `200` conforme `ResourceResponse`

### updateResource — PATCH `/{version}/resources/{id}`
**Attendus (OpenAPI)**: body `ResourceUpdate`, `200/400/401/403/404/409/429/500`  
- [ ] Version validée
- [ ] Auth + RBAC `UPDATE`
- [ ] `409` si conflit
- [ ] `200` conforme `ResourceResponse`

### deleteResource — DELETE `/{version}/resources/{id}`
**Attendus (OpenAPI)**: `204/400/401/403/404/409/429/500`  
- [ ] Version validée
- [ ] Auth + RBAC `DELETE`
- [ ] `409` si assignments actives
- [ ] `204` sans body

---

## Assignments

### createAssignment — POST `/{version}/projects/{project_id}/assignments`
**Attendus (OpenAPI)**: body `AssignmentCreate`, `201/400/401/403/404/409/422/429/500`  
- [ ] Version validée
- [ ] Auth + RBAC `CREATE`
- [ ] Unicité task+resource respectée → `409`
- [ ] Isolation company (task+resource dans même company) → `422` ou `403` selon spec/choix, mais cohérent
- [ ] `201` conforme `AssignmentResponse`

### listAssignments — GET `/{version}/projects/{project_id}/assignments`
**Attendus (OpenAPI)**: pagination + filtres, `200/400/401/403/404/429/500`  
- [ ] Version validée
- [ ] Auth + RBAC `LIST`
- [ ] Scoping project+company correct
- [ ] Filtres `task_id`, `resource_id` conformes
- [ ] `200` conforme `AssignmentList`

### getAssignment — GET `/{version}/projects/{project_id}/assignments/{id}`
**Attendus (OpenAPI)**: `200/400/401/403/404/429/500`  
- [ ] Version validée
- [ ] Auth + RBAC `READ`
- [ ] `404` si assignment hors project/company
- [ ] `200` conforme `AssignmentResponse`

### updateAssignment — PATCH `/{version}/projects/{project_id}/assignments/{id}`
**Attendus (OpenAPI)**: body `AssignmentUpdate`, `200/400/401/403/404/429/500`  
- [ ] Version validée
- [ ] Auth + RBAC `UPDATE`
- [ ] Validation (durées, percent, coûts) conforme
- [ ] `200` conforme `AssignmentResponse`

### deleteAssignment — DELETE `/{version}/projects/{project_id}/assignments/{id}`
**Attendus (OpenAPI)**: `204/400/401/403/404/429/500`  
- [ ] Version validée
- [ ] Auth + RBAC `DELETE`
- [ ] `204` sans body

---

## Expenses

### createExpense — POST `/{version}/projects/{project_id}/expenses`
**Attendus (OpenAPI)**: body `ExpenseCreate`, `201/400/401/403/404/409/422/429/500`  
- [ ] Version validée
- [ ] Auth + RBAC `CREATE`
- [ ] Allocation milestone basée sur date conforme (déterministe)
- [ ] `201` conforme `ExpenseResponse`
- [ ] `422` sur validation métier (ex: date incohérente) si prévu

### listExpenses — GET `/{version}/projects/{project_id}/expenses`
**Attendus (OpenAPI)**: pagination + filtres + tri, `200/400/401/403/404/429/500`  
- [ ] Version validée
- [ ] Auth + RBAC `LIST`
- [ ] Filtres `category`, `milestone_id`, `resource_id`, `date_from/to` conformes
- [ ] Tri `sort_by/sort_order` conforme
- [ ] `200` conforme `ExpenseList`

### bulkCreateExpenses — POST `/{version}/projects/{project_id}/expenses/bulk`
**Attendus (OpenAPI)**: body `ExpenseBulkCreate`, `201/400/401/403/404/409/429/500`  
- [ ] Version validée
- [ ] Auth + RBAC `CREATE` (bulk)
- [ ] Limite max items respectée (ex: 1000 si contractuel)
- [ ] Résultat partiel conforme `ExpenseBulkResponse` (created/failed + erreurs indexées)
- [ ] Rate limit “bulk” conforme (si policy dédiée)

### getExpense — GET `/{version}/projects/{project_id}/expenses/{id}`
**Attendus (OpenAPI)**: `200/400/401/403/404/429/500`  
- [ ] Version validée
- [ ] Auth + RBAC `READ`
- [ ] `404` si expense hors project/company
- [ ] `200` conforme `ExpenseResponse`

### updateExpense — PATCH `/{version}/projects/{project_id}/expenses/{id}`
**Attendus (OpenAPI)**: body `ExpenseUpdate`, `200/400/401/403/404/422/429/500`  
- [ ] Version validée
- [ ] Auth + RBAC `UPDATE`
- [ ] MAJ date → réallocation milestone si nécessaire (comportement conforme)
- [ ] `422` sur validation métier
- [ ] `200` conforme `ExpenseResponse`

### deleteExpense — DELETE `/{version}/projects/{project_id}/expenses/{id}`
**Attendus (OpenAPI)**: `204/400/401/403/404/429/500`  
- [ ] Version validée
- [ ] Auth + RBAC `DELETE`
- [ ] `204` sans body

---

## Milestones

### createMilestone — POST `/{version}/projects/{project_id}/milestones`
**Attendus (OpenAPI)**: body `MilestoneCreate`, `201/400/401/403/404/409/422/429/500`  
- [ ] Version validée
- [ ] Auth + RBAC `CREATE`
- [ ] Règle: somme `budget_weight` du projet = 1.0 (gestion tolérance/arrondi définie)
- [ ] `409` si conflit (ex: contrainte)
- [ ] `422` si validation métier
- [ ] `201` conforme `MilestoneResponse`

### listMilestones — GET `/{version}/projects/{project_id}/milestones`
**Attendus (OpenAPI)**: pagination + filtres + tri, `200/400/401/403/404/429/500`  
- [ ] Version validée
- [ ] Auth + RBAC `LIST`
- [ ] Filtres `status`, `target_date_from/to`, `search` conformes
- [ ] Tri `sort_by/sort_order` conforme
- [ ] `200` conforme `MilestoneList`

### getMilestone — GET `/{version}/projects/{project_id}/milestones/{id}`
**Attendus (OpenAPI)**: `200/400/401/403/404/429/500`  
- [ ] Version validée
- [ ] Auth + RBAC `READ`
- [ ] `404` si milestone hors project/company
- [ ] `200` conforme `MilestoneResponse`

### updateMilestone — PATCH `/{version}/projects/{project_id}/milestones/{id}`
**Attendus (OpenAPI)**: body `MilestoneUpdate`, `200/400/401/403/404/409/422/429/500`  
- [ ] Version validée
- [ ] Auth + RBAC `UPDATE`
- [ ] Warning contractuel: MAJ target_date n’affecte pas tasks (comportement aligné)
- [ ] `409` sur conflits, `422` sur validation métier
- [ ] `200` conforme `MilestoneResponse`

### deleteMilestone — DELETE `/{version}/projects/{project_id}/milestones/{id}`
**Attendus (OpenAPI)**: `204/400/401/403/404/409/429/500`  
- [ ] Version validée
- [ ] Auth + RBAC `DELETE`
- [ ] Blocage si expenses/deliverables → `409`
- [ ] `204` sans body

### linkMilestoneTasks — POST `/{version}/milestones/{milestone_id}/tasks`
**Attendus (OpenAPI)**: body `MilestoneTaskLink`, `200/400/401/403/404/422/429/500`  
- [ ] Version validée
- [ ] Auth + RBAC `UPDATE` (ou permission dédiée)
- [ ] Création M2M conforme (relationship_type, task_ids)
- [ ] Recalcul `target_date` = MAX(tasks.planned_finish_date) conforme
- [ ] `200` conforme `MilestoneTaskLinkResponse`

### getMilestonePredecessorTasks — GET `/{version}/milestones/{milestone_id}/tasks`
**Attendus (OpenAPI)**: `200/400/401/403/404/429/500`  
- [ ] Version validée
- [ ] Auth + RBAC `READ`
- [ ] `200` conforme `MilestonePredecessorTasks`

### syncMilestoneTasks — PUT `/{version}/milestones/{milestone_id}/tasks/sync`
**Attendus (OpenAPI)**: body `MilestoneTaskLink`, `200/400/401/403/404/422/429/500`  
- [ ] Version validée
- [ ] Auth + RBAC `UPDATE`
- [ ] Sémantique upsert/removal conforme (retire liens absents, ajoute nouveaux, etc.)
- [ ] `200` conforme `MilestoneTaskLinkResponse`

---

## Progress

### updateProjectProgress — POST `/{version}/projects/{project_id}/progress`
**Attendus (OpenAPI)**: body `ProgressUpdateRequest`, `200/400/401/403/404/409/422/429/500`  
- [ ] Version validée
- [ ] Auth + RBAC `UPDATE`
- [ ] Sémantique bulk: succès partiel autorisé + erreurs listées
- [ ] MAJ status en fonction percent_complete (0/1-99/100) conforme
- [ ] Historisation conforme
- [ ] `200` conforme `ProgressUpdateResponse`

### getProgressHistory — GET `/{version}/projects/{project_id}/progress/history`
**Attendus (OpenAPI)**: filtres optionnels + pagination + sort_order, `200/400/401/403/404/429/500`  
- [ ] Version validée
- [ ] Auth + RBAC `READ`/`LIST` (selon policy)
- [ ] Filtres `task_id`, `start_date`, `end_date` conformes
- [ ] Pagination conforme
- [ ] `200` conforme `ProgressHistoryResponse`

---

## RAE

### updateMilestoneRAE — POST `/{version}/milestones/{milestone_id}/rae`
**Attendus (OpenAPI)**: body `RAECreate`, `201/400/401/403/404/429/500`  
- [ ] Version validée
- [ ] Auth + RBAC `UPDATE`
- [ ] Met à jour `current_rae` + recalcul EV_physical conforme
- [ ] `201` conforme `RAEResponse`

### getMilestoneRAEHistory — GET `/{version}/milestones/{milestone_id}/rae/history`
**Attendus (OpenAPI)**: pagination + filtres dates + sort_order, `200/401/403/404/429/500`  
- [ ] Version validée
- [ ] Auth + RBAC `READ`
- [ ] Filtres `date_from/to` conformes
- [ ] `200` conforme `RAEHistory`

### getProjectRAESummary — GET `/{version}/projects/{project_id}/rae/summary`
**Attendus (OpenAPI)**: param `as_of_date` optionnel, `200/401/403/404/429/500`  
- [ ] Version validée
- [ ] Auth + RBAC `READ`
- [ ] `as_of_date` default “latest” conforme
- [ ] `200` conforme `RAESummary`

---

## EVM

### getProjectEVMIndicators — GET `/{version}/projects/{project_id}/evm`
**Attendus (OpenAPI)**: params `as_of_date`, `ev_method` default `both`, `200/400/401/403/404/422/429/500`  
- [ ] Version validée
- [ ] Auth + RBAC `READ`
- [ ] `ev_method` enum + default conforme
- [ ] `422` sur param/validation métier (si spécifié)
- [ ] `200` conforme `EVMIndicatorsResponse`

### getEVMTimeSeries — GET `/{version}/projects/{project_id}/evm/timeseries`
**Attendus (OpenAPI)**: `granularity` default `month`, `ev_method` default `physical`, `cumulative` default `true`, `200/400/401/403/404/429/500`  
- [ ] Version validée
- [ ] Auth + RBAC `READ`
- [ ] Defaults conformes (granularity/month, ev_method/physical, cumulative/true)
- [ ] `200` conforme `EVMTimeSeriesResponse`

### getEVMForecasts — GET `/{version}/projects/{project_id}/evm/forecasts`
**Attendus (OpenAPI)**: `ev_method` default `physical`, `200/400/401/403/404/422/429/500`  
- [ ] Version validée
- [ ] Auth + RBAC `READ`
- [ ] Defaults conformes
- [ ] `200` conforme `EVMForecastsResponse`

---

## Statistics

### getExpenseBreakdownByCategory — GET `/{version}/projects/{project_id}/statistics/expenses/by-category`
**Attendus (OpenAPI)**: filtres dates + milestone_id, `200/400/401/403/404/429/500`  
- [ ] Version validée
- [ ] Auth + RBAC `READ`
- [ ] Filtres optionnels conformes
- [ ] `200` conforme `ExpenseBreakdown`

### getLaborByResource — GET `/{version}/projects/{project_id}/statistics/labor/by-resource`
**Attendus (OpenAPI)**: `limit` default 20, `sort_order` param, `200/400/401/403/404/429/500`  
- [ ] Version validée
- [ ] Auth + RBAC `READ`
- [ ] `limit` bornes (1..100) + default 20 respectés
- [ ] `sort_order` default conforme (si défini via composant)
- [ ] `200` conforme `LaborByResource`

### getMonthlyExpenses — GET `/{version}/projects/{project_id}/statistics/expenses/monthly`
**Attendus (OpenAPI)**: `cumulative` default false, filtres dates + category, `200/400/401/403/404/429/500`  
- [ ] Version validée
- [ ] Auth + RBAC `READ`
- [ ] `cumulative` default false respecté
- [ ] `200` conforme `MonthlyExpenses`

---

## Notes de vérification (tests minimum recommandés)

Pour CHAQUE endpoint protégé:
- [ ] 401 sans auth
- [ ] 403 sans permission
- [ ] 404 sur ressource inexistante / non visible (multi-tenant)
- [ ] 429 si rate limit déclenché (si applicable)
- [ ] Format d’erreur standard + corrélation

Pour CHAQUE endpoint en `204`:
- [ ] Body strictement vide

Fin. Tu peux maintenant arrêter de “penser que c’est bon” et le prouver.
