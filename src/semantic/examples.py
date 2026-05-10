"""Supported semantic example prompts."""

SUPPORTED_EXAMPLES = [
    {"category": "Near misses", "prompt": "Who has the most 49s?"},
    {"category": "Near misses", "prompt": "Who has the most 99s in losses since 2020?"},
    {"category": "Near misses", "prompt": "Who has the most 90s without a hundred?"},
    {"category": "Batting setbacks", "prompt": "Who has the most ducks?"},
    {"category": "Batting setbacks", "prompt": "Who has the most golden ducks?"},
    {"category": "Bowling feats", "prompt": "Which bowlers have the most 4-fors without a 5-for?"},
    {"category": "Sequence events", "prompt": "Which bowlers have the most hat-tricks?"},
    {"category": "Sequence events", "prompt": "Show all hat-tricks in IPL history."},
    {"category": "Sequence events", "prompt": "Which overs had the most wickets?"},
    {"category": "Sequence events", "prompt": "Which bowlers have the most maidens?"},
    {"category": "Sequence events", "prompt": "Which bowlers have the most wicket maidens?"},
    {"category": "Sequence events", "prompt": "Which bowlers have the most perfect overs?"},
    {"category": "Sequence events", "prompt": "Which bowlers have the longest wicket streaks?"},
    {"category": "Sequence events", "prompt": "Which bowlers have the longest consecutive maiden streaks?"},
    {"category": "Sequence events", "prompt": "Who has the longest dot-ball streak as a batter?"},
    {"category": "Sequence events", "prompt": "Which bowlers have the longest dot-ball streaks?"},
    {"category": "Sequence events", "prompt": "Who has the longest boundary streak?"},
    {"category": "Sequence events", "prompt": "Who has the longest scoring-shot streak?"},
    {"category": "Innings shape", "prompt": "Who faced the most balls in an IPL innings?"},
    {"category": "Over anomalies", "prompt": "What is the longest over ever bowled?"},
    {"category": "Over anomalies", "prompt": "What are the most expensive overs at Wankhede Stadium?"},
    {"category": "Over anomalies", "prompt": "Which overs had the most wides?"},
    {"category": "Over anomalies", "prompt": "Which overs had the most extras?"},
    {"category": "Over anomalies", "prompt": "Which overs had the most sixes?"},
    {"category": "Discipline", "prompt": "Which bowlers have bowled the most no-balls since 2020?"},
    {"category": "Dismissals", "prompt": "Who has been caught the most?"},
    {"category": "Dismissals", "prompt": "Who has been bowled the most?"},
    {"category": "Dismissals", "prompt": "Which bowlers have the most LBWs?"},
    {"category": "Streaks", "prompt": "Which teams have the longest winning streaks?"},
    {"category": "Streaks", "prompt": "Who has the most consecutive 20+ scores?"},
    {"category": "Streaks", "prompt": "Who has the longest no-duck streak?"},
    {"category": "Consistency", "prompt": "Who has the most seasons with 400+ runs?"},
    {"category": "Consistency", "prompt": "Who has the most consecutive seasons with 400+ runs?"},
    {"category": "Evergreen", "prompt": "Who has the most runs?"},
    {"category": "Evergreen", "prompt": "Who has the most wickets in death overs?"},
    {"category": "Evergreen", "prompt": "Who has hit the most sixes for Chennai Super Kings?"},
    {"category": "Season honors", "prompt": "Show Orange Cap history."},
    {"category": "Season honors", "prompt": "Show Purple Cap history."},
    {"category": "Chases", "prompt": "What are the highest successful chases?"},
    {"category": "Chases", "prompt": "What are the lowest totals defended in playoffs?"},
]


