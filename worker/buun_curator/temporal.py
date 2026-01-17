"""
Temporal client configuration.

Provides a configured Temporal client with Pydantic v2 data converter support.
"""

from collections.abc import Sequence

from temporalio.client import Client, Interceptor
from temporalio.contrib.pydantic import pydantic_data_converter

from buun_curator.config import get_config


async def get_temporal_client(
    interceptors: Sequence[Interceptor] | None = None,
) -> Client:
    """
    Create a Temporal client with Pydantic v2 data converter.

    Parameters
    ----------
    interceptors : Sequence[Interceptor] | None, optional
        Interceptors to apply to the client (e.g., TracingInterceptor).

    Returns
    -------
    Client
        Configured Temporal client.
    """
    config = get_config()
    return await Client.connect(
        config.temporal_host,
        namespace=config.temporal_namespace,
        data_converter=pydantic_data_converter,
        interceptors=interceptors or [],
    )
