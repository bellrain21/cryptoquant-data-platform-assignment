"""Pipeline-level idempotency and dbt var propagation tests."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from cryptoquant_pipeline.config import TRANSFER_TOPIC0, CollectionScope, PipelineSettings
from cryptoquant_pipeline.delta_writer import count_rows
from cryptoquant_pipeline.pipeline import run_interval, run_recent_finalized_interval
from cryptoquant_pipeline.provider import ProviderConfig


class FakeRpcClient:
    base = datetime(2024, 1, 1, tzinfo=UTC)

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        pass

    def __enter__(self) -> FakeRpcClient:
        return self

    def __exit__(self, *_exc_info: object) -> None:
        pass

    def eth_chain_id(self) -> int:
        return 1

    def eth_get_finalized_block(self) -> dict[str, str]:
        return self._block_payload(20)

    def eth_get_block_by_number(
        self,
        block_number: int | str,
        *,
        full_transactions: bool = False,
    ) -> dict[str, str]:
        del full_transactions
        number = 20 if block_number == "finalized" else int(block_number)
        return self._block_payload(number)

    def eth_get_logs(
        self,
        *,
        from_block: int,
        to_block: int,
        address: str | Sequence[str] | None = None,
        topics: Sequence[Any] | None = None,
    ) -> list[Mapping[str, Any]]:
        del to_block
        assert address is None
        assert topics == [TRANSFER_TOPIC0]
        return [
            {
                "blockNumber": hex(from_block),
                "blockHash": "0xabc",
                "transactionHash": "0xdef",
                "transactionIndex": "0x0",
                "logIndex": "0x1",
                "address": "0x1234567890abcdef1234567890abcdef12345678",
                "topics": [TRANSFER_TOPIC0],
                "data": "0x",
                "removed": False,
            }
        ]

    def _block_payload(self, number: int) -> dict[str, str]:
        timestamp = self.base + timedelta(minutes=number)
        return {"number": hex(number), "timestamp": hex(int(timestamp.timestamp()))}


def test_same_interval_twice_keeps_delta_count_and_passes_dbt_vars(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    import cryptoquant_pipeline.pipeline as pipeline_module

    monkeypatch.setattr(pipeline_module, "EthereumJsonRpcClient", FakeRpcClient)
    settings = PipelineSettings(
        provider=ProviderConfig(endpoint_url="https://example.invalid/rpc"),
        chain_id=1,
        max_blocks_per_log_request=10,
        rpc_timeout_seconds=20.0,
        rpc_max_retries=0,
        rpc_requests_per_second=4.0,
        rpc_concurrency=1,
        delta_logs_path=tmp_path / "ethereum_logs",
        duckdb_path=tmp_path / "analytics.duckdb",
        dbt_project_dir=tmp_path / "dbt",
        dbt_profiles_dir=tmp_path / "dbt",
        dbt_bin="dbt",
        collection_scope=CollectionScope.default_transfer_topic_all_addresses(chain_id=1),
        usdt_contract_address="0xdac17f958d2ee523a2206206994597c13d831ec7",
        tether_treasury_address="0x5754284f345afc66a98fbb0a0afe71e0f007b949",
        usdt_decimals=6,
    )
    calls: list[tuple[str, str]] = []

    def fake_dbt_runner(
        _settings: PipelineSettings,
        window_start_utc: datetime,
        window_end_utc: datetime,
    ) -> Mapping[str, Any]:
        calls.append((window_start_utc.isoformat(), window_end_utc.isoformat()))
        return {"returncode": 0}

    start = datetime(2024, 1, 1, 0, 5, tzinfo=UTC)
    end = datetime(2024, 1, 1, 0, 7, tzinfo=UTC)

    first = run_interval(start, end, settings=settings, dbt_runner=fake_dbt_runner)
    second = run_interval(start, end, settings=replace(settings), dbt_runner=fake_dbt_runner)

    assert first.delta_write.row_count_after == 1
    assert second.delta_write.row_count_after == 1
    assert count_rows(settings.delta_logs_path) == 1
    assert calls == [(start.isoformat(), end.isoformat()), (start.isoformat(), end.isoformat())]


def test_recent_finalized_interval_runs_real_pipeline_path(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    import cryptoquant_pipeline.pipeline as pipeline_module

    monkeypatch.setattr(pipeline_module, "EthereumJsonRpcClient", FakeRpcClient)
    settings = PipelineSettings(
        provider=ProviderConfig(endpoint_url="https://example.invalid/rpc"),
        chain_id=1,
        max_blocks_per_log_request=10,
        rpc_timeout_seconds=20.0,
        rpc_max_retries=0,
        rpc_requests_per_second=4.0,
        rpc_concurrency=1,
        delta_logs_path=tmp_path / "ethereum_logs",
        duckdb_path=tmp_path / "analytics.duckdb",
        dbt_project_dir=tmp_path / "dbt",
        dbt_profiles_dir=tmp_path / "dbt",
        dbt_bin="dbt",
        collection_scope=CollectionScope.default_transfer_topic_all_addresses(chain_id=1),
        usdt_contract_address="0xdac17f958d2ee523a2206206994597c13d831ec7",
        tether_treasury_address="0x5754284f345afc66a98fbb0a0afe71e0f007b949",
        usdt_decimals=6,
    )
    calls: list[tuple[str, str]] = []

    def fake_dbt_runner(
        _settings: PipelineSettings,
        window_start_utc: datetime,
        window_end_utc: datetime,
    ) -> Mapping[str, Any]:
        calls.append((window_start_utc.isoformat(), window_end_utc.isoformat()))
        return {"returncode": 0}

    result = run_recent_finalized_interval(
        window_seconds=120,
        settings=settings,
        dbt_runner=fake_dbt_runner,
    )

    assert result.from_block == 18
    assert result.to_block == 19
    assert result.delta_write.row_count_after == 1
    assert calls == [
        (
            datetime(2024, 1, 1, 0, 18, tzinfo=UTC).isoformat(),
            datetime(2024, 1, 1, 0, 20, tzinfo=UTC).isoformat(),
        )
    ]
