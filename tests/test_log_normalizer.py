"""cryptoquant_pipeline log normalization and ERC-20 decode tests."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from cryptoquant_pipeline.config import TRANSFER_TOPIC0
from cryptoquant_pipeline.log_normalizer import (
    amount_with_decimals,
    decode_uint256_decimal,
    hex_quantity_to_int,
    is_erc20_transfer_topic,
    normalize_logs,
    topic_to_address,
)


def test_hex_quantity_to_int() -> None:
    assert hex_quantity_to_int("0x10") == 16


def test_indexed_topic_to_address_and_none_topic() -> None:
    topic = "0x" + "0" * 24 + "5754284f345afc66a98fbb0a0afe71e0f007b949"

    assert topic_to_address(topic) == "0x5754284f345afc66a98fbb0a0afe71e0f007b949"
    assert topic_to_address(None) is None


def test_transfer_topic_detection() -> None:
    assert is_erc20_transfer_topic(TRANSFER_TOPIC0)
    assert not is_erc20_transfer_topic(None)


def test_usdt_raw_uint256_amount_uses_decimal_not_float() -> None:
    data_raw = "0x" + "0" * 58 + "0f4240"
    raw_amount = decode_uint256_decimal(data_raw)

    assert raw_amount == Decimal("1000000")
    assert amount_with_decimals(raw_amount, 6) == Decimal("1")


def test_normalize_logs_uses_required_raw_contract_columns() -> None:
    raw_log = {
        "blockNumber": "0x64",
        "blockHash": "0xabc",
        "transactionHash": "0xdef",
        "transactionIndex": "0x0",
        "logIndex": "0x1",
        "address": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
        "topics": [TRANSFER_TOPIC0],
        "data": "0x",
        "removed": False,
    }

    result = normalize_logs(
        [raw_log],
        block_timestamps_utc={100: datetime(2024, 1, 1, tzinfo=UTC)},
        chain_id=1,
        interval_start_utc=datetime(2024, 1, 1, tzinfo=UTC),
        interval_end_utc=datetime(2024, 1, 1, 1, tzinfo=UTC),
        ingested_at_utc=datetime(2024, 1, 1, 2, tzinfo=UTC),
    )

    row = result.rows[0]
    assert row["contract_address"] == "0xdac17f958d2ee523a2206206994597c13d831ec7"
    assert row["data_raw"] == "0x"
    assert row["topic1"] is None
    assert row["block_timestamp_utc"] == datetime(2024, 1, 1, tzinfo=UTC)
