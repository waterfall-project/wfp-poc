# Copyright (c) 2026 Waterfall Project
# SPDX-License-Identifier: Commercial

"""Test fixtures shared across test modules."""

from pathlib import Path

import pytest


@pytest.fixture
def sample_xml_path():
    """Path to sample MS Project XML file."""
    return str(Path(__file__).parent / "fixtures" / "sample_project.xml")


@pytest.fixture
def sample_msproject_xml():
    """Sample MS Project XML content for testing."""
    return """<?xml version="1.0" encoding="UTF-8"?>
<Project xmlns="http://schemas.microsoft.com/project">
    <Name>Test Project</Name>
    <Title>Test Project Title</Title>
    <SaveVersion>14</SaveVersion>
    <StartDate>2026-01-15T08:00:00</StartDate>
    <FinishDate>2026-12-31T17:00:00</FinishDate>
    <GUID>12345678-1234-1234-1234-123456789012</GUID>
    <Tasks>
        <Task>
            <UID>1</UID>
            <GUID>AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE</GUID>
            <Name>Task 1</Name>
            <WBS>1</WBS>
            <Start>2026-01-15T08:00:00</Start>
            <Finish>2026-02-15T17:00:00</Finish>
            <Duration>PT240H0M0S</Duration>
            <Cost>50000</Cost>
            <PercentComplete>0</PercentComplete>
            <Critical>1</Critical>
            <Milestone>0</Milestone>
            <Summary>0</Summary>
        </Task>
        <Task>
            <UID>2</UID>
            <GUID>BBBBBBBB-CCCC-DDDD-EEEE-FFFFFFFFFFFF</GUID>
            <Name>Milestone 1</Name>
            <WBS>2</WBS>
            <Start>2026-02-15T17:00:00</Start>
            <Finish>2026-02-15T17:00:00</Finish>
            <Duration>PT0H0M0S</Duration>
            <Cost>0</Cost>
            <PercentComplete>0</PercentComplete>
            <Critical>0</Critical>
            <Milestone>1</Milestone>
            <Summary>0</Summary>
            <PredecessorLink>
                <PredecessorUID>1</PredecessorUID>
                <Type>1</Type>
                <LinkLag>0</LinkLag>
            </PredecessorLink>
        </Task>
    </Tasks>
    <Resources>
        <Resource>
            <UID>1</UID>
            <GUID>RESOURCE1-AAAA-BBBB-CCCC-DDDDDDDDDDDD</GUID>
            <Name>Developer</Name>
            <Type>1</Type>
            <StandardRate>750</StandardRate>
            <MaxUnits>1.0</MaxUnits>
        </Resource>
    </Resources>
    <Assignments>
        <Assignment>
            <TaskUID>1</TaskUID>
            <ResourceUID>1</ResourceUID>
            <Work>PT240H0M0S</Work>
            <Units>1.0</Units>
        </Assignment>
    </Assignments>
</Project>"""
