"""RPC provider endpoint and authentication abstraction."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal
from urllib.parse import urlsplit

import httpx

from cryptoquant_pipeline.exceptions import ConfigError

AuthMode = Literal["none", "basic", "bearer"]
PLACEHOLDER_HOSTS = frozenset({"your-provider.example"})
PLACEHOLDER_PATH_TOKENS = ("YOUR_API_KEY",)


@dataclass(frozen=True)
class ProviderConfig:
    """Provider endpoint와 인증 방식을 분리해 Alchemy/Chainstack 양쪽을 지원함."""

    endpoint_url: str = field(repr=False)
    auth_mode: AuthMode = "none"
    username: str | None = field(default=None, repr=False)
    password: str | None = field(default=None, repr=False)
    bearer_token: str | None = field(default=None, repr=False)

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> ProviderConfig:
        """환경 변수에서 provider 설정을 읽되 민감값은 repr/log 대상에서 제외함."""
        env = os.environ if environ is None else environ
        endpoint = _first_non_empty(env, "ETH_RPC_URL", "CHAINSTACK_RPC_URL")
        if endpoint is None:
            raise ConfigError("ETH_RPC_URL must be configured.")
        auth_mode = _first_non_empty(env, "ETH_RPC_AUTH_MODE", "CHAINSTACK_AUTH_MODE") or "none"
        auth_mode = auth_mode.strip().lower()
        if auth_mode not in {"none", "basic", "bearer"}:
            raise ConfigError("ETH_RPC_AUTH_MODE must be one of: none, basic, bearer.")
        config = cls(
            endpoint_url=endpoint,
            auth_mode=auth_mode,  # type: ignore[arg-type]
            username=_first_non_empty(env, "ETH_RPC_USERNAME", "CHAINSTACK_RPC_USERNAME"),
            password=_first_non_empty(env, "ETH_RPC_PASSWORD", "CHAINSTACK_RPC_PASSWORD"),
            bearer_token=_empty_to_none(env.get("ETH_RPC_BEARER_TOKEN")),
        )
        config.validate()
        return config

    def validate(self) -> None:
        """endpoint 형식과 인증 모드별 필수값을 검증함. 실제 secret 값은 오류 메시지에 넣지 않음."""
        parsed = urlsplit(self.endpoint_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ConfigError("ETH_RPC_URL must be an absolute http(s) URL.")
        upper_endpoint = self.endpoint_url.upper()
        if parsed.hostname in PLACEHOLDER_HOSTS or any(
            token in upper_endpoint for token in PLACEHOLDER_PATH_TOKENS
        ):
            raise ConfigError(
                "ETH_RPC_URL still contains the example placeholder. "
                "Replace it with a real provider URL or leave it blank for fixture-only checks."
            )
        if self.auth_mode == "basic" and (not self.username or not self.password):
            raise ConfigError("basic auth requires ETH_RPC_USERNAME and ETH_RPC_PASSWORD.")
        if self.auth_mode == "bearer" and not self.bearer_token:
            raise ConfigError("bearer auth requires ETH_RPC_BEARER_TOKEN.")

    def build_auth(self) -> httpx.Auth | None:
        """httpx가 이해하는 auth 객체를 생성함. Alchemy Free는 none을 사용 가능함."""
        if self.auth_mode == "basic":
            return httpx.BasicAuth(self.username or "", self.password or "")
        return None

    def build_headers(self) -> dict[str, str]:
        """Bearer token 인증만 header에 넣음. URL 또는 key는 로그에 남기지 않음."""
        if self.auth_mode == "bearer":
            return {"Authorization": f"Bearer {self.bearer_token}"}
        return {}

    @property
    def redacted_endpoint(self) -> str:
        """검증 증적에는 endpoint 원문 대신 설정 여부만 남김."""
        return "<configured>"


def _empty_to_none(value: str | None) -> str | None:
    if value is None or value.strip() == "":
        return None
    return value


def _first_non_empty(env: Mapping[str, str], *names: str) -> str | None:
    for name in names:
        value = _empty_to_none(env.get(name))
        if value is not None:
            return value
    return None
