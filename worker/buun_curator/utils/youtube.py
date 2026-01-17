"""
YouTube URL detection utilities.
"""

import re

# YouTube URL patterns
_YOUTUBE_PATTERNS = [
    # Standard watch URL: youtube.com/watch?v=VIDEO_ID
    re.compile(r"(?:https?://)?(?:www\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})"),
    # Short URL: youtu.be/VIDEO_ID
    re.compile(r"(?:https?://)?youtu\.be/([a-zA-Z0-9_-]{11})"),
    # Embed URL: youtube.com/embed/VIDEO_ID
    re.compile(r"(?:https?://)?(?:www\.)?youtube\.com/embed/([a-zA-Z0-9_-]{11})"),
    # Shorts URL: youtube.com/shorts/VIDEO_ID
    re.compile(r"(?:https?://)?(?:www\.)?youtube\.com/shorts/([a-zA-Z0-9_-]{11})"),
]


def extract_youtube_video_id(url: str) -> str | None:
    """
    Extract YouTube video ID from a URL.

    Parameters
    ----------
    url : str
        The URL to check.

    Returns
    -------
    str | None
        The YouTube video ID if found, None otherwise.
    """
    for pattern in _YOUTUBE_PATTERNS:
        match = pattern.search(url)
        if match:
            return match.group(1)
    return None


def is_youtube_url(url: str) -> bool:
    """
    Check if a URL is a YouTube video URL.

    Parameters
    ----------
    url : str
        The URL to check.

    Returns
    -------
    bool
        True if the URL is a YouTube video URL, False otherwise.
    """
    return extract_youtube_video_id(url) is not None
