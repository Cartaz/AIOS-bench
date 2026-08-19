def monthly_total(values):
    """Sum a list of numeric values.

    Converts each element to float to handle int/float/mixed numeric types.
    Raises TypeError for non-numeric values (e.g., strings that aren't numeric).
    """
    total = 0.0
    for value in values:
        total += float(value)
    return total


if __name__ == "__main__":
    print(monthly_total([10, 20, 30]))
