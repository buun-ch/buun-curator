"""
URL normalization utilities.

Provides URL normalization for deduplication purposes.
"""

from urllib.parse import urlparse

from url_normalize import url_normalize


def normalize_url_for_dedup(url: str) -> str:
    """
    Normalize URL for deduplication.

    Applies the following normalizations:
    - Lowercase scheme and host
    - Remove default ports (80 for HTTP, 443 for HTTPS)
    - Remove query parameters
    - Remove fragment (#section)
    - Remove trailing slash (except for root path)

    Parameters
    ----------
    url : str
        The URL to normalize.

    Returns
    -------
    str
        Normalized URL suitable for deduplication.

    Examples
    --------
    >>> normalize_url_for_dedup("http://example.com")
    'http://example.com/'
    >>> normalize_url_for_dedup("http://example.com/?foo=1")
    'http://example.com/'
    >>> normalize_url_for_dedup("HTTP://EXAMPLE.COM/Path#sec")
    'http://example.com/Path'
    """
    # Use url-normalize for standard normalization (lowercase, port removal)
    # filter_params=True with empty allowlist removes all query params
    normalized = url_normalize(url, filter_params=True, param_allowlist=[])

    # Remove fragment and trailing slash
    parsed = urlparse(normalized)
    # urlparse returns str when given str input, but type hints say str | bytes
    scheme = str(parsed.scheme)
    netloc = str(parsed.netloc)
    path = str(parsed.path).rstrip("/") or "/"
    # Construct URL without query and fragment
    return f"{scheme}://{netloc}{path}"
