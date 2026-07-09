"""Tests for shared/bus.py.

Covers: send_messages_batch — single-batch happy path, and the multi-batch
flush path (MessageSizeExceededError from ServiceBusMessageBatch.add_message),
which no other test in the suite exercises (agent tests mock
send_messages_batch entirely).
"""
from unittest.mock import MagicMock

from azure.servicebus.exceptions import MessageSizeExceededError

from shared.bus import send_messages_batch


class _FakeBatch:
    """Minimal stand-in for ServiceBusMessageBatch: accepts up to `capacity` messages."""

    def __init__(self, capacity: int):
        self.capacity = capacity
        self.messages: list = []

    def add_message(self, message):
        if len(self.messages) >= self.capacity:
            raise MessageSizeExceededError()
        self.messages.append(message)


def _patched_bus_client(mocker, sender: MagicMock):
    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.get_queue_sender.return_value.__enter__.return_value = sender
    mocker.patch("shared.bus.ServiceBusClient", return_value=mock_client)


class TestSendMessagesBatch:
    def test_noop_on_empty_bodies(self, mocker):
        sender = MagicMock()
        _patched_bus_client(mocker, sender)

        send_messages_batch("distillate-offer-fetched", [])

        sender.create_message_batch.assert_not_called()
        sender.send_messages.assert_not_called()

    def test_sends_single_batch_when_everything_fits(self, mocker):
        sender = MagicMock()
        sender.create_message_batch.side_effect = lambda: _FakeBatch(capacity=100)
        _patched_bus_client(mocker, sender)

        send_messages_batch(
            "distillate-offer-fetched",
            [{"offer_id": "1"}, {"offer_id": "2"}, {"offer_id": "3"}],
        )

        assert sender.send_messages.call_count == 1
        sent_batch = sender.send_messages.call_args.args[0]
        assert len(sent_batch.messages) == 3

    def test_flushes_and_starts_a_new_batch_when_full(self, mocker):
        # Capacity of 2 — 5 messages must produce 3 batches: [2, 2, 1].
        sender = MagicMock()
        sender.create_message_batch.side_effect = lambda: _FakeBatch(capacity=2)
        _patched_bus_client(mocker, sender)

        send_messages_batch(
            "distillate-offer-fetched",
            [{"offer_id": str(i)} for i in range(5)],
        )

        assert sender.send_messages.call_count == 3
        batch_sizes = [len(c.args[0].messages) for c in sender.send_messages.call_args_list]
        assert batch_sizes == [2, 2, 1]

    def test_propagates_error_when_a_single_message_never_fits(self, mocker):
        # Capacity of 0 — even a fresh batch rejects the first message immediately,
        # and that second add_message() call is not wrapped in its own retry.
        sender = MagicMock()
        sender.create_message_batch.side_effect = lambda: _FakeBatch(capacity=0)
        _patched_bus_client(mocker, sender)

        try:
            send_messages_batch("distillate-offer-fetched", [{"offer_id": "1"}])
            raised = False
        except MessageSizeExceededError:
            raised = True
        assert raised
