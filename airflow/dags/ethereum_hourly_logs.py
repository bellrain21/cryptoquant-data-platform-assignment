"""Airflow DAG for hourly Ethereum Transfer-topic raw log ingestion."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from typing import Any

import pendulum
from airflow.decorators import dag, task
from airflow.exceptions import AirflowFailException
from airflow.operators.python import get_current_context

from cryptoquant_pipeline.exceptions import (
    BlockRangeError,
    ConfigError,
    DbtBuildError,
    DeltaWriteError,
    LogCollectionError,
    NonRetryableRpcError,
    NormalizationError,
)
from cryptoquant_pipeline.pipeline import (
    PipelineRunResult,
    run_interval,
    run_recent_finalized_interval,
)

MANUAL_RUN_MODE_DATA_INTERVAL = "data_interval"
MANUAL_RUN_MODE_RECENT_FINALIZED = "recent_finalized"

TERMINAL_PIPELINE_ERRORS = (
    BlockRangeError,
    ConfigError,
    DbtBuildError,
    DeltaWriteError,
    LogCollectionError,
    NormalizationError,
    NonRetryableRpcError,
)

DAG_DOC_MD = """
`ethereum_hourly_logs`는 UTC 기준 1시간 logical interval을 canonical pipeline으로 실행함.

