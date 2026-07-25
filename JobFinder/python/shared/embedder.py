"""Azure OpenAI embedding client using text-embedding-3-small."""

import os
import time

import openai
import structlog
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI

BATCH_SIZE = 100

_EMBEDDING_MODEL = "text-embedding-3-small"
_API_VERSION = "2024-02-01"

logger = structlog.get_logger()

_endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
if not _endpoint:
    raise ValueError("AZURE_OPENAI_ENDPOINT environment variable is not set")

# No I/O and no resolvable identity needed at import — the credential chain is only
# walked on the first token request (the first .embeddings.create() call below). Unlike
# AZURE_OPENAI_ENDPOINT above, an unusable identity therefore surfaces at call time, not
# at module load — this module still imports cleanly with no Azure login available (e.g.
# under pytest, see conftest.py — this module is also imported transitively by
# offer_fetching and webapp/routers/cv.py|profile.py via shared.embedder.embed()).
_token_provider = get_bearer_token_provider(
    DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"
)

_client = AzureOpenAI(
    azure_endpoint=_endpoint,
    azure_ad_token_provider=_token_provider,
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
        # No "agent" field here (unlike the chat-completion sites): this module is shared
        # across several services with no configure_telemetry() of its own — cloud_RoleName
        # (the OTel service.name resource attribute set by each caller) already carries that
        # attribution. Embedding usage has no completion_tokens, so it's omitted rather than
        # logged as None.
        logger.info(
            "openai_call_completed",
            operation="embedding",
            model=_EMBEDDING_MODEL,
            batch=i + 1,
            total_batches=total_batches,
            prompt_tokens=response.usage.prompt_tokens,
            total_tokens=response.usage.total_tokens,
        )
        vectors.extend(item.embedding for item in response.data)
        if i < total_batches - 1:
            time.sleep(1)
    logger.info("embedding_batch_completed", model=_EMBEDDING_MODEL, count=len(vectors))
    return vectors
