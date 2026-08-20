class DocumentSystemError(RuntimeError):
    """Base error with a user-actionable message."""


class UnsafeArchiveError(DocumentSystemError):
    """The input package violates an archive safety policy."""


class UnsupportedDocumentError(DocumentSystemError):
    """The input format or requested operation is unsupported."""


class ToolUnavailableError(DocumentSystemError):
    """A required external renderer or converter is unavailable."""


class ValidationFailure(DocumentSystemError):
    """A document did not pass a required validation gate."""
