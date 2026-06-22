"""Current environment contract checks for the canonical pipeline package."""

from __future__ import annotations

from pathlib import Path

import pytest

from cryptoquant_pipeline import MAX_BLOCKS_PER_LOG_REQUEST, run_interval
from cryptoquant_pipeline.config import TRANSFER_TOPIC0, PipelineSettings
from cryptoquant_pipeline.exceptions import ConfigError


def _base_env() -> dict[str, str]:
    return {
        "ETH_RPC_URL": "https://rpc.example.invalid/v2/token",
        "ETH_CHAIN_ID": "1",
    }


def test_package_exports_current_pipeline_entrypoint() -> None:
    """삭제된 legacy package 대신 현재 Airflow가 호출하는 package contract를 확인함."""
    assert callable(run_interval)
    assert MAX_BLOCKS_PER_LOG_REQUEST == 10


def test_pipeline_settings_defaults_match_canonical_local_paths() -> None:
    """Docker와 dbt 기본 경로가 `_v2` legacy path로 되돌아가는 회귀를 막음."""
    settings = PipelineSettings.from_env(_base_env())

    assert settings.delta_logs_path == Path("/opt/airflow/data/delta/ethereum_logs")
    assert settings.duckdb_path == Path("/opt/airflow/data/analytics/ethereum_analytics.duckdb")
    assert settings.dbt_project_dir == Path("/opt/airflow/dbt")
    assert settings.dbt_profiles_dir == Path("/opt/airflow/dbt")
    assert settings.collection_scope.address_filter is None
    assert settings.collection_scope.topic_filter == (TRANSFER_TOPIC0,)


def test_pipeline_settings_requires_rpc_url_for_real_collection() -> None:
    """실제 RPC 수집 경로는 secret 없는 fixture 검증과 다르게 provider URL을 요구함."""
    with pytest.raises(ConfigError, match="ETH_RPC_URL"):
        PipelineSettings.from_env({})


def test_pipeline_settings_masks_provider_endpoint() -> None:
    """RPC URL 원문은 설정 객체에 보관되더라도 audit 표현에는 노출하지 않음."""
    settings = PipelineSettings.from_env(_base_env())

    assert settings.provider.endpoint_url == "https://rpc.example.invalid/v2/token"
    assert settings.provider.redacted_endpoint == "<configured>"
