"""
요약:
    delta_writer.py idempotency 테스트.
역할:
    동일 raw log batch를 두 번 적재해도 Delta table row count와 unique key count가
    안정적인지 검증함.
파이프라인 위치:
    log_normalizer.py 이후, dbt staging 이전.
입력:
    중복 log가 포함된 tests/fixtures/rpc_logs.json.
출력:
    local temp Delta table row count와 duplicate key count.
왜 분리하는가:
    Airflow retry/backfill은 실제 운영에서 같은 interval을 다시 처리함.
    이 테스트는 그 재실행이 결과를 부풀리지 않는지 증명함.
핵심 개념:
    raw event identity는 chain_id + transaction_hash + log_index임.
대표 입력값:
    같은 transactionHash/logIndex가 두 번 들어 있는 fixture.
대표 출력값:
    Delta row count=1, duplicate key count=0.
실패 영향:
    이 테스트가 깨지면 downstream Treasury flow가 중복 집계될 수 있음.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from cryptoquant_pipeline.delta_writer import (
    count_duplicate_natural_keys,
    count_rows,
    write_ethereum_logs_insert_only,
)
from cryptoquant_pipeline.log_normalizer import normalize_logs


def test_delta_writer_is_idempotent_for_same_raw_batch(
    tmp_path: Path,  # pytest가 제공하는 임시 디렉터리 fixture.
) -> None:
    """
    검증 목적:
        동일 Ethereum log batch를 두 번 적재해도 row 수가 증가하지 않는지 검증함.
    막는 버그:
        Airflow retry 또는 manual backfill 시 같은 log가 Delta table에 중복 저장되는 문제.
    실제 운영 상황:
        write 직후 task가 실패하거나 DAG를 재실행하면 동일 interval이 다시 처리될 수 있음.
    fixture 의미:
        rpc_logs.json은 같은 transaction_hash/log_index를 가진 log를 두 번 포함함.
    실패 시 우선 확인:
        delta_writer.py의 unique key 생성, existing key filtering, duplicate skip count.
    기대 결과:
        첫 번째 write와 두 번째 write 이후의 row count가 같고 duplicate count는 0임.
    """
    raw_logs = json.loads(Path("tests/fixtures/rpc_logs.json").read_text(encoding="utf-8"))
    normalized = normalize_logs(
        raw_logs,
        block_timestamps_utc={100: datetime(2024, 1, 1, 0, 0, tzinfo=UTC)},
        chain_id=1,
        interval_start_utc=datetime(2024, 1, 1, 0, 0, tzinfo=UTC),
        interval_end_utc=datetime(2024, 1, 1, 1, 0, tzinfo=UTC),
        ingested_at_utc=datetime(2024, 1, 1, 1, 0, tzinfo=UTC),
    )
    table_path = tmp_path / "ethereum_logs"

    first = write_ethereum_logs_insert_only(normalized.rows, table_path=table_path)
    first_count = count_rows(table_path)
    second = write_ethereum_logs_insert_only(normalized.rows, table_path=table_path)
    second_count = count_rows(table_path)

    assert first.inserted_row_count == 1
    assert first_count == 1
    assert second.inserted_row_count == 0
    assert second.duplicate_skipped_count == 2
    assert second_count == first_count
    assert count_duplicate_natural_keys(table_path) == 0
