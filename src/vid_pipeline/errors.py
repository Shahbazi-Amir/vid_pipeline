"""Project-specific exceptions."""


class PipelineError(RuntimeError):
    """Base exception for recoverable pipeline failures."""


class ConfigurationError(PipelineError):
    """Raised when an episode specification is invalid."""


class ExternalToolError(PipelineError):
    """Raised when an external command or optional dependency fails."""


class ReviewRequiredError(PipelineError):
    """Raised when an operation requires a reviewed transcript."""
