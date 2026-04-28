def format_inr(value: float) -> str:
    """Format a number in Indian number system."""
    if value is None:
        return "₹0"
    return f"₹{value:,.0f}"
