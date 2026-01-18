# Copyright (c) 2025 Waterfall
#
# This source code is dual-licensed under:
# - GNU Affero General Public License v3.0 (AGPLv3) for open source use
# - Commercial License for proprietary use
#
# See LICENSE and LICENSE.md files in the root directory for full license text.
# For commercial licensing inquiries, contact: contact@waterfall-project.pro

FROM apache/superset:latest

USER root

RUN /app/.venv/bin/python -m ensurepip && \
	/app/.venv/bin/python -m pip install --no-cache-dir psycopg2-binary

USER superset
