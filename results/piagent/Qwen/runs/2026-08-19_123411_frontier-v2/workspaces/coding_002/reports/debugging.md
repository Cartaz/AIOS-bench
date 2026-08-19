# Debugging Report: broken_tool.py — `monthly_total` TypeError

## Summary

The `monthly_total` function in `projects/broken_tool.py` raised a `TypeError`
when called with a list containing string-represented numbers (e.g. `"30"`).

## Reproduction

```python
>>> from projects.broken_tool import monthly_total
>>> monthly_total([10, 20, "30"])
TypeError: unsupported operand type(s) for +=: 'int' and 'str'
```

Running the script directly:
```
$ python3 projects/broken_tool.py
Traceback (most recent call last):
  File "projects/broken_tool.py", line 9, in <module>
    print(monthly_total([10, 20, "30"]))
  File "projects/broken_tool.py", line 4, in monthly_total
    total += value
TypeError: unsupported operand type(s) for +=: 'int' and 'str'
```

## Root Cause

The `monthly_total` function initialised `total` as an `int` and performed
`total += value` in a loop. When `value` was a `str` (e.g. `"30"`), Python
raised `TypeError` because it cannot add an `int` and a `str` with `+=`.

The function was not defensive about input types — it assumed all elements
were numeric (int or float).

## Fix

Changed line 4 from:
```python
        total += value
```
to:
```python
        total += float(value)
```

This ensures every element is converted to `float` before addition, handling
integers, floats, and string-represented numbers uniformly.

## Regression Test

Added `projects/test_broken_tool.py` with 8 tests covering:
- Sum of integers
- Sum of floats
- Empty list
- Negative values
- Single value
- String-only numbers
- Mixed int/string types (the original failing case)
- Return type check (result is `float`)

## Verification

```
$ pytest projects/test_broken_tool.py -v
8 passed in 0.01s
```

Direct execution also works:
```
$ python3 projects/broken_tool.py
60.0
```
