"""Delta writer idempotency tests for the new raw schema."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

from cryptoquant_pipeline.delta_writer import (
    count_duplicate_natural_keys,
    count_rows,
    write_ethereum_logs_insert_only,
)


def _row(*, chain_id: int = 1, log_index: int = 1) -> dict[str, object]:
    return {
        "chain_id": chain_id,
        "block_number": 100,
        "block_hash": "0xabc",
        "transaction_hash": "0xdef",
        "transaction_index": 0,
        "log_index": log_index,
        "contract_address": "0xdac17f958d2ee523a2206206994597c13d831ec7",
        "topic0": None,
        "topic1": None,
        "topic2": None,
        "topic3": None,
        "data_raw": "0x",
        "data_uint256_decimal_text": None,
        "data_uint256_decode_status": "NOT_UINT256_WORD",
        "removed": False,
        "block_timestamp_utc": datetime(2024, 1, 1, tzinfo=UTC),
        "block_date_utc": date(2024, 1, 1),
        "interval_start_utc": datetime(2024, 1, 1, tzinfo=UTC),
        "interval_end_utc": datetime(2024, 1, 1, 1, tzinfo=UTC),
        "ingested_at_utc": datetime(2024, 1, 1, 2, tzinfo=UTC),
    }


def test_same_event_inserted_twice_results_in_one_row(tmp_path: Path) -> None:
    table_path = tmp_path / "ethereum_logs"

    first = write_ethereum_logs_insert_only([_row()], table_path=table_path)
    second = write_ethereum_logs_insert_only([_row()], table_path=table_path)

    assert first.inserted_row_count == 1
    assert second.inserted_row_count == 0
    assert count_rows(table_path) == 1
    assert count_duplicate_natural_keys(table_path) == 0


def test_different_log_index_is_distinct_event(tmp_path: Path) -> None:
    table_path = tmp_path / "ethereum_logs"

    write_ethereum_logs_insert_only([_row(log_index=1), _row(log_index=2)], table_path=table_path)

    assert count_rows(table_path) == 2
    assert count_duplicate_natural_keys(table_path) == 0


def test_different_chain_id_is_distinct_event(tmp_path: Path) -> None:
    table_path = tmp_path / "ethereum_logs"

    write_ethereum_logs_insert_only([_row(chain_id=1), _row(chain_id=2)], table_path=table_path)

    assert count_rows(table_path) == 2
    assert count_duplicate_natural_keys(table_path) == 0


def test_interval_retry_does_not_increase_row_count(tmp_path: Path) -> None:
    table_path = tmp_path / "ethereum_logs"

    write_ethereum_logs_insert_only([_row()], table_path=table_path)
    before = count_rows(table_path)
    write_ethereum_logs_insert_only([_row()], table_path=table_path)

    assert count_rows(table_path) == before


def test_empty_interval_creates_schema_only_delta_table(tmp_path: Path) -> None:
    table_path = tmp_path / "ethereum_logs"

    result = write_ethereum_logs_insert_only([], table_path=table_path)

    assert result.inserted_row_count == 0
    assert (table_path / "_delta_log").exists()
    assert count_rows(table_path) == 0
