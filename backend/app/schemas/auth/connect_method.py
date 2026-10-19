from enum import StrEnum


class ConnectMethod(StrEnum):
    """How a person attaches this provider from the pairing page."""

    OAUTH = "oauth"
    API_KEY = "api_key"
    SDK = "sdk"
