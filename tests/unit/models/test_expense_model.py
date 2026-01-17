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
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.models import Expense, Project, Resource, db

DEFAULT_START_DATE = datetime(2026, 1, 1, 9, 0, tzinfo=UTC)
DEFAULT_FINISH_DATE = datetime(2026, 1, 31, 18, 0, tzinfo=UTC)
DEFAULT_EXPENSE_DATE = datetime(2026, 2, 15, 12, 0, tzinfo=UTC)


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
            type="labor",
        )
        db.session.add(resource)
        db.session.commit()
        db.session.refresh(resource)
        return resource

    def test_create_expense_minimal(self, app, project):
        """Test creating an expense with minimal required fields.

        Given: Required fields only (project_id, date, amount)
        When: Creating an Expense instance
        Then: Expense is created with correct defaults
        """
        expense = Expense(
            project_id=project.id,
            date=DEFAULT_EXPENSE_DATE,
            amount=Decimal("1000.00"),
        )
        db.session.add(expense)
        db.session.commit()

        assert expense.id is not None
        assert isinstance(expense.id, uuid.UUID)
        assert expense.project_id == project.id
        assert expense.date == DEFAULT_EXPENSE_DATE
        assert expense.amount == Decimal("1000.00")
        assert expense.category == "procurement"
        assert expense.resource_id is None
        assert expense.description is None
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
            category="labor",
            description="Full Test Expense",
            date=DEFAULT_EXPENSE_DATE,
            amount=Decimal("5250.50"),
            reference_number="5129412025",
            purchase_document="24337010",
            fiscal_year=2026,
            period=2,
            otp_element="G.PRJ.12345/13984",
            accounting_nature="60510000",
            vendor_name="ARELIS",
            origin_group="STOR",
        )
        db.session.add(expense)
        db.session.commit()

        assert expense.id is not None
        assert expense.project_id == project.id
        assert expense.resource_id == resource.id
        assert expense.category == "labor"
        assert expense.description == "Full Test Expense"
        assert expense.amount == Decimal("5250.50")
        assert expense.date == DEFAULT_EXPENSE_DATE
        assert expense.reference_number == "5129412025"
        assert expense.purchase_document == "24337010"
        assert expense.fiscal_year == 2026
        assert expense.period == 2
        assert expense.otp_element == "G.PRJ.12345/13984"
        assert expense.accounting_nature == "60510000"
        assert expense.vendor_name == "ARELIS"
        assert expense.origin_group == "STOR"

    def test_expense_category_values(self, app, project):
        """Test valid category values.

        Given: Valid category values (labor, procurement, subcontracting, overhead)
        When: Creating expenses with each category
        Then: Expenses are created successfully
        """
        categories = ["labor", "procurement", "subcontracting", "overhead"]

        for category in categories:
            expense = Expense(
                project_id=project.id,
                date=DEFAULT_EXPENSE_DATE,
                amount=Decimal("100.00"),
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
            date=DEFAULT_EXPENSE_DATE,
            amount=Decimal("250.00"),
        )
        db.session.add(expense)
        db.session.commit()

        assert expense.resource_id == resource.id
        assert expense.resource == resource

    def test_expense_amount_precision(self, app, project):
        """Test amount field with decimal precision.

        Given: An expense with a decimal amount
        When: Setting amount with decimals
        Then: Precision is maintained (2 decimal places)
        """
        expense = Expense(
            project_id=project.id,
            date=DEFAULT_EXPENSE_DATE,
            amount=Decimal("12345.67"),
        )
        db.session.add(expense)
        db.session.commit()

        assert expense.amount == Decimal("12345.67")

    def test_expense_repr(self, app, project):
        """Test string representation of Expense.

        Given: An expense instance
        When: Converting to string
        Then: Repr shows id and category
        """
        expense = Expense(
            project_id=project.id,
            date=DEFAULT_EXPENSE_DATE,
            amount=Decimal("100.00"),
            category="procurement",
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
            date=DEFAULT_EXPENSE_DATE,
            amount=Decimal("100.00"),
        )
        db.session.add(expense)
        db.session.commit()

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
            date=DEFAULT_EXPENSE_DATE,
            amount=Decimal("100.00"),
        )
        db.session.add(expense)
        db.session.commit()

        expense_id = expense.id

        db.session.delete(project)
        db.session.commit()

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
            date=DEFAULT_EXPENSE_DATE,
            amount=Decimal("100.00"),
        )
        db.session.add(expense)
        db.session.commit()

        expense_id = expense.id

        db.session.delete(resource)
        db.session.commit()

        remaining_expense = db.session.get(Expense, expense_id)
        assert remaining_expense is not None
        assert remaining_expense.resource_id is None
