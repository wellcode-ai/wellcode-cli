from dataclasses import dataclass, field
from typing import Dict, List, Set
from collections import defaultdict
from datetime import datetime, timezone
import statistics
from ..utils import ensure_datetime
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
        
        result = {}
        for k, v in self.__dict__.items():
            if not k.startswith('_') and not callable(v):
                result[k] = convert(v)
        return result

@dataclass
class BottleneckMetrics(BaseMetrics):
    stale_prs: int = 0
    long_running_prs: int = 0
    blocked_prs: int = 0
    review_wait_times: List[float] = field(default_factory=list)
    review_response_times: List[float] = field(default_factory=list)
    bottleneck_users: Dict[str, int] = field(default_factory=dict)

    def update_from_pr(self, pr, stale_threshold: float = 168, long_running_threshold: float = 336):
        """Update metrics from a PR (thresholds in hours)"""
        if not pr.merged_at:
            # Ensure timezone-aware datetime
            created_at = ensure_datetime(pr.created_at)
            current_time = datetime.now(timezone.utc)
            age = (current_time - created_at).total_seconds() / 3600
            
            if age > stale_threshold:
                self.stale_prs += 1
            if age > long_running_threshold:
                self.long_running_prs += 1

            # Track blocked PRs
            if any(label.name.lower() in ['blocked', 'on hold'] for label in pr.labels):
                self.blocked_prs += 1
                self.bottleneck_users[pr.user.login] = self.bottleneck_users.get(pr.user.login, 0) + 1

            # Fix timezone awareness for review wait times
            if pr.get_reviews().totalCount > 0:
                first_review = min(pr.get_reviews(), key=lambda r: r.submitted_at)
                review_time = ensure_datetime(first_review.submitted_at)
                wait_time = (review_time - created_at).total_seconds() / 3600
                self.review_wait_times.append(wait_time)

    def get_stats(self) -> Dict:
        return {
            'stale_prs': self.stale_prs,
            'long_running_prs': self.long_running_prs,
            'blocked_prs': self.blocked_prs,
            'avg_review_wait_time': statistics.mean(self.review_wait_times) if self.review_wait_times else 0,
            'avg_response_time': statistics.mean(self.review_response_times) if self.review_response_times else 0,
            'top_bottleneck_users': sorted(self.bottleneck_users.items(), key=lambda x: x[1], reverse=True)[:5]
        }

@dataclass
class ReviewMetrics(BaseMetrics):
    reviews_performed: int = 0
    blocking_reviews_given: int = 0
    review_comments_given: int = 0
    review_comments_received: int = 0
    time_to_first_review: List[float] = field(default_factory=list)
    review_cycles: List[int] = field(default_factory=list)
    review_wait_times: List[float] = field(default_factory=list)
    reviewers_per_pr: Dict[int, Set[str]] = field(default_factory=lambda: defaultdict(set))

    def update_from_review(self, review, pr, org_metrics=None):
        """Update metrics from a single review"""
        if not review.user:
            return
            
        self.reviews_performed += 1
        self.reviewers_per_pr[pr.number].add(review.user.login)
        
        if review.state == 'CHANGES_REQUESTED':
            self.blocking_reviews_given += 1
            
        if review.body:
            self.review_comments_given += 1
            
        if review.user.login != pr.user.login and org_metrics:
            pr_author_metrics = org_metrics.get_or_create_user(pr.user.login)
            pr_author_metrics.review_metrics.review_comments_received += 1
            
        if pr.number not in self.time_to_first_review:
            review_time = (review.submitted_at - pr.created_at).total_seconds() / 3600
            self.time_to_first_review.append(review_time)
            
        self.review_wait_times.append(
            (review.submitted_at - pr.created_at).total_seconds() / 3600
        )

    def get_stats(self) -> Dict:
        return {
            'reviews_performed': self.reviews_performed,
            'blocking_reviews': self.blocking_reviews_given,
            'avg_time_to_first_review': statistics.mean(self.time_to_first_review) if self.time_to_first_review else 0,
            'avg_review_cycles': statistics.mean(self.review_cycles) if self.review_cycles else 0,
            'avg_reviewers_per_pr': statistics.mean([len(r) for r in self.reviewers_per_pr.values()]) if self.reviewers_per_pr else 0,
            'total_comments': self.review_comments_given
        }

