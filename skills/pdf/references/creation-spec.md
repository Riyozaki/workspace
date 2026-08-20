# Declarative PDF creation

`pdf-create` uses ReportLab with embedded Unicode fonts, deterministic styles, repeated table headers, outlines, and a multi-pass table of contents.

Supported top-level features:

- A4/Letter, portrait/landscape, margins;
- metadata, header, footer and page number;
- optional cover and generated TOC;
- restrained color theme.

Content blocks:

- heading levels 1–3;
- paragraphs with rich runs, color, emphasis, and links;
- bullets;
- repeated-header tables;
- callouts;
- images and captions;
- deterministic chart images;
- page breaks and controlled spacers.

Example:

```json
{
  "metadata": {"title": "Assessment", "author": "Review team"},
  "header": "Assessment",
  "footer": "Confidential",
  "toc": true,
  "content": [
    {"type": "heading", "level": 1, "text": "Summary"},
    {
      "type": "paragraph",
      "runs": [
        {"text": "Decision: ", "bold": true},
        {"text": "approved", "color": "26734D"}
      ]
    }
  ]
}
```

PDFs are final-layout artifacts. If the user expects later collaborative editing, create a DOCX alongside or instead of PDF.
