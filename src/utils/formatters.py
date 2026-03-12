"""Number and text formatting utilities."""


def format_number(n, decimals=0):
    """Format a number with commas and optional decimal places."""
    if n is None:
        return "N/A"
    if decimals == 0:
        return f"{int(n):,}"
    return f"{n:,.{decimals}f}"


def format_runs(runs):
    """Format runs with commas."""
    return format_number(runs)


def format_strike_rate(sr):
    """Format strike rate to 1 decimal."""
    if sr is None:
        return "N/A"
    return f"{sr:.1f}"


def format_economy(econ):
    """Format economy rate to 2 decimals."""
    if econ is None:
        return "N/A"
    return f"{econ:.2f}"


def format_average(avg):
    """Format batting/bowling average to 2 decimals."""
    if avg is None:
        return "N/A"
    return f"{avg:.2f}"


def format_overs(balls):
    """Convert ball count to overs.balls format (e.g., 24 balls = 4.0 overs)."""
    if balls is None:
        return "N/A"
    complete_overs = balls // 6
    remaining = balls % 6
    return f"{complete_overs}.{remaining}"


def format_percentage(pct):
    """Format a percentage to 1 decimal."""
    if pct is None:
        return "N/A"
    return f"{pct:.1f}%"
