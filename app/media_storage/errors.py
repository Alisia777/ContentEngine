class StorageError(Exception):
    """Base object-storage failure safe to translate at an API boundary."""


class StorageNotFound(StorageError):
    """The requested object does not exist in the configured backend."""


class StorageSecurityError(StorageError):
    """A key, signature, or backend response violated a storage boundary."""


class MediaArtifactError(Exception):
    """Base media-artifact domain error."""


class MediaArtifactOwnershipError(MediaArtifactError):
    """The actor or linked entity is outside the requested organization."""


class MediaArtifactStateError(MediaArtifactError):
    """The artifact is not in a state that allows the requested operation."""
