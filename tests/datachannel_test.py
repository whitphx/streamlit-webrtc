import asyncio
from typing import Union
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

    @pytest.mark.parametrize("key", ["maxPacketLifeTime", "maxRetransmits"])
    @pytest.mark.parametrize("value", [-1, 65536])
    def test_rejects_out_of_range_partial_reliability_option(
        self, key: str, value: int
    ) -> None:
        with pytest.raises(ValueError, match=key):
            compile_data_channel_specs({"x": {key: value}})  # type: ignore[misc]

    @pytest.mark.parametrize("key", ["maxPacketLifeTime", "maxRetransmits"])
    def test_accepts_the_range_bounds(self, key: str) -> None:
        assert compile_data_channel_specs({"x": {key: 0}, "y": {key: 65535}}) == [  # type: ignore[misc]
            {"label": "x", "id": 0, key: 0},
            {"label": "y", "id": 1, key: 65535},
        ]

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

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("message", "size"),
        [(b"x" * 1024, 1024), (b"", 1), ("", 1)],
        ids=["kibibyte", "empty-bytes", "empty-str"],
    )
    async def test_counts_messages_not_yet_handed_to_the_channel(
        self, message: Union[str, bytes], size: int
    ) -> None:
        raw = Mock(readyState="open", bufferedAmount=0)
        channel = DataChannel(raw, asyncio.get_running_loop())

        results = [channel.send(message, max_buffered=size) for _ in range(1000)]

        assert results.count(True) == 2
        assert results[:2] == [True, True]
        assert channel.buffered_amount == 2 * size
        await asyncio.sleep(0)
        assert raw.send.call_count == 2
        assert channel.buffered_amount == 0
        assert channel.send(message, max_buffered=size) is True

    @pytest.mark.asyncio
    async def test_counts_a_str_by_its_utf8_length(self) -> None:
        raw = Mock(readyState="open", bufferedAmount=0)
        channel = DataChannel(raw, asyncio.get_running_loop())

        channel.send("\u00e9")

        assert channel.buffered_amount == 2
        await asyncio.sleep(0)
        assert channel.buffered_amount == 0

    def test_returns_false_after_the_loop_closed(self) -> None:
        loop = asyncio.new_event_loop()
        loop.close()
        raw = Mock(readyState="open", bufferedAmount=0)

        channel = DataChannel(raw, loop)

        assert channel.send("late") is False

        raw.send.assert_not_called()
        assert channel.buffered_amount == 0
