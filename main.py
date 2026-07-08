import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from doc_builder import build_docx
from executor import execute_plan
from models import AgentRequest, AgentResponse
from planner import generate_plan

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Agent API")

_OUTPUTS_DIR = Path(__file__).parent / "outputs"


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/agent", response_model=AgentResponse)
def run_agent(request: AgentRequest) -> AgentResponse:
    logger.info("Agent request: %s", request.request)
    try:
        plan = generate_plan(request.request)
        sections = execute_plan(plan)
        filepath = build_docx(plan, sections)
        filename = Path(filepath).name
        return AgentResponse(
            task_list=plan.steps,
            assumptions=plan.assumptions,
            summary=(
                f"Generated a {plan.doc_type} titled '{plan.title}' "
                f"with {len(sections)} sections."
            ),
            document_path=f"/agent/download/{filename}",
        )
    except Exception as exc:
        logger.exception("Pipeline failed: %s", exc)
        raise HTTPException(
            status_code=500,
            detail={"error": "Agent pipeline failed", "reason": str(exc)},
        )


@app.get("/agent/download/{filename}")
def download(filename: str) -> FileResponse:
    path = (_OUTPUTS_DIR / filename).resolve()
    if path.parent != _OUTPUTS_DIR.resolve():
        raise HTTPException(status_code=400, detail="Invalid filename")
    if not path.exists() or path.suffix != ".docx":
        raise HTTPException(status_code=404, detail=f"File not found: {filename}")
    return FileResponse(
        path=str(path),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=filename,
    )
