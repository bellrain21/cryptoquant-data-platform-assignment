"""Provider 설정 검증 테스트.

실제 RPC endpoint/API key를 사용하지 않고, 잘못된 `.env.example` 복사 상태를
네트워크 재시도 전에 설정 오류로 차단하는지 확인함.
"""

from __future__ import annotations

import pytest

from cryptoquant_pipeline.exceptions import ConfigError
from cryptoquant_pipeline.provider import ProviderConfig


def test_provider_config_rejects_example_placeholder_endpoint() -> None:
    """`.env.example` placeholder가 실제 provider처럼 실행되는 회귀를 막음."""
    with pytest.raises(ConfigError, match="example placeholder"):
        ProviderConfig.from_env({"ETH_RPC_URL": "https://your-provider.example/v2/YOUR_API_KEY"})


def test_provider_config_rejects_non_absolute_endpoint() -> None:
    """scheme 없는 endpoint가 httpx transport 오류까지 내려가지 않도록 막음."""
    with pytest.raises(ConfigError, match="absolute http"):
        ProviderConfig.from_env({"ETH_RPC_URL": "alchemy.example/v2/token"})


def test_provider_config_accepts_absolute_endpoint_without_exposing_value() -> None:
    """정상 URL은 보관하되 audit/log 표현은 원문을 노출하지 않음."""
    config = ProviderConfig.from_env({"ETH_RPC_URL": "https://rpc.example.net/v2/token"})

    assert config.endpoint_url == "https://rpc.example.net/v2/token"
    assert config.redacted_endpoint == "<configured>"
