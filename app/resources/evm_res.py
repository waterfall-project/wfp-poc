# Copyright (c) 2026 Waterfall
#
# This source code is dual-licensed under:
# - GNU Affero General Public License v3.0 (AGPLv3) for open source use
# - Commercial License for proprietary use
#
# See LICENSE and LICENSE.md files in the root directory for full license text.
# For commercial licensing inquiries, contact: contact@waterfall-project.pro

"""Flask-RESTful resources for EVM endpoints.

Implements project EVM indicators, time-series, and forecast endpoints.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, cast

from flask import request
from flask_restful import Resource
from marshmallow import ValidationError

from app import limiter
from app.models.db import db
from app.models.project import Project
from app.schemas.evm_schema import (
    EVMForecastsQuerySchema,
    EVMForecastsResponseSchema,
    EVMIndicatorsQuerySchema,
    EVMIndicatorsResponseSchema,
    EVMTimeSeriesQuerySchema,
    EVMTimeSeriesResponseSchema,
)
from app.services.evm_service import EVMService
from app.services.guardian_service import Operation
from app.utils.api_version import validate_api_version_or_error_response
from app.utils.correlation import error_response
from app.utils.jwt_decorators import (
    access_required,
    get_current_company_id,
    require_jwt_auth,
)
from app.utils.rate_limit import rate_limit_user_key

ResponseTuple = tuple[dict[str, Any], int] | tuple[dict[str, Any], int, dict[str, str]]
DictStrAny = dict[str, Any]

# Error Types
BAD_REQUEST_ERROR = "Bad Request"
NOT_FOUND_ERROR = "Not Found"
UNPROCESSABLE_ENTITY_ERROR = "Unprocessable Entity"

# Error Messages
PROJECT_NOT_FOUND_MSG = "Project not found"
INVALID_COMPANY_ID_CLAIM_MSG = "Invalid token: company_id claim is not a valid UUID."
VALIDATION_FAILED_MSG = "Validation failed"


def _normalize_datetime(value: datetime | None) -> datetime | None:
    """Normalize datetime to naive UTC for calculations."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


def _get_company_uuid_or_error() -> tuple[uuid.UUID | None, ResponseTuple | None]:
    """Get company UUID from JWT context or return error response."""
    company_id = get_current_company_id()
    try:
        return uuid.UUID(str(company_id)), None
    except (TypeError, ValueError):
        return None, error_response(
            INVALID_COMPANY_ID_CLAIM_MSG, 401, error="Unauthorized"
        )


def _get_project_or_error(
    project_id: str, company_id: uuid.UUID
) -> tuple[Project | None, ResponseTuple | None]:
    """Get project scoped to company or return error response."""
    try:
        project_uuid = uuid.UUID(project_id)
    except ValueError:
        return None, error_response("Invalid project_id", 400, error=BAD_REQUEST_ERROR)

    project = Project.query.filter_by(id=project_uuid, company_id=company_id).first()
    if not project:
        return None, error_response(PROJECT_NOT_FOUND_MSG, 404, error=NOT_FOUND_ERROR)
    return project, None


class ProjectEVMResource(Resource):
    """Resource for EVM indicators endpoint."""

    def __init__(self) -> None:
        """Initialize resource with schema dependencies."""
        self.query_schema = EVMIndicatorsQuerySchema()
        self.response_schema = EVMIndicatorsResponseSchema()
        self.evm_service = EVMService(db.session)

    @require_jwt_auth
    @access_required(Operation.READ, "evm")
    @limiter.limit("20 per minute", key_func=rate_limit_user_key)
    def get(self, project_id: str, version: str | None = None) -> ResponseTuple:
        """Get project EVM indicators."""
        version_error = validate_api_version_or_error_response(version)
        if version_error:
            return version_error

        company_id, company_err = _get_company_uuid_or_error()
        if company_err:
            return company_err
        assert company_id is not None

        project, project_err = _get_project_or_error(project_id, company_id)
        if project_err:
            return project_err
        assert project is not None

        try:
            query_params = cast("DictStrAny", self.query_schema.load(request.args))
        except ValidationError as exc:
            return error_response(
                VALIDATION_FAILED_MSG,
                400,
                error=BAD_REQUEST_ERROR,
                errors=exc.messages,
            )

        as_of_date = _normalize_datetime(query_params.get("as_of_date"))
        if as_of_date is None:
            as_of_date = _normalize_datetime(datetime.now(UTC))
        assert as_of_date is not None

        ev_method = query_params.get("ev_method", "both")
        indicators = self.evm_service.calculate_indicators(
            project, as_of_date, ev_method
        )

        if indicators.get("bac") is None:
            return error_response(
                "Cannot calculate EVM indicators without BAC",
                422,
                error=UNPROCESSABLE_ENTITY_ERROR,
            )

        response = self.response_schema.dump({"data": indicators})
        return response, 200


