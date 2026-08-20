# PPTX quality checklist

## Narrative

- Deck has a clear opening, evidence sequence, decision, and next step.
- Each slide title communicates a conclusion.
- Adjacent slides do not repeat the same claim.
- Data, caveats, and sources support the conclusion.
- Speaker notes contain delivery context without contradicting visible content.

## Content and geometry

- No unresolved placeholders.
- No out-of-bounds shapes.
- No likely text overflow or clipped table cells.
- Overlaps are intentional backgrounds/cards, not collisions.
- Body text is readable at presentation distance.
- Alignment, gutters, title position, footers, and slide numbers are consistent.
- Tables are not overloaded; charts have compatible units and legible labels.
- Images are high resolution and intentionally cropped.

## Package integrity

- All internal relationships resolve.
- Native chart embedded XLSX parts are present.
- Media references are complete.
- No unexpected OLE, macros, external templates, or linked images.
- Open XML SDK validation passes when available.
- Template edits change only expected slide/notes/media/core-property parts.

## Visual QA

1. Render the complete PPTX to PDF through isolated LibreOffice.
2. Confirm rendered page count equals slide count.
3. Review the contact sheet for rhythm, density, palette, and alignment.
4. Open every slide with a table, chart, dense text, or image crop individually.
5. Fix the source spec/edit plan and rerender all slides.

LibreOffice is a smoke test. Complex fonts, animations, SmartArt, charts, and vendor extensions still require PowerPoint review for high-stakes delivery.
