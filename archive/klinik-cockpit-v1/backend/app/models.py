from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Paragraph(StrictModel):
    id: str
    text: str


class Document(StrictModel):
    id: str
    title: str
    kind: str
    system: str
    date: str
    status: Literal["available", "pending"]
    paragraphs: list[Paragraph]


class Citation(StrictModel):
    document_id: str
    paragraph_id: str
    quote: str = Field(min_length=1)


class Section(StrictModel):
    id: str
    title: str
    text: str = Field(min_length=1, max_length=12000)
    citations: list[Citation]


class GeneratedLetter(StrictModel):
    sections: list[Section] = Field(min_length=6, max_length=6)


class EvidenceReference(StrictModel):
    document_id: str
    paragraph_id: str


class ModelSection(StrictModel):
    id: str
    text: str = Field(min_length=1, max_length=12000)
    source_refs: list[EvidenceReference] = Field(min_length=1)


class ModelLetter(StrictModel):
    sections: list[ModelSection] = Field(min_length=6, max_length=6)


class Mutation(StrictModel):
    revision: int = Field(ge=0)


class GenerateRequest(Mutation):
    mode: Literal["foundry", "rehearsal"]


class ResetRequest(StrictModel):
    confirmed: Literal[True]
    revisions: dict[str, Annotated[int, Field(ge=0)]]


class SaveRequest(Mutation):
    sections: list[Section] = Field(min_length=6, max_length=6)


class DecisionRequest(Mutation):
    decision: Literal["acknowledged", "rejected"]
    note: str = Field(min_length=8, max_length=2000)
    reviewer: str = Field(min_length=2, max_length=100)


class FollowupResolutionRequest(Mutation):
    date: Literal["29.10.2026", "30.10.2026"]
    note: str = Field(min_length=8, max_length=2000)
    reviewer: str = Field(min_length=2, max_length=100)
    confirmed: Literal[True]


class ApproveRequest(Mutation):
    reviewer: str = Field(min_length=2, max_length=100)
    confirmed: Literal[True]


class HumanConfirmation(Mutation):
    reviewer: str = Field(min_length=2, max_length=100)
    confirmed: Literal[True]


class AgentResult(ModelLetter):
    summary: str = Field(min_length=1, max_length=3000)
    next_actions: list[str] = Field(max_length=6)
    followup: "FollowupAssessment | None" = None


class FollowupAssessment(StrictModel):
    action: Literal["create", "review", "none"]
    title: str = Field(min_length=1, max_length=200)
    reason: str = Field(min_length=1, max_length=2000)
    role_id: str | None
    source_refs: list[EvidenceReference] = Field(max_length=12)


class IntakeConfirmation(HumanConfirmation):
    synthetic_only: Literal[True]
    monitor_events: bool


class TaskConfirmation(HumanConfirmation):
    role_id: str


class AutomationConfirmation(HumanConfirmation):
    enabled: bool


AgentResult.model_rebuild()


class DocumentRead(StrictModel):
    document_id: str = Field(min_length=1, max_length=150)


class EmptyToolArguments(StrictModel):
    pass


class KisFaultRequest(Mutation):
    enabled: bool
