def monthly_total(values):
    """Sum a list of numeric values, converting strings to float first."""
    total = 0
    for value in values:
        total += float(value)
    return total


if __name__ == "__main__":
    print(monthly_total([10, 20, "30"]))
