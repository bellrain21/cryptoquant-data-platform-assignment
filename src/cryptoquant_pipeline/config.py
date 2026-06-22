"""Runtime configuration for the hourly Ethereum log pipeline."""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cryptoquant_pipeline.chunking import MAX_BLOCKS_PER_LOG_REQUEST
from cryptoquant_pipeline.exceptions import ConfigError
from cryptoquant_pipeline.provider import ProviderConfig

USDT_CONTRACT_ADDRESS = "0xdac17f958d2ee523a2206206994597c13d831ec7"
TETHER_TREASURY_ADDRESS = "0x5754284f345afc66a98fbb0a0afe71e0f007b949"
TRANSFER_TOPIC0 = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
COLLECTION_SCOPE_MODE = "transfer_topic_all_addresses"


@dataclass(frozen=True)
class CollectionScope:
    """eth_getLogs query scope를 run 중 바뀌지 않는 non-secret 계약으로 보존함."""

    scope_id: str
    scope_mode: str
    chain_id: int
    address_filter: str | None
    topic_filter: tuple[str, ...]
    from_address_filter: str | None = None
    to_address_filter: str | None = None

    @classmethod
    def default_transfer_topic_all_addresses(cls, *, chain_id: int) -> CollectionScope:
        """과제 acceptance 기본값: 전체 address 대상 Transfer topic0만 조회함."""
        return cls(
            scope_id=COLLECTION_SCOPE_MODE,
            scope_mode=COLLECTION_SCOPE_MODE,
            chain_id=chain_id,
            address_filter=None,
            topic_filter=(TRANSFER_TOPIC0,),
        )

    @property
    def topics(self) -> list[str]:
        return list(self.topic_filter)

    @property
    def canonical_payload(self) -> dict[str, Any]:
        """manifest/validation에서 같은 scope인지 비교할 canonical JSON payload."""
        return {
            "scope_id": self.scope_id,
            "scope_mode": self.scope_mode,
            "chain_id": self.chain_id,
            "address_filter": self.address_filter,
            "topics": list(self.topic_filter),
            "from_address_filter": self.from_address_filter,
            "to_address_filter": self.to_address_filter,
        }

    @property
    def fingerprint(self) -> str:
        payload = json.dumps(self.canonical_payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def validate(self) -> None:
        """acceptance path가 USDT-only 또는 unfiltered scope로 drift하지 않게 막음."""
        if self.scope_mode != COLLECTION_SCOPE_MODE or self.scope_id != COLLECTION_SCOPE_MODE:
            raise ConfigError("ETH_COLLECTION_SCOPE_MODE must be transfer_topic_all_addresses.")
        if self.chain_id != 1:
            raise ConfigError("collection_scope currently supports Ethereum mainnet chain_id=1.")
        if self.address_filter is not None:
            raise ConfigError(
                "ETH_LOG_ADDRESS_FILTER must be empty for acceptance collection_scope."
            )
        if self.from_address_filter is not None or self.to_address_filter is not None:
            raise ConfigError(
                "from/to address filters are not part of acceptance collection_scope."
            )
        if self.topic_filter != (TRANSFER_TOPIC0,):
            raise ConfigError("ETH_LOG_TOPIC0 must be the ERC-20 Transfer topic0.")


@dataclass(frozen=True)
class PipelineSettings:
    """환경 변수에서 확정한 non-secret 실행 설정."""

    provider: ProviderConfig
    chain_id: int
    max_blocks_per_log_request: int
    rpc_timeout_seconds: float
    rpc_max_retries: int
    rpc_requests_per_second: float
    rpc_concurrency: int
    delta_logs_path: Path
    duckdb_path: Path
    dbt_project_dir: Path
    dbt_profiles_dir: Path
    dbt_bin: str
    collection_scope: CollectionScope
    usdt_contract_address: str
    tether_treasury_address: str
    usdt_decimals: int

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> PipelineSettings:
        """OS 환경 변수 또는 테스트 dict에서 설정을 구성함."""
        env = os.environ if environ is None else environ
        chain_id = _read_int_with_fallback(
            env,
            "ETH_CHAIN_ID",
            "EXPECTED_CHAIN_ID",
            default=1,
            minimum=1,
        )
        settings = cls(
            provider=ProviderConfig.from_env(env),
            chain_id=chain_id,
            max_blocks_per_log_request=_read_int(
                env,
                "ETH_LOG_MAX_BLOCK_RANGE",
                default=MAX_BLOCKS_PER_LOG_REQUEST,
                minimum=1,
            ),
            rpc_timeout_seconds=_read_float_with_fallback(
                env,
                "ETH_RPC_TIMEOUT_SECONDS",
                "RPC_TIMEOUT_SECONDS",
                default=20.0,
                minimum=0.1,
            ),
            rpc_max_retries=_read_int(env, "ETH_RPC_MAX_RETRIES", default=3, minimum=0),
            rpc_requests_per_second=_read_float(
                env,
                "ETH_RPC_REQUESTS_PER_SECOND",
                default=4.0,
                minimum=0.1,
            ),
            rpc_concurrency=_read_int(env, "ETH_RPC_CONCURRENCY", default=1, minimum=1),
            delta_logs_path=_read_path(
                env,
                "DELTA_LOGS_PATH",
                default=Path("/opt/airflow/data/delta/ethereum_logs"),
            ),
            duckdb_path=_read_path(
                env,
                "DUCKDB_PATH",
                default=Path("/opt/airflow/data/analytics/ethereum_analytics.duckdb"),
            ),
            dbt_project_dir=_read_path(env, "DBT_PROJECT_DIR", default=Path("/opt/airflow/dbt")),
            dbt_profiles_dir=_read_path(env, "DBT_PROFILES_DIR", default=Path("/opt/airflow/dbt")),
            dbt_bin=env.get("DBT_BIN", "dbt"),
            collection_scope=_read_collection_scope(env, chain_id=chain_id),
            usdt_contract_address=env.get("DBT_USDT_CONTRACT_ADDRESS", USDT_CONTRACT_ADDRESS),
            tether_treasury_address=env.get(
                "DBT_TETHER_TREASURY_ADDRESS",
                TETHER_TREASURY_ADDRESS,
            ),
            usdt_decimals=_read_int(env, "DBT_USDT_DECIMALS", default=6, minimum=0),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        """과제 불변식을 실행 전 검증함."""
        if self.max_blocks_per_log_request != MAX_BLOCKS_PER_LOG_REQUEST:
            raise ConfigError(
                "ETH_LOG_MAX_BLOCK_RANGE must be exactly "
                f"{MAX_BLOCKS_PER_LOG_REQUEST} for Alchemy Free compatibility."
            )
        if self.rpc_requests_per_second > 4:
            raise ConfigError("ETH_RPC_REQUESTS_PER_SECOND must be less than or equal to 4.")
        if self.rpc_concurrency != 1:
            raise ConfigError("ETH_RPC_CONCURRENCY must be 1 for local single-writer safety.")
        if self.collection_scope.chain_id != self.chain_id:
            raise ConfigError("collection_scope chain_id must match ETH_CHAIN_ID.")
        self.collection_scope.validate()
        _validate_address(self.usdt_contract_address, "DBT_USDT_CONTRACT_ADDRESS")
        _validate_address(self.tether_treasury_address, "DBT_TETHER_TREASURY_ADDRESS")


def _read_path(env: Mapping[str, str], name: str, *, default: Path) -> Path:
    raw = env.get(name)
    if raw is None or raw.strip() == "":
        return default
    return Path(raw)


def _read_int(env: Mapping[str, str], name: str, *, default: int, minimum: int) -> int:
    raw = env.get(name)
    if raw is None or raw.strip() == "":
        value = default
    else:
        try:
            value = int(raw)
        except ValueError as exc:
            raise ConfigError(f"{name} must be an integer.") from exc
    if value < minimum:
        raise ConfigError(f"{name} must be greater than or equal to {minimum}.")
    return value


def _read_int_with_fallback(
    env: Mapping[str, str],
    primary_name: str,
    fallback_name: str,
    *,
    default: int,
    minimum: int,
) -> int:
    if env.get(primary_name) not in (None, ""):
        return _read_int(env, primary_name, default=default, minimum=minimum)
    return _read_int(env, fallback_name, default=default, minimum=minimum)


def _read_float(env: Mapping[str, str], name: str, *, default: float, minimum: float) -> float:
    raw = env.get(name)
    if raw is None or raw.strip() == "":
        value = default
    else:
        try:
            value = float(raw)
        except ValueError as exc:
            raise ConfigError(f"{name} must be a number.") from exc
    if value < minimum:
        raise ConfigError(f"{name} must be greater than or equal to {minimum}.")
    return value


def _read_float_with_fallback(
    env: Mapping[str, str],
    primary_name: str,
    fallback_name: str,
    *,
    default: float,
    minimum: float,
) -> float:
    if env.get(primary_name) not in (None, ""):
        return _read_float(env, primary_name, default=default, minimum=minimum)
    return _read_float(env, fallback_name, default=default, minimum=minimum)


def _validate_address(value: str, name: str) -> None:
    if not isinstance(value, str) or len(value) != 42 or not value.startswith("0x"):
        raise ConfigError(f"{name} must be a 20-byte hex address.")
    int(value[2:], 16)


def _read_collection_scope(env: Mapping[str, str], *, chain_id: int) -> CollectionScope:
    scope = CollectionScope.default_transfer_topic_all_addresses(chain_id=chain_id)
    requested_mode = env.get("ETH_COLLECTION_SCOPE_MODE", scope.scope_mode).strip()
    if requested_mode and requested_mode != scope.scope_mode:
        raise ConfigError("ETH_COLLECTION_SCOPE_MODE must be transfer_topic_all_addresses.")
    address_filter = env.get("ETH_LOG_ADDRESS_FILTER", "").strip()
    topic0 = env.get("ETH_LOG_TOPIC0", TRANSFER_TOPIC0).strip().lower()
    configured = CollectionScope(
        scope_id=scope.scope_id,
        scope_mode=scope.scope_mode,
        chain_id=chain_id,
        address_filter=address_filter or None,
        topic_filter=(topic0,),
    )
    configured.validate()
    return configured
