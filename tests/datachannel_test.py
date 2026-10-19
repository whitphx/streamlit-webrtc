import asyncio
from unittest.mock import Mock

import pytest

from streamlit_webrtc.datachannel import DataChannel, compile_data_channel_specs


class TestCompileDataChannelSpecs:
    def test_assigns_ids_in_declaration_order(self) -> None:
        specs = compile_data_channel_specs(
            {"overlay": {"ordered": False, "maxRetransmits": 0}, "control": {}}
        )
        assert specs == [
            {"label": "overlay", "id": 0, "ordered": False, "maxRetransmits": 0},
            {"label": "control", "id": 1},
        ]

    def test_empty(self) -> None:
        assert compile_data_channel_specs({}) == []

    def test_rejects_unknown_option(self) -> None:
        with pytest.raises(ValueError, match="max_retransmits"):
            compile_data_channel_specs({"x": {"max_retransmits": 0}})  # type: ignore[typeddict-unknown-key]

    def test_drops_options_set_to_none(self) -> None:
        specs = compile_data_channel_specs(
            {"x": {"ordered": None, "maxRetransmits": None, "protocol": None}}  # type: ignore[typeddict-item]
        )
        assert specs == [{"label": "x", "id": 0}]

    def test_rejects_both_partial_reliability_options(self) -> None:
        with pytest.raises(ValueError, match="both"):
            compile_data_channel_specs(
                {"x": {"maxRetransmits": 0, "maxPacketLifeTime": 100}}
            )


class TestDataChannelSend:
    @pytest.mark.asyncio
    async def test_sends_on_the_loop_from_another_thread(self) -> None:
        raw = Mock(readyState="open", bufferedAmount=0)
        channel = DataChannel(raw, asyncio.get_running_loop())

        assert await asyncio.to_thread(channel.send, "hello") is True
        await asyncio.sleep(0)

        raw.send.assert_called_once_with("hello")

    @pytest.mark.asyncio
    async def test_copies_bytes_like_data(self) -> None:
        raw = Mock(readyState="open", bufferedAmount=0)
        channel = DataChannel(raw, asyncio.get_running_loop())
        buffer = bytearray(b"abc")

        channel.send(memoryview(buffer))
        buffer[0] = ord("z")
        await asyncio.sleep(0)

        raw.send.assert_called_once_with(b"abc")

    @pytest.mark.asyncio
    async def test_returns_false_unless_open(self) -> None:
        raw = Mock(readyState="connecting", bufferedAmount=0)
        channel = DataChannel(raw, asyncio.get_running_loop())

        assert channel.send(b"early") is False
        await asyncio.sleep(0)

        raw.send.assert_not_called()

    @pytest.mark.asyncio
    async def test_drops_a_queued_message_if_the_channel_closed_meanwhile(
        self,
    ) -> None:
        raw = Mock(readyState="open", bufferedAmount=0)
        channel = DataChannel(raw, asyncio.get_running_loop())

        assert channel.send(b"late") is True
        raw.readyState = "closed"
        await asyncio.sleep(0)

        raw.send.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_false_above_max_buffered(self) -> None:
        raw = Mock(readyState="open", bufferedAmount=1000)
        channel = DataChannel(raw, asyncio.get_running_loop())

        assert channel.send(b"skipped", max_buffered=999) is False
        assert channel.send(b"sent", max_buffered=1000) is True
        await asyncio.sleep(0)

        raw.send.assert_called_once_with(b"sent")

    def test_returns_false_after_the_loop_closed(self) -> None:
        loop = asyncio.new_event_loop()
        loop.close()
        raw = Mock(readyState="open", bufferedAmount=0)

        assert DataChannel(raw, loop).send("late") is False

        raw.send.assert_not_called()
