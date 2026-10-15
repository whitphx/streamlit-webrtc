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

    def test_rejects_both_partial_reliability_options(self) -> None:
        with pytest.raises(ValueError, match="both"):
            compile_data_channel_specs(
                {"x": {"maxRetransmits": 0, "maxPacketLifeTime": 100}}
            )


class TestDataChannelSend:
    @pytest.mark.asyncio
    async def test_sends_on_the_loop_from_another_thread(self) -> None:
        raw = Mock(readyState="open")
        channel = DataChannel(raw, asyncio.get_running_loop())

        await asyncio.to_thread(channel.send, "hello")
        await asyncio.sleep(0)

        raw.send.assert_called_once_with("hello")

    @pytest.mark.asyncio
    async def test_copies_bytes_like_data(self) -> None:
        raw = Mock(readyState="open")
        channel = DataChannel(raw, asyncio.get_running_loop())
        buffer = bytearray(b"abc")

        channel.send(memoryview(buffer))
        buffer[0] = ord("z")
        await asyncio.sleep(0)

        raw.send.assert_called_once_with(b"abc")

    @pytest.mark.asyncio
    async def test_drops_messages_unless_open(self) -> None:
        raw = Mock(readyState="connecting")
        channel = DataChannel(raw, asyncio.get_running_loop())

        channel.send(b"early")
        await asyncio.sleep(0)

        raw.send.assert_not_called()

    def test_drops_messages_after_the_loop_closed(self) -> None:
        loop = asyncio.new_event_loop()
        loop.close()
        raw = Mock(readyState="open")

        DataChannel(raw, loop).send("late")

        raw.send.assert_not_called()
