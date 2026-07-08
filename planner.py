import json
import logging

from llm_client import call_llm
from models import AgentPlan, TaskStep

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are an autonomous document-planning agent. Given a user request, you must:
1. Choose the single most appropriate doc_type from this list:
   proposal | meeting minutes | project plan | SOP | technical design | business report | product spec
2. Write a concise, professional title for the document.
3. List assumptions for any information that is missing or ambiguous in the request.
4. Decompose the document into 4-7 logical steps. Each step represents one section of the final document.

Return ONLY a valid JSON object — no markdown fences, no prose — matching this exact schema:
{
  "doc_type": "<one of the allowed values>",
  "title": "<document title>",
  "assumptions": ["<assumption 1>", "..."],
  "steps": [
    {
      "step_id": 1,
      "title": "<short step title>",
      "description": "<1-2 sentences explaining what this section covers>",
      "section_heading": "<heading that will appear in the document>"
    }
  ]
}
"""

_FALLBACK_PLAN = AgentPlan(
    doc_type="business report",
    title="Document",
    assumptions=["Fallback template used — LLM unavailable"],
    steps=[
        TaskStep(
            step_id=1,
            title="Introduction",
            description="Provide background and context for the document.",
            section_heading="Introduction",
        ),
        TaskStep(
            step_id=2,
            title="Details",
            description="Present the main body of information.",
            section_heading="Details",
        ),
        TaskStep(
            step_id=3,
            title="Conclusion",
            description="Summarise findings and outline next steps.",
            section_heading="Conclusion",
        ),
    ],
)


def generate_plan(user_request: str) -> AgentPlan:
    """Call the LLM to produce a structured AgentPlan for the given request.

    Builds a planning prompt, calls the LLM in JSON mode, and parses the
    response into an AgentPlan.  Falls back to a generic 3-step plan when
    the LLM is unavailable or returns unparseable output.

    Args:
        user_request: The raw string describing what the user wants to create.

    Returns:
        A fully populated AgentPlan (from the LLM or the hardcoded fallback).
    """
    prompt = f"{_SYSTEM_PROMPT}\n\nUser request: {user_request}"
    raw = call_llm(prompt, json_mode=True)

    if raw is None:
        logger.warning("LLM returned None — using fallback plan")
        return _FALLBACK_PLAN

    try:
        data = json.loads(raw)
        plan = AgentPlan.model_validate(data)
        logger.info("Plan parsed: doc_type=%s, steps=%d", plan.doc_type, len(plan.steps))
        return plan
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("Failed to parse LLM response (%s) — using fallback plan", exc)
        return _FALLBACK_PLAN


if __name__ == "__main__":
    import sys
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stdout,
    )
    plan = generate_plan("Create a project plan for migrating our CRM")
    print("\n--- AgentPlan ---")
    print(plan.model_dump_json(indent=2))
