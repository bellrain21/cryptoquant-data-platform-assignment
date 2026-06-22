"""Thin pipeline orchestration callable used by Airflow and tests."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from cryptoquant_pipeline.block_range import (
    block_timestamp_from_payload,
    resolve_interval_block_range,
)
from cryptoquant_pipeline.config import PipelineSettings
from cryptoquant_pipeline.dbt_runner import run_dbt_build
from cryptoquant_pipeline.delta_writer import (
    DeltaWriteResult,
    write_ethereum_logs_insert_only,
)
from cryptoquant_pipeline.exceptions import (
    NonRetryableRpcError,
    NormalizationError,
    RpcErrorDetail,
)
from cryptoquant_pipeline.log_collector import collect_raw_logs
from cryptoquant_pipeline.log_normalizer import normalize_logs
from cryptoquant_pipeline.rpc_client import EthereumJsonRpcClient

DbtRunner = Callable[[PipelineSettings, datetime, datetime], Mapping[str, Any]]

@dataclass(frozen=True)
class PipelineRunResult:
    """한 logical interval의 수집·적재·dbt 실행 결과 요약."""

    from_block: int
    to_block: int
    raw_log_count: int
    normalized_log_count: int
    invalid_log_count: int
    delta_write: DeltaWriteResult
    dbt_result: Mapping[str, Any]


def run_interval(
    interval_start_utc: datetime,
    interval_end_utc: datetime,
    *,
    settings: PipelineSettings | None = None,
    dbt_runner: DbtRunner | None = None,
) -> PipelineRunResult:
    """
    하나의 UTC logical interval을 수집하고 Delta 적재 후 dbt build를 실행함.

    불변식:
    source_schema_invalid가 하나라도 있으면 Delta와 dbt로 진행하지 않음.
    """
    resolved_settings = settings or PipelineSettings.from_env()
    start, end = _normalize_interval_bounds(
        interval_start_utc,
        interval_end_utc,
    )

    with EthereumJsonRpcClient(
        resolved_settings.provider,
        timeout_seconds=resolved_settings.rpc_timeout_seconds,
        max_retries=resolved_settings.rpc_max_retries,
        requests_per_second=resolved_settings.rpc_requests_per_second,
    ) as client:
        chain_id = client.eth_chain_id()

        if chain_id != resolved_settings.chain_id:
            raise NonRetryableRpcError(
                RpcErrorDetail(
                    method="eth_chainId",
                    message="Provider chain id does not match ETH_CHAIN_ID.",
                    retryable=False,
                )
            )

        block_range = resolve_interval_block_range(
            client,
            interval_start_utc=start,
            interval_end_utc=end,
        )

        raw_logs = collect_raw_logs(
            client,
            from_block=block_range.from_block,
            to_block=block_range.to_block,
            collection_scope=resolved_settings.collection_scope,
            max_blocks=resolved_settings.max_blocks_per_log_request,
        )

        block_timestamps = _load_block_timestamps(client, raw_logs)

    normalized = normalize_logs(
        raw_logs,
        block_timestamps_utc=block_timestamps,
        chain_id=resolved_settings.chain_id,
        interval_start_utc=start,
        interval_end_utc=end,
    )

    if normalized.invalid_log_count > 0:
        # 실패 정책: RPC raw landing contract 위반은 부분 성공으로 넘기지 않음.
        raise NormalizationError(
            "source_schema_invalid_count="
            f"{normalized.invalid_log_count}, "
            f"raw_log_count={len(raw_logs)}"
        )

    delta_result = write_ethereum_logs_insert_only(
        normalized.rows,
        table_path=resolved_settings.delta_logs_path,
    )

    dbt_result = (dbt_runner or run_dbt_build)(
        resolved_settings,
        start,
        end,
    )

    return PipelineRunResult(
        from_block=block_range.from_block,
        to_block=block_range.to_block,
        raw_log_count=len(raw_logs),
        normalized_log_count=len(normalized.rows),
        invalid_log_count=normalized.invalid_log_count,
        delta_write=delta_result,
        dbt_result=dbt_result,
    )


def run_recent_finalized_interval(
    *,
    window_seconds: int = 120,
    finalized_lag_seconds: int = 0,
    settings: PipelineSettings | None = None,
    dbt_runner: DbtRunner | None = None,
) -> PipelineRunResult:
    """
    개발용 provider smoke helper.

    과제 제출용 1시간 E2E는 Airflow data_interval 경로를 사용해야 함.
    """
    if window_seconds <= 0:
        raise ValueError("window_seconds must be positive.")

    if finalized_lag_seconds < 0:
        raise ValueError(
            "finalized_lag_seconds must be greater than or equal to 0."
        )

    resolved_settings = settings or PipelineSettings.from_env()

    with EthereumJsonRpcClient(
        resolved_settings.provider,
        timeout_seconds=resolved_settings.rpc_timeout_seconds,
        max_retries=resolved_settings.rpc_max_retries,
        requests_per_second=resolved_settings.rpc_requests_per_second,
    ) as client:
        chain_id = client.eth_chain_id()

        if chain_id != resolved_settings.chain_id:
            raise NonRetryableRpcError(
                RpcErrorDetail(
                    method="eth_chainId",
                    message="Provider chain id does not match ETH_CHAIN_ID.",
                    retryable=False,
                )
            )

        finalized_ts = block_timestamp_from_payload(
            client.eth_get_finalized_block()
        )

    interval_end = finalized_ts - timedelta(
        seconds=finalized_lag_seconds
    )
    interval_start = interval_end - timedelta(
        seconds=window_seconds
    )

    return run_interval(
        interval_start,
        interval_end,
        settings=resolved_settings,
        dbt_runner=dbt_runner,
    )


def _load_block_timestamps(
    client: EthereumJsonRpcClient,
    raw_logs: list[Mapping[str, Any]],
) -> dict[int, datetime]:
    """raw event log가 속한 block의 UTC timestamp를 조회함."""
    block_numbers = sorted(
        {
            int(str(raw_log["blockNumber"]), 16)
            for raw_log in raw_logs
            if isinstance(raw_log.get("blockNumber"), str)
        }
    )

    timestamps: dict[int, datetime] = {}

    for block_number in block_numbers:
        timestamps[block_number] = block_timestamp_from_payload(
            client.eth_get_block_by_number(
                block_number,
                full_transactions=False,
            )
        )

    return timestamps


def _normalize_interval_bounds(
    interval_start_utc: datetime,
    interval_end_utc: datetime,
) -> tuple[datetime, datetime]:
    """timezone-aware 입력을 UTC로 정규화하고 시간 경계 역전을 차단함."""
    if interval_start_utc.tzinfo is None:
        raise ValueError("interval_start_utc must include timezone information.")

    if interval_end_utc.tzinfo is None:
        raise ValueError("interval_end_utc must include timezone information.")

    start = interval_start_utc.astimezone(UTC)
    end = interval_end_utc.astimezone(UTC)

    if start >= end:
        raise ValueError(
            "interval_start_utc must be earlier than interval_end_utc."
        )

    return start, end
