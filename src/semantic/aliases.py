"""Alias maps and unsupported metadata markers for semantic parsing."""

PHASE_ALIASES = {
    "powerplay": "powerplay",
    "power play": "powerplay",
    "middle": "middle",
    "middle overs": "middle",
    "middle phase": "middle",
    "death": "death",
    "death overs": "death",
    "death phase": "death",
}

STAGE_ALIASES = {
    "league": ["League"],
    "playoff": ["Eliminator", "Elimination Final", "Qualifier 1", "Qualifier 2", "Semi Final", "Final", "3rd Place Play-Off"],
    "playoffs": ["Eliminator", "Elimination Final", "Qualifier 1", "Qualifier 2", "Semi Final", "Final", "3rd Place Play-Off"],
    "knockout": ["Eliminator", "Elimination Final", "Qualifier 1", "Qualifier 2", "Semi Final", "Final", "3rd Place Play-Off"],
    "final": ["Final"],
}

UNSUPPORTED_KEYWORDS = {
    "captain": "captaincy filters are not available in the current dataset",
    "captaincy": "captaincy filters are not available in the current dataset",
    "uncapped": "uncapped-player metadata is not available in the current dataset",
    "wicketkeeper": "role metadata like wicketkeeper is not fully modeled in the current dataset",
    "left arm": "bowling-style metadata is not available in the current dataset",
    "right arm": "bowling-style metadata is not available in the current dataset",
    "overseas": "nationality metadata is not available in the current dataset",
    "indian": "nationality metadata is not available in the current dataset",
}
