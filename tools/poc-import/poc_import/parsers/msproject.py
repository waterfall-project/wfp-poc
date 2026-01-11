# Copyright (c) 2026 Waterfall Project
# SPDX-License-Identifier: Commercial

"""MS Project XML parser."""

import logging
from datetime import datetime
from typing import Optional

from lxml import etree
from pydantic import ValidationError

from poc_import.models import (
    Assignment,
    DependencyType,
    MSProjectData,
    ProjectMetadata,
    Resource,
    ResourceType,
    Task,
    TaskPredecessor,
)

logger = logging.getLogger(__name__)

# MS Project XML namespace
NS = "{http://schemas.microsoft.com/project}"


class MSProjectParserError(Exception):
    """MS Project parser error."""

    pass


class MSProjectParser:
    """Parser for MS Project 2010+ XML files."""

    def __init__(self, xml_path: str) -> None:
        """Initialize parser with XML file path."""
        self.xml_path = xml_path
        self.tree: Optional[etree._ElementTree] = None
        self.root: Optional[etree._Element] = None

    def parse(self) -> MSProjectData:
        """Parse MS Project XML file."""
        try:
            self.tree = etree.parse(self.xml_path)
            self.root = self.tree.getroot()

            project = self._parse_project_metadata()
            tasks = self._parse_tasks()
            resources = self._parse_resources()
            assignments = self._parse_assignments()

            logger.info(
                f"Parsed MS Project: {len(tasks)} tasks, "
                f"{len(resources)} resources, {len(assignments)} assignments"
            )

            return MSProjectData(
                project=project,
                tasks=tasks,
                resources=resources,
                assignments=assignments,
            )

        except etree.XMLSyntaxError as e:
            raise MSProjectParserError(f"Invalid XML format: {e}") from e
        except ValidationError as e:
            raise MSProjectParserError(f"Data validation error: {e}") from e
        except Exception as e:
            raise MSProjectParserError(f"Unexpected parsing error: {e}") from e

    def _parse_project_metadata(self) -> ProjectMetadata:
        """Parse project-level metadata."""
        name = self._get_text("Name", default="Unnamed Project")
        title = self._get_text("Title")
        start_date_str = self._get_text("StartDate")
        finish_date_str = self._get_text("FinishDate")
        guid = self._get_text("GUID")

        start_date = self._parse_datetime(start_date_str) if start_date_str else None
        finish_date = self._parse_datetime(finish_date_str) if finish_date_str else None

        if not start_date or not finish_date:
            raise MSProjectParserError("Project must have StartDate and FinishDate")

        return ProjectMetadata(
            name=name or "Untitled Project",
            title=title,
            start_date=start_date,
            finish_date=finish_date,
            guid=guid,
        )

    def _parse_tasks(self) -> list[Task]:
        """Parse all tasks from Tasks section."""
        tasks: list[Task] = []
        if self.root is None:
            return tasks

        tasks_elem = self.root.find(f"{NS}Tasks")
        if tasks_elem is None:
            logger.warning("No Tasks section found")
            return tasks

        for task_elem in tasks_elem.findall(f"{NS}Task"):
            try:
                task = self._parse_task(task_elem)
                if task:
                    tasks.append(task)
            except Exception as e:
                uid = task_elem.findtext(f"{NS}UID", default="unknown")
                logger.warning(f"Failed to parse task UID={uid}: {e}")

        return tasks

    def _parse_task(self, elem: etree._Element) -> Optional[Task]:
        """Parse single task element."""
        uid_text = elem.findtext(f"{NS}UID")
        if not uid_text or uid_text == "0":
            return None

        uid = int(uid_text)
        name = elem.findtext(f"{NS}Name", default="Unnamed Task")
        guid = elem.findtext(f"{NS}GUID")
        wbs_code = elem.findtext(f"{NS}WBS")

        is_summary = elem.findtext(f"{NS}Summary") == "1"
        is_milestone = elem.findtext(f"{NS}Milestone") == "1"
        is_critical = elem.findtext(f"{NS}Critical") == "1"

        start_text = elem.findtext(f"{NS}Start")
        finish_text = elem.findtext(f"{NS}Finish")
        planned_start = self._parse_datetime(start_text) if start_text else None
        planned_finish = self._parse_datetime(finish_text) if finish_text else None

        duration_text = elem.findtext(f"{NS}Duration")
        duration_hours = self._parse_duration(duration_text) if duration_text else None

        cost_text = elem.findtext(f"{NS}Cost")
        budget = float(cost_text) if cost_text else None

        percent_text = elem.findtext(f"{NS}PercentComplete", default="0")
        percent_complete = float(percent_text)

        predecessors = self._parse_predecessors(elem)

        return Task(
            uid=uid,
            guid=guid,
            name=name,
            wbs_code=wbs_code,
            is_summary=is_summary,
            is_milestone=is_milestone,
            planned_start_date=planned_start,
            planned_finish_date=planned_finish,
            duration_hours=duration_hours,
            budget=budget,
            percent_complete=percent_complete,
            is_critical=is_critical,
            predecessors=predecessors,
        )

    def _parse_predecessors(self, elem: etree._Element) -> list[TaskPredecessor]:
        """Parse predecessor links for a task."""
        predecessors: list[TaskPredecessor] = []

        pred_elem = elem.find(f"{NS}PredecessorLink")
        if pred_elem is not None:
            uid_text = pred_elem.findtext(f"{NS}PredecessorUID")
            if uid_text and uid_text != "0":
                pred_uid = int(uid_text)
                type_text = pred_elem.findtext(f"{NS}Type", default="1")
                type_map = {
                    "0": DependencyType.SS,
                    "1": DependencyType.FS,
                    "2": DependencyType.FF,
                    "3": DependencyType.SF,
                }
                dep_type = type_map.get(type_text, DependencyType.FS)
                lag_text = pred_elem.findtext(f"{NS}LinkLag", default="0")
                lag = int(lag_text)

                predecessors.append(
                    TaskPredecessor(
                        predecessor_task_uid=pred_uid, type=dep_type, lag=lag
                    )
                )

        return predecessors

    def _parse_resources(self) -> list[Resource]:
        """Parse all resources from Resources section."""
        resources: list[Resource] = []
        if self.root is None:
            return resources

        res_elem = self.root.find(f"{NS}Resources")
        if res_elem is None:
            logger.warning("No Resources section found")
            return resources

        for r_elem in res_elem.findall(f"{NS}Resource"):
            try:
                resource = self._parse_resource(r_elem)
                if resource:
                    resources.append(resource)
            except Exception as e:
                uid = r_elem.findtext(f"{NS}UID", default="unknown")
                logger.warning(f"Failed to parse resource UID={uid}: {e}")

        return resources

    def _parse_resource(self, elem: etree._Element) -> Optional[Resource]:
        """Parse single resource element."""
        uid_text = elem.findtext(f"{NS}UID")
        if not uid_text or uid_text == "0":
            return None

        uid = int(uid_text)
        name = elem.findtext(f"{NS}Name", default="Unnamed Resource")
        guid = elem.findtext(f"{NS}GUID")

        type_text = elem.findtext(f"{NS}Type", default="1")
        type_map = {
            "0": ResourceType.MATERIAL,
            "1": ResourceType.LABOR,
            "2": ResourceType.COST,
        }
        resource_type = type_map.get(type_text, ResourceType.LABOR)

        rate_text = elem.findtext(f"{NS}StandardRate")
        standard_rate = float(rate_text) if rate_text else None

        units_text = elem.findtext(f"{NS}MaxUnits", default="1.0")
        max_units = float(units_text)

        return Resource(
            uid=uid,
            guid=guid,
            name=name,
            type=resource_type,
            standard_rate=standard_rate,
            max_units=max_units,
        )

    def _parse_assignments(self) -> list[Assignment]:
        """Parse all assignments from Assignments section."""
        assignments: list[Assignment] = []
        if self.root is None:
            return assignments

        assign_elem = self.root.find(f"{NS}Assignments")
        if assign_elem is None:
            logger.warning("No Assignments section found")
            return assignments

        for a_elem in assign_elem.findall(f"{NS}Assignment"):
            try:
                assignment = self._parse_assignment(a_elem)
                if assignment:
                    assignments.append(assignment)
            except Exception as e:
                logger.warning(f"Failed to parse assignment: {e}")

        return assignments

    def _parse_assignment(self, elem: etree._Element) -> Optional[Assignment]:
        """Parse single assignment element."""
        task_uid_text = elem.findtext(f"{NS}TaskUID")
        resource_uid_text = elem.findtext(f"{NS}ResourceUID")

        if not task_uid_text or not resource_uid_text:
            return None

        task_uid = int(task_uid_text)
        resource_uid = int(resource_uid_text)

        work_text = elem.findtext(f"{NS}Work", default="PT0H0M0S")
        work_hours = self._parse_duration(work_text)

        units_text = elem.findtext(f"{NS}Units", default="1.0")
        units = float(units_text)

        return Assignment(
            task_uid=task_uid,
            resource_uid=resource_uid,
            work_hours=work_hours,
            units=units,
        )

    def _get_text(
        self, element_name: str, default: Optional[str] = None
    ) -> Optional[str]:
        """Get text content of element."""
        if self.root is None:
            return default
        result: Optional[str] = self.root.findtext(
            f"{NS}{element_name}", default=default
        )
        return result

    def _parse_datetime(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse MS Project datetime string."""
        if not date_str:
            return None
        try:
            date_str = date_str.replace("Z", "")
            return datetime.fromisoformat(date_str)
        except ValueError as e:
            logger.warning(f"Failed to parse datetime '{date_str}': {e}")
            return None

    def _parse_duration(self, duration_str: str) -> float:
        """Parse MS Project duration format to hours."""
        if not duration_str or duration_str == "PT0H0M0S":
            return 0.0

        try:
            duration_str = duration_str.replace("PT", "")
            hours = 0.0
            minutes = 0.0

            if "H" in duration_str:
                h_part, rest = duration_str.split("H", 1)
                hours = float(h_part)
                duration_str = rest

            if "M" in duration_str:
                m_part, rest = duration_str.split("M", 1)
                minutes = float(m_part)

            return hours + (minutes / 60.0)

        except Exception as e:
            logger.warning(f"Failed to parse duration '{duration_str}': {e}")
            return 0.0
