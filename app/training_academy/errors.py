class TrainingAcademyError(Exception):
    """Base error for training academy workflows."""


class TrainingAcademyDataError(TrainingAcademyError):
    """Raised when training academy data is missing or invalid."""
