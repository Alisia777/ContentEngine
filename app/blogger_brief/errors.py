class BloggerBriefError(Exception):
    """Base error for blogger meaning and UGC script workflows."""


class BloggerBriefDataError(BloggerBriefError):
    """Raised when required product, demand, or variant data is missing."""
