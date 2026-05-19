"""Azure OpenAI embedding client using text-embedding-3-small."""

import os

import openai
import structlog
from openai import AzureOpenAI

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
)


def embed(texts: list[str]) -> list[list[float]]:
    """Return embedding vectors for a batch of texts (1536 dimensions each).

    Args:
        texts: Input texts to embed.

    Returns:
        A list of embedding vectors, one per input text.
    """
    logger.info("embedding_batch_started", model=_EMBEDDING_MODEL, count=len(texts))
    try:
        response = _client.embeddings.create(input=texts, model=_EMBEDDING_MODEL)
    except openai.OpenAIError as e:
        logger.error("embedding_failed", model=_EMBEDDING_MODEL, exc_info=True)
        raise
    vectors = [item.embedding for item in response.data]
    logger.info("embedding_batch_completed", model=_EMBEDDING_MODEL, count=len(vectors))
    return vectors
