import logging

from llm_client import call_llm
from models import AgentPlan, SectionContent, TaskStep

logger = logging.getLogger(__name__)

_FALLBACK_CONTENT = "Content unavailable for this section — see assumptions."


def _build_prompt(plan: AgentPlan, step: TaskStep) -> str:
    assumptions_block = "\n".join(f"- {a}" for a in plan.assumptions) or "None"
    return (
        f"You are writing one section of a {plan.doc_type} titled \"{plan.title}\".\n\n"
        f"Section heading: {step.section_heading}\n"
        f"Section context: {step.description}\n\n"
        f"Working assumptions for this document:\n{assumptions_block}\n\n"
        "Write 2-4 plain-text paragraphs of professional content for this section. "
        "Do not use markdown, bullet points, headings, or any special formatting — "
        "only plain prose separated by blank lines."
    )


def execute_plan(plan: AgentPlan) -> list[SectionContent]:
    """Generate prose content for every step in the plan, preserving step order.

    Calls the LLM once per TaskStep with a prompt scoped to that section's
    heading, description, and the document's working assumptions.  Uses plain
    text mode (json_mode=False).  If the LLM returns None for a step, a
    fallback string is used so the list always contains one entry per step.

    Args:
        plan: The AgentPlan produced by planner.generate_plan().

    Returns:
        A list of SectionContent objects in the same order as plan.steps.
    """
    sections: list[SectionContent] = []

    for step in plan.steps:
        logger.info(
            "Executing step %d/%d: %s", step.step_id, len(plan.steps), step.title
        )
        prompt = _build_prompt(plan, step)
        raw = call_llm(prompt, json_mode=False)

        content = raw.strip() if raw else _FALLBACK_CONTENT
        if not raw:
            logger.warning("Step %d got no LLM response — using fallback", step.step_id)

        sections.append(SectionContent(heading=step.section_heading, content=content))

    return sections


if __name__ == "__main__":
    import sys
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stdout,
    )

    from models import TaskStep

    fixture_plan = AgentPlan(
        doc_type="project plan",
        title="CRM Migration Project Plan",
        assumptions=[
            "The current CRM system and its functional requirements are well understood",
            "The target CRM system has been selected and its capabilities are known",
        ],
        steps=[
            TaskStep(
                step_id=1,
                title="Introduction",
                description="Overview of the CRM migration project, its objectives and scope.",
                section_heading="1. Introduction",
            ),
            TaskStep(
                step_id=2,
                title="Migration Strategy",
                description="Strategy for migrating data, system integration, and testing approach.",
                section_heading="2. Migration Strategy",
            ),
        ],
    )

    sections = execute_plan(fixture_plan)

    print("\n--- SectionContent results ---")
    for sec in sections:
        print(f"\n[{sec.heading}]")
        print(sec.content)
        print("-" * 60)
