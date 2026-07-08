"""Azure Service Bus helpers: send and receive messages."""

import json
import os
from contextlib import contextmanager
from typing import Generator

import structlog
from azure.identity import DefaultAzureCredential
from azure.servicebus import ServiceBusClient, ServiceBusMessage
from azure.servicebus.exceptions import ServiceBusError

RECEIVE_MAX_WAIT_SECONDS = 30

logger = structlog.get_logger()

_namespace = os.environ.get("AZURE_SERVICEBUS_FULLY_QUALIFIED_NAMESPACE")
if not _namespace:
    raise ValueError("AZURE_SERVICEBUS_FULLY_QUALIFIED_NAMESPACE environment variable is not set")

_credential = DefaultAzureCredential()


def send_message(queue_name: str, body: dict) -> None:
    """Serialize body as JSON and send it to the specified Service Bus queue.

    Args:
        queue_name: Target Service Bus queue name.
        body: Message payload to serialize as JSON.

    Returns:
        None
    """
    logger.info("servicebus_send_started", queue=queue_name)
    with ServiceBusClient(fully_qualified_namespace=_namespace, credential=_credential) as client:
        with client.get_queue_sender(queue_name) as sender:
            message = ServiceBusMessage(json.dumps(body))
            try:
                sender.send_messages(message)
            except ServiceBusError as e:
                logger.error("servicebus_send_failed", queue=queue_name, exc_info=True)
                raise
            logger.info("servicebus_message_sent", queue=queue_name)


@contextmanager
def receive_message(queue_name: str) -> Generator[dict, None, None]:
    """Receive exactly one message from the specified queue.

    Yields the decoded message body as a dict.
    Calls complete_message() on success, abandon_message() on exception.

    Note: processes exactly one message per call — intentional.
    KEDA handles parallelism by launching one container instance per message.
    @contextmanager with yield in a loop is invalid for multiple messages.

    Args:
        queue_name: Source Service Bus queue name.

    Yields:
        dict: Decoded JSON message body.
    """
    logger.info("servicebus_receive_started", queue=queue_name)
    with ServiceBusClient(fully_qualified_namespace=_namespace, credential=_credential) as client:
        with client.get_queue_receiver(queue_name) as receiver:
            # max_wait_time is required for the empty-queue path to exist at
            # all: without it the SDK blocks until a message arrives. KEDA can
            # fire a job for a message that is gone by the time the container
            # starts (consumed by an overlapping run, expired to the DLQ) —
            # the job must then exit as "no message", not hang until its
            # replica timeout kills it and reports the execution as Failed.
            messages = receiver.receive_messages(
                max_message_count=1, max_wait_time=RECEIVE_MAX_WAIT_SECONDS
            )
            if not messages:
                logger.info("servicebus_no_messages", queue=queue_name)
                return
            msg = messages[0]
            try:
                yield json.loads(b"".join(msg.body))
                receiver.complete_message(msg)
                logger.info("servicebus_message_completed", queue=queue_name)
            except Exception:  # re-raise intentional — context manager pattern
                receiver.abandon_message(msg)
                logger.error("servicebus_message_abandoned", queue=queue_name, exc_info=True)
                raise