class ProjectEVMTimeSeriesResource(Resource):
    """Resource for EVM time-series endpoint."""

    def __init__(self) -> None:
        """Initialize resource with schema dependencies."""
        self.query_schema = EVMTimeSeriesQuerySchema()
        self.response_schema = EVMTimeSeriesResponseSchema()
        self.evm_service = EVMService(db.session)

    @require_jwt_auth
    @access_required(Operation.READ, "evm")
    @limiter.limit("20 per minute", key_func=rate_limit_user_key)
    def get(self, project_id: str, version: str | None = None) -> ResponseTuple:
        """Get project EVM time series."""
        version_error = validate_api_version_or_error_response(version)
        if version_error:
            return version_error

        company_id, company_err = _get_company_uuid_or_error()
        if company_err:
            return company_err
        assert company_id is not None

        project, project_err = _get_project_or_error(project_id, company_id)
        if project_err:
            return project_err
        assert project is not None

        try:
            query_params = cast("DictStrAny", self.query_schema.load(request.args))
        except ValidationError as exc:
            return error_response(
                VALIDATION_FAILED_MSG,
                400,
                error=BAD_REQUEST_ERROR,
                errors=exc.messages,
            )

        start_date = _normalize_datetime(query_params.get("start_date"))
        end_date = _normalize_datetime(query_params.get("end_date"))

        if start_date is None:
            start_date = _normalize_datetime(project.start_date)
        if end_date is None:
            end_date = _normalize_datetime(datetime.now(UTC))

        if start_date is None or end_date is None:
            return error_response(
                "Invalid date range",
                400,
                error=BAD_REQUEST_ERROR,
            )

        if start_date > end_date:
            return error_response(
                "Invalid date range",
                400,
                error=BAD_REQUEST_ERROR,
            )

        granularity = query_params.get("granularity", "month")
        ev_method = query_params.get("ev_method", "physical")
        cumulative = query_params.get("cumulative", True)

        try:
            series = self.evm_service.get_time_series(
                project,
                start_date,
                end_date,
                granularity,
                ev_method,
                cumulative,
            )
        except ValueError as exc:
            return error_response(str(exc), 400, error=BAD_REQUEST_ERROR)

        response = self.response_schema.dump({"data": series})
        return response, 200


class ProjectEVMForecastsResource(Resource):
    """Resource for EVM forecasts endpoint."""

    def __init__(self) -> None:
        """Initialize resource with schema dependencies."""
        self.query_schema = EVMForecastsQuerySchema()
        self.response_schema = EVMForecastsResponseSchema()
        self.evm_service = EVMService(db.session)

    @require_jwt_auth
    @access_required(Operation.READ, "evm")
    @limiter.limit("20 per minute", key_func=rate_limit_user_key)
    def get(self, project_id: str, version: str | None = None) -> ResponseTuple:
        """Get project EVM forecasts."""
        version_error = validate_api_version_or_error_response(version)
        if version_error:
            return version_error

        company_id, company_err = _get_company_uuid_or_error()
        if company_err:
            return company_err
        assert company_id is not None

        project, project_err = _get_project_or_error(project_id, company_id)
        if project_err:
            return project_err
        assert project is not None

        try:
            query_params = cast("DictStrAny", self.query_schema.load(request.args))
        except ValidationError as exc:
            return error_response(
                VALIDATION_FAILED_MSG,
                400,
                error=BAD_REQUEST_ERROR,
                errors=exc.messages,
            )

        as_of_date = _normalize_datetime(query_params.get("as_of_date"))
        if as_of_date is None:
            as_of_date = _normalize_datetime(datetime.now(UTC))
        assert as_of_date is not None

        ev_method = query_params.get("ev_method", "physical")
        forecasts = self.evm_service.get_forecasts(project, as_of_date, ev_method)

        if forecasts.get("bac") is None:
            return error_response(
                "Cannot calculate forecasts without BAC",
                422,
                error=UNPROCESSABLE_ENTITY_ERROR,
            )

        response = self.response_schema.dump({"data": forecasts})
        return response, 200