@dataclass
class CodeMetrics(BaseMetrics):
    changes_per_pr: List[int] = field(default_factory=list)
    files_changed: List[int] = field(default_factory=list)
    commits_count: List[int] = field(default_factory=list)
    reverts: int = 0
    hotfixes: int = 0
    total_additions: int = 0
    total_deletions: int = 0
    avg_pr_size: float = 0

    def update_from_pr(self, pr):
        """Update metrics from a pull request"""
        changes = pr.additions + pr.deletions
        self.changes_per_pr.append(changes)
        self.files_changed.append(len(list(pr.get_files())))
        self.commits_count.append(len(list(pr.get_commits())))
        self.total_additions += pr.additions
        self.total_deletions += pr.deletions
        
        if 'revert' in pr.title.lower():
            self.reverts += 1
        if 'hotfix' in pr.title.lower() or any(label.name.lower() == 'hotfix' for label in pr.labels):
            self.hotfixes += 1
            
        if self.changes_per_pr:
            self.avg_pr_size = sum(self.changes_per_pr) / len(self.changes_per_pr)

    def get_stats(self) -> Dict:
        return {
            'avg_changes_per_pr': statistics.mean(self.changes_per_pr) if self.changes_per_pr else 0,
            'avg_files_changed': statistics.mean(self.files_changed) if self.files_changed else 0,
            'avg_commits': statistics.mean(self.commits_count) if self.commits_count else 0,
            'reverts': self.reverts,
            'hotfixes': self.hotfixes,
            'total_changes': self.total_additions + self.total_deletions
        }

@dataclass
class TimeMetrics(BaseMetrics):
    time_to_merge: List[float] = field(default_factory=list)
    lead_times: List[float] = field(default_factory=list)
    merge_distribution: Dict[str, int] = field(default_factory=lambda: {
        'business_hours': 0,
        'after_hours': 0,
        'weekends': 0
    })
    deployment_frequency: float = 0
    cycle_time: List[float] = field(default_factory=list)

    def update_from_pr(self, pr, first_commit_date=None):
        """Update metrics from a pull request"""
        if not pr.merged_at:
            return
            
        merge_time = ensure_datetime(pr.merged_at)
        created_time = ensure_datetime(pr.created_at)
        first_commit_date = ensure_datetime(first_commit_date) if first_commit_date else None
        
        # Time to merge
        merge_duration = (merge_time - created_time).total_seconds() / 3600
        self.time_to_merge.append(merge_duration)
        
        # Lead time (if we have first commit)
        if first_commit_date:
            lead_time = (merge_time - first_commit_date).total_seconds() / 3600
            self.lead_times.append(lead_time)
            
        # Update merge distribution
        if merge_time.weekday() >= 5:  # Weekend
            self.merge_distribution['weekends'] += 1
        elif 9 <= merge_time.hour < 17:  # Business hours (simplified)
            self.merge_distribution['business_hours'] += 1
        else:
            self.merge_distribution['after_hours'] += 1

    def get_stats(self) -> Dict:
        return {
            'avg_time_to_merge': statistics.mean(self.time_to_merge) if self.time_to_merge else 0,
            'median_time_to_merge': statistics.median(self.time_to_merge) if self.time_to_merge else 0,
            'avg_lead_time': statistics.mean(self.lead_times) if self.lead_times else 0,
            'median_lead_time': statistics.median(self.lead_times) if self.lead_times else 0,
            'merge_distribution': self.merge_distribution,
            'deployment_frequency': self.deployment_frequency,
            'avg_cycle_time': statistics.mean(self.cycle_time) if self.cycle_time else 0
        }

