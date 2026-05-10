"""Helpers for presenting semantic plan explanations."""

from src.semantic.examples import related_prompts
from src.semantic.planner import SemanticPlan


def explain_plan(plan: SemanticPlan) -> dict:
    """Return a UI-friendly explanation payload."""
    return {
        "question_understood_as": plan.question_understood_as,
        "metric": plan.metric_label,
        "grouping": plan.grouping_label,
        "filters": plan.active_filters,
        "sample_constraints": plan.sample_constraints,
        "assumptions": plan.assumptions,
        "warnings": plan.warnings,
        "related_prompts": plan.related_prompts or related_prompts(plan.intent_id),
    }
