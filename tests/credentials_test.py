import io
import json
import urllib.error
from unittest.mock import patch

import pytest

from streamlit_webrtc.credentials import (
    get_available_ice_servers,
    get_cloudflare_ice_servers,
)

CLOUDFLARE_RESPONSE = {
    "iceServers": [
        {"urls": ["stun:stun.cloudflare.com:3478"]},
        {
            "urls": ["turn:turn.cloudflare.com:3478?transport=udp"],
            "username": "user",
            "credential": "secret",
        },
    ]
}


class FakeResponse(io.BytesIO):
    def __init__(self, payload: dict, status: int = 201) -> None:
        super().__init__(json.dumps(payload).encode())
        self.status = status

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


@pytest.fixture(autouse=True)
def clear_caches():
    get_cloudflare_ice_servers.clear()
    get_available_ice_servers.clear()
    yield


@pytest.fixture(autouse=True)
def no_ambient_credentials(monkeypatch: pytest.MonkeyPatch):
    for name in (
        "CLOUDFLARE_TURN_KEY_ID",
        "CLOUDFLARE_TURN_KEY_API_TOKEN",
        "TWILIO_ACCOUNT_SID",
        "TWILIO_AUTH_TOKEN",
        "HF_TOKEN",
    ):
        monkeypatch.delenv(name, raising=False)


def test_get_cloudflare_ice_servers_posts_to_the_turn_key_endpoint():
    with patch(
        "urllib.request.urlopen", return_value=FakeResponse(CLOUDFLARE_RESPONSE)
    ) as urlopen:
        ice_servers = get_cloudflare_ice_servers("key-id", "api-token")

    assert ice_servers == CLOUDFLARE_RESPONSE["iceServers"]

    request = urlopen.call_args.args[0]
    assert request.method == "POST"
    assert request.full_url == (
        "https://rtc.live.cloudflare.com/v1/turn/keys/key-id"
        "/credentials/generate-ice-servers"
    )
    assert request.get_header("Authorization") == "Bearer api-token"
    assert json.loads(request.data)["ttl"] > 0
    # Without a timeout a hung connection would stall the Streamlit script thread.
    assert urlopen.call_args.kwargs["timeout"] > 0


def test_get_cloudflare_ice_servers_escapes_the_key_id():
    with patch(
        "urllib.request.urlopen", return_value=FakeResponse(CLOUDFLARE_RESPONSE)
    ) as urlopen:
        get_cloudflare_ice_servers("a/../b", "api-token")

    assert "a%2F..%2Fb" in urlopen.call_args.args[0].full_url


def test_get_cloudflare_ice_servers_raises_on_a_failed_request():
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("boom")):
        with pytest.raises(ValueError):
            get_cloudflare_ice_servers("key-id", "api-token")


def test_get_cloudflare_ice_servers_raises_on_a_read_timeout():
    # A read that times out inside the `with` raises TimeoutError, not URLError.
    with patch("urllib.request.urlopen", side_effect=TimeoutError("timed out")):
        with pytest.raises(ValueError):
            get_cloudflare_ice_servers("key-id", "api-token")


def test_get_cloudflare_ice_servers_raises_on_a_response_without_ice_servers():
    with patch("urllib.request.urlopen", return_value=FakeResponse({"errors": []})):
        with pytest.raises(ValueError):
            get_cloudflare_ice_servers("key-id", "api-token")


@pytest.mark.parametrize("turn_key_id, api_token", [("", "token"), ("key-id", "")])
def test_get_cloudflare_ice_servers_rejects_incomplete_credentials(
    turn_key_id: str, api_token: str
):
    with pytest.raises(ValueError):
        get_cloudflare_ice_servers(turn_key_id, api_token)


def test_get_available_ice_servers_uses_cloudflare_when_configured(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("CLOUDFLARE_TURN_KEY_ID", "key-id")
    monkeypatch.setenv("CLOUDFLARE_TURN_KEY_API_TOKEN", "api-token")
    # Twilio is configured too, so this also pins the precedence between them.
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "sid")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "token")

    with patch(
        "streamlit_webrtc.credentials.get_cloudflare_ice_servers",
        return_value=CLOUDFLARE_RESPONSE["iceServers"],
    ) as get_cloudflare:
        with patch("streamlit_webrtc.credentials.get_twilio_ice_servers") as get_twilio:
            ice_servers = get_available_ice_servers()

    assert ice_servers == CLOUDFLARE_RESPONSE["iceServers"]
    get_cloudflare.assert_called_once_with("key-id", "api-token")
    get_twilio.assert_not_called()


def test_get_available_ice_servers_falls_back_to_twilio_when_cloudflare_fails(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("CLOUDFLARE_TURN_KEY_ID", "key-id")
    monkeypatch.setenv("CLOUDFLARE_TURN_KEY_API_TOKEN", "api-token")
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "sid")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "token")

    twilio_ice_servers = [{"urls": ["turn:turn.twilio.example:3478"]}]
    with patch(
        "streamlit_webrtc.credentials.get_cloudflare_ice_servers",
        side_effect=ValueError("boom"),
    ):
        with patch(
            "streamlit_webrtc.credentials.get_twilio_ice_servers",
            return_value=twilio_ice_servers,
        ):
            assert get_available_ice_servers() == twilio_ice_servers


@pytest.mark.parametrize(
    "set_var, expected_warning",
    [
        (
            "CLOUDFLARE_TURN_KEY_ID",
            "CLOUDFLARE_TURN_KEY_ID is set but CLOUDFLARE_TURN_KEY_API_TOKEN is not. "
            "Cloudflare's STUN/TURN servers will not be used.",
        ),
        (
            "CLOUDFLARE_TURN_KEY_API_TOKEN",
            "CLOUDFLARE_TURN_KEY_API_TOKEN is set but CLOUDFLARE_TURN_KEY_ID is not. "
            "Cloudflare's STUN/TURN servers will not be used.",
        ),
        (
            "TWILIO_ACCOUNT_SID",
            "TWILIO_ACCOUNT_SID is set but TWILIO_AUTH_TOKEN is not. "
            "Twilio's STUN/TURN servers will not be used.",
        ),
        (
            "TWILIO_AUTH_TOKEN",
            "TWILIO_AUTH_TOKEN is set but TWILIO_ACCOUNT_SID is not. "
            "Twilio's STUN/TURN servers will not be used.",
        ),
    ],
)
def test_get_available_ice_servers_warns_on_a_half_configured_provider(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    set_var: str,
    expected_warning: str,
):
    monkeypatch.setenv(set_var, "value")

    with caplog.at_level("WARNING", logger="streamlit_webrtc.credentials"):
        ice_servers = get_available_ice_servers()

    assert expected_warning in caplog.text
    assert ice_servers == [{"urls": "stun:stun.l.google.com:19302"}]
