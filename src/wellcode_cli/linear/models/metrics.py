from dataclasses import dataclass, field
from typing import Dict, List, Set
from collections import defaultdict
from datetime import datetime
import statistics
import json
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
        if hasattr(obj, '__dict__'):
            return {k: v for k, v in obj.__dict__.items() 
                   if not k.startswith('_') and not callable(v)}
        try:
            return super().default(obj)
        except:
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
            if hasattr(obj, 'to_dict'):
                return obj.to_dict()
            if hasattr(obj, '__dict__'):
                return {k: convert(v) for k, v in obj.__dict__.items() 
                       if not k.startswith('_') and not callable(v)}
            return obj
        
        return {k: convert(v) for k, v in self.__dict__.items() 
                if not k.startswith('_') and not callable(v)}

@dataclass
class IssueMetrics(BaseMetrics):
    total_created: int = 0
    total_completed: int = 0
    total_in_progress: int = 0
    bugs_created: int = 0
    bugs_completed: int = 0
    features_created: int = 0
    features_completed: int = 0
    by_priority: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    by_state: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    by_team: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    by_project: Dict[str, Dict] = field(default_factory=lambda: defaultdict(lambda: {
        'total': 0,
        'bugs': 0,
        'features': 0,
        'completed': 0,
        'in_progress': 0
    }))

    def get_stats(self) -> Dict:
        completion_rate = (self.total_completed / self.total_created * 100) if self.total_created > 0 else 0
        bug_rate = (self.bugs_created / self.total_created * 100) if self.total_created > 0 else 0
        
        return {
            'total_issues': self.total_created,
            'completion_rate': completion_rate,
            'bug_rate': bug_rate,
            'features_to_bugs_ratio': self.features_created / self.bugs_created if self.bugs_created > 0 else 0,
            'in_progress_rate': (self.total_in_progress / self.total_created * 100) if self.total_created > 0 else 0,
            'priority_distribution': dict(self.by_priority),
            'state_distribution': dict(self.by_state),
            'team_distribution': dict(self.by_team),
            'project_metrics': dict(self.by_project)
        }

    def update_from_issue(self, issue: dict):
        self.total_created += 1
        
        state = issue.get('state', {})
        state_type = state.get('type')
        state_name = state.get('name', 'Unknown')
        
        # Update state metrics
        self.by_state[state_name] += 1
        
        if state_type == 'completed':
            self.total_completed += 1
        elif state_type in ['started', 'inProgress']:
            self.total_in_progress += 1

        # Update bug/feature metrics
        is_bug = any(label.get('name', '').lower() == 'bug' 
                    for label in issue.get('labels', {}).get('nodes', []))
        is_feature = any(label.get('name', '').lower() in ['feature', 'enhancement'] 
                        for label in issue.get('labels', {}).get('nodes', []))

        if is_bug:
            self.bugs_created += 1
            if state_type == 'completed':
                self.bugs_completed += 1
        elif is_feature:
            self.features_created += 1
            if state_type == 'completed':
                self.features_completed += 1

        # Update priority metrics
        priority = issue.get('priority')
        if priority:
            self.by_priority[str(priority)] += 1

        # Update team metrics
        team = issue.get('team', {}).get('key')
        if team:
            self.by_team[team] += 1

        # Update project metrics
        project = issue.get('project', {})
        if project:
            project_key = project.get('key')
            if project_key:
                self.by_project[project_key]['total'] += 1
                if is_bug:
                    self.by_project[project_key]['bugs'] += 1
                elif is_feature:
                    self.by_project[project_key]['features'] += 1
                if state_type == 'completed':
                    self.by_project[project_key]['completed'] += 1
                elif state_type in ['started', 'inProgress']:
                    self.by_project[project_key]['in_progress'] += 1

