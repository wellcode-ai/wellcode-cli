import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Set

from ...linear.models.metrics import BaseMetrics


@dataclass
class JiraIssueMetrics(BaseMetrics):
    total_created: int = 0
    total_completed: int = 0
    total_in_progress: int = 0
    bugs_created: int = 0
    bugs_completed: int = 0
    stories_created: int = 0
    stories_completed: int = 0
    tasks_created: int = 0
    tasks_completed: int = 0
    by_priority: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    by_status: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    by_project: Dict[str, Dict] = field(
        default_factory=lambda: defaultdict(
            lambda: {
                "total": 0,
                "bugs": 0,
                "stories": 0,
                "tasks": 0,
                "completed": 0,
                "in_progress": 0,
            }
        )
    )
    by_assignee: Dict[str, int] = field(default_factory=lambda: defaultdict(int))

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
            "project_metrics": dict(self.by_project),
            "assignee_distribution": dict(self.by_assignee),
        }

    _TYPE_COUNTERS = {
        "bug": ("bugs_created", "bugs_completed"),
        "story": ("stories_created", "stories_completed"),
        "task": ("tasks_created", "tasks_completed"),
    }

    _TYPE_PROJECT_KEY = {"bug": "bugs", "story": "stories", "task": "tasks"}

    def update_from_issue(self, issue_type: str, status_category: str,
                          priority: str, project_key: str,
                          assignee: Optional[str]):
        self.total_created += 1
        self.by_status[status_category] += 1
        is_done = status_category == "done"

        if is_done:
            self.total_completed += 1
        elif status_category == "indeterminate":
            self.total_in_progress += 1

        issue_type_lower = issue_type.lower()
        self._update_type_counters(issue_type_lower, is_done)

        if priority:
            self.by_priority[priority] += 1
        if project_key:
            self._update_project(project_key, issue_type_lower, status_category)
        if assignee:
            self.by_assignee[assignee] += 1

    def _update_type_counters(self, issue_type_lower: str, is_done: bool):
        counters = self._TYPE_COUNTERS.get(issue_type_lower)
        if not counters:
            return
        created_attr, completed_attr = counters
        setattr(self, created_attr, getattr(self, created_attr) + 1)
        if is_done:
            setattr(self, completed_attr, getattr(self, completed_attr) + 1)

    def _update_project(self, project_key: str, issue_type_lower: str,
                        status_category: str):
        proj = self.by_project[project_key]
        proj["total"] += 1
        proj_key = self._TYPE_PROJECT_KEY.get(issue_type_lower)
        if proj_key:
            proj[proj_key] += 1
        if status_category == "done":
            proj["completed"] += 1
        elif status_category == "indeterminate":
            proj["in_progress"] += 1


@dataclass
class JiraCycleTimeMetrics(BaseMetrics):
    cycle_times: List[float] = field(default_factory=list)
    time_to_start: List[float] = field(default_factory=list)
    time_in_progress: List[float] = field(default_factory=list)
    by_project: Dict[str, List[float]] = field(
        default_factory=lambda: defaultdict(list)
    )
    by_priority: Dict[str, List[float]] = field(
        default_factory=lambda: defaultdict(list)
    )
    by_issue_type: Dict[str, List[float]] = field(
        default_factory=lambda: defaultdict(list)
    )

    def get_stats(self) -> Dict:
        def safe_mean(lst: List[float]) -> float:
            return statistics.mean(lst) if lst else 0

        return {
            "avg_cycle_time": safe_mean(self.cycle_times),
            "avg_time_to_start": safe_mean(self.time_to_start),
            "avg_time_in_progress": safe_mean(self.time_in_progress),
            "project_cycle_times": {
                project: safe_mean(times)
                for project, times in self.by_project.items()
            },
            "priority_cycle_times": {
                priority: safe_mean(times)
                for priority, times in self.by_priority.items()
            },
            "issue_type_cycle_times": {
                itype: safe_mean(times)
                for itype, times in self.by_issue_type.items()
            },
            "cycle_time_p95": (
                statistics.quantiles(self.cycle_times, n=20)[-1]
                if self.cycle_times
                else 0
            ),
            "cycle_time_p50": (
                statistics.median(self.cycle_times) if self.cycle_times else 0
            ),
        }

    def update_from_issue(self, created_at: datetime,
                          resolution_date: Optional[datetime],
                          in_progress_date: Optional[datetime],
                          project_key: str, priority: str,
                          issue_type: str):
        if resolution_date:
            cycle_time = (resolution_date - created_at).total_seconds() / 3600
            self.cycle_times.append(cycle_time)

            if project_key:
                self.by_project[project_key].append(cycle_time)
            if priority:
                self.by_priority[priority].append(cycle_time)
            if issue_type:
                self.by_issue_type[issue_type].append(cycle_time)

        if in_progress_date:
            time_to_start = (in_progress_date - created_at).total_seconds() / 3600
            self.time_to_start.append(time_to_start)

            if resolution_date:
                time_in_prog = (
                    (resolution_date - in_progress_date).total_seconds() / 3600
                )
                self.time_in_progress.append(time_in_prog)


