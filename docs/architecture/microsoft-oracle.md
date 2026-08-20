# Optional Microsoft Office compatibility oracle

LibreOffice WASM and Microsoft Open XML SDK now run locally in Arena. The remaining renderer diversity tier is Microsoft’s own Office conversion engine.

## Provider

The optional provider uses Microsoft Graph DriveItem conversion:

1. upload the Office file to the authenticated user’s OneDrive root under a random temporary name;
2. request `GET /me/drive/items/{id}/content?format=pdf`;
3. download the pre-signed PDF without forwarding the bearer token;
4. delete the temporary DriveItem;
5. compare Microsoft and LibreOffice PDFs semantically and visually.

## Explicit opt-in

The provider is disabled unless the caller supplies an access token in the process environment:

```bash
export MS_GRAPH_ACCESS_TOKEN='short-lived delegated token'
scripts/documentctl microsoft-oracle report.docx \
  -o .document-work/microsoft-oracle/report
```

The repository never requests, stores, logs, or commits Microsoft credentials. The command is not part of default workflows because it uploads document content outside Arena.

Required delegated access must permit the caller to create/read/delete files in their own OneDrive. Use a short-lived token and an appropriately isolated test account.

## Output

- LibreOffice-rendered PDF and pages;
- Microsoft Graph-rendered PDF;
- semantic PDF text diff;
- per-page visual difference PNGs;
- changed-pixel ratio, RMS and bounding boxes;
- input/output hashes;
- `oracle-report.json`.

## Limits

- Graph conversion has a 30 MB input ceiling in this adapter.
- Encrypted or rights-managed files are not supported.
- Microsoft cloud rendering can still differ from desktop Word/Excel/PowerPoint.
- Network access to Microsoft Graph is currently blocked in the interactive Arena sandbox.
- A true desktop Office oracle still requires an approved Windows/M365 worker.

The interface is ready, but live execution depends on the user’s Microsoft environment and data-governance approval.