@dataclass
class CycleTimeMetrics(BaseMetrics):
    cycle_times: List[float] = field(default_factory=list)
    time_to_triage: List[float] = field(default_factory=list)
    time_to_start: List[float] = field(default_factory=list)
    time_in_progress: List[float] = field(default_factory=list)
    time_in_review: List[float] = field(default_factory=list)
    blocked_time: List[float] = field(default_factory=list)
    by_team: Dict[str, List[float]] = field(default_factory=lambda: defaultdict(list))
    by_priority: Dict[str, List[float]] = field(default_factory=lambda: defaultdict(list))

    def get_stats(self) -> Dict:
        def safe_mean(lst: List[float]) -> float:
            return statistics.mean(lst) if lst else 0
            
        return {
            'avg_cycle_time': safe_mean(self.cycle_times),
            'avg_time_to_triage': safe_mean(self.time_to_triage),
            'avg_time_to_start': safe_mean(self.time_to_start),
            'avg_time_in_progress': safe_mean(self.time_in_progress),
            'avg_time_in_review': safe_mean(self.time_in_review),
            'avg_blocked_time': safe_mean(self.blocked_time),
            'team_cycle_times': {team: safe_mean(times) for team, times in self.by_team.items()},
            'priority_cycle_times': {priority: safe_mean(times) for priority, times in self.by_priority.items()},
            'cycle_time_p95': statistics.quantiles(self.cycle_times, n=20)[-1] if self.cycle_times else 0,
            'cycle_time_p50': statistics.median(self.cycle_times) if self.cycle_times else 0
        }

    def update_from_issue(self, issue: dict):
        created_at = datetime.fromisoformat(issue['createdAt'].replace('Z', '+00:00'))
        completed_at = None if not issue.get('completedAt') else datetime.fromisoformat(issue['completedAt'].replace('Z', '+00:00'))
        started_at = None if not issue.get('startedAt') else datetime.fromisoformat(issue['startedAt'].replace('Z', '+00:00'))
        
        if completed_at:
            cycle_time = (completed_at - created_at).total_seconds() / 3600
            self.cycle_times.append(cycle_time)
            
            team = issue.get('team', {}).get('key')
            if team:
                self.by_team[team].append(cycle_time)
                
            priority = issue.get('priority')
            if priority:
                self.by_priority[str(priority)].append(cycle_time)
        
        if started_at:
            time_to_start = (started_at - created_at).total_seconds() / 3600
            self.time_to_start.append(time_to_start)
            
            if completed_at:
                time_in_progress = (completed_at - started_at).total_seconds() / 3600
                self.time_in_progress.append(time_in_progress)

        # Track blocked time from history
        blocked_duration = 0
        for history in issue.get('history', {}).get('nodes', []):
            if history.get('toState', {}).get('name', '').lower() == 'blocked':
                blocked_start = datetime.fromisoformat(history['createdAt'].replace('Z', '+00:00'))
                # Find when it was unblocked
                for next_history in issue.get('history', {}).get('nodes', []):
                    if (datetime.fromisoformat(next_history['createdAt'].replace('Z', '+00:00')) > blocked_start and 
                        next_history.get('fromState', {}).get('name', '').lower() == 'blocked'):
                        blocked_end = datetime.fromisoformat(next_history['createdAt'].replace('Z', '+00:00'))
                        blocked_duration += (blocked_end - blocked_start).total_seconds() / 3600
                        break
        
        if blocked_duration > 0:
            self.blocked_time.append(blocked_duration)

@dataclass
class EstimationMetrics(BaseMetrics):
    total_estimated: int = 0
    accurate_estimates: int = 0
    underestimates: int = 0
    overestimates: int = 0
    estimation_variance: List[float] = field(default_factory=list)
    by_team: Dict[str, Dict] = field(default_factory=lambda: defaultdict(lambda: {
        'total': 0,
        'accurate': 0,
        'under': 0,
        'over': 0,
        'variance': []
    }))

    def get_stats(self) -> Dict:
        def safe_mean(lst: List[float]) -> float:
            return statistics.mean(lst) if lst else 0
            
        accuracy_rate = (self.accurate_estimates / self.total_estimated * 100) if self.total_estimated > 0 else 0
        
        return {
            'total_estimated': self.total_estimated,
            'accuracy_rate': accuracy_rate,
            'underestimate_rate': (self.underestimates / self.total_estimated * 100) if self.total_estimated > 0 else 0,
            'overestimate_rate': (self.overestimates / self.total_estimated * 100) if self.total_estimated > 0 else 0,
            'avg_variance': safe_mean(self.estimation_variance),
            'team_accuracy': {
                team: {
                    'accuracy_rate': (stats['accurate'] / stats['total'] * 100) if stats['total'] > 0 else 0,
                    'avg_variance': safe_mean(stats['variance'])
                } for team, stats in self.by_team.items()
            }
        }

    def update_from_issue(self, issue: dict, actual_time: float):
        estimate = issue.get('estimate')
        if not estimate or actual_time <= 0:
            return
            
        expected_hours = estimate * 2  # Assuming points to hours conversion
        variance_percent = ((actual_time - expected_hours) / expected_hours) * 100
        
        self.total_estimated += 1
        self.estimation_variance.append(variance_percent)
        
        if abs(variance_percent) <= 20:
            self.accurate_estimates += 1
        elif variance_percent > 20:
            self.underestimates += 1
        else:
            self.overestimates += 1
            
        team = issue.get('team', {}).get('key')
        if team:
            team_stats = self.by_team[team]
            team_stats['total'] += 1
            team_stats['variance'].append(variance_percent)
            if abs(variance_percent) <= 20:
                team_stats['accurate'] += 1
            elif variance_percent > 20:
                team_stats['under'] += 1
            else:
                team_stats['over'] += 1