- scheduled run과 기본 manual trigger는 Airflow `data_interval_start/end`를 그대로 사용함.
- DAG run conf에 `window_start`, `window_end`를 함께 넣으면 지정한 UTC 1시간 구간을 실행함.
- `ETH_AIRFLOW_MANUAL_RUN_MODE=recent_finalized`는 개발용 smoke 실행에만 사용함.
- `DbtBuildError`, schema/config 오류, single-block collection failure는 재시도 없이 failed 처리함.
"""


@dag(
    dag_id="ethereum_hourly_logs",
    schedule="@hourly",
    start_date=pendulum.datetime(2024, 1, 1, tz="UTC"),
    catchup=False,
    max_active_runs=1,
    is_paused_upon_creation=True,
    description="Hourly Ethereum Transfer-topic raw log ingestion.",
    doc_md=DAG_DOC_MD,
    default_args={
        "retries": 5,
        "retry_delay": timedelta(minutes=5),
        "retry_exponential_backoff": True,
    },
    tags=["ethereum", "delta", "dbt", "ethereum_hourly"],
)
def ethereum_hourly_logs() -> None:
    """Airflow UTC interval을 pipeline callable로 연결하는 얇은 orchestration DAG."""

    @task(task_id="run_interval")
    def run_interval_task() -> dict[str, Any]:
        context = get_current_context()

        try:
            mode, result = _run_from_context(context)
        except TERMINAL_PIPELINE_ERRORS as exc:
            # 실패 정책: 동일 입력 재시도로 해결되지 않는 계약·dbt·Delta 오류는 즉시 종료.
            # RetryableRpcError와 finality retry 오류는 잡지 않아 Airflow retry를 유지함.
            raise AirflowFailException(str(exc)) from exc

        return _result_payload(mode, result)

    run_interval_task()


def _run_from_context(context: dict[str, Any]) -> tuple[str, PipelineRunResult]:
    """실행 구간을 하나로 확정해 pipeline에 전달함."""
    conf = _dag_run_conf(context)

    if "window_start" in conf or "window_end" in conf:
        if "window_start" not in conf or "window_end" not in conf:
            raise ConfigError("DAG run conf requires both window_start and window_end.")

        start = _context_datetime(conf["window_start"])
        end = _context_datetime(conf["window_end"])
        _validate_hourly_interval(start, end, source="DAG run conf")

        return "conf_window", run_interval(start, end)

    if _is_manual_run(context):
        manual_mode = _manual_run_mode()

        if manual_mode == MANUAL_RUN_MODE_RECENT_FINALIZED:
            # 목적: 개발 중 provider 연결만 빠르게 확인하는 opt-in smoke helper.
            # 과제 제출용 1시간 E2E 증거에는 사용하지 않음.
            return (
                MANUAL_RUN_MODE_RECENT_FINALIZED,
                run_recent_finalized_interval(
                    window_seconds=_positive_int_env(
                        "ETH_AIRFLOW_RECENT_WINDOW_SECONDS",
                        default=120,
                    ),
                    finalized_lag_seconds=_non_negative_int_env(
                        "ETH_AIRFLOW_RECENT_FINALIZED_LAG_SECONDS",
                        default=0,
                    ),
                ),
            )

    start = _context_datetime(context["data_interval_start"])
    end = _context_datetime(context["data_interval_end"])

    # 불변식: acceptance path는 항상 완결된 UTC 1시간 [start, end) interval만 처리함.
    _validate_hourly_interval(start, end, source="Airflow data interval")

    return MANUAL_RUN_MODE_DATA_INTERVAL, run_interval(start, end)


def _result_payload(mode: str, result: PipelineRunResult) -> dict[str, Any]:
    """Airflow XCom에 남길 비밀값 없는 실행 결과 요약."""
    return {
        "mode": mode,
        "from_block": result.from_block,
        "to_block": result.to_block,
        "raw_log_count": result.raw_log_count,
        "normalized_log_count": result.normalized_log_count,
        "invalid_log_count": result.invalid_log_count,
        "inserted_row_count": result.delta_write.inserted_row_count,
        "duplicate_skipped_count": result.delta_write.duplicate_skipped_count,
        "row_count_after": result.delta_write.row_count_after,
        "dbt": dict(result.dbt_result),
    }


def _dag_run_conf(context: dict[str, Any]) -> dict[str, Any]:
    """DAG run config를 안전한 dict로 정규화."""
    dag_run = context.get("dag_run")
    conf = getattr(dag_run, "conf", None)
    return dict(conf) if isinstance(conf, dict) else {}


def _is_manual_run(context: dict[str, Any]) -> bool:
    """Airflow manual trigger 여부 확인."""
    dag_run = context.get("dag_run")
    return "manual" in str(getattr(dag_run, "run_type", "")).lower()


def _manual_run_mode() -> str:
    """manual trigger의 실행 경로를 명시적으로 제한."""
    mode = os.getenv(
        "ETH_AIRFLOW_MANUAL_RUN_MODE",
        MANUAL_RUN_MODE_DATA_INTERVAL,
    ).strip().lower()

    allowed_modes = {
        MANUAL_RUN_MODE_DATA_INTERVAL,
        MANUAL_RUN_MODE_RECENT_FINALIZED,
    }

    if mode not in allowed_modes:
        raise ConfigError(
            "ETH_AIRFLOW_MANUAL_RUN_MODE must be "
            "'data_interval' or 'recent_finalized'."
        )

    return mode


def _validate_hourly_interval(
    start: datetime,
    end: datetime,
    *,
    source: str,
) -> None:
    """UTC 1시간 [start, end) 계약을 검증."""
    if start >= end:
        raise ConfigError(f"{source} start must be earlier than end.")

    if end - start != timedelta(hours=1):
        raise ConfigError(
            f"{source} must define exactly one UTC hour, "
            f"received duration={end - start}."
        )


def _positive_int_env(name: str, *, default: int) -> int:
    """양수 환경 변수 읽기."""
    value = _non_negative_int_env(name, default=default)

    if value <= 0:
        raise ConfigError(f"{name} must be positive.")

    return value


def _non_negative_int_env(name: str, *, default: int) -> int:
    """0 이상 정수 환경 변수 읽기."""
    raw = os.getenv(name, "").strip()

    if not raw:
        return default

    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer.") from exc

    if value < 0:
        raise ConfigError(f"{name} must be greater than or equal to 0.")

    return value


def _context_datetime(value: object) -> datetime:
    """Airflow context 또는 DAG conf의 시간을 UTC-aware datetime으로 변환."""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ConfigError("Datetime value must include timezone information.")
        return value.astimezone(UTC)

    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))

    if parsed.tzinfo is None:
        raise ConfigError("Datetime string must include timezone information.")

    return parsed.astimezone(UTC)


ethereum_hourly_logs()