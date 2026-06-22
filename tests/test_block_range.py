"""
요약:
    block_range.py 경계 조건 테스트.
역할:
    Airflow logical interval이 Ethereum block range로 바뀔 때 누락/중복이 없는지
    fake block chain으로 검증함.
파이프라인 위치:
    현재 block range resolver의 핵심 로직을 외부 RPC 없이 테스트함.
입력:
    FakeBlockClient와 UTC interval.
출력:
    ResolvedBlockRange.
왜 분리하는가:
    실제 Ethereum RPC는 시간과 provider 상태에 따라 변함. deterministic fake로
    boundary invariant를 고정 필요함.
핵심 개념:
    `toBlock`은 inclusive이고 Airflow interval은 `[start, end)`임.
대표 입력값:
    00:00~01:00, block 100부터 18초 간격 timestamp.
대표 출력값:
    [100, 299].
실패 영향:
    이 테스트가 깨지면 실제 DAG backfill에서 block log가 누락 또는 중복될 수 있음.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from cryptoquant_pipeline.block_range import (
    estimate_recent_search_low_block,
    find_first_block_at_or_after,
    resolve_interval_block_range,
)
from cryptoquant_pipeline.exceptions import BlockRangeError, NonRetryableRpcError, RpcErrorDetail


class FakeFinalizedClient:
    """cryptoquant_pipeline block range tests용 deterministic fake."""

    def __init__(self, *, finalized_block: int, base: datetime | None = None) -> None:
        self.finalized_block = finalized_block
        self.base = base or datetime(2024, 1, 1, tzinfo=UTC)
        self.requested_blocks: list[int] = []

    def eth_get_finalized_block(self) -> dict[str, str]:
        timestamp = self.base + timedelta(seconds=self.finalized_block * 12)
        return {
            "number": hex(self.finalized_block),
            "timestamp": hex(int(timestamp.timestamp())),
        }

    def eth_get_block_by_number(
        self,
        block_number: int | str,
        *,
        full_transactions: bool = False,
    ) -> dict[str, str]:
        del full_transactions
        number = int(block_number, 16) if isinstance(block_number, str) else block_number
        self.requested_blocks.append(number)
        timestamp = self.base + timedelta(seconds=number * 12)
        return {"number": hex(number), "timestamp": hex(int(timestamp.timestamp()))}


class LimitedBlockLookupClient(FakeFinalizedClient):
    """특정 block보다 오래된 metadata 조회를 HTTP 403처럼 거부하는 fake."""

    def __init__(self, *, finalized_block: int, min_accessible_block: int) -> None:
        super().__init__(finalized_block=finalized_block)
        self.min_accessible_block = min_accessible_block

    def eth_get_block_by_number(
        self,
        block_number: int | str,
        *,
        full_transactions: bool = False,
    ) -> dict[str, str]:
        number = int(block_number, 16) if isinstance(block_number, str) else block_number
        if number < self.min_accessible_block:
            raise NonRetryableRpcError(
                RpcErrorDetail(
                    method="eth_getBlockByNumber",
                    message="forbidden",
                    http_status=403,
                    retryable=False,
                )
            )
        return super().eth_get_block_by_number(
            number,
            full_transactions=full_transactions,
        )


def test_find_first_block_at_or_after_exact_timestamp_boundary() -> None:
    """
    검증 목적:
        target timestamp와 같은 block timestamp가 있으면 그 block을 반환함.
    막는 버그:
        경계가 같은 block을 다음 block으로 밀어 한 구간을 누락시키는 문제.
    """
    client = FakeFinalizedClient(finalized_block=100)
    target = datetime(2024, 1, 1, 0, 2, tzinfo=UTC)

    assert find_first_block_at_or_after(client, target, high_block=100) == 10


def test_find_first_block_at_or_after_between_blocks_returns_next_block() -> None:
    """
    검증 목적:
        target이 두 block timestamp 사이면 이후 첫 block을 반환함.
    막는 버그:
        target 이전 block을 포함해 half-open interval 왼쪽 경계가 깨지는 문제.
    """
    client = FakeFinalizedClient(finalized_block=100)
    target = datetime(2024, 1, 1, 0, 2, 1, tzinfo=UTC)

    assert find_first_block_at_or_after(client, target, high_block=100) == 11


def test_resolve_interval_uses_end_exclusive_minus_one() -> None:
    """
    검증 목적:
        end_exclusive_block - 1 계산으로 to_block을 만든다는 계약을 고정함.
    막는 버그:
        다음 Airflow interval의 첫 block까지 현재 interval에 포함하는 문제.
    """
    client = FakeFinalizedClient(finalized_block=100)

    result = resolve_interval_block_range(
        client,
        interval_start_utc=datetime(2024, 1, 1, 0, 2, tzinfo=UTC),
        interval_end_utc=datetime(2024, 1, 1, 0, 4, tzinfo=UTC),
    )

    assert result.from_block == 10
    assert result.end_exclusive_block == 20
    assert result.to_block == 19


def test_resolve_interval_rejects_empty_or_impossible_range() -> None:
    """
    검증 목적:
        빈 interval 입력을 수집 성공처럼 처리하지 않음.
    막는 버그:
        Airflow 수동 실행 오입력으로 잘못된 block range를 만드는 문제.
    """
    client = FakeFinalizedClient(finalized_block=100)

    try:
        resolve_interval_block_range(
            client,
            interval_start_utc=datetime(2024, 1, 1, 0, 2, tzinfo=UTC),
            interval_end_utc=datetime(2024, 1, 1, 0, 2, tzinfo=UTC),
        )
    except BlockRangeError:
        pass
    else:
        raise AssertionError("BlockRangeError was not raised")


def test_find_first_block_does_not_use_fixed_recent_lookback() -> None:
    """
    검증 목적:
        임의 과거 backfill을 위해 finalized high 전체 범위를 이진 탐색함.
    막는 버그:
        latest에서 최근 1000 block만 역산해 오래된 interval을 찾지 못하는 문제.
    """
    client = FakeFinalizedClient(finalized_block=5000)
    target = datetime(2024, 1, 1, 0, 10, tzinfo=UTC)

    assert find_first_block_at_or_after(client, target, high_block=5000) == 50
    assert max(client.requested_blocks) > 1000


def test_resolve_recent_interval_avoids_archive_sized_midpoint_lookup() -> None:
    """
    검증 목적:
        최근 hourly interval을 찾을 때 genesis~finalized 전체 이진 탐색으로 오래된
        midpoint block을 조회하지 않음.
    막는 버그:
        non-archive RPC provider가 오래된 `eth_getBlockByNumber`를 HTTP 403으로
        거부해 최신 interval도 실패하는 문제.
    """
    client = FakeFinalizedClient(finalized_block=10_000)
    finalized_ts = client.base + timedelta(seconds=10_000 * 12)
    interval_start = finalized_ts - timedelta(hours=1)
    interval_end = finalized_ts - timedelta(minutes=30)
    expected_low = estimate_recent_search_low_block(
        finalized_block_number=10_000,
        finalized_block_timestamp_utc=finalized_ts,
        target_timestamp_utc=interval_start,
    )

    result = resolve_interval_block_range(
        client,
        interval_start_utc=interval_start,
        interval_end_utc=interval_end,
    )

    assert result.from_block == 9700
    assert result.to_block == 9849
    assert min(client.requested_blocks) >= expected_low


def test_resolve_interval_succeeds_inside_provider_metadata_window() -> None:
    """
    검증 목적:
        provider가 아주 최근 block metadata만 허용해도 interval start가 그 window 안이면
        안전하게 block range를 계산함.
    """
    client = LimitedBlockLookupClient(finalized_block=10_000, min_accessible_block=9980)
    interval_start = client.base + timedelta(seconds=9985 * 12)
    interval_end = client.base + timedelta(seconds=9990 * 12)

    result = resolve_interval_block_range(
        client,
        interval_start_utc=interval_start,
        interval_end_utc=interval_end,
    )

    assert result.from_block == 9985
    assert result.to_block == 9989


def test_resolve_interval_fails_when_provider_metadata_window_is_too_short() -> None:
    """
    검증 목적:
        provider가 interval start 이전 block metadata를 허용하지 않으면 추정값으로
        조용히 누락시키지 않고 실패함.
    """
    client = LimitedBlockLookupClient(finalized_block=10_000, min_accessible_block=9980)
    interval_start = client.base + timedelta(seconds=9970 * 12)
    interval_end = client.base + timedelta(seconds=9990 * 12)

    try:
        resolve_interval_block_range(
            client,
            interval_start_utc=interval_start,
            interval_end_utc=interval_end,
        )
    except BlockRangeError as exc:
        assert "provider block metadata lookup window" in str(exc)
    else:
        raise AssertionError("BlockRangeError was not raised")
