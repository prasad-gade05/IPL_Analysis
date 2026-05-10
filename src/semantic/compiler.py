"""Safe SQL compilation for semantic query plans."""

from src.semantic.planner import SemanticPlan


def compile_plan(plan: SemanticPlan) -> str:
    """Compile a supported semantic plan into a validated SQL string."""
    if not plan.supported:
        raise ValueError(plan.unsupported_reason or "Unsupported semantic query.")

    sql = (plan.sql_override or "").strip()
    if not sql:
        raise ValueError("Semantic plan did not provide SQL.")

    lowered = sql.lower()
    if ";" in sql:
        raise ValueError("Semicolons are not allowed in compiled SQL.")
    if not (lowered.startswith("select") or lowered.startswith("with")):
        raise ValueError("Compiled SQL must start with SELECT or WITH.")

    return sql
