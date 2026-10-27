"""Livestock metrics utilities."""


def calculate_fcr(feed_consumed_kg, weight_gain_kg):
    """
    Calculate Feed Conversion Ratio (FCR).

    FCR = feed_consumed_kg / weight_gain_kg

    Args:
        feed_consumed_kg (int | float): Total feed consumed in kilograms.
        weight_gain_kg (int | float): Total weight gain in kilograms.

    Returns:
        float | int: Numeric result of feed_consumed_kg / weight_gain_kg.

    Raises:
        TypeError: If either parameter is not of type int or float, or if bool.
        ValueError: If either parameter is negative, or if weight_gain_kg == 0.
    """
    # Strict numeric type validation: allow int/float but exclude bool
    if isinstance(feed_consumed_kg, bool) or not isinstance(feed_consumed_kg, (int, float)):
        raise TypeError("feed_consumed_kg must be numeric (int or float)")

    if isinstance(weight_gain_kg, bool) or not isinstance(weight_gain_kg, (int, float)):
        raise TypeError("weight_gain_kg must be numeric (int or float)")

    # Non-negativity validation
    if feed_consumed_kg < 0 or weight_gain_kg < 0:
        raise ValueError("feed_consumed_kg and weight_gain_kg must be >= 0")

    # Division by zero validation (must be explicit and before division)
    if weight_gain_kg == 0:
        raise ValueError("weight_gain_kg cannot be 0")

    # Valid calculation
    result = feed_consumed_kg / weight_gain_kg
    return result
