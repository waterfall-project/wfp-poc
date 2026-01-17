# Copyright (c) 2025 Waterfall
#
# This source code is dual-licensed under:
# - GNU Affero General Public License v3.0 (AGPLv3) for open source use
# - Commercial License for proprietary use
#
# See LICENSE and LICENSE.md files in the root directory for full license text.
# For commercial licensing inquiries, contact: contact@waterfall-project.pro

"""Unit tests for Resource model.

Tests cover model creation, validation, constraints, relationships,
and business logic for the Resource entity.

Note: SonarQube false positives suppressed:
- "No parameter named X": SQLAlchemy models accept kwargs for all mapped columns
- Float equality: SQLAlchemy returns Decimal, comparison with float is well-defined
"""

import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Resource, db


class TestResourceModel:
    """Test suite for Resource model."""

    def test_create_resource_minimal(self, app, company_id):
        """Test creating a resource with minimal required fields.

        Given: Required fields only (company_id, name, type)
        When: Creating a Resource instance
        Then: Resource is created with correct defaults
        """
        with app.app_context():
            resource = Resource(
                company_id=uuid.UUID(company_id),
                name="John Doe",
                type="labor",
            )
            db.session.add(resource)
            db.session.commit()

            assert resource.id is not None
            assert isinstance(resource.id, uuid.UUID)
            assert resource.company_id == uuid.UUID(company_id)
            assert resource.name == "John Doe"
            assert resource.type == "labor"
            assert resource.is_active is True  # Default value
            assert resource.ms_project_uid is None
            assert resource.standard_rate is None
            assert resource.overtime_rate is None
            assert resource.email is None
            assert resource.created_at is not None
            assert resource.updated_at is not None

    def test_create_resource_full_labor(self, app, company_id):
        """Test creating a labor resource with all fields.

        Given: All fields for a labor resource
        When: Creating a Resource instance
        Then: Resource is created with all values correctly set
        """
        with app.app_context():
            resource = Resource(
                company_id=uuid.UUID(company_id),
                name="Jane Smith",
                type="labor",
                ms_project_uid=123,
                standard_rate=75.50,
                overtime_rate=112.75,
                email="jane.smith@example.com",
                is_active=True,
            )
            db.session.add(resource)
            db.session.commit()

            assert resource.name == "Jane Smith"
            assert resource.type == "labor"
            assert resource.ms_project_uid == 123
            assert resource.standard_rate == pytest.approx(75.50)
            assert resource.overtime_rate == pytest.approx(112.75)
            assert resource.email == "jane.smith@example.com"
            assert resource.is_active is True

    def test_create_resource_material(self, app, company_id):
        """Test creating a material resource.

        Given: Material resource fields
        When: Creating a Resource instance with type='material'
        Then: Resource is created successfully
        """
        with app.app_context():
            resource = Resource(
                company_id=uuid.UUID(company_id),
                name="Steel Beams",
                type="material",
                standard_rate=150.00,
            )
            db.session.add(resource)
            db.session.commit()

            assert resource.type == "material"
            assert resource.standard_rate == pytest.approx(150.00)

    def test_create_resource_cost(self, app, company_id):
        """Test creating a cost resource.

        Given: Cost resource fields
        When: Creating a Resource instance with type='cost'
        Then: Resource is created successfully
        """
        with app.app_context():
            resource = Resource(
                company_id=uuid.UUID(company_id),
                name="Equipment Rental",
                type="cost",
                standard_rate=500.00,
            )
            db.session.add(resource)
            db.session.commit()

            assert resource.type == "cost"
            assert resource.standard_rate == pytest.approx(500.00)

    def test_resource_unique_name_per_company(self, app, company_id):
        """Test unique constraint on (company_id, name).

        Given: A resource with a specific name exists for a company
        When: Creating another resource with the same name for the same company
        Then: IntegrityError is raised
        """
        with app.app_context():
            resource1 = Resource(
                company_id=uuid.UUID(company_id),
                name="John Doe",
                type="labor",
            )
            db.session.add(resource1)
            db.session.commit()

            resource2 = Resource(
                company_id=uuid.UUID(company_id),
                name="John Doe",
                type="material",
            )
            db.session.add(resource2)

            with pytest.raises(IntegrityError):
                db.session.commit()

    def test_resource_same_name_different_companies(self, app, generate_uuid):
        """Test same name allowed for different companies.

        Given: Two different companies
        When: Creating resources with the same name for each company
        Then: Both resources are created successfully
        """
        with app.app_context():
            company1_id = uuid.UUID(generate_uuid())
            company2_id = uuid.UUID(generate_uuid())

            resource1 = Resource(
                company_id=company1_id,
                name="John Doe",
                type="labor",
            )
            resource2 = Resource(
                company_id=company2_id,
                name="John Doe",
                type="labor",
            )

            db.session.add_all([resource1, resource2])
            db.session.commit()

            assert resource1.id != resource2.id
            assert resource1.name == resource2.name
            assert resource1.company_id != resource2.company_id

    def test_resource_type_values(self, app, company_id):
        """Test valid type values.

        Given: Valid type values (labor, material, cost)
        When: Creating resources with each type
        Then: Resources are created successfully
        """
        with app.app_context():
            types = ["labor", "material", "cost"]

            for resource_type in types:
                resource = Resource(
                    company_id=uuid.UUID(company_id),
                    name=f"Resource {resource_type}",
                    type=resource_type,
                )
                db.session.add(resource)
                db.session.commit()

                assert resource.type == resource_type
                db.session.rollback()

    def test_resource_soft_delete(self, app, company_id):
        """Test soft delete functionality with is_active flag.

        Given: An active resource
        When: Setting is_active to False
        Then: Resource is marked as inactive but not deleted
        """
        with app.app_context():
            resource = Resource(
                company_id=uuid.UUID(company_id),
                name="To Be Deactivated",
                type="labor",
            )
            db.session.add(resource)
            db.session.commit()

            resource_id = resource.id
            assert resource.is_active is True

            # Soft delete
            resource.is_active = False
            db.session.commit()

            # Resource still exists but is inactive
            inactive_resource = db.session.get(Resource, resource_id)
            assert inactive_resource is not None
            assert inactive_resource.is_active is False

    def test_resource_repr(self, app, company_id):
        """Test string representation of Resource.

        Given: A resource instance
        When: Converting to string
        Then: Repr shows id, name, and type
        """
        with app.app_context():
            resource = Resource(
                company_id=uuid.UUID(company_id),
                name="Test Resource",
                type="labor",
            )
            db.session.add(resource)
            db.session.commit()

            repr_str = repr(resource)
            assert "Resource" in repr_str
            assert str(resource.id) in repr_str
            assert "Test Resource" in repr_str
            assert "labor" in repr_str

    def test_resource_relationships_exist(self, app, company_id):
        """Test that relationship attributes exist.

        Given: A resource instance
        When: Accessing relationship attributes
        Then: Attributes exist and return empty lists
        """
        with app.app_context():
            resource = Resource(
                company_id=uuid.UUID(company_id),
                name="Test Resource",
                type="labor",
            )
            db.session.add(resource)
            db.session.commit()

            # Test relationships exist
            assert hasattr(resource, "assignments")
            assert hasattr(resource, "expenses")

            # All should be empty lists initially
            assert resource.assignments == []
            assert resource.expenses == []

    def test_resource_rates_precision(self, app, company_id):
        """Test numeric precision for rate fields.

        Given: Rates with 2 decimal places
        When: Creating a resource
        Then: Rates are stored with correct precision
        """
        with app.app_context():
            resource = Resource(
                company_id=uuid.UUID(company_id),
                name="Precise Rates",
                type="labor",
                standard_rate=75.99,
                overtime_rate=113.49,
            )
            db.session.add(resource)
            db.session.commit()

            # Retrieve and check precision
            retrieved = db.session.get(Resource, resource.id)
            assert retrieved is not None
            assert retrieved.standard_rate is not None
            assert retrieved.overtime_rate is not None
            assert float(retrieved.standard_rate) == pytest.approx(75.99)
            assert float(retrieved.overtime_rate) == pytest.approx(113.49)
