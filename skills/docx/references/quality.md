# DOCX quality and compatibility checklist

## Structural gate

- ZIP CRC and archive safety pass.
- Required OPC parts and officeDocument relationship exist.
- Every internal relationship resolves.
- Every part has a content type.
- XML parses with DTD/entities disabled.
- Drawing IDs do not collide.
- Macros, embedded objects, and external links are inventoried.

## Semantic gate

- Required title, sections, names, dates, units, figures, and disclaimers are present.
- No TODO/TBD/template placeholders remain.
- Tables contain the expected row and column values.
- Headings use real styles and have a coherent hierarchy.
- Header/footer/PAGE/TOC fields exist when required.
- Comments and tracked changes are anchored and attributed.
- Accepted and rejected revision views both make sense for redlined documents.

## Visual gate

Render to page images and inspect:

- cover hierarchy and contrast;
- body font size and line length;
- heading orphaning and paragraph widows;
- unwanted blank pages;
- table width, row splitting, repeated headers, clipped cells;
- images, chart labels, captions, and resolution;
- header/footer collisions;
- page numbering and TOC behavior;
- edge clipping or content outside margins;
- consistent spacing and alignment.

A contact sheet is an overview, not a replacement for viewing pages containing dense tables, charts, small print, or suspicious wrapping.

## Preservation gate for edits

Run `documentctl diff` and explain every changed package part. Typical expected changes:

- `word/document.xml` for body edits;
- a specific header/footer part for scoped replacements;
- `word/comments.xml`, main relationships, and content types for first comments;
- `word/settings.xml` when enabling revision tracking;
- `docProps/core.xml` for metadata.

Unexplained changes to styles, numbering, themes, media, section properties, charts, embedded objects, or unrelated stories are defects.

## Compatibility statement

LibreOffice is a smoke test and rendering oracle for this Linux environment. It is not Microsoft Word. Complex fields, SmartArt, charts, fonts, tracked changes, content controls, equations, and vendor extensions may behave differently. For high-stakes distribution, add a Microsoft Word review or future Office compatibility worker.
