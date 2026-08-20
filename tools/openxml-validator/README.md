# Open XML schema validator

Optional second validation layer using Microsoft's MIT-licensed Open XML SDK.

```bash
dotnet run --project tools/openxml-validator/OpenXmlValidator.csproj -- file.docx
```

The project pins `DocumentFormat.OpenXml` 3.3.0 and targets .NET 8. Build output is ignored by Git. `documentctl validate` invokes it automatically when `dotnet` is available; use `--require-openxml-sdk` to make absence a validation error.

This validator checks schema/semantic constraints understood by the SDK. It does not render the document and does not replace visual QA or a Microsoft Office compatibility test.
