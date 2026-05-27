"""Azure OpenAI embedding client using text-embedding-3-small."""

import os
import time

import openai
import structlog
from openai import AzureOpenAI

BATCH_SIZE = 100

_EMBEDDING_MODEL = "text-embedding-3-small"
_API_VERSION = "2024-02-01"

logger = structlog.get_logger()

_endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
if not _endpoint:
    raise ValueError("AZURE_OPENAI_ENDPOINT environment variable is not set")

_api_key = os.environ.get("AZURE_OPENAI_API_KEY")
if not _api_key:
    raise ValueError("AZURE_OPENAI_API_KEY environment variable is not set")

_client = AzureOpenAI(
    azure_endpoint=_endpoint,
    api_key=_api_key,
    api_version=_API_VERSION,
    max_retries=10,
)


def embed(texts: list[str]) -> list[list[float]]:
    """Return embedding vectors for a batch of texts (1536 dimensions each).

    Args:
        texts: Input texts to embed.

    Returns:
        A list of embedding vectors, one per input text.
    """
    chunks = [texts[i : i + BATCH_SIZE] for i in range(0, len(texts), BATCH_SIZE)]
    total_batches = len(chunks)
    logger.info("embedding_batch_started", model=_EMBEDDING_MODEL, count=len(texts))
    vectors: list[list[float]] = []
    for i, chunk in enumerate(chunks):
        logger.info(
            "embedding_batch_progress",
            batch=i + 1,
            total_batches=total_batches,
            count=len(chunk),
        )
        try:
            response = _client.embeddings.create(input=chunk, model=_EMBEDDING_MODEL)
        except openai.OpenAIError:
            logger.error("embedding_failed", model=_EMBEDDING_MODEL, exc_info=True)
            raise
        vectors.extend(item.embedding for item in response.data)
        if i < total_batches - 1:
            time.sleep(1)
    logger.info("embedding_batch_completed", model=_EMBEDDING_MODEL, count=len(vectors))
    return vectors