@dataclass
class CollaborationMetrics(BaseMetrics):
    cross_team_reviews: int = 0
    self_merges: int = 0
    team_reviews: int = 0
    external_reviews: int = 0
    review_comments_per_pr: Dict[int, int] = field(default_factory=dict)
    review_participation_rate: float = 0
    comments_by_user: Dict[str, Dict[int, int]] = field(default_factory=lambda: defaultdict(lambda: defaultdict(int)))

    def update_from_review(self, review, pr, author_team=None, reviewer_team=None):
        """Update metrics from a review"""
        if not review.user:
            return

        reviewer = review.user.login
        
        # Track review type
        if reviewer == pr.user.login:
            self.self_merges += 1
        elif author_team and reviewer_team:
            if author_team == reviewer_team:
                self.team_reviews += 1
            else:
                self.cross_team_reviews += 1
        else:
            self.external_reviews += 1

        # Track comments
        if review.body:
            self.review_comments_per_pr[pr.number] = self.review_comments_per_pr.get(pr.number, 0) + 1
            self.comments_by_user[reviewer][pr.number] += 1

    def update_from_comments(self, comments, pr_number: int):
        """Update metrics from PR comments"""
        for comment in comments:
            if not comment.user:
                continue
                
            commenter = comment.user.login
            self.comments_by_user[commenter][pr_number] += 1
            self.review_comments_per_pr[pr_number] = self.review_comments_per_pr.get(pr_number, 0) + 1

    def get_stats(self) -> Dict:
        total_reviews = self.team_reviews + self.cross_team_reviews + self.external_reviews
        total_prs = len(self.review_comments_per_pr)
        total_comments = sum(self.review_comments_per_pr.values())
        
        return {
            'cross_team_reviews': self.cross_team_reviews,
            'self_merges': self.self_merges,
            'team_reviews': self.team_reviews,
            'external_reviews': self.external_reviews,
            'avg_comments_per_pr': total_comments / total_prs if total_prs > 0 else 0,
            'review_participation_rate': total_reviews / (total_reviews + self.self_merges) if total_reviews + self.self_merges > 0 else 0,
            'total_comments': total_comments,
            'active_reviewers': len(self.comments_by_user)
        }

@dataclass
class UserMetrics(BaseMetrics):
    username: str
    prs_created: int = 0
    prs_merged: int = 0
    review_metrics: ReviewMetrics = field(default_factory=ReviewMetrics)
    code_metrics: CodeMetrics = field(default_factory=CodeMetrics)
    time_metrics: TimeMetrics = field(default_factory=TimeMetrics)
    collaboration_metrics: CollaborationMetrics = field(default_factory=CollaborationMetrics)
    bottleneck_metrics: BottleneckMetrics = field(default_factory=BottleneckMetrics)
    team: str = ""
    role: str = ""

@dataclass
class RepositoryMetrics(BaseMetrics):
    name: str
    default_branch: str = "main"
    prs_created: int = 0
    prs_merged: int = 0
    prs_merged_to_main: int = 0
    review_metrics: ReviewMetrics = field(default_factory=ReviewMetrics)
    code_metrics: CodeMetrics = field(default_factory=CodeMetrics)
    time_metrics: TimeMetrics = field(default_factory=TimeMetrics)
    collaboration_metrics: CollaborationMetrics = field(default_factory=CollaborationMetrics)
    bottleneck_metrics: BottleneckMetrics = field(default_factory=BottleneckMetrics)
    contributors: Set[str] = field(default_factory=set)
    teams_involved: Set[str] = field(default_factory=set)
    last_updated: datetime = field(default_factory=datetime.now)

    def update_teams(self, author_team: str, reviewer_team: str):
        if author_team:
            self.teams_involved.add(author_team)
        if reviewer_team:
            self.teams_involved.add(reviewer_team)
    
    def update_timestamp(self):
        self.last_updated = datetime.now(timezone.utc)

