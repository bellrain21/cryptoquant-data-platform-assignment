"""10-block chunk invariant tests."""

from __future__ import annotations

from cryptoquant_pipeline.chunking import MAX_BLOCKS_PER_LOG_REQUEST, iter_block_chunks


def _covered_blocks(from_block: int, to_block: int) -> list[int]:
    chunks = iter_block_chunks(from_block, to_block)
    blocks: list[int] = []
    for chunk in chunks:
        assert chunk.block_count <= MAX_BLOCKS_PER_LOG_REQUEST
        blocks.extend(range(chunk.from_block, chunk.to_block + 1))
    return blocks


def test_chunks_cover_full_range_without_gap_or_duplicate() -> None:
    blocks = _covered_blocks(100, 135)

    assert blocks == list(range(100, 136))
    assert len(blocks) == len(set(blocks))


def test_single_block_range() -> None:
    chunks = iter_block_chunks(10, 10)

    assert [(chunk.from_block, chunk.to_block) for chunk in chunks] == [(10, 10)]


def test_range_exact_multiple_of_ten() -> None:
    chunks = iter_block_chunks(1, 20)

    assert [(chunk.from_block, chunk.to_block) for chunk in chunks] == [(1, 10), (11, 20)]


def test_range_smaller_than_ten() -> None:
    chunks = iter_block_chunks(1, 9)

    assert [(chunk.from_block, chunk.to_block) for chunk in chunks] == [(1, 9)]
