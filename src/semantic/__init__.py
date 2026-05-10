"""Deterministic semantic query engine for IPL analytics."""

from src.semantic.examples import SUPPORTED_EXAMPLES, related_prompts
from src.semantic.service import run_semantic_query

__all__ = ["SUPPORTED_EXAMPLES", "related_prompts", "run_semantic_query"]
