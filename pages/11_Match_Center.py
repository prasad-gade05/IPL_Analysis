"""
Match Center — Ball-by-ball replay and analysis of any match.

Select any IPL match to view full scorecards, run-progression worm charts,
partnership breakdowns, over-by-over heatmaps, and head-to-head match stats.
"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from src.db.connection import query
from src.visualizations.theme import (
    apply_ipl_style, styled_bar, styled_pie,
    get_team_color, big_number_style, IPL_COLORWAY,
)
from src.utils.constants import TEAM_COLORS, ALL_SEASONS
from src.utils.formatters import (
    format_number, format_strike_rate, format_economy, format_overs,
)

st.markdown(big_number_style(), unsafe_allow_html=True)

# ── Cached Data Loaders ──────────────────────────────────────────────────────


@st.cache_data(ttl=3600)
def load_season_matches(season: int) -> pd.DataFrame:
    """All matches for a season, sorted by date."""
    return query(
        "SELECT * FROM matches WHERE season = ? ORDER BY date", [season]
    )


@st.cache_data(ttl=3600)
def load_match_balls(match_id) -> pd.DataFrame:
    """Ball-by-ball data for a single match."""
    return query(
        "SELECT * FROM balls WHERE match_id = ? ORDER BY innings, over, ball",
        [match_id],
    )


@st.cache_data(ttl=3600)
def load_match_partnerships(match_id) -> pd.DataFrame:
    """Partnership records for a single match."""
    return query(
        "SELECT * FROM partnerships WHERE match_id = ? ORDER BY innings, wicket_number",
        [match_id],
    )


# ── Helpers ───────────────────────────────────────────────────────────────────


def _safe_int(val):
    """Convert to int safely, returning 0 for NaN / None."""
    try:
        if pd.isna(val):
            return 0
        return int(val)
    except (TypeError, ValueError):
        return 0


def _fmt_partners(val):
    """Format batting_partners which may arrive as a tuple, list, or string."""
    if isinstance(val, (tuple, list)):
        return " & ".join(str(v) for v in val)
    return str(val) if pd.notna(val) else ""


def _is_out(player_out):
    """True when the player_out field represents an actual dismissal."""
    return pd.notna(player_out) and str(player_out).strip() not in ("", "none")


def _dismissal_text(kind, bowler, fielders):
    """Build cricket-style dismissal string."""
    if pd.isna(kind) or not kind or str(kind) == "not_out":
        return "not out"
    f_raw = str(fielders).strip() if pd.notna(fielders) else ""
    f = f_raw if f_raw and f_raw != "none" else ""
    mapping = {
        "caught":           f"c {f} b {bowler}" if f else f"c ? b {bowler}",
        "caught and bowled": f"c & b {bowler}",
        "bowled":            f"b {bowler}",
        "lbw":               f"lbw b {bowler}",
        "stumped":           f"st {f} b {bowler}" if f else f"st ? b {bowler}",
        "run out":           f"run out ({f})" if f else "run out",
        "hit wicket":        f"hit wicket b {bowler}",
        "retired hurt":      "retired hurt",
        "retired out":       "retired out",
        "obstructing the field": "obstructing the field",
    }
    return mapping.get(kind, kind)


def _extras_breakdown(inn_df: pd.DataFrame):
    """Return (display_string, total_extras_int) for an innings DataFrame."""
    if inn_df.empty:
        return "0", 0
    ext = inn_df[inn_df["runs_extras"] > 0]
    if ext.empty:
        return "0", 0
    by_type = ext.groupby("extra_type")["runs_extras"].sum()
    total = int(by_type.sum())
    abbr = {"wides": "w", "noballs": "nb", "byes": "b", "legbyes": "lb", "penalty": "p"}
    parts = [f"{abbr.get(t, t)} {int(v)}" for t, v in by_type.items()
             if v > 0 and str(t) != "none"]
    text = f"{total} ({', '.join(parts)})" if parts else str(total)
    return text, total


# ── Scorecard Builders ────────────────────────────────────────────────────────

_REAL_WICKETS = {"bowled", "caught", "caught and bowled", "lbw",
                 "stumped", "hit wicket", "run out", "obstructing the field"}
_BOWLER_WICKETS = {"bowled", "caught", "caught and bowled", "lbw",
                   "stumped", "hit wicket"}


def _batting_card(balls_df: pd.DataFrame, innings: int) -> pd.DataFrame:
    """Batting scorecard for one innings."""
    inn = balls_df[balls_df["innings"] == innings].reset_index(drop=True)
    if inn.empty:
        return pd.DataFrame()

    # Order batters by first appearance (DataFrame row index)
    first_idx = (
        inn.groupby("batter")
        .apply(lambda g: g.index[0], include_groups=False)
        .reset_index(name="_order")
    )
    stats = inn.groupby("batter").agg(
        R=("runs_batter", "sum"),
        B=("valid_ball", lambda x: int(x.astype(int).sum())),
        _4s=("is_four", lambda x: int(x.astype(int).sum())),
        _6s=("is_six", lambda x: int(x.astype(int).sum())),
    ).reset_index()
    stats = stats.merge(first_idx, on="batter").sort_values("_order")

    # Dismissal map — player_out can differ from batter (run-out non-striker)
    # Data uses "none" (string) for no dismissal, not NaN
    dism_rows = (
        inn[inn["player_out"].apply(_is_out)]
        [["player_out", "wicket_kind", "bowler", "fielders"]]
        .drop_duplicates(subset=["player_out"], keep="first")
    )
    dism_map = {
        r["player_out"]: _dismissal_text(r["wicket_kind"], r["bowler"], r["fielders"])
        for _, r in dism_rows.iterrows()
    }
    stats["Dismissal"] = stats["batter"].map(dism_map).fillna("not out")

    # Strike rate
    stats["SR"] = stats.apply(
        lambda r: round(r["R"] * 100.0 / r["B"], 2) if r["B"] > 0 else 0.00,
        axis=1,
    )
    return (
        stats[["batter", "Dismissal", "R", "B", "_4s", "_6s", "SR"]]
        .rename(columns={"batter": "Batter", "_4s": "4s", "_6s": "6s"})
    )


def _bowling_card(balls_df: pd.DataFrame, innings: int) -> pd.DataFrame:
    """Bowling scorecard for one innings."""
    inn = balls_df[balls_df["innings"] == innings].reset_index(drop=True)
    if inn.empty:
        return pd.DataFrame()

    first_idx = (
        inn.groupby("bowler")
        .apply(lambda g: g.index[0], include_groups=False)
        .reset_index(name="_order")
    )

    # Use runs_bowler if available, otherwise runs_batter + wides/noballs
    runs_col = "runs_bowler" if "runs_bowler" in inn.columns else "runs_batter"

    stats = inn.groupby("bowler").agg(
        _balls=("valid_ball", lambda x: int(x.astype(int).sum())),
        R=(runs_col, "sum"),
        Dots=("is_dot", lambda x: int(x.astype(int).sum())),
    ).reset_index()
    stats["R"] = stats["R"].astype(int)

    # Wickets credited to bowler (exclude run-outs, retired, obstruction)
    wk = (
        inn[inn["wicket_kind"].isin(_BOWLER_WICKETS)]
        .groupby("bowler").size()
        .reset_index(name="W")
    )
    stats = stats.merge(wk, on="bowler", how="left")
    stats["W"] = stats["W"].fillna(0).astype(int)

    # Maidens
    if "is_maiden" in inn.columns:
        maiden_balls = inn[inn["is_maiden"].fillna(False).astype(bool)]
        if not maiden_balls.empty:
            mdn = (
                maiden_balls.drop_duplicates(subset=["bowler", "over"])
                .groupby("bowler").size()
                .reset_index(name="M")
            )
        else:
            mdn = pd.DataFrame(columns=["bowler", "M"])
    else:
        ov = inn.groupby(["bowler", "over"]).agg(
            vb=("valid_ball", lambda x: int(x.astype(int).sum())),
            r=(runs_col, "sum"),
        ).reset_index()
        mdn = (
            ov[(ov["vb"] == 6) & (ov["r"] == 0)]
            .groupby("bowler").size()
            .reset_index(name="M")
        )
    stats = stats.merge(mdn, on="bowler", how="left")
    stats["M"] = stats["M"].fillna(0).astype(int)

    stats = stats.merge(first_idx, on="bowler").sort_values("_order")
    stats["O"] = stats["_balls"].apply(format_overs)
    stats["Econ"] = stats.apply(
        lambda r: round(r["R"] * 6.0 / r["_balls"], 2) if r["_balls"] > 0 else 0.00,
        axis=1,
    )
    return (
        stats[["bowler", "O", "M", "R", "W", "Econ", "Dots"]]
        .rename(columns={"bowler": "Bowler"})
    )


def _fall_of_wickets(balls_df: pd.DataFrame, innings: int) -> list[str]:
    """Return list like '1-23 (Player, 3.2 ov)'."""
    inn = (
        balls_df[balls_df["innings"] == innings]
        .sort_values(["over", "ball"])
        .reset_index(drop=True)
    )
    if inn.empty:
        return []

    inn["_total"] = inn["runs_batter"] + inn["runs_extras"]
    inn["_cum"] = inn["_total"].cumsum()

    wk = inn[
        inn["player_out"].notna()
        & inn["wicket_kind"].isin(_REAL_WICKETS)
    ]
    fow = []
    for i, (_, r) in enumerate(wk.iterrows(), 1):
        score = int(r["_cum"])
        ov_str = f"{r['over']}.{int(r['ball'])}"
        fow.append(f"{i}-{score} ({r['player_out']}, {ov_str} ov)")
    return fow


# ── Section Renderers ─────────────────────────────────────────────────────────


def render_header(match: pd.Series):
    """Match header: scores, result, metadata, flags."""
    team1, team2 = match["team1"], match["team2"]
    s1 = f"{_safe_int(match['team1_score'])}/{_safe_int(match['team1_wickets'])}"
    s2 = f"{_safe_int(match['team2_score'])}/{_safe_int(match['team2_wickets'])}"
    c1, c2 = get_team_color(team1), get_team_color(team2)

    # ── Score display ──
    left, vs, right = st.columns([5, 1, 5])
    with left:
        st.markdown(
            f"<h2 style='color:{c1};text-align:right;margin-bottom:0'>{team1}</h2>"
            f"<h1 style='text-align:right;margin-top:0'>{s1}</h1>",
            unsafe_allow_html=True,
        )
    with vs:
        st.markdown(
            "<h2 style='text-align:center;padding-top:28px'>vs</h2>",
            unsafe_allow_html=True,
        )
    with right:
        st.markdown(
            f"<h2 style='color:{c2};margin-bottom:0'>{team2}</h2>"
            f"<h1 style='margin-top:0'>{s2}</h1>",
            unsafe_allow_html=True,
        )

    # ── Result line ──
    winner = match.get("match_won_by")
    margin_val = match.get("win_margin_value")
    margin_type = match.get("win_margin_type")
    method = match.get("method")
    is_so = match.get("is_super_over_match")

    parts: list[str] = []
    if pd.notna(winner) and winner:
        parts.append(f"**{winner}** won")
        if pd.notna(margin_val) and pd.notna(margin_type):
            parts.append(f"by **{_safe_int(margin_val)}** {margin_type}")
        if pd.notna(method) and method and str(method).lower() not in ("", "na", "nan"):
            method_display = str(method).upper().replace("_", " ")
            if method_display not in ("NO DLS",):
                parts.append(f"({method_display})")
        if is_so:
            parts.append("(Super Over)")
    else:
        parts.append("**No Result**")

    result_line = " ".join(parts)
    st.markdown(
        f"<div style='text-align:center;font-size:1.1rem'>{result_line}</div>",
        unsafe_allow_html=True,
    )

    # ── Metadata row ──
    date_str = pd.to_datetime(match["date"]).strftime("%d %b %Y")
    meta_parts = []

    meta_parts.append(date_str)

    venue = match.get("venue", "")
    city = match.get("city", "")
    if venue:
        loc = str(venue)
        if pd.notna(city) and city:
            loc += f", {city}"
        meta_parts.append(loc)

    stage = match.get("stage", "")
    if pd.notna(stage) and stage:
        meta_parts.append(str(stage))

    tw = match.get("toss_winner", "")
    td = match.get("toss_decision", "")
    if pd.notna(tw) and tw:
        meta_parts.append(f"{tw} won toss, chose to {td}")

    potm = match.get("player_of_match", "")
    if pd.notna(potm) and potm:
        meta_parts.append(f"Player of the Match: **{potm}**")

    st.markdown(
        "<div style='text-align:center; color:#aaa; font-size:0.9rem'>"
        + " &nbsp;|&nbsp; ".join(meta_parts)
        + "</div>",
        unsafe_allow_html=True,
    )
    st.divider()


# ─────────────────────────────────────────────────────────────────
# TAB 1 — Scorecard
# ─────────────────────────────────────────────────────────────────


def render_scorecard(match: pd.Series, balls_df: pd.DataFrame):
    """Full batting + bowling scorecards for both innings."""
    all_innings = sorted(balls_df["innings"].unique())
    main_innings = [i for i in all_innings if i <= 2]

    for inn_num in main_innings:
        inn_balls = balls_df[balls_df["innings"] == inn_num]
        if inn_balls.empty:
            continue

        batting_team = inn_balls["batting_team"].iloc[0]
        bowling_team = inn_balls["bowling_team"].iloc[0]
        tc = get_team_color(batting_team)

        st.markdown(
            f"### <span style='color:{tc}'>{batting_team}</span> — Innings {inn_num}",
            unsafe_allow_html=True,
        )

        # Batting card
        bat = _batting_card(balls_df, inn_num)
        if not bat.empty:
            st.dataframe(
                bat,
                width='stretch',
                hide_index=True,
                column_config={
                    "SR": st.column_config.NumberColumn(format="%.2f"),
                },
            )

        # Extras + Total
        ext_text, ext_total = _extras_breakdown(inn_balls)
        bat_runs = int(inn_balls["runs_batter"].sum())
        total_runs = bat_runs + ext_total
        valid_balls = int(inn_balls["valid_ball"].astype(int).sum())
        total_overs = format_overs(valid_balls)
        total_wk = int(
            inn_balls[
                inn_balls["player_out"].notna()
                & inn_balls["wicket_kind"].isin(_REAL_WICKETS)
            ].shape[0]
        )

        ec1, ec2 = st.columns(2)
        with ec1:
            st.markdown(f"**Extras:** {ext_text}")
        with ec2:
            st.markdown(f"**Total:** {total_runs}/{total_wk} ({total_overs} overs)")

        # Bowling card
        st.markdown(f"**Bowling — {bowling_team}**")
        bowl = _bowling_card(balls_df, inn_num)
        if not bowl.empty:
            st.dataframe(
                bowl,
                width='stretch',
                hide_index=True,
                column_config={
                    "Econ": st.column_config.NumberColumn(format="%.2f"),
                },
            )

        # Fall of wickets
        fow = _fall_of_wickets(balls_df, inn_num)
        if fow:
            st.markdown("**Fall of Wickets:** " + " • ".join(fow))

        st.divider()

    # Super-over innings (3, 4, …)
    super_innings = [i for i in all_innings if i > 2]
    if super_innings:
        st.markdown("### Super Over")
        for inn_num in super_innings:
            sib = balls_df[balls_df["innings"] == inn_num]
            if sib.empty:
                continue
            bt = sib["batting_team"].iloc[0]
            runs = int(sib["runs_batter"].sum() + sib["runs_extras"].sum())
            wks = int(sib[sib["wicket_kind"].isin(_REAL_WICKETS)].shape[0])
            st.markdown(f"**{bt}:** {runs}/{wks}")
            detail = sib[
                ["ball", "batter", "bowler", "runs_batter",
                 "runs_extras", "wicket_kind", "player_out"]
            ].copy()
            detail.columns = ["Ball", "Batter", "Bowler", "Runs",
                              "Extras", "Wicket", "Out"]
            detail["Wicket"] = detail["Wicket"].replace("not_out", "")
            detail["Out"] = detail["Out"].replace("none", "")
            st.dataframe(detail, width='stretch', hide_index=True)


# ─────────────────────────────────────────────────────────────────
# TAB 2 — Worm Chart
# ─────────────────────────────────────────────────────────────────


def render_worm(match: pd.Series, balls_df: pd.DataFrame):
    """Run-progression worm + required-run-rate chart."""

    fig = go.Figure()
    innings_cum: dict[int, pd.DataFrame] = {}

    for inn_num in [1, 2]:
        inn = (
            balls_df[balls_df["innings"] == inn_num]
            .sort_values(["over", "ball"])
            .copy()
        )
        if inn.empty:
            continue

        inn["_total"] = inn["runs_batter"] + inn["runs_extras"]

        # Over-level cumulative
        over_agg = (
            inn.groupby("over")
            .agg(runs=("_total", "sum"))
            .reset_index()
        )
        over_agg["cum_runs"] = over_agg["runs"].cumsum()
        over_agg["over_num"] = over_agg["over"]  # already 1-indexed

        # Prepend origin (0, 0)
        start = pd.DataFrame({"over": [-1], "runs": [0],
                               "cum_runs": [0], "over_num": [0]})
        over_agg = pd.concat([start, over_agg], ignore_index=True)
        innings_cum[inn_num] = over_agg

        batting_team = inn["batting_team"].iloc[0]
        color = get_team_color(batting_team)

        # Main worm line
        fig.add_trace(go.Scatter(
            x=over_agg["over_num"],
            y=over_agg["cum_runs"],
            mode="lines+markers",
            name=f"{batting_team} (Inn {inn_num})",
            line=dict(color=color, width=3),
            marker=dict(size=4),
            hovertemplate="Over %{x}: %{y} runs<extra></extra>",
        ))

        # Wicket markers (ball-level for accurate y-position)
        inn["_cum"] = inn["_total"].cumsum()
        wk = inn[
            inn["player_out"].notna()
            & inn["wicket_kind"].isin(_REAL_WICKETS)
        ]
        if not wk.empty:
            wk_x = (wk["over"] - 1) + wk["ball"] / 6.0  # place within the over
            fig.add_trace(go.Scatter(
                x=wk_x,
                y=wk["_cum"],
                mode="markers",
                name=f"Wickets (Inn {inn_num})",
                marker=dict(color="red", size=10, symbol="x"),
                text=wk["player_out"],
                hovertemplate="%{text} out at %{y} runs<extra></extra>",
            ))

    # Target line
    if 1 in innings_cum and 2 in innings_cum:
        target = int(innings_cum[1]["cum_runs"].iloc[-1]) + 1
        fig.add_hline(
            y=target, line_dash="dash", line_color="rgba(255,255,255,0.6)",
            annotation_text=f"Target: {target}",
            annotation_font_color="white",
        )

    fig.update_layout(
        title="Run Progression",
        xaxis_title="Over",
        yaxis_title="Cumulative Runs",
        xaxis=dict(dtick=2, range=[-0.5, 21]),
    )
    apply_ipl_style(fig, height=500)
    st.plotly_chart(fig, width='stretch')

    # ── Required Run Rate vs Current Run Rate (2nd innings) ──
    if 1 in innings_cum and 2 in innings_cum:
        target = int(innings_cum[1]["cum_runs"].iloc[-1]) + 1
        chase = innings_cum[2][innings_cum[2]["over_num"] > 0].copy()
        if not chase.empty:
            chase["CRR"] = (chase["cum_runs"] / chase["over_num"]).round(2)
            chase["RRR"] = chase.apply(
                lambda r: max(
                    0.0,
                    round((target - r["cum_runs"]) / max(20 - r["over_num"], 0.1), 2),
                ),
                axis=1,
            )
            fig_rr = go.Figure()
            fig_rr.add_trace(go.Scatter(
                x=chase["over_num"], y=chase["CRR"],
                mode="lines+markers", name="Current RR",
                line=dict(color="#4ECDC4", width=2),
            ))
            fig_rr.add_trace(go.Scatter(
                x=chase["over_num"], y=chase["RRR"],
                mode="lines+markers", name="Required RR",
                line=dict(color="#FF6B6B", width=2),
            ))
            fig_rr.update_layout(
                title="Current vs Required Run Rate (2nd Innings Chase)",
                xaxis_title="Over", yaxis_title="Run Rate",
                xaxis=dict(dtick=2),
            )
            apply_ipl_style(fig_rr, height=400)
            st.plotly_chart(fig_rr, width='stretch')


# ─────────────────────────────────────────────────────────────────
# TAB 3 — Partnerships
# ─────────────────────────────────────────────────────────────────


def render_partnerships(
    match: pd.Series,
    balls_df: pd.DataFrame,
    partnerships_df: pd.DataFrame,
):
    """Partnership bar chart + details table for each innings."""
    for inn_num in [1, 2]:
        inn_parts = partnerships_df[partnerships_df["innings"] == inn_num].copy()
        if inn_parts.empty:
            continue

        inn_balls = balls_df[balls_df["innings"] == inn_num]
        bt = (
            inn_balls["batting_team"].iloc[0]
            if not inn_balls.empty
            else f"Innings {inn_num}"
        )
        tc = get_team_color(bt)
        st.markdown(
            f"### <span style='color:{tc}'>{bt}</span> — Innings {inn_num} Partnerships",
            unsafe_allow_html=True,
        )

        # ── Horizontal stacked bar ──
        fig = go.Figure()
        colors = IPL_COLORWAY[: len(inn_parts)]
        for i, (_, p) in enumerate(inn_parts.iterrows()):
            runs = _safe_int(p.get("runs", 0))
            partners = _fmt_partners(p.get("batting_partners", ""))
            fig.add_trace(go.Bar(
                x=[runs],
                y=[bt],
                orientation="h",
                name=partners,
                text=[f"{partners}: {runs}"],
                textposition="auto",
                marker_color=colors[i % len(colors)],
                hovertemplate=f"{partners}<br>{runs} runs<extra></extra>",
            ))
        fig.update_layout(
            barmode="stack",
            title="Partnership Contributions",
            xaxis_title="Runs", yaxis=dict(showticklabels=False),
        )
        apply_ipl_style(fig, height=180, show_legend=False)
        st.plotly_chart(fig, width='stretch')

        # ── How each partnership ended ──
        wickets_inn = (
            inn_balls[
                inn_balls["player_out"].notna()
                & inn_balls["wicket_kind"].isin(_REAL_WICKETS)
            ]
            .sort_values(["over", "ball"])
            .reset_index(drop=True)
        )
        how_ended_map: dict[int, str] = {}
        for idx, (_, wr) in enumerate(wickets_inn.iterrows(), 1):
            how_ended_map[idx] = _dismissal_text(
                wr["wicket_kind"], wr["bowler"], wr["fielders"]
            )

        # ── Details table ──
        detail_rows = []
        for _, p in inn_parts.iterrows():
            wn = _safe_int(p.get("wicket_number", 0))
            row = {
                "Wkt#": wn if wn > 0 else "-",
                "Batters": _fmt_partners(p.get("batting_partners", "")),
                "Runs": _safe_int(p.get("runs", 0)),
            }
            if "balls" in p.index:
                row["Balls"] = _safe_int(p.get("balls", 0))
            if "run_rate" in p.index:
                rr = p.get("run_rate")
                row["RR"] = round(float(rr), 2) if pd.notna(rr) else "-"
            if "boundaries" in p.index:
                row["Boundaries"] = _safe_int(p.get("boundaries", 0))
            row["How Ended"] = how_ended_map.get(wn, "not out")
            detail_rows.append(row)

        if detail_rows:
            st.dataframe(
                pd.DataFrame(detail_rows),
                width='stretch',
                hide_index=True,
            )

        st.divider()


# ─────────────────────────────────────────────────────────────────
# TAB 4 — Over-by-Over
# ─────────────────────────────────────────────────────────────────


def render_over_by_over(match: pd.Series, balls_df: pd.DataFrame):
    """Over-by-over heatmap + expandable ball-by-ball detail."""

    # ── Build heatmap matrix ──
    heat_rows: list[dict] = []
    labels: dict[int, str] = {}

    for inn_num in [1, 2]:
        inn = balls_df[balls_df["innings"] == inn_num].copy()
        if inn.empty:
            continue
        bt = inn["batting_team"].iloc[0]
        labels[inn_num] = f"Inn {inn_num} — {bt}"
        inn["_total"] = inn["runs_batter"] + inn["runs_extras"]
        overs = inn.groupby("over")["_total"].sum().reset_index()
        for _, row in overs.iterrows():
            heat_rows.append({
                "innings_label": labels[inn_num],
                "over": int(row["over"]),  # already 1-indexed
                "runs": int(row["_total"]),
            })

    if not heat_rows:
        st.info("No over-by-over data available.")
        return

    heat_df = pd.DataFrame(heat_rows)

    # Ensure all 20 overs present for both innings
    full_overs = list(range(1, 21))
    for lbl in labels.values():
        existing = set(heat_df[heat_df["innings_label"] == lbl]["over"])
        for ov in full_overs:
            if ov not in existing:
                heat_df = pd.concat(
                    [heat_df, pd.DataFrame([{
                        "innings_label": lbl, "over": ov, "runs": 0,
                    }])],
                    ignore_index=True,
                )

    pivot = (
        heat_df.pivot(index="innings_label", columns="over", values="runs")
        .fillna(0)
        .reindex(columns=full_overs, fill_value=0)
    )

    fig = go.Figure(data=go.Heatmap(
        z=pivot.values,
        x=[str(c) for c in pivot.columns],
        y=list(pivot.index),
        colorscale="YlOrRd",
        text=pivot.values.astype(int),
        texttemplate="%{text}",
        textfont={"size": 12, "color": "white"},
        hovertemplate="Over %{x}<br>%{y}<br>Runs: %{z}<extra></extra>",
        colorbar=dict(title="Runs"),
    ))
    fig.update_layout(
        title="Over-by-Over Runs Heatmap",
        xaxis_title="Over", yaxis_title="",
    )
    apply_ipl_style(fig, height=280)
    st.plotly_chart(fig, width='stretch')

    # ── Ball-by-ball detail (expandable) ──
    st.markdown("#### Ball-by-Ball Details")

    available_innings = sorted(balls_df["innings"].unique())
    display_innings = [i for i in available_innings if i <= 2]
    if not display_innings:
        return

    inn_choice = st.selectbox(
        "Select Innings",
        display_innings,
        format_func=lambda x: f"Innings {x}",
        key="obo_innings",
    )
    inn = balls_df[balls_df["innings"] == inn_choice].copy()
    if inn.empty:
        st.info("No data for this innings.")
        return

    overs_bowled = sorted(inn["over"].unique())
    for ov in overs_bowled:
        ov_balls = inn[inn["over"] == ov]
        ov_total = int(ov_balls["runs_batter"].sum() + ov_balls["runs_extras"].sum())
        wk_cnt = int(
            ov_balls[
                ov_balls["player_out"].notna()
                & ov_balls["wicket_kind"].isin(_REAL_WICKETS)
            ].shape[0]
        )
        label = f"Over {ov} — {ov_total} runs"  # overs already 1-indexed
        if wk_cnt:
            label += f", {wk_cnt} wicket{'s' if wk_cnt > 1 else ''}"

        with st.expander(label):
            cols = ["ball", "batter", "bowler", "runs_batter",
                    "runs_extras", "extra_type", "wicket_kind", "player_out"]
            detail = ov_balls[[c for c in cols if c in ov_balls.columns]].copy()
            rename = {
                "ball": "Ball", "batter": "Batter", "bowler": "Bowler",
                "runs_batter": "Runs", "runs_extras": "Extras",
                "extra_type": "Extra Type", "wicket_kind": "Wicket",
                "player_out": "Out",
            }
            detail = detail.rename(columns=rename)
            # Clean sentinel strings used instead of NaN
            for col, sentinel in [("Extra Type", "none"), ("Wicket", "not_out"), ("Out", "none")]:
                if col in detail.columns:
                    detail[col] = detail[col].replace(sentinel, "").fillna("")
            st.dataframe(detail, width='stretch', hide_index=True)


# ─────────────────────────────────────────────────────────────────
# TAB 5 — Match Stats
# ─────────────────────────────────────────────────────────────────


def render_match_stats(match: pd.Series, balls_df: pd.DataFrame):
    """Side-by-side statistical comparison of both innings."""
    team_stats: dict[int, dict] = {}

    for inn_num in [1, 2]:
        inn = balls_df[balls_df["innings"] == inn_num].copy()
        if inn.empty:
            team_stats[inn_num] = {}
            continue

        team = inn["batting_team"].iloc[0]
        total_runs = int(inn["runs_batter"].sum() + inn["runs_extras"].sum())
        vb = int(inn["valid_ball"].astype(int).sum())
        wks = int(
            inn[
                inn["player_out"].notna()
                & inn["wicket_kind"].isin(_REAL_WICKETS)
            ].shape[0]
        )
        fours = int(inn["is_four"].astype(int).sum())
        sixes = int(inn["is_six"].astype(int).sum())
        dots = int(inn["is_dot"].astype(int).sum())
        extras = int(inn["runs_extras"].sum())
        rr = round(total_runs * 6.0 / vb, 2) if vb > 0 else 0.0
        dot_pct = round(dots * 100.0 / vb, 1) if vb > 0 else 0.0

        # Powerplay (overs 1-6)
        pp = inn[inn["over"] <= 6]
        pp_runs = int(pp["runs_batter"].sum() + pp["runs_extras"].sum())

        # Death overs (overs 16-20)
        death = inn[inn["over"] >= 16]
        death_runs = int(death["runs_batter"].sum() + death["runs_extras"].sum())

        team_stats[inn_num] = {
            "_team": team,
            "Runs": total_runs,
            "Wickets": wks,
            "Run Rate": rr,
            "Boundaries (4s+6s)": fours + sixes,
            "Sixes": sixes,
            "Dot Balls": dots,
            "Dot %": f"{dot_pct}%",
            "Extras": extras,
            "Powerplay Score": pp_runs,
            "Death Overs Score": death_runs,
        }

    if not team_stats.get(1) or not team_stats.get(2):
        st.info("Insufficient data for comparison.")
        return

    t1 = team_stats[1]["_team"]
    t2 = team_stats[2]["_team"]
    c1, c2 = get_team_color(t1), get_team_color(t2)

    st.markdown("### Match Statistics Comparison")

    # Header row
    h1, hm, h2 = st.columns([2, 3, 2])
    h1.markdown(
        f"<h4 style='color:{c1};text-align:center'>{t1}</h4>",
        unsafe_allow_html=True,
    )
    hm.markdown(
        "<h4 style='text-align:center;color:#aaa'>Stat</h4>",
        unsafe_allow_html=True,
    )
    h2.markdown(
        f"<h4 style='color:{c2};text-align:center'>{t2}</h4>",
        unsafe_allow_html=True,
    )

    stat_keys = [
        "Runs", "Wickets", "Run Rate", "Boundaries (4s+6s)", "Sixes",
        "Dot Balls", "Dot %", "Extras", "Powerplay Score", "Death Overs Score",
    ]
    for stat in stat_keys:
        v1 = team_stats[1].get(stat, "-")
        v2 = team_stats[2].get(stat, "-")
        c_l, c_m, c_r = st.columns([2, 3, 2])
        c_l.markdown(
            f"<div style='text-align:center;font-size:1.2rem;font-weight:bold'>{v1}</div>",
            unsafe_allow_html=True,
        )
        c_m.markdown(
            f"<div style='text-align:center;color:#aaa'>{stat}</div>",
            unsafe_allow_html=True,
        )
        c_r.markdown(
            f"<div style='text-align:center;font-size:1.2rem;font-weight:bold'>{v2}</div>",
            unsafe_allow_html=True,
        )


# ── Main Page Logic ───────────────────────────────────────────────────────────

st.title("Match Center")

# ── Match Selection (on page, not sidebar) ──
sel_col1, sel_col2 = st.columns([1, 3])

with sel_col1:
    default_idx = ALL_SEASONS.index(2025) if 2025 in ALL_SEASONS else len(ALL_SEASONS) - 1
    season = st.selectbox("Season", ALL_SEASONS, index=default_idx, key="mc_season")

matches_df = load_season_matches(int(season))
if matches_df.empty:
    st.warning(f"No matches found for {season}.")
    st.stop()

# Build human-readable labels sorted by date
matches_df = matches_df.sort_values("date").reset_index(drop=True)
matches_df["_label"] = matches_df.apply(
    lambda r: (
        f"{r['team1']} vs {r['team2']} -- "
        f"{pd.to_datetime(r['date']).strftime('%d %b %Y')} -- "
        f"{r['venue']}"
    ),
    axis=1,
)

with sel_col2:
    selected_label = st.selectbox("Select Match", matches_df["_label"].tolist(), key="mc_match")

# ── Load selected match data ──
match_row = matches_df[matches_df["_label"] == selected_label].iloc[0]
match_id = int(match_row["match_id"])

balls_df = load_match_balls(match_id)
partnerships_df = load_match_partnerships(match_id)

if balls_df.empty:
    st.warning("No ball-by-ball data available for this match.")
    st.stop()

# ── Header (always visible) ──
render_header(match_row)

# ── Tabs ──
tab_sc, tab_worm, tab_part, tab_obo, tab_stats = st.tabs([
    "Scorecard",
    "Worm Chart",
    "Partnerships",
    "Over-by-Over",
    "Match Stats",
])

with tab_sc:
    render_scorecard(match_row, balls_df)

with tab_worm:
    render_worm(match_row, balls_df)

with tab_part:
    render_partnerships(match_row, balls_df, partnerships_df)

with tab_obo:
    render_over_by_over(match_row, balls_df)

with tab_stats:
    render_match_stats(match_row, balls_df)
