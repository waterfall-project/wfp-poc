"""Update milestones table for OpenAPI compliance

Revision ID: 7754e8504794
Revises: daae3789a8f5
Create Date: 2026-01-15 05:53:57.026335

"""
from typing import Sequence

# revision identifiers, used by Alembic.
revision = '7754e8504794'
down_revision = 'daae3789a8f5'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    """Apply milestone schema adjustments for OpenAPI compliance."""
    # No-op migration: the initial schema already matches current models.
    return None


def downgrade() -> None:
    """Revert milestone schema adjustments for OpenAPI compliance."""
    # No-op migration: no schema changes applied in upgrade.
    return None
