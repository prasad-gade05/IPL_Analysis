"""Execution service for semantic queries."""

from __future__ import annotations

import pandas as pd

from src.db.connection import query
from src.semantic.compiler import compile_plan
from src.semantic.explain import explain_plan
from src.semantic.planner import plan_query


def run_semantic_query(question: str) -> dict:
    """Plan, compile, execute, and explain a semantic question."""
    plan = plan_query(question)
    if not plan.supported:
        return {
            "supported": False,
            "plan": plan,
            "explanation": explain_plan(plan),
            "sql": None,
            "data": pd.DataFrame(),
        }

    sql = compile_plan(plan)
    data = query(sql)
    explanation = explain_plan(plan)
    if data.empty:
        explanation["warnings"] = explanation["warnings"] + [
            "The query is supported, but the current filters returned no rows."
        ]

    return {
        "supported": True,
        "plan": plan,
        "explanation": explanation,
        "sql": sql,
        "data": data,
    }
