def monthly_total(values):
    total = 0
    for value in values:
        total += float(value)
    # Return int if the result is a whole number, otherwise float
    return int(total) if total == int(total) else total


if __name__ == "__main__":
    print(monthly_total([10, 20, "30"]))
