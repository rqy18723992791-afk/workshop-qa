"""故障排查向导 API：主题、会话、逐步作答、回退、处置单。"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from ..services import diagnosis

router = APIRouter(prefix="/api/diag", tags=["故障排查"])


class StartRequest(BaseModel):
    topic_id: str = Field(default="temp-anomaly", description="故障主题 ID")


class AnswerRequest(BaseModel):
    node_id: str = Field(..., description="当前节点 ID，用于防止重复提交错位")
    option_id: str = Field(..., description="所选选项 ID")


def _raise(exc: diagnosis.DiagnosisError):
    raise HTTPException(exc.status, str(exc)) from exc


@router.get("/topics", summary="可用的故障诊断主题")
def topics() -> dict:
    return {"topics": diagnosis.list_topics()}


@router.post("/sessions", summary="开始一次诊断")
def start(req: StartRequest) -> dict:
    try:
        return diagnosis.start_session(req.topic_id)
    except diagnosis.DiagnosisError as exc:
        _raise(exc)


@router.get("/sessions/{session_id}", summary="查看诊断会话当前状态")
def get_session(session_id: str) -> dict:
    try:
        return diagnosis.get_session(session_id)
    except diagnosis.DiagnosisError as exc:
        _raise(exc)


@router.post("/sessions/{session_id}/answer", summary="提交当前步骤的选择")
def answer(session_id: str, req: AnswerRequest) -> dict:
    try:
        return diagnosis.submit_answer(session_id, req.node_id, req.option_id)
    except diagnosis.DiagnosisError as exc:
        _raise(exc)


@router.post("/sessions/{session_id}/back", summary="回退到上一步")
def back(session_id: str) -> dict:
    try:
        return diagnosis.go_back(session_id)
    except diagnosis.DiagnosisError as exc:
        _raise(exc)


@router.get("/sessions/{session_id}/report", summary="结构化处置单")
def report(session_id: str) -> dict:
    try:
        return diagnosis.get_report(session_id)
    except diagnosis.DiagnosisError as exc:
        _raise(exc)


@router.get(
    "/sessions/{session_id}/report.md",
    summary="下载 Markdown 处置单",
    response_class=PlainTextResponse,
)
def report_markdown(session_id: str) -> PlainTextResponse:
    try:
        text = diagnosis.report_markdown(session_id)
    except diagnosis.DiagnosisError as exc:
        _raise(exc)
    return PlainTextResponse(
        text,
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="fault-report-{session_id}.md"'
        },
    )
