from pydantic import BaseModel, Field


class AgentRequest(BaseModel):
    request: str = Field(
        min_length=10,
        strip_whitespace=True,
        description="Natural language description of the document to generate (min 10 characters).",
    )


class TaskStep(BaseModel):
    step_id: int
    title: str
    description: str
    section_heading: str


class AgentPlan(BaseModel):
    doc_type: str
    title: str
    assumptions: list[str]
    steps: list[TaskStep]


class SectionContent(BaseModel):
    heading: str
    content: str


class AgentResponse(BaseModel):
    task_list: list[TaskStep]
    assumptions: list[str]
    summary: str
    document_path: str  # Relative download URL: /agent/download/{filename}
