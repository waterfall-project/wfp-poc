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

### simple_project.xml

A simple MS Project XML fixture with 2 tasks, 1 resource, 1 assignment, and a
single dependency.

### large_project.xml

A synthetic MS Project XML fixture with 1000 tasks for parser scale testing.

### circular_dependency.xml

An MS Project XML fixture with a circular dependency (A → B → C → A).

### invalid_dates.xml

An MS Project XML fixture with a task where Finish < Start.

### missing_references.xml

An MS Project XML fixture with a dependency referencing a non-existent task.

### expenses_valid.xlsx

An expenses Excel fixture with 50 valid rows.

### expenses_grouped.xlsx

An expenses Excel fixture with multiple rows sharing the same reference.

### rae_valid.xlsx

A RAE Excel fixture with two valid milestone entries.

### rae_invalid_sum.xlsx

A RAE Excel fixture where task breakdown sum does not match remaining amount.
