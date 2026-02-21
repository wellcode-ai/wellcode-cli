"""Developer Experience survey service."""

import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from ..db.engine import get_session
from ..db.models import Survey, SurveyQuestion, SurveyResponse
from ..db.repository import MetricStore

DX_PULSE_QUESTIONS = [
    {
        "text": "How productive did you feel this week? (1=Not at all, 5=Very productive)",
        "type": "rating",
        "category": "productivity",
    },
    {
        "text": "How easy was it to get your code reviewed? (1=Very difficult, 5=Very easy)",
        "type": "rating",
        "category": "code_review",
    },
    {
        "text": "How confident are you in deploying to production? (1=Not confident, 5=Very confident)",
        "type": "rating",
        "category": "deployment",
    },
]

DX_FULL_QUESTIONS = [
    {"text": "I can quickly find the information I need to do my work.", "type": "rating", "category": "speed"},
    {"text": "Our CI/CD pipeline is fast and reliable.", "type": "rating", "category": "speed"},
    {"text": "I can stay in a state of flow during development.", "type": "rating", "category": "effectiveness"},
    {"text": "Our codebase is easy to understand and navigate.", "type": "rating", "category": "effectiveness"},
    {"text": "I rarely encounter flaky tests or broken builds.", "type": "rating", "category": "quality"},
    {"text": "Our code review process improves code quality.", "type": "rating", "category": "quality"},
    {"text": "My work directly impacts our business goals.", "type": "rating", "category": "impact"},
    {"text": "I understand how my team's work connects to company objectives.", "type": "rating", "category": "impact"},
    {"text": "What is the biggest bottleneck in your development workflow?", "type": "text", "category": "open"},
    {"text": "What tools or processes would you like to see improved?", "type": "text", "category": "open"},
]

SURVEY_TEMPLATES = {
    "pulse": DX_PULSE_QUESTIONS,
    "full_dx": DX_FULL_QUESTIONS,
}


@dataclass
class SurveyAnalytics:
    survey_id: int
    title: str
    total_responses: int = 0
    response_rate: float = 0.0
    dxi_score: float = 0.0  # Developer Experience Index (1-5)
    category_scores: dict = field(default_factory=dict)
    question_scores: dict = field(default_factory=dict)
    text_responses: list = field(default_factory=list)


def create_survey_from_template(
    template: str = "pulse",
    title: Optional[str] = None,
    target_teams: Optional[list] = None,
    recurrence: str = "none",
) -> Survey:
    """Create a new survey from a predefined template."""
    session = get_session()
    store = MetricStore(session)

    questions = SURVEY_TEMPLATES.get(template, DX_PULSE_QUESTIONS)

    survey = Survey(
        title=title or f"Developer Experience Survey ({template})",
        description=f"Auto-generated {template} survey",
        survey_type=template,
        status="active",
        starts_at=datetime.now(timezone.utc),
        recurrence=recurrence,
        target_teams=target_teams,
    )
    store.surveys.create_survey(survey)

    for i, q in enumerate(questions):
        sq = SurveyQuestion(
            survey_id=survey.id,
            question_text=q["text"],
            question_type=q["type"],
            category=q.get("category"),
            order=i,
            options={"min": 1, "max": 5} if q["type"] == "rating" else None,
        )
        session.add(sq)

    store.commit()
    session.close()
    return survey


def submit_response(survey_id: int, answers: dict, developer_id: Optional[int] = None) -> SurveyResponse:
    """Submit a survey response."""
    session = get_session()
    store = MetricStore(session)

    # Calculate average sentiment score from rating questions
    ratings = [v for v in answers.values() if isinstance(v, (int, float))]
    sentiment = statistics.mean(ratings) if ratings else None

    response = SurveyResponse(
        survey_id=survey_id,
        developer_id=developer_id,
        answers=answers,
        sentiment_score=sentiment,
    )
    store.surveys.add_response(response)
    store.commit()
    session.close()
    return response


def analyze_survey(survey_id: int) -> SurveyAnalytics:
    """Compute analytics for a survey."""
    session = get_session()
    store = MetricStore(session)

    responses = store.surveys.get_responses(survey_id)

    survey = session.get(Survey, survey_id)
    questions = list(session.execute(
        session.query(SurveyQuestion).filter_by(survey_id=survey_id).order_by(SurveyQuestion.order).statement
    ).scalars().all()) if survey else []

    analytics = SurveyAnalytics(
        survey_id=survey_id,
        title=survey.title if survey else "",
        total_responses=len(responses),
    )

    if not responses:
        session.close()
        return analytics

    # Aggregate scores by category
    category_ratings = defaultdict(list)
    question_ratings = defaultdict(list)
    text_answers = []

    for resp in responses:
        answers = resp.answers or {}
        for key, value in answers.items():
            if isinstance(value, (int, float)):
                question_ratings[key].append(value)
                # Find category for this question
                for q in questions:
                    if str(q.id) == key or q.question_text == key:
                        if q.category:
                            category_ratings[q.category].append(value)
                        break
            elif isinstance(value, str) and value.strip():
                text_answers.append({"question": key, "answer": value})

    analytics.category_scores = {
        cat: statistics.mean(vals)
        for cat, vals in category_ratings.items()
    }

    analytics.question_scores = {
        q: statistics.mean(vals)
        for q, vals in question_ratings.items()
    }

    analytics.text_responses = text_answers

    all_ratings = [v for vals in category_ratings.values() for v in vals]
    analytics.dxi_score = statistics.mean(all_ratings) if all_ratings else 0

    session.close()
    return analytics
