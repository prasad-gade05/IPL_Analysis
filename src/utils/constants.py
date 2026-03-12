"""IPL team colors, phase definitions, and other constants."""

TEAM_COLORS = {
    "Chennai Super Kings": "#FFFF00",
    "Mumbai Indians": "#004BA0",
    "Royal Challengers Bengaluru": "#EC1C24",
    "Royal Challengers Bangalore": "#EC1C24",
    "Kolkata Knight Riders": "#3A225D",
    "Delhi Capitals": "#004C93",
    "Delhi Daredevils": "#004C93",
    "Rajasthan Royals": "#EA1A85",
    "Sunrisers Hyderabad": "#FF822A",
    "Punjab Kings": "#ED1B24",
    "Kings XI Punjab": "#ED1B24",
    "Gujarat Titans": "#1C1C1C",
    "Lucknow Super Giants": "#A72056",
    # Legacy / Defunct
    "Deccan Chargers": "#1C1C1C",
    "Kochi Tuskers Kerala": "#6F2DA8",
    "Pune Warriors India": "#2F9BE3",
    "Gujarat Lions": "#E04F16",
    "Rising Pune Supergiants": "#6F2DA8",
    "Rising Pune Supergiant": "#6F2DA8",
}

PHASE_COLORS = {
    "powerplay": "#FF6B6B",
    "middle": "#4ECDC4",
    "death": "#45B7D1",
}

PHASE_OVER_RANGES = {
    "powerplay": (1, 6),
    "middle": (7, 15),
    "death": (16, 20),
}

BATTING_POSITION_LABELS = {
    "top_order": "Top Order (1-3)",
    "middle_order": "Middle Order (4-5)",
    "lower_middle": "Lower Middle (6-7)",
    "tail": "Tail (8-11)",
}

# Team name standardization mapping
TEAM_NAME_MAP = {
    "Royal Challengers Bangalore": "Royal Challengers Bengaluru",
    "Delhi Daredevils": "Delhi Capitals",
    "Kings XI Punjab": "Punjab Kings",
    "Rising Pune Supergiant": "Rising Pune Supergiants",
    "Pune Warriors": "Pune Warriors India",
}

# Season string → integer year mapping
SEASON_MAP = {
    "2007/08": 2008, "2009": 2009, "2009/10": 2010,
    "2011": 2011, "2012": 2012, "2013": 2013, "2014": 2014,
    "2015": 2015, "2016": 2016, "2017": 2017, "2018": 2018,
    "2019": 2019, "2020/21": 2020, "2021": 2021,
    "2022": 2022, "2023": 2023, "2024": 2024, "2025": 2025,
}

STAGE_ORDER = {
    "League": 0,
    "Eliminator": 1,
    "Qualifier 1": 2,
    "Qualifier 2": 3,
    "Semi Final": 3,
    "Final": 4,
}

ALL_SEASONS = list(range(2008, 2026))
