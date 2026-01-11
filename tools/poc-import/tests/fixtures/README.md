# Test Fixtures

This directory contains sample data files for testing purposes.

## Files

### sample_project.xml

A minimal MS Project 2010+ XML file for testing the MSProjectParser.

**Contents:**
- 1 summary task (Project Initiation)
- 2 regular tasks (Requirements Analysis, System Design)
- 1 milestone (Requirements Approved)
- 3 resources (1 work, 1 material, 1 cost)
- 3 assignments
- Task dependencies with lag times

**Use in tests:**
- Validates XML parsing
- Tests task hierarchies and milestones
- Tests resource and assignment handling
- Tests predecessor relationships

This file is purely fictional and contains no sensitive data.
