import json
import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Set, Optional


class MetricsJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, set):
            return list(obj)
        if isinstance(obj, defaultdict):
            return dict(obj)
        if callable(obj):
            return None
        if hasattr(obj, "__dict__"):
            return {
                k: v
                for k, v in obj.__dict__.items()
                if not k.startswith("_") and not callable(v)
            }
        try:
            return super().default(obj)
        except Exception:
            return str(obj)


@dataclass
class BaseMetrics:
    def to_dict(self):
        def convert(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            if isinstance(obj, set):
                return list(obj)
            if isinstance(obj, defaultdict):
                return dict(obj)
            if callable(obj):
                return None
            if hasattr(obj, "to_dict"):
                return obj.to_dict()
            if hasattr(obj, "__dict__"):
                return {
                    k: convert(v)
                    for k, v in obj.__dict__.items()
                    if not k.startswith("_") and not callable(v)
                }
            return obj

        return {
            k: convert(v)
            for k, v in self.__dict__.items()
            if not k.startswith("_") and not callable(v)
        }


@dataclass
class IssueMetrics(BaseMetrics):
    total_created: int = 0
    total_completed: int = 0
    total_in_progress: int = 0
    bugs_created: int = 0
    bugs_completed: int = 0
    stories_created: int = 0
    stories_completed: int = 0
    tasks_created: int = 0
    tasks_completed: int = 0
    epics_created: int = 0
    epics_completed: int = 0
    by_priority: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    by_status: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    by_assignee: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    by_project: Dict[str, Dict] = field(
        default_factory=lambda: defaultdict(
            lambda: {
                "total": 0,
                "bugs": 0,
                "stories": 0,
                "tasks": 0,
                "epics": 0,
                "completed": 0,
                "in_progress": 0,
            }
        )
    )

    def get_stats(self) -> Dict:
        completion_rate = (
            (self.total_completed / self.total_created * 100)
            if self.total_created > 0
            else 0
        )
        bug_rate = (
            (self.bugs_created / self.total_created * 100)
            if self.total_created > 0
            else 0
        )

        return {
            "total_issues": self.total_created,
            "completion_rate": completion_rate,
            "bug_rate": bug_rate,
            "stories_to_bugs_ratio": (
                self.stories_created / self.bugs_created
                if self.bugs_created > 0
                else 0
            ),
            "in_progress_rate": (
                (self.total_in_progress / self.total_created * 100)
                if self.total_created > 0
                else 0
            ),
            "priority_distribution": dict(self.by_priority),
            "status_distribution": dict(self.by_status),
            "assignee_distribution": dict(self.by_assignee),
            "project_metrics": dict(self.by_project),
        }

    def update_from_issue(self, issue: dict):
        self.total_created += 1

        # Get issue type and status
        issue_type = issue.get("fields", {}).get("issuetype", {}).get("name", "").lower()
        status_name = issue.get("fields", {}).get("status", {}).get("name", "Unknown")
        status_category = issue.get("fields", {}).get("status", {}).get("statusCategory", {}).get("key", "")

        # Update status metrics
        self.by_status[status_name] += 1

        # Update completion status based on status category
        if status_category == "done":
            self.total_completed += 1
        elif status_category == "indeterminate":
            self.total_in_progress += 1

        # Update issue type metrics
        if "bug" in issue_type:
            self.bugs_created += 1
            if status_category == "done":
                self.bugs_completed += 1
        elif "story" in issue_type:
            self.stories_created += 1
            if status_category == "done":
                self.stories_completed += 1
        elif "task" in issue_type:
            self.tasks_created += 1
            if status_category == "done":
                self.tasks_completed += 1
        elif "epic" in issue_type:
            self.epics_created += 1
            if status_category == "done":
                self.epics_completed += 1

        # Update priority metrics
        priority = issue.get("fields", {}).get("priority", {})
        if priority:
            priority_name = priority.get("name", "Unknown")
            self.by_priority[priority_name] += 1

        # Update assignee metrics
        assignee = issue.get("fields", {}).get("assignee", {})
        if assignee:
            assignee_name = assignee.get("displayName", "Unassigned")
            self.by_assignee[assignee_name] += 1
        else:
            self.by_assignee["Unassigned"] += 1

        # Update project metrics
        project = issue.get("fields", {}).get("project", {})
        if project:
            project_key = project.get("key")
            if project_key:
                self.by_project[project_key]["total"] += 1
                if "bug" in issue_type:
                    self.by_project[project_key]["bugs"] += 1
                elif "story" in issue_type:
                    self.by_project[project_key]["stories"] += 1
                elif "task" in issue_type:
                    self.by_project[project_key]["tasks"] += 1
                elif "epic" in issue_type:
                    self.by_project[project_key]["epics"] += 1
                
                if status_category == "done":
                    self.by_project[project_key]["completed"] += 1
                elif status_category == "indeterminate":
                    self.by_project[project_key]["in_progress"] += 1


@dataclass
class CycleTimeMetrics(BaseMetrics):
    cycle_times: List[float] = field(default_factory=list)
    time_to_start: List[float] = field(default_factory=list)
    time_in_progress: List[float] = field(default_factory=list)
    time_in_review: List[float] = field(default_factory=list)
    resolution_times: List[float] = field(default_factory=list)
    by_assignee: Dict[str, List[float]] = field(default_factory=lambda: defaultdict(list))
    by_priority: Dict[str, List[float]] = field(
        default_factory=lambda: defaultdict(list)
    )
    by_issue_type: Dict[str, List[float]] = field(
        default_factory=lambda: defaultdict(list)
    )

    def get_stats(self) -> Dict:
        def safe_mean(lst: List[float]) -> float:
            return statistics.mean(lst) if lst else 0

        def safe_median(lst: List[float]) -> float:
            return statistics.median(lst) if lst else 0

        def safe_p95(lst: List[float]) -> float:
            if not lst:
                return 0
            sorted_list = sorted(lst)
            index = int(0.95 * len(sorted_list))
            return sorted_list[min(index, len(sorted_list) - 1)]

        return {
            "avg_cycle_time": safe_mean(self.cycle_times),
            "median_cycle_time": safe_median(self.cycle_times),
            "p95_cycle_time": safe_p95(self.cycle_times),
            "avg_time_to_start": safe_mean(self.time_to_start),
            "avg_time_in_progress": safe_mean(self.time_in_progress),
            "avg_time_in_review": safe_mean(self.time_in_review),
            "avg_resolution_time": safe_mean(self.resolution_times),
            "assignee_cycle_times": {
                assignee: safe_mean(times) for assignee, times in self.by_assignee.items()
            },
            "priority_cycle_times": {
                priority: safe_mean(times)
                for priority, times in self.by_priority.items()
            },
            "issue_type_cycle_times": {
                issue_type: safe_mean(times)
                for issue_type, times in self.by_issue_type.items()
            },
        }

    def update_from_issue(self, issue: dict):
        fields = issue.get("fields", {})
        created = fields.get("created")
        resolved = fields.get("resolutiondate")
        
        if not created:
            return

        try:
            created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
            
            if resolved:
                resolved_dt = datetime.fromisoformat(resolved.replace("Z", "+00:00"))
                cycle_time = (resolved_dt - created_dt).total_seconds() / 3600  # hours
                self.cycle_times.append(cycle_time)
                self.resolution_times.append(cycle_time)

                # Track by assignee
                assignee = fields.get("assignee", {})
                if assignee:
                    assignee_name = assignee.get("displayName", "Unassigned")
                    self.by_assignee[assignee_name].append(cycle_time)

                # Track by priority
                priority = fields.get("priority", {})
                if priority:
                    priority_name = priority.get("name", "Unknown")
                    self.by_priority[priority_name].append(cycle_time)

                # Track by issue type
                issue_type = fields.get("issuetype", {})
                if issue_type:
                    type_name = issue_type.get("name", "Unknown")
                    self.by_issue_type[type_name].append(cycle_time)

        except (ValueError, TypeError) as e:
            # Skip issues with invalid date formats
            pass


@dataclass
class EstimationMetrics(BaseMetrics):
    total_estimated: int = 0
    accurate_estimates: int = 0
    underestimates: int = 0
    overestimates: int = 0
    estimation_variance: List[float] = field(default_factory=list)
    by_assignee: Dict[str, Dict] = field(
        default_factory=lambda: defaultdict(
            lambda: {"total": 0, "accurate": 0, "under": 0, "over": 0, "variance": []}
        )
    )
    by_issue_type: Dict[str, Dict] = field(
        default_factory=lambda: defaultdict(
            lambda: {"total": 0, "accurate": 0, "under": 0, "over": 0, "variance": []}
        )
    )

    def get_stats(self) -> Dict:
        def safe_mean(lst: List[float]) -> float:
            return statistics.mean(lst) if lst else 0

        accuracy_rate = (
            (self.accurate_estimates / self.total_estimated * 100)
            if self.total_estimated > 0
            else 0
        )

        return {
            "total_estimated": self.total_estimated,
            "accuracy_rate": accuracy_rate,
            "underestimate_rate": (
                (self.underestimates / self.total_estimated * 100)
                if self.total_estimated > 0
                else 0
            ),
            "overestimate_rate": (
                (self.overestimates / self.total_estimated * 100)
                if self.total_estimated > 0
                else 0
            ),
            "avg_variance": safe_mean(self.estimation_variance),
            "assignee_accuracy": {
                assignee: {
                    "accuracy_rate": (
                        (stats["accurate"] / stats["total"] * 100)
                        if stats["total"] > 0
                        else 0
                    ),
                    "avg_variance": safe_mean(stats["variance"]),
                }
                for assignee, stats in self.by_assignee.items()
            },
            "issue_type_accuracy": {
                issue_type: {
                    "accuracy_rate": (
                        (stats["accurate"] / stats["total"] * 100)
                        if stats["total"] > 0
                        else 0
                    ),
                    "avg_variance": safe_mean(stats["variance"]),
                }
                for issue_type, stats in self.by_issue_type.items()
            },
        }

    def update_from_issue(self, issue: dict, actual_time: float):
        fields = issue.get("fields", {})
        
        # Try to get story points or time estimate
        story_points = fields.get("customfield_10016")  # Common story points field
        original_estimate = fields.get("timeoriginalestimate")  # Time estimate in seconds
        
        estimate_hours = None
        if story_points:
            # Convert story points to hours (assuming 1 point = 4 hours)
            estimate_hours = story_points * 4
        elif original_estimate:
            # Convert seconds to hours
            estimate_hours = original_estimate / 3600

        if not estimate_hours or actual_time <= 0:
            return

        variance_percent = ((actual_time - estimate_hours) / estimate_hours) * 100

        self.total_estimated += 1
        self.estimation_variance.append(variance_percent)

        # Categorize accuracy (within 25% is considered accurate)
        if abs(variance_percent) <= 25:
            self.accurate_estimates += 1
        elif variance_percent > 25:
            self.underestimates += 1
        else:
            self.overestimates += 1

        # Track by assignee
        assignee = fields.get("assignee", {})
        if assignee:
            assignee_name = assignee.get("displayName", "Unassigned")
            assignee_stats = self.by_assignee[assignee_name]
            assignee_stats["total"] += 1
            assignee_stats["variance"].append(variance_percent)
            if abs(variance_percent) <= 25:
                assignee_stats["accurate"] += 1
            elif variance_percent > 25:
                assignee_stats["under"] += 1
            else:
                assignee_stats["over"] += 1

        # Track by issue type
        issue_type = fields.get("issuetype", {})
        if issue_type:
            type_name = issue_type.get("name", "Unknown")
            type_stats = self.by_issue_type[type_name]
            type_stats["total"] += 1
            type_stats["variance"].append(variance_percent)
            if abs(variance_percent) <= 25:
                type_stats["accurate"] += 1
            elif variance_percent > 25:
                type_stats["under"] += 1
            else:
                type_stats["over"] += 1


@dataclass
class ProjectMetrics(BaseMetrics):
    key: str
    name: str
    total_issues: int = 0
    completed_issues: int = 0
    bugs_count: int = 0
    stories_count: int = 0
    tasks_count: int = 0
    epics_count: int = 0
    avg_cycle_time: float = 0
    assignees_involved: Set[str] = field(default_factory=set)
    estimation_accuracy: float = 0
    lead: Optional[str] = None
    project_type: Optional[str] = None

    def get_stats(self) -> Dict:
        completion_rate = (
            (self.completed_issues / self.total_issues * 100)
            if self.total_issues > 0
            else 0
        )
        return {
            "key": self.key,
            "name": self.name,
            "total_issues": self.total_issues,
            "completed_issues": self.completed_issues,
            "completion_rate": completion_rate,
            "bugs_count": self.bugs_count,
            "stories_count": self.stories_count,
            "tasks_count": self.tasks_count,
            "epics_count": self.epics_count,
            "avg_cycle_time": self.avg_cycle_time,
            "assignees_involved": list(self.assignees_involved),
            "estimation_accuracy": self.estimation_accuracy,
            "lead": self.lead,
            "project_type": self.project_type,
        }

    def update_from_issue(self, issue: dict):
        self.total_issues += 1

        fields = issue.get("fields", {})
        status_category = fields.get("status", {}).get("statusCategory", {}).get("key", "")
        
        if status_category == "done":
            self.completed_issues += 1

        # Update issue type counts
        issue_type = fields.get("issuetype", {}).get("name", "").lower()
        if "bug" in issue_type:
            self.bugs_count += 1
        elif "story" in issue_type:
            self.stories_count += 1
        elif "task" in issue_type:
            self.tasks_count += 1
        elif "epic" in issue_type:
            self.epics_count += 1

        # Track assignee involvement
        assignee = fields.get("assignee", {})
        if assignee:
            assignee_name = assignee.get("displayName")
            if assignee_name:
                self.assignees_involved.add(assignee_name)


@dataclass
class JiraOrgMetrics(BaseMetrics):
    name: str
    issues: IssueMetrics = field(default_factory=IssueMetrics)
    projects: Dict[str, ProjectMetrics] = field(default_factory=dict)
    cycle_time: CycleTimeMetrics = field(default_factory=CycleTimeMetrics)
    estimation: EstimationMetrics = field(default_factory=EstimationMetrics)
    component_counts: Dict[str, int] = field(default_factory=dict)
    version_counts: Dict[str, int] = field(default_factory=dict)

    def get_stats(self) -> Dict:
        return {
            "name": self.name,
            "projects": {
                key: project.get_stats() for key, project in self.projects.items()
            },
            "issues": self.issues.get_stats(),
            "cycle_time": self.cycle_time.get_stats(),
            "estimation": self.estimation.get_stats(),
            "component_distribution": self.component_counts,
            "version_distribution": self.version_counts,
        }

    def aggregate_metrics(self):
        """Aggregate metrics across all projects"""
        if self.projects:
            # Calculate average cycle time across projects
            project_cycle_times = [
                p.avg_cycle_time for p in self.projects.values() if p.avg_cycle_time > 0
            ]
            if project_cycle_times:
                avg_cycle_time = statistics.mean(project_cycle_times)
                for project in self.projects.values():
                    if project.avg_cycle_time == 0:
                        project.avg_cycle_time = avg_cycle_time

            # Calculate estimation accuracy across projects
            project_accuracies = [
                p.estimation_accuracy for p in self.projects.values() if p.estimation_accuracy > 0
            ]
            if project_accuracies:
                avg_accuracy = statistics.mean(project_accuracies)
                for project in self.projects.values():
                    if project.estimation_accuracy == 0:
                        project.estimation_accuracy = avg_accuracy 