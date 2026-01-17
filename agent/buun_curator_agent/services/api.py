"""Base API service for Next.js API calls."""

import httpx


class APIService:
    """Base service for making API calls to Next.js backend."""

    def __init__(self, api_base_url: str, api_token: str = "") -> None:
        """
        Initialize the API service.

        Parameters
        ----------
        api_base_url : str
            Base URL of the Next.js API.
        api_token : str, optional
            Token for authenticating internal API calls (default: "").
        """
        self.api_base_url = api_base_url.rstrip("/")
        self.api_token = api_token

    def _get_headers(self) -> dict[str, str]:
        """
        Get common headers for API requests.

        Returns
        -------
        dict[str, str]
            Headers including Authorization if token is set.
        """
        headers: dict[str, str] = {}
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"
        return headers

    def _get_client(self, timeout: float = 30.0) -> httpx.AsyncClient:
        """
        Create an async HTTP client.

        Parameters
        ----------
        timeout : float, optional
            Request timeout in seconds (default: 30.0).

        Returns
        -------
        httpx.AsyncClient
            Configured async HTTP client.
        """
        return httpx.AsyncClient(timeout=timeout)
