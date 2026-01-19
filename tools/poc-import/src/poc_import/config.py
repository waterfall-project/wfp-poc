# Copyright (c) 2026 Waterfall Project
# SPDX-License-Identifier: Commercial

"""Configuration management for poc-import."""

from __future__ import annotations

import os
import time
from pathlib import Path

import jwt
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field


def _load_env_file() -> None:
    """Load poc-import environment file if present."""
    repo_root = Path(__file__).resolve().parents[4]
    env_value = os.getenv("WFP_ENV_FILE")
    if env_value:
        env_path = Path(env_value)
        if not env_path.is_absolute():
            cwd_path = (Path.cwd() / env_path).resolve()
            if cwd_path.exists():
                load_dotenv(cwd_path)
                return
            repo_path = (repo_root / env_path).resolve()
            if repo_path.exists():
                load_dotenv(repo_path)
                return
        if env_path.exists():
            load_dotenv(env_path)
        return

    default_path = repo_root / "tools" / "poc-import" / ".env"
    if default_path.exists():
        load_dotenv(default_path)


_load_env_file()


class Config(BaseModel):
    """Application configuration."""

    model_config = ConfigDict(frozen=True)

    api_url: str = Field(
        default_factory=lambda: os.getenv("WFP_API_URL", "http://localhost:5000"),
        description="wfp-poc API base URL",
    )
    jwt_token: str | None = Field(
        default_factory=lambda: os.getenv("WFP_JWT_TOKEN"),
        description="JWT authentication token",
    )
    user_id: str | None = Field(
        default_factory=lambda: os.getenv("WFP_USER_ID"),
        description="User UUID for local token generation",
    )
    company_id: str | None = Field(
        default_factory=lambda: os.getenv("WFP_COMPANY_ID"),
        description="Company UUID for local token generation",
    )
    jwt_secret_key: str | None = Field(
        default_factory=lambda: os.getenv("JWT_SECRET_KEY"),
        description="JWT secret key for local token generation",
    )
    jwt_algorithm: str = Field(
        default_factory=lambda: os.getenv("JWT_ALGORITHM", "HS256"),
        description="JWT signing algorithm",
    )
    jwt_expires_in: int = Field(
        default_factory=lambda: int(os.getenv("JWT_ACCESS_TOKEN_EXPIRES", "3600")),
        description="JWT expiration in seconds",
    )
    jwt_email: str = Field(
        default_factory=lambda: os.getenv("WFP_JWT_EMAIL", "user@example.com"),
        description="Email claim for locally generated JWTs",
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

    def build_jwt_token(self) -> str | None:
        """Generate a JWT token from local config values.

        Returns:
            JWT token string if required inputs are available, otherwise None.
        """
        if not self.jwt_secret_key or not self.user_id or not self.company_id:
            return None

        payload = {
            "user_id": self.user_id,
            "company_id": self.company_id,
            "email": self.jwt_email,
            "exp": int(time.time()) + self.jwt_expires_in,
        }
        token = jwt.encode(payload, self.jwt_secret_key, algorithm=self.jwt_algorithm)
        return token if isinstance(token, str) else token.decode("utf-8")
