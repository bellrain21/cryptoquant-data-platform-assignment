"""
요약:
    Raw/analytics 품질 검증과 구조화 metric 모듈.
역할:
    수집, 정규화, 적재, dbt 실행 후 row count와 duplicate 상태를 검증하고
    JSON 형태의 관측 metric을 로그로 남김.
파이프라인 위치:
    delta_writer.py -> quality_checks.py -> dbt build -> quality_checks.py.
입력:
    Airflow task metadata, Delta table path, DuckDB path.
출력:
    RawQualityMetrics 또는 analytics metric dict.
왜 분리하는가:
    검증 로직이 DAG에 섞이면 테스트와 재사용이 어려움. 별도 모듈로 두면
    같은 검증을 script와 Airflow에서 공유 가능함.
핵심 개념:
    데이터 파이프라인은 "실행됨"보다 "몇 건을 처리했고 중복/실패가 없었는지"가
    중요함. metric은 복구 범위를 판단하는 증거임.
대표 입력값:
    fetched_log_count=10, inserted_log_count=9, failed_subranges=[].
대표 출력값:
    unique_key_duplicate_count=0.
실패 영향:
    실패 subrange나 duplicate key를 놓치면 downstream 분석 결과가 불완전하거나
    과대 집계될 수 있음.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cryptoquant_pipeline.delta_writer import count_duplicate_natural_keys
from cryptoquant_pipeline.exceptions import DataQualityError

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class RawQualityMetrics:
    """
    요약:
        Raw layer 검증 metric 묶음.
    목적:
        Airflow log와 XCom에 남길 수 있는 작은 검증 결과를 표현함.
    왜 필요한가:
        raw payload 전체가 아니라 count와 범위만 보관해도 재처리 판단이 가능함.
    입력값:
        run_id, interval, block range, row counts, failed subranges.
    반환값:
        dataclass instance.
    정상 입력 예시:
        duplicate_skipped_count=1, failed_subranges=[].
    정상 출력 예시:
        unique_key_duplicate_count=0.
    실패 또는 경계 사례:
        failed_subranges가 있으면 validate_raw_metrics가 실패함.
    호출하는 모듈:
        Airflow validate_raw_data task.
    다음 단계:
        raw 검증 통과 후 dbt build가 실행됨.
    불변식:
        duplicate key count는 0이어야 함.
    """

    run_id: str  # Airflow run_id 또는 테스트 실행 id.
    interval_start: str  # logical interval 시작 시각.
    interval_end: str  # logical interval 종료 시각.
    start_block: int | None  # 실제 수집 시작 block.
    end_block: int | None  # 실제 수집 종료 block.
    fetched_log_count: int  # RPC에서 받은 raw log 수.
    normalized_log_count: int  # Delta schema 변환 성공 row 수.
    inserted_log_count: int  # Delta 신규 append row 수.
    duplicate_skipped_count: int  # 중복으로 skip된 row 수.
    invalid_log_count: int  # malformed payload로 제외된 log 수.
    failed_subranges: list[tuple[int, int]]  # 끝까지 실패한 block subrange.
    unique_key_duplicate_count: int  # Delta table 내 raw unique key 중복 수.


def validate_raw_metrics(
    *,
    run_id: str,  # Airflow run_id 또는 테스트 실행 id.
    interval_start: str,  # 수집 logical interval 시작 시각.
    interval_end: str,  # 수집 logical interval 종료 시각.
    start_block: int | None,  # 실제 수집 시작 block.
    end_block: int | None,  # 실제 수집 종료 block.
    fetched_log_count: int,  # RPC에서 받은 raw log 수.
    normalized_log_count: int,  # Delta schema로 변환된 row 수.
    inserted_log_count: int,  # Delta에 새로 append된 row 수.
    duplicate_skipped_count: int,  # unique key 기준 skip된 중복 row 수.
    invalid_log_count: int,  # schema 변환에서 제외된 malformed log 수.
    failed_subranges: list[tuple[int, int]],  # 최종 실패한 block subrange 목록.
    delta_logs_path: str | Path,  # duplicate key를 확인할 Delta table path.
) -> RawQualityMetrics:
    """
    목적:
        raw Delta table의 기본 품질 계약을 검증함.
    왜 필요한가:
        `eth_getLogs` 일부 range 실패 또는 Delta 중복은 dbt 모델이 바로
        알아채기 어려움.
    입력값:
        run id, interval, block range, count metadata, Delta path.
    반환값:
        RawQualityMetrics.
    정상 입력 예시:
        failed_subranges=[], duplicate_count=0.
    정상 출력 예시:
        RawQualityMetrics(unique_key_duplicate_count=0).
    실패 또는 경계 사례:
        failed_subranges가 남아 있거나 duplicate key가 있으면 DataQualityError.
    호출 위치:
        legacy cryptoquant_pipeline tests. 현재 DAG는 airflow/dags/ethereum_hourly_logs.py.
    다음 단계:
        통과 후 dbt_runner.run_dbt_build 경계가 실행됨.
    불변식:
        수집 성공으로 넘어가려면 실패 subrange와 raw duplicate가 없어야 함.
    """
    duplicate_count = count_duplicate_natural_keys(delta_logs_path)
    metrics = RawQualityMetrics(
        run_id=run_id,
        interval_start=interval_start,
        interval_end=interval_end,
        start_block=start_block,
        end_block=end_block,
        fetched_log_count=fetched_log_count,
        normalized_log_count=normalized_log_count,
        inserted_log_count=inserted_log_count,
        duplicate_skipped_count=duplicate_skipped_count,
        invalid_log_count=invalid_log_count,
        failed_subranges=failed_subranges,
        unique_key_duplicate_count=duplicate_count,
    )
    log_structured("raw_quality_metrics", asdict(metrics))
    if failed_subranges:
        raise DataQualityError(f"Failed block subranges remain: {failed_subranges}")
    if duplicate_count > 0:
        raise DataQualityError(f"Raw Delta table has {duplicate_count} duplicate unique keys.")
    return metrics


def validate_analytics_metrics(
    duckdb_path: str | Path,  # dbt 결과가 저장된 DuckDB 파일 경로.
) -> dict[str, Any]:
    """
    목적:
        dbt build 이후 analytics table의 핵심 count를 조회함.
    왜 필요한가:
        dbt test 통과 여부와 별도로 Airflow log에 ERC-20/Treasury 결과 규모를
        남겨야 실행 결과를 추적 가능함.
    입력값:
        DuckDB database path.
    반환값:
        erc20_transfer_count, treasury transfer count, inflow/outflow/net_flow dict.
    정상 입력 예시:
        duckdb_path="/opt/airflow/data/analytics/ethereum_analytics.duckdb".
    정상 출력 예시:
        {"erc20_transfer_count": 1, "net_flow": "100"}.
    실패 또는 경계 사례:
        DuckDB 파일이 없으면 DataQualityError.
    호출 위치:
        Airflow validate_analytics_data task.
    다음 단계:
        DAG 최종 로그에 analytics metric을 남김.
    불변식:
        이 함수는 analytics row를 변경하지 않고 read-only connection을 사용함.
    """
    try:
        import duckdb
    except ImportError as exc:
        raise DataQualityError("duckdb is required for analytics validation.") from exc

    path = Path(duckdb_path)
    if not path.exists():
        raise DataQualityError(f"DuckDB database does not exist: {path}")

    try:
        with duckdb.connect(str(path), read_only=True) as con:
            erc20_count = _required_scalar(
                con,
                "select count(*) from main.erc20_transfers",
                metric_name="erc20_transfer_count",
            )
            treasury_count = _required_scalar(
                con,
                "select coalesce(sum(transfer_count), 0) from main.tether_treasury_flow",
                metric_name="usdt_treasury_transfer_count",
            )
            flow = con.execute(
                """
                select
                    coalesce(
                        sum(
                            case
                                when direction = 'INFLOW' then total_amount_usdt
                                else 0
                            end
                        ),
                        0
                    ) as inflow,
                    coalesce(
                        sum(
                            case
                                when direction = 'OUTFLOW' then total_amount_usdt
                                else 0
                            end
                        ),
                        0
                    ) as outflow,
                    coalesce(
                        sum(
                            case
                                when direction = 'INFLOW' then total_amount_usdt
                                when direction = 'OUTFLOW' then -total_amount_usdt
                                else 0
                            end
                        ),
                        0
                    ) as net_flow
                from main.tether_treasury_flow
                """
            ).fetchone()
    except DataQualityError:
        raise
    except Exception as exc:
        raise DataQualityError("Analytics validation query failed.") from exc

    metrics = {
        "erc20_transfer_count": erc20_count,
        "usdt_treasury_transfer_count": treasury_count,
        "inflow": str(flow[0]) if flow else "0",
        "outflow": str(flow[1]) if flow else "0",
        "net_flow": str(flow[2]) if flow else "0",
    }
    log_structured("analytics_quality_metrics", metrics)
    return metrics


def log_structured(
    event: str,  # 로그 event 이름.
    fields: dict[str, Any],  # JSON으로 남길 metric field.
) -> None:
    """
    목적:
        key/value metric을 JSON 문자열로 로그에 남김.
    왜 필요한가:
        자유 문장 로그보다 JSON 로그가 run_id, interval, count 검색에 유리함.
    입력값:
        event name, fields dict.
    반환값:
        없음.
    정상 입력 예시:
        event="raw_quality_metrics", fields={"run_id": "..."}.
    정상 출력 예시:
        logger.info에 JSON 문자열 기록.
    실패 또는 경계 사례:
        datetime 등은 default=str로 직렬화함.
    호출 위치:
        validate_raw_metrics, validate_analytics_metrics.
    다음 단계:
        Airflow task log에서 실행 증거로 사용됨.
    불변식:
        API key나 full RPC URL 같은 민감값을 fields에 넣지 않아야 함.
    """
    payload = {
        "event": event,
        "logged_at": datetime.now(UTC).isoformat(),
        **fields,
    }
    LOGGER.info(json.dumps(payload, sort_keys=True, default=str))


def _required_scalar(
    con: Any,  # DuckDB connection.
    sql: str,  # 단일 scalar 값을 반환해야 하는 SQL.
    *,
    metric_name: str,  # 실패 메시지에 남길 metric 이름.
) -> int:
    try:
        value = con.execute(sql).fetchone()[0]
    except Exception as exc:
        # schema drift나 누락 table을 0건 성공처럼 숨기지 않음.
        raise DataQualityError(f"Analytics metric query failed: {metric_name}") from exc
    return int(value or 0)
