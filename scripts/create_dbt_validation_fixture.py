"""Create a small Delta fixture for local dbt validation."""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from datetime import UTC, date, datetime
from pathlib import Path

from cryptoquant_pipeline.config import TRANSFER_TOPIC0
from cryptoquant_pipeline.delta_writer import write_ethereum_logs_insert_only


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("data/tmp/dbt_validation"))
    args = parser.parse_args()

    root = args.root
    resolved = root.resolve()
    if "dbt_validation" not in resolved.parts:
        raise SystemExit("Refusing to remove a path outside a dbt_validation directory.")
    shutil.rmtree(resolved, ignore_errors=True)

    treasury_topic = "0x" + "0" * 24 + "5754284f345afc66a98fbb0a0afe71e0f007b949"
    random_topic = "0x" + "0" * 24 + "1111111111111111111111111111111111111111"
    rows = [
        _row(
            transaction_hash="0xdef",
            log_index=1,
            contract_address="0xdac17f958d2ee523a2206206994597c13d831ec7",
            topic1=treasury_topic,
            topic2=random_topic,
        ),
        # 목적: erc20_transfers는 collection scope 안의 Transfer를 모두 decode해야 함.
        # Gold treasury 집계에서만 USDT contract 조건으로 business_rule_excluded 처리됨.
        _row(
            transaction_hash="0xbeef",
            log_index=2,
            contract_address="0x2222222222222222222222222222222222222222",
            topic1=treasury_topic,
            topic2=random_topic,
        ),
    ]
    result = write_ethereum_logs_insert_only(rows, table_path=resolved / "ethereum_logs")
    print({"inserted": result.inserted_row_count, "rows": result.row_count_after})


def _row(
    *,
    transaction_hash: str,
    log_index: int,
    contract_address: str,
    topic1: str,
    topic2: str,
) -> dict[str, object]:
    return {
        "chain_id": 1,
        "block_number": 100,
        "block_hash": "0xabc",
        "transaction_hash": transaction_hash,
        "transaction_index": 0,
        "log_index": log_index,
        "contract_address": contract_address,
        "topic0": TRANSFER_TOPIC0,
        "topic1": topic1,
        "topic2": topic2,
        "topic3": None,
        "data_raw": "0x" + "0" * 58 + "0f4240",
        # 불변: raw data와 Python normalizer가 확정한 uint256 해석 상태를 함께 저장한다.
        # dbt는 이 계약을 기준으로 ERC-20 amount를 손실 없이 파생한다.
        "data_uint256_decimal_text": "1000000",
        "data_uint256_decode_status": "DECIMAL38_AVAILABLE",
        "removed": False,
        "block_timestamp_utc": datetime(2024, 1, 1, 0, 5, tzinfo=UTC),
        "block_date_utc": date(2024, 1, 1),
        "interval_start_utc": datetime(2024, 1, 1, 0, 0, tzinfo=UTC),
        "interval_end_utc": datetime(2024, 1, 1, 1, 0, tzinfo=UTC),
        "ingested_at_utc": datetime(2024, 1, 1, 1, 5, tzinfo=UTC),
    }


if __name__ == "__main__":
    main()
    # deltalake/pyarrow native teardown can abort after successful fixture output
    # in a one-shot validation script. Exceptions still propagate before this point.
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)