@dataclass
class OrganizationMetrics(BaseMetrics):
    name: str
    repositories: Dict[str, RepositoryMetrics] = field(default_factory=dict)
    users: Dict[str, UserMetrics] = field(default_factory=dict)
    teams: Dict[str, Set[str]] = field(default_factory=lambda: defaultdict(set))
    review_metrics: ReviewMetrics = field(default_factory=ReviewMetrics)
    code_metrics: CodeMetrics = field(default_factory=CodeMetrics)
    time_metrics: TimeMetrics = field(default_factory=TimeMetrics)
    collaboration_metrics: CollaborationMetrics = field(default_factory=CollaborationMetrics)
    bottleneck_metrics: BottleneckMetrics = field(default_factory=BottleneckMetrics)

    def get_or_create_repository(self, name: str, default_branch: str = "main") -> RepositoryMetrics:
        if name not in self.repositories:
            self.repositories[name] = RepositoryMetrics(name=name, default_branch=default_branch)
        return self.repositories[name]

    def get_or_create_user(self, username: str, team: str = "") -> UserMetrics:
        if username not in self.users:
            self.users[username] = UserMetrics(username=username, team=team)
            if team:
                self.teams[team].add(username)
        return self.users[username]

    def get_repository_stats(self, repo_name: str) -> Dict:
        """Get aggregated statistics for a specific repository"""
        if repo_name not in self.repositories:
            return {}
        repo = self.repositories[repo_name]
        return {
            'name': repo.name,
            'prs_created': repo.prs_created,
            'prs_merged': repo.prs_merged,
            'contributors_count': len(repo.contributors),
            'teams_involved': len(repo.teams_involved),
            'avg_time_to_merge': statistics.mean(repo.time_metrics.time_to_merge) if repo.time_metrics.time_to_merge else 0,
            'avg_review_time': statistics.mean(repo.review_metrics.review_wait_times) if repo.review_metrics.review_wait_times else 0,
            'hotfixes': repo.code_metrics.hotfixes,
            'reverts': repo.code_metrics.reverts,
            'last_updated': repo.last_updated
        }

    def get(self, attribute, default=None):
        """Get an attribute safely with a default value"""
        return getattr(self, attribute, default)

    def get_all_contributors(self):
        """Get a set of all contributors across all repositories"""
        all_contributors = set()
        for repo in self.repositories.values():
            all_contributors.update(repo.contributors)
        return all_contributors

    def aggregate_metrics(self):
        """Aggregate metrics from all repositories"""
        for repo in self.repositories.values():
            # Code metrics
            self.code_metrics.total_additions += repo.code_metrics.total_additions
            self.code_metrics.total_deletions += repo.code_metrics.total_deletions
            self.code_metrics.changes_per_pr.extend(repo.code_metrics.changes_per_pr)
            self.code_metrics.files_changed.extend(repo.code_metrics.files_changed)
            self.code_metrics.commits_count.extend(repo.code_metrics.commits_count)
            self.code_metrics.reverts += repo.code_metrics.reverts
            self.code_metrics.hotfixes += repo.code_metrics.hotfixes

            # Review metrics
            self.review_metrics.reviews_performed += repo.review_metrics.reviews_performed
            self.review_metrics.blocking_reviews_given += repo.review_metrics.blocking_reviews_given
            self.review_metrics.review_comments_given += repo.review_metrics.review_comments_given
            self.review_metrics.time_to_first_review.extend(repo.review_metrics.time_to_first_review)
            self.review_metrics.review_cycles.extend(repo.review_metrics.review_cycles)
            self.review_metrics.review_wait_times.extend(repo.review_metrics.review_wait_times)

            # Time metrics
            self.time_metrics.time_to_merge.extend(repo.time_metrics.time_to_merge)
            self.time_metrics.lead_times.extend(repo.time_metrics.lead_times)
            self.time_metrics.cycle_time.extend(repo.time_metrics.cycle_time)
            for key in self.time_metrics.merge_distribution:
                self.time_metrics.merge_distribution[key] += repo.time_metrics.merge_distribution[key]

    def to_dict(self):
        return {
            "name": self.name,
            "repositories": {name: repo.to_dict() for name, repo in self.repositories.items()},
            "users": {name: user.to_dict() for name, user in self.users.items()},
            "teams": {team: list(members) for team, members in self.teams.items()},
            "review_metrics": self.review_metrics.to_dict(),
            "code_metrics": self.code_metrics.to_dict(),
            "time_metrics": self.time_metrics.to_dict(),
            "collaboration_metrics": self.collaboration_metrics.to_dict(),
            "bottleneck_metrics": self.bottleneck_metrics.to_dict()
        }
