# Copyright (c) 2026 Waterfall
#
# This source code is dual-licensed under:
# - GNU Affero General Public License v3.0 (AGPLv3) for open source use
# - Commercial License for proprietary use
#
# See LICENSE and LICENSE.md files in the root directory for full license text.
# For commercial licensing inquiries, contact: contact@waterfall-project.pro

"""Rate limiting helpers.

Flask-Limiter's `key_func` is used across multiple resources; centralizing it
avoids copy/paste drift and keeps behavior consistent.
"""

from __future__ import annotations

from flask import request

from app.utils.jwt_decorators import get_current_user_id


def rate_limit_user_key() -> str:
    """Rate limiting key based on authenticated user.

    Falls back to remote address when user context is not available.
    """
    user_id = get_current_user_id()
    if user_id:
        return str(user_id)
    return request.remote_addr or "anonymous"