@dataclass
class TeamMetrics(BaseMetrics):
    name: str
    issues_created: int = 0
    issues_completed: int = 0
    bugs_created: int = 0
    bugs_completed: int = 0
    avg_cycle_time: float = 0
    estimation_accuracy: float = 0
    members: Set[str] = field(default_factory=set)
    projects: Dict[str, Dict] = field(default_factory=dict)

    def get_stats(self) -> Dict:
        completion_rate = (self.issues_completed / self.issues_created * 100) if self.issues_created > 0 else 0
        bug_resolution_rate = (self.bugs_completed / self.bugs_created * 100) if self.bugs_created > 0 else 0
        
        return {
            'name': self.name,
            'issues': {
                'total': self.issues_created,
                'completed': self.issues_completed,
                'completion_rate': completion_rate
            },
            'bugs': {
                'total': self.bugs_created,
                'completed': self.bugs_completed,
                'resolution_rate': bug_resolution_rate
            },
            'cycle_time': self.avg_cycle_time,
            'estimation_accuracy': self.estimation_accuracy,
            'members_count': len(self.members),
            'projects': self.projects
        }

    def update_from_issue(self, issue: dict):
        self.issues_created += 1
        if issue.get('state', {}).get('type') == 'completed':
            self.issues_completed += 1
            
        is_bug = any(label.get('name', '').lower() == 'bug' 
                    for label in issue.get('labels', {}).get('nodes', []))
        if is_bug:
            self.bugs_created += 1
            if issue.get('state', {}).get('type') == 'completed':
                self.bugs_completed += 1
                
        assignee = issue.get('assignee', {}).get('name')
        if assignee:
            self.members.add(assignee)
            
        project = issue.get('project', {})
        if project:
            project_key = project.get('key')
            if project_key:
                if project_key not in self.projects:
                    self.projects[project_key] = {
                        'total_issues': 0,
                        'completed_issues': 0,
                        'bugs': 0
                    }
                self.projects[project_key]['total_issues'] += 1
                if is_bug:
                    self.projects[project_key]['bugs'] += 1
                if issue.get('state', {}).get('type') == 'completed':
                    self.projects[project_key]['completed_issues'] += 1

@dataclass
class ProjectMetrics(BaseMetrics):
    key: str
    name: str
    total_issues: int = 0
    completed_issues: int = 0
    bugs_count: int = 0
    features_count: int = 0
    avg_cycle_time: float = 0
    teams_involved: Set[str] = field(default_factory=set)
    estimation_accuracy: float = 0
    start_date: datetime = None
    target_date: datetime = None
    progress: float = 0

    def get_stats(self) -> Dict:
        completion_rate = (self.completed_issues / self.total_issues * 100) if self.total_issues > 0 else 0
        return {
            'key': self.key,
            'name': self.name,
            'total_issues': self.total_issues,
            'completed_issues': self.completed_issues,
            'completion_rate': completion_rate,
            'bugs_count': self.bugs_count,
            'features_count': self.features_count,
            'avg_cycle_time': self.avg_cycle_time,
            'teams_involved': list(self.teams_involved),
            'estimation_accuracy': self.estimation_accuracy,
            'start_date': self.start_date,
            'target_date': self.target_date,
            'progress': self.progress
        }

    def update_from_issue(self, issue: dict):
        self.total_issues += 1
        
        if issue.get('state', {}).get('type') == 'completed':
            self.completed_issues += 1
            
        # Update bug/feature counts
        is_bug = any(label.get('name', '').lower() == 'bug' 
                    for label in issue.get('labels', {}).get('nodes', []))
        is_feature = any(label.get('name', '').lower() in ['feature', 'enhancement'] 
                        for label in issue.get('labels', {}).get('nodes', []))
                        
        if is_bug:
            self.bugs_count += 1
        elif is_feature:
            self.features_count += 1
            
        # Track team involvement
        team = issue.get('team', {}).get('key')
        if team:
            self.teams_involved.add(team)

@dataclass
class LinearOrgMetrics(BaseMetrics):
    name: str
    issues: IssueMetrics = field(default_factory=IssueMetrics)
    teams: Dict[str, TeamMetrics] = field(default_factory=dict)
    projects: Dict[str, ProjectMetrics] = field(default_factory=dict)
    cycle_time: CycleTimeMetrics = field(default_factory=CycleTimeMetrics)
    estimation: EstimationMetrics = field(default_factory=EstimationMetrics)
    label_counts: Dict[str, int] = field(default_factory=dict)

    def get_stats(self) -> Dict:
        return {
            'name': self.name,
            'teams': {name: team.get_stats() for name, team in self.teams.items()},
            'projects': {key: project.get_stats() for key, project in self.projects.items()},
            'issues': self.issues.get_stats(),
            'cycle_time': self.cycle_time.get_stats(),
            'estimation': self.estimation.get_stats()
        }

    def aggregate_metrics(self):
        """Aggregate metrics across all teams and projects"""
        for team in self.teams.values():
            team_issues = [i for i in team.projects.values()]
            if team_issues:
                team.avg_cycle_time = statistics.mean([i['cycle_time'] for i in team_issues if i.get('cycle_time')])
                team.estimation_accuracy = statistics.mean([i['estimation_accuracy'] for i in team_issues if i.get('estimation_accuracy')])
