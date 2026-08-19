def monthly_total(values):
    """Sum a list of numeric values, converting strings to numbers.

    This is a reusable procedure for computing monthly totals from
    data sources (e.g. CSV rows) where numeric fields may arrive as
    strings.  The original version silently failed on string inputs,
    which could produce incorrect results when used in a pipeline.
    """
    total = 0
    for value in values:
        total += float(value)
    return total


if __name__ == "__main__":
    # Demonstrate the fix handles string-formatted numbers correctly
    result = monthly_total([10, 20, "30"])
    print(f"monthly_total([10, 20, '30']) = {result}")
