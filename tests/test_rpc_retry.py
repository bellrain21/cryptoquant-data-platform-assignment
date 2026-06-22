"""RPC retry and adaptive chunk split tests without external network."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

import httpx
import pytest

from cryptoquant_pipeline.config import TRANSFER_TOPIC0, CollectionScope
from cryptoquant_pipeline.exceptions import (
    LogCollectionError,
    NonRetryableRpcError,
    RpcErrorDetail,
    RpcTooManyResultsError,
)
from cryptoquant_pipeline.log_collector import collect_raw_logs
from cryptoquant_pipeline.provider import ProviderConfig
from cryptoquant_pipeline.rpc_client import EthereumJsonRpcClient

COLLECTION_SCOPE = CollectionScope.default_transfer_topic_all_addresses(chain_id=1)


def _client_with_responses(responses: list[httpx.Response | Exception]) -> EthereumJsonRpcClient:
    calls = iter(responses)

    def handler(_request: httpx.Request) -> httpx.Response:
        item = next(calls)
        if isinstance(item, Exception):
            raise item
        return item

    return EthereumJsonRpcClient(
        ProviderConfig(endpoint_url="https://example.invalid/rpc"),
        max_retries=1,
        retry_backoff_seconds=0,
        retry_jitter_seconds=0,
        sleep_fn=lambda _seconds: None,
        transport=httpx.MockTransport(handler),
    )


def _ok_result(value: str = "0x1") -> httpx.Response:
    return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": value})


def test_429_is_retried() -> None:
    with _client_with_responses([httpx.Response(429), _ok_result("0x1")]) as client:
        assert client.eth_chain_id() == 1


def test_5xx_is_retried() -> None:
    with _client_with_responses([httpx.Response(500), _ok_result("0x1")]) as client:
        assert client.eth_chain_id() == 1


def test_timeout_is_retried() -> None:
    timeout = httpx.ReadTimeout("timeout", request=httpx.Request("POST", "https://x.invalid"))
    with _client_with_responses([timeout, _ok_result("0x1")]) as client:
        assert client.eth_chain_id() == 1


def test_4xx_non_retryable_error() -> None:
    with (
        _client_with_responses([httpx.Response(401)]) as client,
        pytest.raises(NonRetryableRpcError),
    ):
        client.eth_chain_id()


class SplitOnRangeClient:
    """2블록 이상 요청은 oversized로 실패하고 단일 블록은 성공함."""

    def eth_get_logs(
        self,
        *,
        from_block: int,
        to_block: int,
        address: str | Sequence[str] | None = None,
        topics: Sequence[Any] | None = None,
    ) -> list[Mapping[str, Any]]:
        assert address is None
        assert topics == [TRANSFER_TOPIC0]
        if to_block > from_block:
            raise RpcTooManyResultsError(
                RpcErrorDetail(method="eth_getLogs", message="too many logs", retryable=True)
            )
        return [{"blockNumber": hex(from_block), "transactionHash": hex(from_block)}]


def test_persistent_oversized_response_splits_until_single_blocks() -> None:
    logs = collect_raw_logs(
        SplitOnRangeClient(),
        from_block=1,
        to_block=3,
        collection_scope=COLLECTION_SCOPE,
    )

    assert [log["blockNumber"] for log in logs] == ["0x1", "0x2", "0x3"]


class AlwaysFailClient:
    def eth_get_logs(
        self,
        *,
        from_block: int,
        to_block: int,
        address: str | Sequence[str] | None = None,
        topics: Sequence[Any] | None = None,
    ) -> list[Mapping[str, Any]]:
        del from_block, to_block, address, topics
        raise RpcTooManyResultsError(
            RpcErrorDetail(method="eth_getLogs", message="still too many", retryable=True)
        )


def test_single_block_persistent_failure_raises() -> None:
    with pytest.raises(LogCollectionError):
        collect_raw_logs(
            AlwaysFailClient(),
            from_block=1,
            to_block=1,
            collection_scope=COLLECTION_SCOPE,
        )


def test_rpc_too_many_results_is_not_client_retried() -> None:
    attempts = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(
            200,
            content=json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": attempts,
                    "error": {"code": -32005, "message": "query returned more than allowed"},
                }
            ).encode(),
        )

    with (
        EthereumJsonRpcClient(
            ProviderConfig(endpoint_url="https://example.invalid/rpc"),
            max_retries=3,
            retry_backoff_seconds=0,
            retry_jitter_seconds=0,
            sleep_fn=lambda _seconds: None,
            transport=httpx.MockTransport(handler),
        ) as client,
        pytest.raises(RpcTooManyResultsError),
    ):
        client.eth_get_logs(
            from_block=1,
            to_block=10,
            topics=[TRANSFER_TOPIC0],
        )

    assert attempts == 1


def test_eth_get_logs_omits_address_for_transfer_topic_all_addresses_scope() -> None:
    request_payloads: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        request_payloads.append(json.loads(request.content.decode()))
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": []})

    with EthereumJsonRpcClient(
        ProviderConfig(endpoint_url="https://example.invalid/rpc"),
        max_retries=0,
        retry_backoff_seconds=0,
        retry_jitter_seconds=0,
        sleep_fn=lambda _seconds: None,
        transport=httpx.MockTransport(handler),
    ) as client:
        assert client.eth_get_logs(from_block=1, to_block=1, topics=[TRANSFER_TOPIC0]) == []

    params = request_payloads[0]["params"][0]
    assert "address" not in params
    assert params["topics"] == [TRANSFER_TOPIC0]
