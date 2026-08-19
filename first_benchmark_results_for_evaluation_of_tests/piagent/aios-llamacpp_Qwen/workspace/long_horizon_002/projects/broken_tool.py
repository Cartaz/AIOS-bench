def monthly_total(values):
    total = 0
    for value in values:
        total += float(value)
    return total


if __name__ == "__main__":
    print(monthly_total([10, 20, "30"]))
