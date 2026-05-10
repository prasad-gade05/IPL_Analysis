"""
Ask Anything — deterministic semantic IPL stats search.
"""

import plotly.express as px
import streamlit as st

from src.semantic import SUPPORTED_EXAMPLES, run_semantic_query
from src.visualizations.card_renderer import render_active_filters, render_bar_chart, render_dataframe
from src.visualizations.theme import apply_ipl_style, big_number_style

st.title("Ask Anything")
st.caption("Deterministic semantic search over the IPL dataset. The engine only answers supported question families and shows its assumptions instead of guessing.")
st.markdown(big_number_style(), unsafe_allow_html=True)

if "ask_anything_question" not in st.session_state:
    st.session_state["ask_anything_question"] = SUPPORTED_EXAMPLES[0]["prompt"]

example_prompt = st.selectbox(
    "Try a supported example",
    [item["prompt"] for item in SUPPORTED_EXAMPLES],
    index=0,
    key="ask_anything_example",
)

if st.button("Use example", key="ask_anything_use_example", width="stretch"):
    st.session_state["ask_anything_question"] = example_prompt

question = st.text_area(
    "Ask a supported IPL stats question",
    key="ask_anything_question",
    height=110,
    placeholder="Example: Which teams have the longest winning streaks?",
)

st.info(
    "Accuracy rule: if the engine cannot map a question to a supported, whitelisted query pattern, it will say so plainly instead of inventing a result."
)

run_clicked = st.button("Run semantic search", type="primary", width="stretch")

if run_clicked and question.strip():
    result = run_semantic_query(question.strip())
    explanation = result["explanation"]

    if not result["supported"]:
        st.warning(explanation["warnings"][0] if explanation["warnings"] else "This question is not supported yet.")
        st.markdown("**Supported prompt families**")
        st.write(", ".join(item["prompt"] for item in SUPPORTED_EXAMPLES[:8]))
    else:
        plan = result["plan"]
        data = result["data"]

        st.subheader(plan.title)
        st.markdown(f"**Question understood as:** {explanation['question_understood_as']}")
        st.markdown(f"**Metric:** {explanation['metric']}")
        st.markdown(f"**Grouping:** {explanation['grouping']}")
        render_active_filters(explanation["filters"])

        if explanation["sample_constraints"]:
            st.caption("Sample constraints: " + " · ".join(explanation["sample_constraints"]))

        for assumption in explanation["assumptions"]:
            st.info(assumption)

        for warning in explanation["warnings"]:
            st.warning(warning)

        if plan.chart_type == "line" and not data.empty and plan.chart_x in data.columns and plan.chart_y in data.columns:
            fig = px.line(data, x=plan.chart_x, y=plan.chart_y, markers=True, title=plan.title)
            fig = apply_ipl_style(fig, height=420, show_legend=False)
            st.plotly_chart(fig, width="stretch")
        else:
            render_bar_chart(data, plan.chart_x, plan.chart_y, plan.title)

        render_dataframe(data, "The semantic query compiled correctly, but the current filters returned no rows.")

        with st.expander("Generated SQL", expanded=False):
            st.code(result["sql"] or "", language="sql")

        if explanation["related_prompts"]:
            st.markdown("**Related prompts**")
            for prompt in explanation["related_prompts"]:
                st.markdown(f"- {prompt}")