@dataclass
class JiraSprintMetrics(BaseMetrics):
    sprint_id: int = 0
    name: str = ""
    state: str = ""
    goal: str = ""
    total_issues: int = 0
    completed_issues: int = 0
    story_points_committed: float = 0
    story_points_completed: float = 0

    @property
    def velocity(self) -> float:
        return self.story_points_completed

    @property
    def completion_rate(self) -> float:
        if self.total_issues == 0:
            return 0
        return (self.completed_issues / self.total_issues) * 100

    @property
    def points_completion_rate(self) -> float:
        if self.story_points_committed == 0:
            return 0
        return (self.story_points_completed / self.story_points_committed) * 100

    def get_stats(self) -> Dict:
        return {
            "name": self.name,
            "state": self.state,
            "goal": self.goal,
            "total_issues": self.total_issues,
            "completed_issues": self.completed_issues,
            "completion_rate": self.completion_rate,
            "story_points_committed": self.story_points_committed,
            "story_points_completed": self.story_points_completed,
            "points_completion_rate": self.points_completion_rate,
            "velocity": self.velocity,
        }


@dataclass
class JiraEstimationMetrics(BaseMetrics):
    total_estimated: int = 0
    accurate_estimates: int = 0
    underestimates: int = 0
    overestimates: int = 0
    estimation_variance: List[float] = field(default_factory=list)
    by_project: Dict[str, Dict] = field(
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
            "project_accuracy": {
                project: {
                    "accuracy_rate": (
                        (stats["accurate"] / stats["total"] * 100)
                        if stats["total"] > 0
                        else 0
                    ),
                    "avg_variance": safe_mean(stats["variance"]),
                }
                for project, stats in self.by_project.items()
            },
        }

    def update_from_issue(self, story_points: float, actual_hours: float,
                          project_key: str):
        if not story_points or actual_hours <= 0:
            return

        expected_hours = story_points * 2
        variance_percent = ((actual_hours - expected_hours) / expected_hours) * 100

        self.total_estimated += 1
        self.estimation_variance.append(variance_percent)

        if abs(variance_percent) <= 20:
            self.accurate_estimates += 1
        elif variance_percent > 20:
            self.underestimates += 1
        else:
            self.overestimates += 1

        if project_key:
            proj_stats = self.by_project[project_key]
            proj_stats["total"] += 1
            proj_stats["variance"].append(variance_percent)
            if abs(variance_percent) <= 20:
                proj_stats["accurate"] += 1
            elif variance_percent > 20:
                proj_stats["under"] += 1
            else:
                proj_stats["over"] += 1


@dataclass
class JiraProjectMetrics(BaseMetrics):
    key: str = ""
    name: str = ""
    total_issues: int = 0
    completed_issues: int = 0
    bugs_count: int = 0
    stories_count: int = 0
    tasks_count: int = 0
    avg_cycle_time: float = 0
    members: Set[str] = field(default_factory=set)

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
            "avg_cycle_time": self.avg_cycle_time,
            "members_count": len(self.members),
        }

    def update_from_issue(self, issue_type: str, status_category: str,
                          assignee: Optional[str]):
        self.total_issues += 1

        if status_category == "done":
            self.completed_issues += 1

        issue_type_lower = issue_type.lower()
        if issue_type_lower == "bug":
            self.bugs_count += 1
        elif issue_type_lower == "story":
            self.stories_count += 1
        elif issue_type_lower == "task":
            self.tasks_count += 1

        if assignee:
            self.members.add(assignee)


@dataclass
class JiraOrgMetrics(BaseMetrics):
    name: str = ""
    issues: JiraIssueMetrics = field(default_factory=JiraIssueMetrics)
    projects: Dict[str, JiraProjectMetrics] = field(default_factory=dict)
    sprints: List[JiraSprintMetrics] = field(default_factory=list)
    cycle_time: JiraCycleTimeMetrics = field(default_factory=JiraCycleTimeMetrics)
    estimation: JiraEstimationMetrics = field(default_factory=JiraEstimationMetrics)
    label_counts: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    component_counts: Dict[str, int] = field(default_factory=lambda: defaultdict(int))

    def get_stats(self) -> Dict:
        return {
            "name": self.name,
            "issues": self.issues.get_stats(),
            "projects": {
                key: project.get_stats()
                for key, project in self.projects.items()
            },
            "sprints": [sprint.get_stats() for sprint in self.sprints],
            "cycle_time": self.cycle_time.get_stats(),
            "estimation": self.estimation.get_stats(),
            "label_counts": dict(self.label_counts),
            "component_counts": dict(self.component_counts),
        }

    def aggregate_project_cycle_times(self):
        """Update per-project avg_cycle_time from the cycle_time metrics."""
        for project_key, times in self.cycle_time.by_project.items():
            if project_key in self.projects and times:
                self.projects[project_key].avg_cycle_time = statistics.mean(times)
