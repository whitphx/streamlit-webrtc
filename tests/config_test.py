from typing import Any, List

import pytest
from aiortc import RTCConfiguration as AiortcRTCConfiguration
from aiortc import RTCIceServer as AiortcRTCIceServer

from streamlit_webrtc.config import (
    compile_ice_servers,
    compile_rtc_configuration,
    compile_rtc_ice_server,
)


class TestCompileRtcIceServer:
    def test_minimal(self) -> None:
        server = compile_rtc_ice_server({"urls": "stun:stun.l.google.com:19302"})
        assert isinstance(server, AiortcRTCIceServer)
        assert server.urls == "stun:stun.l.google.com:19302"
        assert server.username is None
        assert server.credential is None

    def test_with_credentials(self) -> None:
        server = compile_rtc_ice_server(
            {"urls": ["turn:t1", "turn:t2"], "username": "u", "credential": "c"}
        )
        assert server.urls == ["turn:t1", "turn:t2"]
        assert server.username == "u"
        assert server.credential == "c"

    def test_missing_urls_raises(self) -> None:
        with pytest.raises(ValueError, match="urls"):
            compile_rtc_ice_server({"username": "u"})  # type: ignore[arg-type]

    def test_non_dict_raises(self) -> None:
        with pytest.raises(ValueError, match="dict"):
            compile_rtc_ice_server("stun:stun.l.google.com:19302")  # type: ignore[arg-type]


class TestCompileIceServers:
    def test_empty_list(self) -> None:
        assert compile_ice_servers([]) == []

    def test_filters_invalid_entries(self) -> None:
        # Entries missing `urls` or not dicts are silently dropped — this is
        # the contract: callers feed possibly-malformed input from JSON.
        # The annotation here loosens the type so mypy lets us mix valid and
        # invalid shapes; the function's runtime contract is "tolerate junk."
        servers: List[Any] = [
            {"urls": "stun:a"},
            {"username": "no-urls-here"},
            "string-not-dict",
            {"urls": "stun:b", "username": "u"},
        ]
        result = compile_ice_servers(servers)
        assert len(result) == 2
        assert result[0].urls == "stun:a"
        assert result[1].urls == "stun:b"


class TestCompileRtcConfiguration:
    def test_minimal(self) -> None:
        config = compile_rtc_configuration({})
        assert isinstance(config, AiortcRTCConfiguration)
        assert config.iceServers == []

    def test_with_servers(self) -> None:
        config = compile_rtc_configuration(
            {"iceServers": [{"urls": "stun:stun.l.google.com:19302"}]}
        )
        assert len(config.iceServers) == 1
        assert config.iceServers[0].urls == "stun:stun.l.google.com:19302"

    def test_non_dict_raises(self) -> None:
        with pytest.raises(ValueError, match="dict"):
            compile_rtc_configuration([])  # type: ignore[arg-type]

    def test_non_list_iceservers_raises(self) -> None:
        with pytest.raises(ValueError, match="iceServers"):
            compile_rtc_configuration({"iceServers": "not-a-list"})  # type: ignore[typeddict-item]
