# Copyright (c) 2025 Waterfall
#
# This source code is dual-licensed under:
# - GNU Affero General Public License v3.0 (AGPLv3) for open source use
# - Commercial License for proprietary use
#
# See LICENSE and LICENSE.md files in the root directory for full license text.
# For commercial licensing inquiries, contact: contact@waterfall-project.pro

"""Route registration."""

from flask_restful import Api

from app.resources.assignment_res import AssignmentListResource, AssignmentResource
from app.resources.evm_res import (
    ProjectEVMForecastsResource,
    ProjectEVMResource,
    ProjectEVMTimeSeriesResource,
)
from app.resources.expense_res import (
    ExpenseBulkResource,
    ExpenseListResource,
    ExpenseResource,
)
from app.resources.health import HealthResource, ReadyResource, VersionResource
from app.resources.milestone_res import MilestoneListResource, MilestoneResource
from app.resources.milestone_task_res import (
    MilestoneTasksResource,
    MilestoneTasksSyncResource,
)
from app.resources.progress_res import (
    ProjectProgressHistoryResource,
    ProjectProgressResource,
)
from app.resources.project_res import ProjectListResource, ProjectResource
from app.resources.rae_res import (
    MilestoneRAEHistoryResource,
    MilestoneRAEResource,
    ProjectRAESummaryResource,
)
from app.resources.resource_res import ResourceListResource, ResourceResource
from app.resources.statistics_res import (
    ExpenseByCategoryResource,
    LaborByResourceResource,
    MonthlyExpensesResource,
)
from app.resources.task_res import (
    TaskBulkResource,
    TaskListResource,
    TaskResource,
    TaskSyncResource,
)


def register_routes(app):
    """Register all API routes.

    Registers health endpoints first (no version prefix), then versioned
    API routes. Health endpoints are required for Kubernetes probes and
    monitoring systems.

    Args:
        app: Flask application instance.
    """
    api = Api(app)

    # Health endpoints (no version prefix, no authentication)
    api.add_resource(HealthResource, "/health")
    api.add_resource(ReadyResource, "/ready")
    api.add_resource(VersionResource, "/version")

    # Versioned API endpoints
    # Projects
    api.add_resource(ProjectListResource, "/v0/projects", "/<string:version>/projects")
    api.add_resource(
        ProjectResource,
        "/v0/projects/<string:project_id>",
        "/<string:version>/projects/<string:id>",
    )

    # Tasks
    api.add_resource(
        TaskListResource,
        "/v0/projects/<string:project_id>/tasks",
        "/<string:version>/projects/<string:project_id>/tasks",
    )
    api.add_resource(
        TaskResource,
        "/v0/projects/<string:project_id>/tasks/<string:id>",
        "/<string:version>/projects/<string:project_id>/tasks/<string:id>",
    )
    api.add_resource(
        TaskBulkResource,
        "/v0/projects/<string:project_id>/tasks/bulk",
        "/<string:version>/projects/<string:project_id>/tasks/bulk",
    )
    api.add_resource(
        TaskSyncResource,
        "/v0/projects/<string:project_id>/tasks/sync",
        "/<string:version>/projects/<string:project_id>/tasks/sync",
    )

    # Assignments
    api.add_resource(
        AssignmentListResource,
        "/v0/projects/<string:project_id>/assignments",
        "/<string:version>/projects/<string:project_id>/assignments",
    )
    api.add_resource(
        AssignmentResource,
        "/v0/projects/<string:project_id>/assignments/<string:id>",
        "/<string:version>/projects/<string:project_id>/assignments/<string:id>",
    )

    # Expenses
    api.add_resource(
        ExpenseListResource,
        "/v0/projects/<string:project_id>/expenses",
        "/<string:version>/projects/<string:project_id>/expenses",
    )
    api.add_resource(
        ExpenseBulkResource,
        "/v0/projects/<string:project_id>/expenses/bulk",
        "/<string:version>/projects/<string:project_id>/expenses/bulk",
    )
    api.add_resource(
        ExpenseResource,
        "/v0/projects/<string:project_id>/expenses/<string:id>",
        "/<string:version>/projects/<string:project_id>/expenses/<string:id>",
    )

    # Milestones
    api.add_resource(
        MilestoneListResource,
        "/v0/projects/<string:project_id>/milestones",
        "/<string:version>/projects/<string:project_id>/milestones",
    )
    api.add_resource(
        MilestoneResource,
        "/v0/projects/<string:project_id>/milestones/<string:id>",
        "/<string:version>/projects/<string:project_id>/milestones/<string:id>",
    )

    # Milestone-Task Links
    api.add_resource(
        MilestoneTasksResource,
        "/v0/milestones/<string:milestone_id>/tasks",
        "/<string:version>/milestones/<string:milestone_id>/tasks",
    )
    api.add_resource(
        MilestoneTasksSyncResource,
        "/v0/milestones/<string:milestone_id>/tasks/sync",
        "/<string:version>/milestones/<string:milestone_id>/tasks/sync",
    )

    # Progress Updates
    api.add_resource(
        ProjectProgressResource,
        "/v0/projects/<string:project_id>/progress",
        "/<string:version>/projects/<string:project_id>/progress",
    )
    api.add_resource(
        ProjectProgressHistoryResource,
        "/v0/projects/<string:project_id>/progress/history",
        "/<string:version>/projects/<string:project_id>/progress/history",
    )

    # RAE
    api.add_resource(
        MilestoneRAEResource,
        "/v0/milestones/<string:milestone_id>/rae",
        "/<string:version>/milestones/<string:milestone_id>/rae",
    )
    api.add_resource(
        MilestoneRAEHistoryResource,
        "/v0/milestones/<string:milestone_id>/rae/history",
        "/<string:version>/milestones/<string:milestone_id>/rae/history",
    )
    api.add_resource(
        ProjectRAESummaryResource,
        "/v0/projects/<string:project_id>/rae/summary",
        "/<string:version>/projects/<string:project_id>/rae/summary",
    )

    # EVM
    api.add_resource(
        ProjectEVMResource,
        "/v0/projects/<string:project_id>/evm",
        "/<string:version>/projects/<string:project_id>/evm",
    )
    api.add_resource(
        ProjectEVMTimeSeriesResource,
        "/v0/projects/<string:project_id>/evm/timeseries",
        "/<string:version>/projects/<string:project_id>/evm/timeseries",
    )
    api.add_resource(
        ProjectEVMForecastsResource,
        "/v0/projects/<string:project_id>/evm/forecasts",
        "/<string:version>/projects/<string:project_id>/evm/forecasts",
    )

    # Resources
    api.add_resource(
        ResourceListResource,
        "/v0/resources",
        "/<string:version>/resources",
    )
    api.add_resource(
        ResourceResource,
        "/v0/resources/<string:id>",
        "/<string:version>/resources/<string:id>",
    )

    # Statistics
    api.add_resource(
        ExpenseByCategoryResource,
        "/v0/projects/<string:project_id>/statistics/expenses/by-category",
        "/<string:version>/projects/<string:project_id>/statistics/expenses/by-category",
    )
    api.add_resource(
        LaborByResourceResource,
        "/v0/projects/<string:project_id>/statistics/labor/by-resource",
        "/<string:version>/projects/<string:project_id>/statistics/labor/by-resource",
    )
    api.add_resource(
        MonthlyExpensesResource,
        "/v0/projects/<string:project_id>/statistics/expenses/monthly",
        "/<string:version>/projects/<string:project_id>/statistics/expenses/monthly",
    )
