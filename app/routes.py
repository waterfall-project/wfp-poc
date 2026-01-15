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

from app.resources.health import HealthResource, ReadyResource, VersionResource
from app.resources.milestone_res import MilestoneListResource, MilestoneResource
from app.resources.milestone_task_res import (
    MilestoneTasksResource,
    MilestoneTasksSyncResource,
)
from app.resources.project_res import ProjectListResource, ProjectResource
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
    api.add_resource(ProjectListResource, "/v0/projects")
    api.add_resource(ProjectResource, "/v0/projects/<string:project_id>")

    # Tasks
    api.add_resource(TaskListResource, "/v0/projects/<string:project_id>/tasks")
    api.add_resource(TaskResource, "/v0/projects/<string:project_id>/tasks/<string:id>")
    api.add_resource(TaskBulkResource, "/v0/projects/<string:project_id>/tasks/bulk")
    api.add_resource(TaskSyncResource, "/v0/projects/<string:project_id>/tasks/sync")

    # Milestones
    api.add_resource(
        MilestoneListResource, "/v0/projects/<string:project_id>/milestones"
    )
    api.add_resource(
        MilestoneResource, "/v0/projects/<string:project_id>/milestones/<string:id>"
    )

    # Milestone-Task Links
    api.add_resource(
        MilestoneTasksResource, "/v0/milestones/<string:milestone_id>/tasks"
    )
    api.add_resource(
        MilestoneTasksSyncResource, "/v0/milestones/<string:milestone_id>/tasks/sync"
    )
