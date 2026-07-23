"""Tests for shared/bus.py.

Covers: send_messages_batch — single-batch happy path, and the multi-batch
flush path (MessageSizeExceededError from ServiceBusMessageBatch.add_message),
which no other test in the suite exercises (agent tests mock
send_messages_batch entirely). Also covers receive_message's lock-renewal and
lock-loss-tolerant settlement (see JOURNAL entry for the MessageLockLostError
fix): AutoLockRenewer registration, swallowing MessageLockLostError on
complete_message/abandon_message while never swallowing it around the
caller's own business logic, and renewer.close() always running.
"""
import json
from unittest.mock import MagicMock

import pytest
from azure.servicebus.exceptions import MessageLockLostError, MessageSizeExceededError

from shared.bus import receive_message, send_messages_batch


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


def _fake_message(body: dict) -> MagicMock:
    msg = MagicMock()
    msg.body = [json.dumps(body).encode("utf-8")]
    return msg


def _patched_bus_receiver(mocker, receiver: MagicMock):
    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.get_queue_receiver.return_value.__enter__.return_value = receiver
    mocker.patch("shared.bus.ServiceBusClient", return_value=mock_client)


class TestReceiveMessage:
    def test_registers_autolockrenewer_with_receiver_and_message(self, mocker):
        receiver = MagicMock()
        msg = _fake_message({"cv_id": "1"})
        receiver.receive_messages.return_value = [msg]
        _patched_bus_receiver(mocker, receiver)
        renewer = MagicMock()
        mocker.patch("shared.bus.AutoLockRenewer", return_value=renewer)

        with receive_message("cv-analysis") as body:
            assert body == {"cv_id": "1"}

        renewer.register.assert_called_once()
        args, kwargs = renewer.register.call_args
        assert args[0] is receiver
        assert args[1] is msg

    def test_completes_message_and_closes_renewer_on_success(self, mocker):
        receiver = MagicMock()
        msg = _fake_message({"cv_id": "1"})
        receiver.receive_messages.return_value = [msg]
        _patched_bus_receiver(mocker, receiver)
        renewer = MagicMock()
        mocker.patch("shared.bus.AutoLockRenewer", return_value=renewer)

        with receive_message("cv-analysis") as _body:
            pass

        receiver.complete_message.assert_called_once_with(msg)
        receiver.abandon_message.assert_not_called()
        renewer.close.assert_called_once()

    def test_swallows_lock_lost_error_from_complete_message(self, mocker):
        receiver = MagicMock()
        msg = _fake_message({"cv_id": "1"})
        receiver.receive_messages.return_value = [msg]
        receiver.complete_message.side_effect = MessageLockLostError()
        _patched_bus_receiver(mocker, receiver)
        mocker.patch("shared.bus.AutoLockRenewer", return_value=MagicMock())

        # Work already committed; settlement losing the lock must not raise or fail the job.
        with receive_message("cv-analysis") as _body:
            pass

    def test_reraises_business_exception_and_abandons_message(self, mocker):
        receiver = MagicMock()
        msg = _fake_message({"cv_id": "1"})
        receiver.receive_messages.return_value = [msg]
        _patched_bus_receiver(mocker, receiver)
        renewer = MagicMock()
        mocker.patch("shared.bus.AutoLockRenewer", return_value=renewer)

        with pytest.raises(ValueError, match="business failure"):
            with receive_message("cv-analysis") as _body:
                raise ValueError("business failure")

        receiver.abandon_message.assert_called_once_with(msg)
        receiver.complete_message.assert_not_called()
        renewer.close.assert_called_once()

    def test_original_exception_wins_even_if_abandon_message_loses_the_lock(self, mocker):
        receiver = MagicMock()
        msg = _fake_message({"cv_id": "1"})
        receiver.receive_messages.return_value = [msg]
        receiver.abandon_message.side_effect = MessageLockLostError()
        _patched_bus_receiver(mocker, receiver)
        mocker.patch("shared.bus.AutoLockRenewer", return_value=MagicMock())

        with pytest.raises(ValueError, match="business failure"):
            with receive_message("cv-analysis") as _body:
                raise ValueError("business failure")

    def test_never_registers_renewer_when_queue_is_empty(self, mocker):
        # receive_message returns without yielding when the queue is empty — callers
        # (e.g. cv_analysis/main.py) catch the resulting RuntimeError deliberately;
        # unrelated to this fix, just asserting the renewer is never touched on this path.
        receiver = MagicMock()
        receiver.receive_messages.return_value = []
        _patched_bus_receiver(mocker, receiver)
        renewer = MagicMock()
        mocker.patch("shared.bus.AutoLockRenewer", return_value=renewer)

        with pytest.raises(RuntimeError):
            with receive_message("cv-analysis") as _body:
                pass

        renewer.register.assert_not_called()
