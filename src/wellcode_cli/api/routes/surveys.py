"""DX Survey API endpoints."""

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...db.engine import get_session
from ...db.models import Survey
from ...db.repository import MetricStore
from ...services.surveys import (
    SURVEY_TEMPLATES,
    analyze_survey,
    create_survey_from_template,
    submit_response,
)

router = APIRouter()


class CreateSurveyRequest(BaseModel):
    template: str = "pulse"
    title: Optional[str] = None
    target_teams: Optional[list] = None
    recurrence: str = "none"


class SurveyResponseModel(BaseModel):
    id: int
    title: str
    survey_type: Optional[str]
    status: Optional[str]
    created_at: str
    total_questions: int


class SubmitResponseRequest(BaseModel):
    survey_id: int
    answers: dict
    developer_id: Optional[int] = None


class SurveyAnalyticsResponse(BaseModel):
    survey_id: int
    title: str
    total_responses: int
    dxi_score: float
    category_scores: dict
    question_scores: dict
    text_responses: list


@router.get("/templates")
def list_templates():
    return {
        name: [{"text": q["text"], "type": q["type"], "category": q.get("category")}
               for q in questions]
        for name, questions in SURVEY_TEMPLATES.items()
    }


@router.post("/create", response_model=SurveyResponseModel)
def create_survey(req: CreateSurveyRequest):
    if req.template not in SURVEY_TEMPLATES:
        raise HTTPException(400, f"Unknown template: {req.template}")

    survey = create_survey_from_template(
        template=req.template,
        title=req.title,
        target_teams=req.target_teams,
        recurrence=req.recurrence,
    )
    session = get_session()
    s = session.get(Survey, survey.id)
    q_count = len(SURVEY_TEMPLATES.get(req.template, []))
    session.close()

    return SurveyResponseModel(
        id=survey.id,
        title=survey.title,
        survey_type=survey.survey_type,
        status=survey.status,
        created_at=survey.created_at.isoformat() if survey.created_at else "",
        total_questions=q_count,
    )


@router.get("/active", response_model=list[SurveyResponseModel])
def list_active_surveys():
    session = get_session()
    store = MetricStore(session)
    surveys = store.surveys.get_active_surveys()
    result = []
    for s in surveys:
        result.append(SurveyResponseModel(
            id=s.id,
            title=s.title,
            survey_type=s.survey_type,
            status=s.status,
            created_at=s.created_at.isoformat() if s.created_at else "",
            total_questions=len(s.questions) if s.questions else 0,
        ))
    session.close()
    return result


@router.post("/respond")
def submit_survey_response(req: SubmitResponseRequest):
    response = submit_response(req.survey_id, req.answers, req.developer_id)
    return {"id": response.id, "submitted_at": response.submitted_at.isoformat()}


@router.get("/{survey_id}/analytics", response_model=SurveyAnalyticsResponse)
def get_survey_analytics(survey_id: int):
    analytics = analyze_survey(survey_id)
    return SurveyAnalyticsResponse(
        survey_id=analytics.survey_id,
        title=analytics.title,
        total_responses=analytics.total_responses,
        dxi_score=analytics.dxi_score,
        category_scores=analytics.category_scores,
        question_scores=analytics.question_scores,
        text_responses=analytics.text_responses,
    )