RELATED_PROMPTS = {
    "most-49s": [
        "Who has the most 99s?",
        "Who has the most 90s without a hundred?",
        "Who has the most 49s in losses?",
        "Who has the most 49s since 2020?",
    ],
    "most-99s": [
        "Who has the most 49s?",
        "Who has the most 90s without a hundred?",
        "Who has the most 99s in wins?",
    ],
    "most-90s": [
        "Who has the most 99s?",
        "Who has the most centuries?",
        "Who has the most 90s without a hundred since 2020?",
    ],
    "most-ducks": [
        "Who has the most golden ducks?",
        "Who has the longest no-duck streak?",
        "Who has been bowled the most?",
    ],
    "most-golden-ducks": [
        "Who has the most ducks?",
        "Who has the longest no-duck streak?",
        "Who has been caught the most?",
    ],
    "four-fors-no-five": [
        "Who has the most wickets?",
        "Who has the most four-wicket hauls?",
        "Who has the most 4-fors without a 5-for since 2020?",
    ],
    "most-hat-tricks": [
        "Show all hat-tricks in IPL history.",
        "Which overs had the most wickets?",
        "Which bowlers have the most wicket maidens?",
    ],
    "all-hat-tricks": [
        "Which bowlers have the most hat-tricks?",
        "Which overs had the most wickets?",
        "Which bowlers have the longest consecutive maiden streaks?",
    ],
    "most-wickets-in-over": [
        "Which bowlers have the most hat-tricks?",
        "Which overs had the most wides?",
        "What are the most expensive overs?",
    ],
    "most-maidens": [
        "Which bowlers have the most wicket maidens?",
        "Which bowlers have the longest consecutive maiden streaks?",
        "Which bowlers have the most wickets?",
    ],
    "most-wicket-maidens": [
        "Which bowlers have the most maidens?",
        "Which bowlers have the most hat-tricks?",
        "Which overs had the most wickets?",
    ],
    "most-perfect-overs": [
        "Which bowlers have the most maidens?",
        "Which bowlers have the most wicket maidens?",
        "Which bowlers have the longest dot-ball streaks?",
    ],
    "wicket-streak": [
        "Which bowlers have the most hat-tricks?",
        "Which bowlers have the most wicket maidens?",
        "Which overs had the most wickets?",
    ],
    "maiden-streak": [
        "Which bowlers have the most maidens?",
        "Which bowlers have the most wicket maidens?",
        "Which bowlers have the longest dot-ball streaks?",
    ],
    "batter-dot-streak": [
        "Which bowlers have the longest dot-ball streaks?",
        "Who has the longest boundary streak?",
        "Who has the longest no-duck streak?",
    ],
    "bowler-dot-streak": [
        "Who has the longest dot-ball streak as a batter?",
        "Which bowlers have the most wicket maidens?",
        "Which bowlers have the longest consecutive maiden streaks?",
    ],
    "boundary-streak": [
        "Who has the longest dot-ball streak as a batter?",
        "Who has the most sixes?",
        "Who has the most consecutive 20+ scores?",
    ],
    "scoring-streak": [
        "Who has the longest boundary streak?",
        "Who has the longest dot-ball streak as a batter?",
        "Who has the most runs?",
    ],
    "most-balls-in-innings": [
        "Who has the most runs?",
        "Who has the longest scoring-shot streak?",
        "Who has the most centuries?",
    ],
    "longest-over": [
        "What are the most expensive overs?",
        "Which overs had the most wides?",
        "Which overs had the most no-balls?",
    ],
    "most-expensive-over": [
        "What is the longest over ever bowled?",
        "Which overs had the most wides?",
        "Which overs had the most no-balls?",
    ],
    "most-wides-over": [
        "What is the longest over ever bowled?",
        "Which bowlers have bowled the most no-balls?",
    ],
    "most-no-balls": [
        "Which overs had the most no-balls?",
        "Which bowlers have the most wides?",
    ],
    "most-extras-over": [
        "Which overs had the most wides?",
        "Which overs had the most no-balls?",
        "What are the most expensive overs?",
    ],
    "most-sixes-over": [
        "Which overs had the most extras?",
        "What are the most expensive overs?",
        "Who has the longest boundary streak?",
    ],
    "batter-dismissal-type": [
        "Who has been caught the most?",
        "Who has been bowled the most?",
        "Which bowlers have the most LBWs?",
    ],
    "bowler-dismissal-type": [
        "Which bowlers have the most LBWs?",
        "Who has been bowled the most?",
        "Which bowlers have the most wickets?",
    ],
    "team-winning-streak": [
        "Which teams have the longest losing streaks?",
        "What are the highest successful chases?",
    ],
    "twenty-plus-streak": [
        "Who has the longest no-duck streak?",
        "Who has the most seasons with 400+ runs?",
    ],
    "no-duck-streak": [
        "Who has the most consecutive 20+ scores?",
        "Who has the most ducks?",
    ],
    "seasons-with-runs-threshold": [
        "Who has the most consecutive seasons with 400+ runs?",
        "Who has the most runs?",
    ],
    "consecutive-seasons-runs-threshold": [
        "Who has the most seasons with 400+ runs?",
        "Who has the most runs since 2020?",
    ],
    "most-runs": [
        "Who has the most sixes?",
        "Who has the most centuries?",
        "Show Orange Cap history.",
    ],
    "most-wickets": [
        "Show Purple Cap history.",
        "Which bowlers have the most 4-fors without a 5-for?",
        "Which bowlers have the most hat-tricks?",
    ],
    "most-sixes": [
        "Who has the most runs?",
        "Who has the most centuries?",
        "Who has the longest boundary streak?",
    ],
    "most-centuries": [
        "Who has the most 90s without a hundred?",
        "Who has the most runs?",
    ],
    "orange-cap-history": [
        "Show Purple Cap history.",
        "Who has the most seasons with 400+ runs?",
    ],
    "purple-cap-history": [
        "Show Orange Cap history.",
        "Who has the most wickets?",
        "Which bowlers have the most hat-tricks?",
    ],
    "highest-successful-chase": [
        "What are the lowest totals defended?",
        "Which teams have the longest winning streaks?",
    ],
    "lowest-defended-total": [
        "What are the highest successful chases?",
        "Which teams have the longest winning streaks?",
    ],
}


def related_prompts(intent_id: str) -> list[str]:
    """Return related prompt suggestions for a supported intent."""
    return RELATED_PROMPTS.get(intent_id, [])
