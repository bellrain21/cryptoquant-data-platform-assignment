"""Raw Transfer-topic log collection with fixed scope and range splitting."""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from typing import Any, Protocol

from cryptoquant_pipeline.chunking import (
    MAX_BLOCKS_PER_LOG_REQUEST,
    BlockChunk,
    iter_block_chunks,
)
from cryptoquant_pipeline.config import CollectionScope
from cryptoquant_pipeline.exceptions import LogCollectionError, RetryableRpcError

LOGGER = logging.getLogger(__name__)


class LogRpcClient(Protocol):
    """log collector가 요구하는 최소 `eth_getLogs` interface."""

    def eth_get_logs(
        self,
        *,
        from_block: int,
        to_block: int,
        address: str | Sequence[str] | None = None,
        topics: Sequence[Any] | None = None,
    ) -> list[Mapping[str, Any]]: ...


def collect_raw_logs(
    client: LogRpcClient,
    *,
    from_block: int,
    to_block: int,
    collection_scope: CollectionScope,
    max_blocks: int = MAX_BLOCKS_PER_LOG_REQUEST,
) -> list[Mapping[str, Any]]:
    """configured collection_scope와 chunk 상한으로 raw RPC log를 수집함."""
    collection_scope.validate()

    logs: list[Mapping[str, Any]] = []
    for chunk in iter_block_chunks(from_block, to_block, max_blocks=max_blocks):
        logs.extend(_collect_chunk(client, chunk, collection_scope=collection_scope))
    return logs


def _collect_chunk(
    client: LogRpcClient,
    chunk: BlockChunk,
    *,
    collection_scope: CollectionScope,
) -> list[Mapping[str, Any]]:
    try:
        return client.eth_get_logs(
            from_block=chunk.from_block,
            to_block=chunk.to_block,
            address=collection_scope.address_filter,
            topics=collection_scope.topics,
        )
    except RetryableRpcError as exc:
        if chunk.from_block == chunk.to_block:
            raise LogCollectionError(
                "eth_getLogs failed after splitting down to a single block.",
                failed_range=(chunk.from_block, chunk.to_block),
            ) from exc
        mid = (chunk.from_block + chunk.to_block) // 2
        LOGGER.warning(
            "splitting_failed_log_chunk from_block=%s to_block=%s reason=%s",
            chunk.from_block,
            chunk.to_block,
            exc.__class__.__name__,
        )
        left = _collect_chunk(
            client,
            BlockChunk(chunk.from_block, mid),
            collection_scope=collection_scope,
        )
        right = _collect_chunk(
            client,
            BlockChunk(mid + 1, chunk.to_block),
            collection_scope=collection_scope,
        )
        return [*left, *right]
