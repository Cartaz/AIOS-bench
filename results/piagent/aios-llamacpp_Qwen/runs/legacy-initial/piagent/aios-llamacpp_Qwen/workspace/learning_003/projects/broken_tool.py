def monthly_total(values):
    total = 0
    for value in values:
        total += float(value)
    return total


def monthly_summary(revenues, units):
    total_revenue = monthly_total(revenues)
    total_units = monthly_total(units)
    return {
        "total_revenue": total_revenue,
        "total_units": total_units
    }


if __name__ == "__main__":
    result = monthly_total([10, 20, "30"])
    print(result)
    summary = monthly_summary([100, 80, 120, 100, 100, 80], [10, 4, 12, 2, 5, 8])
    print(summary)
