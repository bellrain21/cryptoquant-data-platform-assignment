"""Block chunk generation with the Alchemy Free 10-block invariant."""

from __future__ import annotations

from dataclasses import dataclass

from cryptoquant_pipeline.exceptions import BlockRangeError

MAX_BLOCKS_PER_LOG_REQUEST = 10


@dataclass(frozen=True)
class BlockChunk:
    """eth_getLogs 1회 요청에 들어갈 inclusive block range."""

    from_block: int
    to_block: int

    @property
    def block_count(self) -> int:
        return self.to_block - self.from_block + 1


def iter_block_chunks(
    from_block: int,
    to_block: int,
    *,
    max_blocks: int = MAX_BLOCKS_PER_LOG_REQUEST,
) -> list[BlockChunk]:
    """누락/중복 없이 inclusive range를 10블록 이하 chunk로 나눔."""
    if from_block < 0 or to_block < 0:
        raise BlockRangeError("block numbers must be non-negative.")
    if from_block > to_block:
        raise BlockRangeError("from_block must be less than or equal to to_block.")
    if max_blocks < 1 or max_blocks > MAX_BLOCKS_PER_LOG_REQUEST:
        raise BlockRangeError(
            f"max_blocks must be between 1 and {MAX_BLOCKS_PER_LOG_REQUEST}."
        )

    chunks: list[BlockChunk] = []
    chunk_start = from_block
    while chunk_start <= to_block:
        # 불변식: chunk_end = min(chunk_start + 9, to_block)
        chunk_end = min(chunk_start + max_blocks - 1, to_block)
        chunk = BlockChunk(chunk_start, chunk_end)
        if not 1 <= chunk.block_count <= MAX_BLOCKS_PER_LOG_REQUEST:
            raise BlockRangeError("generated chunk violated max block count invariant.")
        chunks.append(chunk)
        chunk_start = chunk_end + 1
    return chunks
