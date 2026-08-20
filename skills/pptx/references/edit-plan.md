# PPTX preservation-safe edit plans

Apply with:

```bash
scripts/documentctl pptx-edit source.pptx result.pptx --plan plan.json
```

## Text and speaker notes

```json
{
  "replacements": [
    {
      "find": "two pilot teams",
      "replace": "three pilot teams",
      "expected": 1,
      "slides": [1],
      "include_notes": true
    },
    {
      "find": "31 October",
      "replace": "7 November",
      "expected": 1,
      "slides": [8, 9]
    }
  ]
}
```

Visible phrases often span multiple DrawingML runs. The editor maps text across runs and rebuilds only the affected range using the first/last run properties. It does not perform raw XML string replacement.

## Media replacement

```json
{
  "media_replacements": [
    {
      "part": "ppt/media/image3.png",
      "path": "assets/new-product.png",
      "expected_sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    }
  ]
}
```

The replacement must retain the existing image format so content types and relationships remain valid. The optional SHA-256 prevents replacing the wrong image in a changed template. Existing crop and placement remain intact because only media bytes change.

## Structural slide plan

Run structural operations before text/media edits:

```json
{
  "duplicate": [{"slide": 3, "after": 3}],
  "delete": [2],
  "order": [3, 1, 2],
  "clean_orphans": true
}
```

`pptx-structure` registers duplicated slides, deletes and reorders by presentation order, and recursively removes unreferenced charts, media, embedded workbooks, notes and diagrams. Duplicates share referenced chart/media assets and omit notes rather than creating invalid shared notes ownership.

## Guarantees and limits

- Plan validation and expected counts make edits atomic.
- Slide numbers follow presentation order, not `slideN.xml` filenames.
- Notes parts are resolved through slide relationships.
- Unrelated slides, layouts, masters, themes, charts, and media remain byte-identical.
- The first implementation edits text runs and same-format image media. Structural slide rearrangement, master editing, chart-data mutation, comments, and animations require dedicated tested routes rather than ad-hoc XML.
