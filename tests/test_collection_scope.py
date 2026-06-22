"""Collection scope contract tests for the acceptance ingestion path."""

from __future__ import annotations

import pytest

from cryptoquant_pipeline.config import (
    COLLECTION_SCOPE_MODE,
    TRANSFER_TOPIC0,
    CollectionScope,
    PipelineSettings,
)
from cryptoquant_pipeline.exceptions import ConfigError


def _base_env() -> dict[str, str]:
    return {
        "ETH_RPC_URL": "https://rpc.example.invalid/v2/token",
        "ETH_CHAIN_ID": "1",
    }


def test_default_collection_scope_is_transfer_topic_all_addresses() -> None:
    scope = CollectionScope.default_transfer_topic_all_addresses(chain_id=1)

    assert scope.scope_id == COLLECTION_SCOPE_MODE
    assert scope.scope_mode == COLLECTION_SCOPE_MODE
    assert scope.chain_id == 1
    assert scope.address_filter is None
    assert scope.from_address_filter is None
    assert scope.to_address_filter is None
    assert scope.topic_filter == (TRANSFER_TOPIC0,)
    assert len(scope.fingerprint) == 64


def test_pipeline_settings_rejects_address_filter_scope_downgrade() -> None:
    env = _base_env() | {
        "ETH_LOG_ADDRESS_FILTER": "0xdac17f958d2ee523a2206206994597c13d831ec7"
    }

    with pytest.raises(ConfigError, match="ETH_LOG_ADDRESS_FILTER"):
        PipelineSettings.from_env(env)


def test_pipeline_settings_rejects_non_transfer_topic_scope() -> None:
    env = _base_env() | {"ETH_LOG_TOPIC0": "0x" + "0" * 64}

    with pytest.raises(ConfigError, match="ETH_LOG_TOPIC0"):
        PipelineSettings.from_env(env)
