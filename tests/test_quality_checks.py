"""
요약:
    quality_checks.py raw quality metric 테스트.
역할:
    Delta write 이후 raw table duplicate 검증 metric이 정상 생성되는지 확인함.
파이프라인 위치:
    write_delta_logs task 이후 validate_raw_data task.
입력:
    fixture log 1건을 적재한 임시 Delta table.
출력:
    RawQualityMetrics.
왜 분리하는가:
    DAG 성공 여부만으로는 failed subrange나 duplicate key를 알 수 없음.
핵심 개념:
    품질 검증은 "몇 건 처리했는가"와 "중복이 없는가"를 실행 증거로 남김.
대표 입력값:
    fetched_log_count=1, inserted_log_count=1.
대표 출력값:
    unique_key_duplicate_count=0.
실패 영향:
    품질 검증이 깨지면 raw 오류가 dbt 결과로 전파될 수 있음.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from cryptoquant_pipeline.delta_writer import write_ethereum_logs_insert_only
from cryptoquant_pipeline.exceptions import DataQualityError
from cryptoquant_pipeline.log_normalizer import normalize_logs
from cryptoquant_pipeline.quality_checks import validate_analytics_metrics, validate_raw_metrics


def test_validate_raw_metrics_reports_duplicate_free_delta_table(
    tmp_path: Path,  # pytest가 제공하는 임시 Delta table root.
) -> None:
    """
    검증 목적:
        duplicate가 없는 Delta table에 대해 raw quality metric이 성공하는지 확인함.
    막는 버그:
        정상 적재 결과를 잘못 실패 처리하거나 duplicate count를 잘못 계산하는 문제.
    실제 운영 상황:
        write_delta_logs 이후 validate_raw_data task가 실행됨.
    fixture 의미:
        ERC-20 Transfer log 1건을 임시 Delta table에 적재함.
    실패 시 우선 확인:
        quality_checks.validate_raw_metrics와 delta_writer.count_duplicate_natural_keys.
    기대 결과:
        unique_key_duplicate_count=0, inserted_log_count=1.
    """
    raw_logs = json.loads(Path("tests/fixtures/rpc_logs.json").read_text(encoding="utf-8"))[:1]
    normalized = normalize_logs(
        raw_logs,
        block_timestamps_utc={100: datetime(2024, 1, 1, 0, 0, tzinfo=UTC)},
        chain_id=1,
        interval_start_utc=datetime(2024, 1, 1, 0, 0, tzinfo=UTC),
        interval_end_utc=datetime(2024, 1, 1, 1, 0, tzinfo=UTC),
        ingested_at_utc=datetime(2024, 1, 1, 1, 0, tzinfo=UTC),
    )
    table_path = tmp_path / "ethereum_logs"
    write_result = write_ethereum_logs_insert_only(normalized.rows, table_path=table_path)

    metrics = validate_raw_metrics(
        run_id="test-run",
        interval_start="2024-01-01T00:00:00+00:00",
        interval_end="2024-01-01T01:00:00+00:00",
        start_block=100,
        end_block=100,
        fetched_log_count=1,
        normalized_log_count=len(normalized.rows),
        inserted_log_count=write_result.inserted_row_count,
        duplicate_skipped_count=write_result.duplicate_skipped_count,
        invalid_log_count=0,
        failed_subranges=[],
        delta_logs_path=table_path,
    )

    assert metrics.unique_key_duplicate_count == 0
    assert metrics.inserted_log_count == 1


def test_validate_analytics_metrics_fails_when_required_table_is_missing(
    tmp_path: Path,  # pytest가 제공하는 임시 DuckDB 파일 경로.
) -> None:
    """
    검증 목적:
        dbt 결과 table이 없을 때 analytics metric을 0으로 숨기지 않는지 확인함.
    막는 버그:
        schema drift 또는 dbt 미실행 상태를 `0 rows` 성공처럼 보고하는 문제.
    실제 운영 상황:
        dbt build가 실패했거나 DuckDB 파일은 있지만 모델 table이 생성되지 않음.
    fixture 의미:
        빈 DuckDB database 파일만 만들고 `erc20_transfers` table은 만들지 않음.
    실패 시 우선 확인:
        quality_checks._required_scalar.
    기대 결과:
        DataQualityError가 발생함.
    """
    import duckdb

    db_path = tmp_path / "analytics.duckdb"
    duckdb.connect(str(db_path)).close()

    with pytest.raises(DataQualityError, match="Analytics metric query failed"):
        validate_analytics_metrics(db_path)
