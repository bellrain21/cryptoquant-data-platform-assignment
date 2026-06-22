"""
요약:
    rpc_client.py bounded retry 정책 테스트.
역할:
    HTTP/transport retryable 오류는 설정된 횟수 안에서 재시도하고,
    range split 대상 오류는 client 내부 반복 대신 log_fetcher로 넘기는지 검증함.
파이프라인 위치:
    Airflow task -> EthereumJsonRpcClient -> block_range/log_fetcher.
입력:
    httpx.MockTransport 기반 JSON-RPC 응답 fixture.
출력:
    RPC result 또는 분류된 RpcTooManyResultsError.
왜 분리하는가:
    실제 provider 장애와 rate limit은 재현하기 어렵고 API quota를 소모함.
핵심 개념:
    retry는 bounded여야 하며, too-many-results는 같은 요청 반복보다 block range split이 맞음.
대표 입력값:
    첫 요청 HTTP 500, 두 번째 요청 정상 latest block.
대표 출력값:
    latest block number 100.
실패 영향:
    이 테스트가 깨지면 설정된 retry 정책이 문서와 다르거나 range split이 지연될 수 있음.
"""

from __future__ import annotations

import json

import httpx
import pytest

from cryptoquant_pipeline.config import TRANSFER_TOPIC0
from cryptoquant_pipeline.exceptions import RpcTooManyResultsError
from cryptoquant_pipeline.provider import ProviderConfig
from cryptoquant_pipeline.rpc_client import EthereumJsonRpcClient


def test_rpc_client_retries_retryable_http_error_then_succeeds() -> None:
    """
    검증 목적:
        HTTP 5xx가 `max_retries` 안에서 한 번 재시도되는지 확인함.
    막는 버그:
        `ETH_RPC_MAX_RETRIES`가 설정 객체에만 있고 실제 client에 연결되지 않는 문제.
    실제 운영 상황:
        provider가 일시적으로 HTTP 500을 반환한 뒤 다음 요청에서 회복.
    fixture 의미:
            MockTransport가 첫 응답만 500, 두 번째 응답은 `0x1`을 반환함.
    실패 시 우선 확인:
        EthereumJsonRpcClient._request retry loop.
    기대 결과:
            요청 횟수는 2회이고 반환 chain id는 1.
    """
    attempts = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(500, json={"error": "temporary provider failure"})
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": attempts, "result": "0x1"})

    with EthereumJsonRpcClient(
        ProviderConfig(endpoint_url="https://example.invalid/rpc"),
        max_retries=1,
        retry_backoff_seconds=0,
        transport=httpx.MockTransport(handler),
    ) as client:
        assert client.eth_chain_id() == 1

    assert attempts == 2


def test_rpc_client_does_not_retry_range_split_error() -> None:
    """
    검증 목적:
        too-many-results 오류가 내부 재시도로 반복되지 않고 즉시 상위로 전달되는지 확인함.
    막는 버그:
        큰 `eth_getLogs` 요청을 같은 범위로 반복해 provider quota와 시간을 낭비하는 문제.
    실제 운영 상황:
        provider가 result size limit 때문에 JSON-RPC error를 반환함.
    fixture 의미:
        MockTransport가 항상 "query returned more than allowed" 오류를 반환함.
    실패 시 우선 확인:
        `_should_skip_client_retry`와 `_classify_rpc_error`.
    기대 결과:
        RpcTooManyResultsError가 발생하고 요청 횟수는 1회임.
    """
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
            ).encode("utf-8"),
        )

    with EthereumJsonRpcClient(
        ProviderConfig(endpoint_url="https://example.invalid/rpc"),
        max_retries=3,
        retry_backoff_seconds=0,
        transport=httpx.MockTransport(handler),
    ) as client, pytest.raises(RpcTooManyResultsError):
        client.eth_get_logs(from_block=1, to_block=10, topics=[TRANSFER_TOPIC0])

    assert attempts == 1
