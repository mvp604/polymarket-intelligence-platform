from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EndpointSettings:
    """
    Immutable configuration for an HTTP or WebSocket endpoint.
    """

    base_url: str
    timeout_seconds: int = 30
    max_retries: int = 3
    rate_limit_per_second: int = 5


@dataclass(frozen=True, slots=True)
class ApiSettings:
    """
    Configuration for all official Polymarket endpoints.
    """

    gamma: EndpointSettings
    data: EndpointSettings
    clob: EndpointSettings
    websocket: EndpointSettings


API_SETTINGS = ApiSettings(
    gamma=EndpointSettings(
        base_url="https://gamma-api.polymarket.com"
    ),
    data=EndpointSettings(
        base_url="https://data-api.polymarket.com"
    ),
    clob=EndpointSettings(
        base_url="https://clob.polymarket.com"
    ),
    websocket=EndpointSettings(
        base_url="wss://ws-subscriptions-clob.polymarket.com/ws"
    ),
)
