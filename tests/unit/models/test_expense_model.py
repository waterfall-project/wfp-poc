# Copyright (c) 2025 Waterfall
#
# This source code is dual-licensed under:
# - GNU Affero General Public License v3.0 (AGPLv3) for open source use
# - Commercial License for proprietary use
#
# See LICENSE and LICENSE.md files in the root directory for full license text.
# For commercial licensing inquiries, contact: contact@waterfall-project.pro

"""Unit tests for Expense model.

Tests cover model creation, validation, constraints, relationships,
and business logic for the Expense entity.
"""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from app.models import Expense, Project, Resource, db

DEFAULT_START_DATE = datetime(2026, 1, 1, 9, 0, tzinfo=UTC)
DEFAULT_FINISH_DATE = datetime(2026, 1, 31, 18, 0, tzinfo=UTC)


class TestExpenseModel:
    """Test suite for Expense model."""

    @pytest.fixture
    def project(self, app, company_id):
        """Create a test project."""
        project = Project(
            company_id=uuid.UUID(company_id),
            name="Test Project",
            start_date=DEFAULT_START_DATE,
            finish_date=DEFAULT_FINISH_DATE,
        )
        db.session.add(project)
        db.session.commit()
        db.session.refresh(project)
        return project

    @pytest.fixture
    def resource(self, app, company_id):
        """Create a test resource."""
        resource = Resource(
            company_id=uuid.UUID(company_id),
            name="Test Resource",
            type="material",
        )
        db.session.add(resource)
        db.session.commit()
        db.session.refresh(resource)
        return resource

    def test_create_expense_minimal(self, app, project):
        """Test creating an expense with minimal required fields.

        Given: Required fields only (project_id, description)
        When: Creating an Expense instance
        Then: Expense is created with correct defaults
        """
        expense = Expense(
            project_id=project.id,
            description="Test Expense",
        )
        db.session.add(expense)
        db.session.commit()

        assert expense.id is not None
        assert isinstance(expense.id, uuid.UUID)
        assert expense.project_id == project.id
        assert expense.description == "Test Expense"
        assert expense.category == "other"  # Default value
        assert expense.resource_id is None
        assert expense.planned_cost is None
        assert expense.actual_cost is None
        assert expense.expense_date is None
        assert expense.created_at is not None
        assert expense.updated_at is not None

    def test_create_expense_full(self, app, project, resource):
        """Test creating an expense with all fields populated.

        Given: All fields provided
        When: Creating an Expense instance
        Then: Expense is created with all values correctly set
        """
        expense = Expense(
            project_id=project.id,
            resource_id=resource.id,
            category="material",
            description="Full Test Expense",
            planned_cost=Decimal("5000.00"),
            actual_cost=Decimal("5250.50"),
            expense_date=date(2026, 3, 15),
        )
        db.session.add(expense)
        db.session.commit()

        assert expense.id is not None
        assert expense.project_id == project.id
        assert expense.resource_id == resource.id
        assert expense.category == "material"
        assert expense.description == "Full Test Expense"
        assert expense.planned_cost == pytest.approx(5000.00)
        assert expense.actual_cost == pytest.approx(5250.50)
        assert expense.expense_date == date(2026, 3, 15)

    def test_expense_category_values(self, app, project):
        """Test valid category values.

        Given: Valid category values (material, fixed, other)
        When: Creating expenses with each category
        Then: Expenses are created successfully
        """
        categories = ["material", "fixed", "other"]

        for category in categories:
            expense = Expense(
                project_id=project.id,
                description=f"Expense {category}",
                category=category,
            )
            db.session.add(expense)
            db.session.commit()

            assert expense.category == category

    def test_expense_with_optional_resource(self, app, project, resource):
        """Test expense with optional resource association.

        Given: An expense with resource_id
        When: Creating the expense
        Then: Resource relationship is established
        """
        expense = Expense(
            project_id=project.id,
            resource_id=resource.id,
            description="Resource-linked Expense",
        )
        db.session.add(expense)
        db.session.commit()

        assert expense.resource_id == resource.id
        assert expense.resource == resource

    def test_expense_without_resource(self, app, project):
        """Test expense without resource association.

        Given: An expense without resource_id
        When: Creating the expense
        Then: Expense is created with null resource_id
        """
        expense = Expense(
            project_id=project.id,
            description="Standalone Expense",
        )
        db.session.add(expense)
        db.session.commit()

        assert expense.resource_id is None

    def test_expense_planned_vs_actual_cost(self, app, project):
        """Test planned vs actual cost tracking.

        Given: An expense with planned cost
        When: Setting actual cost
        Then: Both costs are tracked independently
        """
        expense = Expense(
            project_id=project.id,
            description="Cost Tracking Expense",
            planned_cost=Decimal("1000.00"),
        )
        db.session.add(expense)
        db.session.commit()

        assert expense.planned_cost == pytest.approx(1000.00)
        assert expense.actual_cost is None

        # Update actual cost
        expense.actual_cost = 1100.00
        db.session.commit()

        assert expense.actual_cost == pytest.approx(1100.00)
        assert expense.planned_cost == pytest.approx(1000.00)

    def test_expense_cost_precision(self, app, project):
        """Test cost fields with decimal precision.

        Given: An expense with costs
        When: Setting cost values with decimals
        Then: Precision is maintained (2 decimal places)
        """
        expense = Expense(
            project_id=project.id,
            description="Precision Test",
            planned_cost=Decimal("12345.67"),
            actual_cost=Decimal("12399.99"),
        )
        db.session.add(expense)
        db.session.commit()

        assert expense.planned_cost == pytest.approx(12345.67)
        assert expense.actual_cost == pytest.approx(12399.99)

    def test_expense_repr(self, app, project):
        """Test string representation of Expense.

        Given: An expense instance
        When: Converting to string
        Then: Repr shows id, category, and description
        """
        expense = Expense(
            project_id=project.id,
            category="material",
            description="Test Expense",
        )
        db.session.add(expense)
        db.session.commit()

        repr_str = repr(expense)
        assert "Expense" in repr_str
        assert str(expense.id) in repr_str
        assert expense.category in repr_str

    def test_expense_relationships_exist(self, app, project, resource):
        """Test that relationship attributes exist.

        Given: An expense instance with resource
        When: Accessing relationship attributes
        Then: Attributes exist and return correct values
        """
        expense = Expense(
            project_id=project.id,
            resource_id=resource.id,
            description="Test Expense",
        )
        db.session.add(expense)
        db.session.commit()

        # Check relationship attributes exist
        assert hasattr(expense, "project")
        assert hasattr(expense, "resource")
        assert expense.project == project
        assert expense.resource == resource

    def test_expense_cascade_delete_project(self, app, project):
        """Test cascade delete when project is deleted.

        Given: An expense linked to a project
        When: Deleting the project
        Then: Expense is also deleted
        """
        expense = Expense(
            project_id=project.id,
            description="Test Expense",
        )
        db.session.add(expense)
        db.session.commit()

        expense_id = expense.id

        # Delete project
        db.session.delete(project)
        db.session.commit()

        # Verify expense was deleted
        deleted_expense = db.session.get(Expense, expense_id)
        assert deleted_expense is None

    def test_expense_set_null_on_resource_delete(self, app, project, resource):
        """Test SET NULL when resource is deleted.

        Given: An expense linked to a resource
        When: Deleting the resource
        Then: Expense remains but resource_id is set to NULL
        """
        expense = Expense(
            project_id=project.id,
            resource_id=resource.id,
            description="Test Expense",
        )
        db.session.add(expense)
        db.session.commit()

        expense_id = expense.id

        # Delete resource
        db.session.delete(resource)
        db.session.commit()

        # Verify expense still exists but resource_id is NULL
        remaining_expense = db.session.get(Expense, expense_id)
        assert remaining_expense is not None
        assert remaining_expense.resource_id is None
