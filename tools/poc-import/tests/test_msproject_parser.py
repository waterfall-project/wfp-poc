# Copyright (c) 2026 Waterfall Project
# SPDX-License-Identifier: Commercial

"""Tests for MS Project XML parser."""

import tempfile
from pathlib import Path

import pytest

from poc_import.models import DependencyType, ResourceType
from poc_import.parsers.msproject import MSProjectParser, MSProjectParserError


class TestMSProjectParser:
    """Test cases for MSProjectParser."""

    def test_parse_sample_xml(self, sample_msproject_xml):
        """Test parsing a valid MS Project XML file."""
        # Write sample XML to temporary file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as tmp:
            tmp.write(sample_msproject_xml)
            tmp_path = tmp.name

        try:
            # Parse the file
            parser = MSProjectParser(tmp_path)
            data = parser.parse()

            # Verify project metadata
            assert data.project.name == "Test Project"
            assert data.project.title == "Test Project Title"
            assert data.project.guid == "12345678-1234-1234-1234-123456789012"

            # Verify tasks
            assert len(data.tasks) == 2

            # Check first task
            task1 = data.tasks[0]
            assert task1.uid == 1
            assert task1.name == "Task 1"
            assert task1.wbs_code == "1"
            assert task1.is_milestone is False
            assert task1.is_summary is False
            assert task1.is_critical is True
            assert task1.duration_hours == pytest.approx(240.0)
            assert task1.budget == pytest.approx(50000.0)
            assert len(task1.predecessors) == 0

            # Check milestone
            task2 = data.tasks[1]
            assert task2.uid == 2
            assert task2.name == "Milestone 1"
            assert task2.is_milestone is True
            assert task2.duration_hours == pytest.approx(0.0)
            assert len(task2.predecessors) == 1
            assert task2.predecessors[0].predecessor_task_uid == 1
            assert task2.predecessors[0].type == DependencyType.FS

            # Verify resources
            assert len(data.resources) == 1
            resource = data.resources[0]
            assert resource.uid == 1
            assert resource.name == "Developer"
            assert resource.type == ResourceType.LABOR
            assert resource.standard_rate == pytest.approx(750.0)

            # Verify assignments
            assert len(data.assignments) == 1
            assignment = data.assignments[0]
            assert assignment.task_uid == 1
            assert assignment.resource_uid == 1
            assert assignment.work_hours == pytest.approx(240.0)

        finally:
            # Cleanup temporary file
            Path(tmp_path).unlink()

    def test_parse_invalid_xml(self):
        """Test parsing invalid XML file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as tmp:
            tmp.write("<invalid xml")
            tmp_path = tmp.name

        try:
            parser = MSProjectParser(tmp_path)
            with pytest.raises(MSProjectParserError, match="Invalid XML format"):
                parser.parse()
        finally:
            Path(tmp_path).unlink()

    def test_parse_missing_dates(self, sample_msproject_xml):
        """Test parsing XML with missing required dates."""
        # Remove StartDate from XML
        invalid_xml = sample_msproject_xml.replace(
            "<StartDate>2026-01-15T08:00:00</StartDate>", ""
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as tmp:
            tmp.write(invalid_xml)
            tmp_path = tmp.name

        try:
            parser = MSProjectParser(tmp_path)
            with pytest.raises(
                MSProjectParserError, match="Project must have StartDate and FinishDate"
            ):
                parser.parse()
        finally:
            Path(tmp_path).unlink()

    def test_parse_duration_formats(self):
        """Test parsing various duration formats."""
        parser = MSProjectParser("")

        # Test valid durations
        assert parser._parse_duration("PT0H0M0S") == pytest.approx(0.0)
        assert parser._parse_duration("PT8H0M0S") == pytest.approx(8.0)
        assert parser._parse_duration("PT4H30M0S") == pytest.approx(4.5)
        assert parser._parse_duration("PT240H0M0S") == pytest.approx(240.0)

        # Test invalid duration
        assert parser._parse_duration("invalid") == pytest.approx(0.0)

    def test_parse_sample_file(self, sample_xml_path):
        """Test parsing sample MS Project XML file."""
        xml_path = Path(sample_xml_path)

        if not xml_path.exists():
            pytest.skip("Sample MS Project file not found")

        parser = MSProjectParser(str(xml_path))
        data = parser.parse()

        # Basic assertions - real file should have content
        assert data.project.name
        assert len(data.tasks) > 0
        assert data.project.start_date
        assert data.project.finish_date

        # Count milestones
        milestones = [t for t in data.tasks if t.is_milestone]
        print(f"\nParsed {len(data.tasks)} tasks, {len(milestones)} milestones")
        print(f"Project: {data.project.name}")
        print(f"Period: {data.project.start_date} to {data.project.finish_date}")
