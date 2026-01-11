# Copyright (c) 2025 Waterfall
#
# This source code is dual-licensed under:
# - GNU Affero General Public License v3.0 (AGPLv3) for open source use
# - Commercial License for proprietary use
#
# See LICENSE and LICENSE.md files in the root directory for full license text.
# For commercial licensing inquiries, contact: contact@waterfall-project.pro
"""SQLAlchemy database instance.

This module re-exports the SQLAlchemy instance (db) from app for use
throughout the models package. This avoids circular imports.
"""

# Import db from the main app module where it's initialized
# This ensures we use the same instance that's registered with the Flask app
from app import db

__all__ = ["db"]
