"""Synchronous Ethereum JSON-RPC client with bounded retry and rate limiting."""

from __future__ import annotations

import itertools
import logging
import random
import time
from collections.abc import Callable, Mapping, Sequence
from typing import Any

import httpx

from cryptoquant_pipeline.chunking import MAX_BLOCKS_PER_LOG_REQUEST
from cryptoquant_pipeline.exceptions import (
    NonRetryableRpcError,
    RetryableRpcError,
    RpcErrorDetail,
    RpcRangeTooLargeError,
    RpcRateLimitError,
    RpcTimeoutError,
    RpcTooManyResultsError,
)
from cryptoquant_pipeline.provider import ProviderConfig

LOGGER = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


class EthereumJsonRpcClient:
    """Ethereum JSON-RPC transport 경계. URL/key는 로그에 남기지 않음."""

    def __init__(
        self,
        provider: ProviderConfig,
        *,
        timeout_seconds: float = 20.0,
        max_retries: int = 3,
        requests_per_second: float = 4.0,
        retry_backoff_seconds: float = 1.0,
        retry_jitter_seconds: float = 0.25,
        transport: httpx.BaseTransport | None = None,
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> None:
        if requests_per_second <= 0 or requests_per_second > 4:
            raise ValueError("requests_per_second must be > 0 and <= 4.")
        self._provider = provider
        self._max_retries = max_retries
        self._retry_backoff_seconds = retry_backoff_seconds
        self._retry_jitter_seconds = retry_jitter_seconds
        self._sleep_fn = sleep_fn
        self._min_interval_seconds = 1.0 / requests_per_second
        self._last_request_at: float | None = None
        self._ids = itertools.count(1)
        self._client = httpx.Client(
            timeout=timeout_seconds,
            transport=transport,
            auth=provider.build_auth(),
            headers=provider.build_headers(),
        )

    def __enter__(self) -> EthereumJsonRpcClient:
        return self

    def __exit__(self, *_exc_info: object) -> None:
        self.close()

    def close(self) -> None:
        """HTTP connection pool을 명시적으로 닫음."""
        self._client.close()

    def eth_chain_id(self) -> int:
        """현재 provider가 연결된 chain id를 조회함."""
        return _hex_to_int(self._request("eth_chainId", []))

    def eth_get_block_by_number(
        self,
        block_number: int | str,
        *,
        full_transactions: bool = False,
    ) -> Mapping[str, Any]:
        """정수 block number 또는 `"finalized"` 같은 tag로 block metadata를 조회함."""
        block_ref = block_number if isinstance(block_number, str) else hex(block_number)
        result = self._request("eth_getBlockByNumber", [block_ref, full_transactions])
        if not isinstance(result, Mapping):
            raise NonRetryableRpcError(
                RpcErrorDetail(
                    method="eth_getBlockByNumber",
                    message="Provider returned non-object block payload.",
                    retryable=False,
                )
            )
        return result

    def eth_get_finalized_block(self) -> Mapping[str, Any]:
        """Ethereum finalized head를 provider tag 기준으로 조회함."""
        return self.eth_get_block_by_number("finalized", full_transactions=False)

    def eth_get_logs(
        self,
        *,
        from_block: int,
        to_block: int,
        address: str | Sequence[str] | None = None,
        topics: Sequence[Any] | None = None,
    ) -> list[Mapping[str, Any]]:
        """address 또는 topic filter가 있는 10블록 이하 `eth_getLogs` 요청만 허용함."""
        block_count = to_block - from_block + 1
        if block_count < 1 or block_count > MAX_BLOCKS_PER_LOG_REQUEST:
            raise ValueError("eth_getLogs block range must contain 1 to 10 blocks.")
        if not address and not topics:
            raise ValueError("eth_getLogs requires an address or topic filter.")

        params: dict[str, Any] = {
            "fromBlock": hex(from_block),
            "toBlock": hex(to_block),
        }
        if address:
            params["address"] = address
        if topics is not None:
            params["topics"] = list(topics)

        result = self._request("eth_getLogs", [params])
        if not isinstance(result, list):
            raise NonRetryableRpcError(
                RpcErrorDetail(
                    method="eth_getLogs",
                    message="Provider returned non-list logs payload.",
                    retryable=False,
                )
            )
        return [row for row in result if isinstance(row, Mapping)]

    def _request(self, method: str, params: Sequence[Any]) -> Any:
        for attempt in range(self._max_retries + 1):
            try:
                self._rate_limit()
                return self._request_once(method, params)
            except RetryableRpcError as exc:
                if _must_split_instead_of_retry(exc) or attempt >= self._max_retries:
                    raise
                delay = self._backoff_delay(attempt)
                LOGGER.warning(
                    "rpc_retry method=%s attempt=%s max_retries=%s error=%s delay_seconds=%.3f",
                    method,
                    attempt + 1,
                    self._max_retries,
                    exc.__class__.__name__,
                    delay,
                )
                self._sleep_fn(delay)
        raise RuntimeError("unreachable RPC retry state")

    def _request_once(self, method: str, params: Sequence[Any]) -> Any:
        payload = {
            "jsonrpc": "2.0",
            "id": next(self._ids),
            "method": method,
            "params": list(params),
        }
        try:
            response = self._client.post(self._provider.endpoint_url, json=payload)
        except httpx.TimeoutException as exc:
            raise RpcTimeoutError(
                RpcErrorDetail(method=method, message=f"{method} timed out.", retryable=True)
            ) from exc
        except httpx.TransportError as exc:
            raise RetryableRpcError(
                RpcErrorDetail(
                    method=method,
                    message=f"{method} transport error: {exc.__class__.__name__}.",
                    retryable=True,
                )
            ) from exc

        if response.status_code == 429:
            raise RpcRateLimitError(
                RpcErrorDetail(
                    method=method,
                    message=f"{method} provider rate limit.",
                    http_status=429,
                    retryable=True,
                )
            )
        if 500 <= response.status_code <= 599:
            raise RetryableRpcError(
                RpcErrorDetail(
                    method=method,
                    message=f"{method} provider HTTP {response.status_code}.",
                    http_status=response.status_code,
                    retryable=True,
                )
            )
        if response.status_code >= 400:
            raise NonRetryableRpcError(
                RpcErrorDetail(
                    method=method,
                    message=f"{method} provider HTTP {response.status_code}.",
                    http_status=response.status_code,
                    retryable=False,
                )
            )

        try:
            body = response.json()
        except ValueError as exc:
            raise RetryableRpcError(
                RpcErrorDetail(
                    method=method,
                    message=f"{method} returned invalid JSON.",
                    retryable=True,
                )
            ) from exc
        if not isinstance(body, Mapping):
            raise RetryableRpcError(
                RpcErrorDetail(
                    method=method,
                    message=f"{method} returned non-object JSON.",
                    retryable=True,
                )
            )
        if "error" in body:
            raise _classify_rpc_error(method, body["error"])
        if "result" not in body:
            raise RetryableRpcError(
                RpcErrorDetail(
                    method=method,
                    message=f"{method} missed result field.",
                    retryable=True,
                )
            )
        return body["result"]

    def _rate_limit(self) -> None:
        now = time.monotonic()
        if self._last_request_at is not None:
            elapsed = now - self._last_request_at
            remaining = self._min_interval_seconds - elapsed
            if remaining > 0:
                self._sleep_fn(remaining)
                now = time.monotonic()
        self._last_request_at = now

    def _backoff_delay(self, attempt: int) -> float:
        base = self._retry_backoff_seconds * (2**attempt)
        jitter = random.uniform(0, self._retry_jitter_seconds)
        return base + jitter


def _classify_rpc_error(method: str, payload: object) -> Exception:
    if isinstance(payload, Mapping):
        message = str(payload.get("message", "JSON-RPC error"))
        code = payload.get("code") if isinstance(payload.get("code"), int) else None
    else:
        message = str(payload)
        code = None

    lowered = message.lower()
    too_many_markers = ("too many", "more than", "response size", "log response")
    if any(token in lowered for token in too_many_markers):
        return RpcTooManyResultsError(
            RpcErrorDetail(method=method, message=message, code=code, retryable=True)
        )
    if "range" in lowered and any(token in lowered for token in ("large", "limit", "exceed")):
        return RpcRangeTooLargeError(
            RpcErrorDetail(method=method, message=message, code=code, retryable=True)
        )
    if any(token in lowered for token in ("timeout", "timed out")):
        return RpcTimeoutError(
            RpcErrorDetail(method=method, message=message, code=code, retryable=True)
        )
    if any(token in lowered for token in ("rate limit", "rate-limit", "throttle", "compute unit")):
        return RpcRateLimitError(
            RpcErrorDetail(method=method, message=message, code=code, retryable=True)
        )
    if code in {-32005, -32002}:
        return RetryableRpcError(
            RpcErrorDetail(method=method, message=message, code=code, retryable=True)
        )
    return NonRetryableRpcError(
        RpcErrorDetail(method=method, message=message, code=code, retryable=False)
    )


def _must_split_instead_of_retry(error: RetryableRpcError) -> bool:
    return isinstance(error, RpcRangeTooLargeError | RpcTooManyResultsError)


def _hex_to_int(value: object) -> int:
    if not isinstance(value, str) or not value.startswith("0x"):
        raise ValueError("Expected Ethereum hex quantity.")
    return int(value, 16)
