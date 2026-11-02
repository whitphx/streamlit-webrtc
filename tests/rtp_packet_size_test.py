import asyncio
import fractions
import logging

import av
import pytest
from aiortc.codecs import get_encoder, h264, vpx
from aiortc.contrib.media import MediaRelay
from aiortc.rtcrtpparameters import RTCRtpCodecParameters

from streamlit_webrtc.rtp_packet_size import (
    AIORTC_LEGACY_PAYLOAD_SIZE,
    DEFAULT_PAYLOAD_SIZE,
    PAYLOAD_SIZE_ENV_VAR,
    cap_video_rtp_payload_size,
)
from streamlit_webrtc.webrtc import WebRtcMode, WebRtcWorker

from .webrtc_loopback_test import _WORKER_DEFAULTS


def _packet(data: bytes) -> av.Packet:
    packet = av.Packet(data)
    packet.pts = 0
    packet.time_base = fractions.Fraction(1, 90000)
    return packet


@pytest.fixture
def packet_max(monkeypatch):
    def set_packet_max(value):
        monkeypatch.setattr(vpx, "PACKET_MAX", value)
        monkeypatch.setattr(h264, "PACKET_MAX", value)

    monkeypatch.delenv(PAYLOAD_SIZE_ENV_VAR, raising=False)
    set_packet_max(AIORTC_LEGACY_PAYLOAD_SIZE)
    return set_packet_max


def test_caps_legacy_aiortc_payload_size(packet_max):
    cap_video_rtp_payload_size()

    assert vpx.PACKET_MAX == DEFAULT_PAYLOAD_SIZE
    assert h264.PACKET_MAX == DEFAULT_PAYLOAD_SIZE


def test_vp8_packetizer_honours_cap(packet_max):
    cap_video_rtp_payload_size()
    encoder = get_encoder(
        RTCRtpCodecParameters(mimeType="video/VP8", clockRate=90000, payloadType=96)
    )

    payloads, _ = encoder.pack(_packet(bytes(5000)))

    assert max(len(payload) for payload in payloads) == DEFAULT_PAYLOAD_SIZE


def test_h264_packetizer_honours_cap(packet_max):
    cap_video_rtp_payload_size()
    encoder = get_encoder(
        RTCRtpCodecParameters(mimeType="video/H264", clockRate=90000, payloadType=97)
    )

    # A single IDR NAL unit after an Annex B start code.
    payloads, _ = encoder.pack(_packet(b"\x00\x00\x00\x01\x65" + bytes(4999)))

    assert len(payloads) > 1
    assert max(len(payload) for payload in payloads) <= DEFAULT_PAYLOAD_SIZE


@pytest.mark.asyncio
async def test_worker_applies_cap(packet_max):
    worker = WebRtcWorker(
        loop=asyncio.get_running_loop(),
        relay=MediaRelay(),
        mode=WebRtcMode.SENDRECV,
        **_WORKER_DEFAULTS,
    )
    try:
        assert vpx.PACKET_MAX == DEFAULT_PAYLOAD_SIZE
        assert h264.PACKET_MAX == DEFAULT_PAYLOAD_SIZE
    finally:
        await asyncio.to_thread(worker.stop, 1.0)


@pytest.mark.parametrize("value", [1150, 1200, 1400])
def test_leaves_other_values_alone(packet_max, value):
    packet_max(value)

    cap_video_rtp_payload_size()

    assert vpx.PACKET_MAX == value
    assert h264.PACKET_MAX == value


def test_env_var_overrides_payload_size(packet_max, monkeypatch):
    monkeypatch.setenv(PAYLOAD_SIZE_ENV_VAR, "1000")

    cap_video_rtp_payload_size()

    assert vpx.PACKET_MAX == 1000
    assert h264.PACKET_MAX == 1000


def test_env_var_zero_opts_out(packet_max, monkeypatch):
    monkeypatch.setenv(PAYLOAD_SIZE_ENV_VAR, "0")

    cap_video_rtp_payload_size()

    assert vpx.PACKET_MAX == AIORTC_LEGACY_PAYLOAD_SIZE
    assert h264.PACKET_MAX == AIORTC_LEGACY_PAYLOAD_SIZE


@pytest.mark.parametrize("value", ["small", "4", "-1", "1e3"])
def test_invalid_env_var_falls_back_to_default(packet_max, monkeypatch, caplog, value):
    monkeypatch.setenv(PAYLOAD_SIZE_ENV_VAR, value)

    with caplog.at_level(logging.WARNING, logger="streamlit_webrtc"):
        cap_video_rtp_payload_size()

    assert vpx.PACKET_MAX == DEFAULT_PAYLOAD_SIZE
    assert PAYLOAD_SIZE_ENV_VAR in caplog.text


def test_tolerates_aiortc_without_packet_max(monkeypatch):
    monkeypatch.delenv(PAYLOAD_SIZE_ENV_VAR, raising=False)
    monkeypatch.delattr(vpx, "PACKET_MAX")
    monkeypatch.delattr(h264, "PACKET_MAX")

    cap_video_rtp_payload_size()

    assert not hasattr(vpx, "PACKET_MAX")
    assert not hasattr(h264, "PACKET_MAX")
