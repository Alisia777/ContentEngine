class VideoGeneratorError(RuntimeError):
    """Base error for spec-driven video generation."""


class VideoGeneratorDataError(VideoGeneratorError):
    """Raised when a spec-driven generation input is missing or invalid."""
