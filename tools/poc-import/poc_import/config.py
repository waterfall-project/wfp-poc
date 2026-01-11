# Copyright (c) 2026 Waterfall Project
# SPDX-License-Identifier: Commercial

"""Configuration management for poc-import."""

import os
from typing import Optional

from pydantic import BaseModel, Field


class Config(BaseModel):
    """Application configuration."""

    api_url: str = Field(
        default_factory=lambda: os.getenv("WFP_API_URL", "http://localhost:5000"),
        description="wfp-poc API base URL",
    )
    jwt_token: Optional[str] = Field(
        default_factory=lambda: os.getenv("WFP_JWT_TOKEN"),
        description="JWT authentication token",
    )
    api_timeout: int = Field(default=30, description="API request timeout in seconds")
    retry_attempts: int = Field(default=3, description="Number of retry attempts")
    batch_size_tasks: int = Field(
        default=100, description="Batch size for task bulk import"
    )
    batch_size_expenses: int = Field(
        default=200, description="Batch size for expense bulk import"
    )
    verbose: bool = Field(default=False, description="Enable verbose logging")

    class Config:
        """Pydantic config."""

        frozen = True
