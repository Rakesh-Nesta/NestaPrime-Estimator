"""Section 15 (Amendment 15): an AI assistant in the Education tab,
answering "how do I use this app" questions grounded in the handbook
content the frontend already has (Section 13) -- never live app data,
never a tool with database access, by explicit design (see the
approved spec's Decision 2). Open to every role, same as the Education
nav item itself has always been.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.auth import require_roles
from app.services import ai_content

education_router = APIRouter(prefix="/education", tags=["education"])

ALL_ROLES = ("sales", "pm", "director", "procurement", "site_engineer", "ca_tax")

_SYSTEM_PROMPT_HEADER = (
    "You are the in-app help assistant for the NestaPrime Estimator application. Answer "
    "ONLY using the reference material below -- this is the app's own verified user "
    "handbook, not general knowledge, and it does not include any real project, pricing, "
    "or client data. If the answer isn't in the reference material, say you don't know "
    "rather than guessing or inventing a screen, field, or behavior. Keep answers short "
    "and practical: a sentence or two, plain business language, no markdown headers or "
    "bullet lists unless the question genuinely needs a short list.\n\n"
    "Reference material:\n"
)


class ChatTurn(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class EducationAskRequest(BaseModel):
    question: str = Field(min_length=1)
    # The frontend's own role-appropriate handbook text, already
    # assembled client-side from handbookData.js -- see Help.jsx's own
    # per-role tab visibility for the exact same conditional this
    # mirrors (Director/Admin Guide only when the asking user is a
    # Director). Kept as one plain string rather than parsed structure
    # here, since the backend has no independent copy of the handbook
    # to validate it against -- Section 13's whole point was a single
    # source of truth, not a second one.
    context: str = Field(min_length=1)
    history: list[ChatTurn] = []


class EducationAskOut(BaseModel):
    answer: str


@education_router.post("/ask", response_model=EducationAskOut)
def ask_education_assistant(
    payload: EducationAskRequest,
    current_user=Depends(require_roles(*ALL_ROLES)),
):
    """Never touches the database beyond the role check above -- no live
    project/Cost Sheet/Rate Sheet data ever reaches the model here, by
    design. Nothing is persisted; conversation history lives in the
    frontend's own React state only, same as every other AI feature in
    this app never saves a draft until a human explicitly does."""
    system = _SYSTEM_PROMPT_HEADER + payload.context
    messages = [{"role": t.role, "content": t.content} for t in payload.history]
    messages.append({"role": "user", "content": payload.question})
    try:
        answer = ai_content.generate_chat_reply(system, messages)
    except ai_content.AiContentError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return EducationAskOut(answer=answer)
