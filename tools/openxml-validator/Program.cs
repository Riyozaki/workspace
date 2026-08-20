using System.Text.Json;
using DocumentFormat.OpenXml;
using DocumentFormat.OpenXml.Packaging;
using DocumentFormat.OpenXml.Validation;

if (args.Length != 1)
{
    Console.Error.WriteLine("Usage: openxml-validator FILE.docx|FILE.xlsx|FILE.pptx");
    return 64;
}

var path = Path.GetFullPath(args[0]);
if (!File.Exists(path))
{
    Console.Error.WriteLine($"File not found: {path}");
    return 66;
}

try
{
    using OpenXmlPackage package = Path.GetExtension(path).ToLowerInvariant() switch
    {
        ".docx" or ".dotx" or ".docm" => WordprocessingDocument.Open(path, false),
        ".xlsx" or ".xltx" or ".xlsm" => SpreadsheetDocument.Open(path, false),
        ".pptx" or ".potx" or ".pptm" => PresentationDocument.Open(path, false),
        _ => throw new ArgumentException("Unsupported Open XML extension")
    };

    var validator = new OpenXmlValidator(FileFormatVersions.Microsoft365);
    var errors = validator.Validate(package).ToList();
    var payload = new
    {
        path,
        validator = "DocumentFormat.OpenXml 3.3.0 / Microsoft365",
        valid = errors.Count == 0,
        error_count = errors.Count,
        errors = errors.Take(500).Select(error => new
        {
            description = error.Description,
            error_type = error.ErrorType.ToString(),
            part = error.Part?.Uri.ToString(),
            path = error.Path?.XPath,
            node = error.Node?.LocalName,
            related_node = error.RelatedNode?.LocalName
        }),
        truncated = Math.Max(0, errors.Count - 500)
    };
    Console.WriteLine(JsonSerializer.Serialize(payload, new JsonSerializerOptions { WriteIndented = true }));
    return errors.Count == 0 ? 0 : 2;
}
catch (Exception exception)
{
    var payload = new
    {
        path,
        valid = false,
        fatal = true,
        exception = exception.GetType().FullName,
        message = exception.Message
    };
    Console.WriteLine(JsonSerializer.Serialize(payload, new JsonSerializerOptions { WriteIndented = true }));
    return 2;
}
