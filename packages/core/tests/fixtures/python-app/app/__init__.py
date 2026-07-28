"""Fixture app for arena tests - contains a deliberately broken discount.

Bug: the 10% discount is applied for subtotals over $100 instead of $50,
so the two discount tests fail at baseline. The fix is a one-line change.
"""


def calc_total(items):
    """Sum item prices and apply a 10% discount over $50."""
    subtotal = sum(item["price"] for item in items)
    if subtotal > 100:  # bug: should be 50
        return subtotal * 0.9
    return subtotal
