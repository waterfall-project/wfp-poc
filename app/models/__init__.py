# Copyright (c) 2025 Waterfall
#
# This source code is dual-licensed under:
# - GNU Affero General Public License v3.0 (AGPLv3) for open source use
# - Commercial License for proprietary use
#
# See LICENSE and LICENSE.md files in the root directory for full license text.
# For commercial licensing inquiries, contact: contact@waterfall-project.pro

"""Database models package.

Provides SQLAlchemy database instance, custom types, mixins, and all models
for the Project Management & EVM system.
"""

from app.models.assignment import Assignment
from app.models.db import db
from app.models.dummy import Dummy
from app.models.evm_snapshot import EVMSnapshot
from app.models.expense import Expense
from app.models.milestone import Milestone
from app.models.milestone_rae import MilestoneRAE
from app.models.milestone_task import MilestoneTask
from app.models.progress_update import ProgressUpdate
from app.models.project import Project
from app.models.resource import Resource
from app.models.task import Task
from app.models.task_predecessor import TaskPredecessor
from app.models.types import GUID, JSONB, TimestampMixin, UUIDMixin

__all__ = [
    "db",
    # Custom types and mixins
    "GUID",
    "JSONB",
    "UUIDMixin",
    "TimestampMixin",
    # Legacy model
    "Dummy",
    # Project Management & EVM models
    "Project",
    "Task",
    "TaskPredecessor",
    "Milestone",
    "MilestoneTask",
    "Resource",
    "Assignment",
    "Expense",
    "ProgressUpdate",
    "MilestoneRAE",
    "EVMSnapshot",
]
