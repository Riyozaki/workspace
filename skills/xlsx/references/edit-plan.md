# XLSX preservation-safe edit plans

Apply with:

```bash
scripts/documentctl xlsx-edit source.xlsx result.xlsx --plan plan.json
```

Example:

```json
{
  "updates": [
    {
      "sheet": "Assumptions",
      "cell": "B3",
      "expected": 0.08,
      "value": 0.06
    },
    {
      "sheet": "Summary",
      "cell": "B10",
      "expected": "=SUM(Data!B2:B9)",
      "formula": "=SUM(Data!B2:B9)*$B$3"
    }
  ],
  "metadata": {"description": "Downside scenario"}
}
```

## Guarantees

- The plan is schema-validated before editing.
- `expected` provides optimistic concurrency and protects against editing the wrong workbook/version.
- Existing style IDs are preserved.
- Strings are written as inline strings, avoiding shared-string table rewrites.
- Untouched package members remain byte-identical.
- Formula changes remove a stale calculation chain and force full recalculation on open.
- Output is not written if any operation fails.

## Intentional limits

The direct editor refuses:

- a sheet or cell that does not exist when required by the plan;
- updates to a non-anchor cell inside a merged range;
- replacing one member of a shared, array, or data-table formula group;
- changing style/number-format definitions through a cell plan;
- macro-enabled fidelity claims.

For broad restyling or structural redesign, create a new workbook from a reviewed spec. For a complex third-party workbook, prefer narrow value/formula updates and compare package-part hashes before delivery.
