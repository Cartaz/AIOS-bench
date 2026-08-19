def monthly_total(values):
    """Return the sum of numeric values (ints, floats, or numeric strings)."""
    total = 0
    for value in values:
        total += float(value)
    return total


if __name__ == "__main__":
    result = monthly_total([10, 20, "30"])
    print(result)
