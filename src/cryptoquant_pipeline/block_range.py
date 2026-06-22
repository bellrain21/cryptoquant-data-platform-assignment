"""UTC 반개구간([start, end))을 Ethereum block range로 변환한다.

시간 정책
---------
- 파이프라인의 canonical 시간대는 UTC다.
- 모든 입력 datetime은 timezone-aware여야 하며 UTC로 정규화한다.
- 반환 block range는 [from_block, to_block]의 양끝 포함 범위다.

Finality 정책
-------------
수집 대상 interval의 종료 시각(end)까지 finalized head가 도달한 경우에만
block range 계산과 이후 수집을 진행한다.

    finalized_block_timestamp_utc >= interval_end_utc

조건이 충족되지 않으면 아직 reorg 위험이 남아 있다고 보고,
RetryableIntervalNotFinalized를 발생시켜 Airflow가 같은 interval을 재시도하게 한다.
이 경우 eth_getLogs, Delta write, dbt build는 실행되지 않는다.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from math import ceil
from typing import Any, Protocol

from cryptoquant_pipeline.exceptions import (
    BlockRangeError,
    NonRetryableRpcError,
    RetryableIntervalNotFinalized,
)

logger = logging.getLogger(__name__)

# 최근 구간의 예상 block 수를 계산할 때 사용하는 보수적 최저 block time 가정이다.
# 실제 Ethereum block time보다 짧게 잡아, 필요한 과거 block 조회 범위를 넉넉하게 산정한다.
RECENT_SEARCH_MIN_SECONDS_PER_BLOCK = 6

# 위 예상치에 추가하는 block 단위 여유분이다.
# 현재 resolve_interval_block_range()의 기본 탐색 흐름은 지수 탐색을 사용한다.
# 이 상수는 estimate_recent_search_low_block() 보조 함수에서만 사용된다.
RECENT_SEARCH_SAFETY_BLOCKS = 256


class BlockLookupClient(Protocol):
    """시간→block range 탐색에 필요한 최소 Ethereum RPC interface."""

    def eth_get_block_by_number(
        self,
        block_number: int | str,
        *,
        full_transactions: bool = False,
    ) -> Mapping[str, Any]: ...

    def eth_get_finalized_block(self) -> Mapping[str, Any]: ...


@dataclass(frozen=True)
class IntervalBlockRange:
    """UTC [start, end) interval에 대응하는 양끝 포함 block range.

    Attributes:
        interval_start_utc: 수집 시작 시각(포함).
        interval_end_utc: 수집 종료 시각(미포함).
        finalized_block_number: range 계산 시점의 finalized head block number.
        finalized_block_timestamp_utc: finalized head의 UTC timestamp.
        from_block: block.timestamp >= interval_start_utc 인 첫 block.
        end_exclusive_block: block.timestamp >= interval_end_utc 인 첫 block.
        to_block: interval에 포함되는 마지막 block (= end_exclusive_block - 1).
    """

    interval_start_utc: datetime
    interval_end_utc: datetime
    finalized_block_number: int
    finalized_block_timestamp_utc: datetime
    from_block: int
    end_exclusive_block: int
    to_block: int


def resolve_interval_block_range(
    client: BlockLookupClient,
    *,
    interval_start_utc: datetime,
    interval_end_utc: datetime,
) -> IntervalBlockRange:
    """UTC [start, end) interval을 Ethereum의 양끝 포함 block range로 변환한다.

    처리 순서:
    1. 입력 시각을 timezone-aware UTC로 정규화한다.
    2. finalized head가 interval 종료 시각까지 도달했는지 확인한다.
    3. interval_start 이전의 탐색 하한을 찾는다.
    4. 이진 탐색으로 from_block / end_exclusive_block을 계산한다.
    5. [from_block, end_exclusive_block) → [from_block, to_block]로 변환한다.

    Raises:
        RetryableIntervalNotFinalized:
            finalized head가 interval 종료 시각에 아직 도달하지 않은 경우.
            Airflow retry 대상이며, 이후 수집/적재 단계는 실행되지 않는다.
        BlockRangeError:
            비정상 시간 입력, empty range, provider 조회 범위 부족 등의 경우.
    """
    start = ensure_utc(interval_start_utc, "interval_start_utc")
    end = ensure_utc(interval_end_utc, "interval_end_utc")
    if start >= end:
        raise BlockRangeError("interval_start_utc must be earlier than interval_end_utc.")

    # finalized는 latest보다 늦지만, reorg 위험을 줄인 안전한 수집 경계다.
    finalized_block = client.eth_get_finalized_block()
    finalized_number = block_number_from_payload(finalized_block)
    finalized_ts = block_timestamp_from_payload(finalized_block)

    # 양수/0: finalized head가 interval 종료 시각에 도달했거나 앞섬 → 처리 가능.
    # 음수: finalized head가 interval 종료 시각보다 과거 → retry 필요.
    finality_offset_seconds = (finalized_ts - end).total_seconds()
    finality_status = "READY" if finality_offset_seconds >= 0 else "NOT_READY"

    logger.info(
        "Finality check: status=%s finalized_block=%s "
        "finalized_timestamp_utc=%s required_interval_end_utc=%s "
        "finality_offset_seconds=%.1f",
        finality_status,
        finalized_number,
        finalized_ts.isoformat(),
        end.isoformat(),
        finality_offset_seconds,
    )

    if finalized_ts < end:
        raise RetryableIntervalNotFinalized(
            "finalized block timestamp is earlier than interval_end_utc; "
            "retry this Airflow interval later."
        )

    # 같은 block timestamp를 반복 조회하지 않도록 per-run cache를 공유한다.
    timestamp_cache: dict[int, datetime] = {finalized_number: finalized_ts}

    # provider가 허용하는 범위 안에서 interval_start 이전의 탐색 하한을 확보한다.
    search_low = find_search_low_block(
        client,
        target_timestamp_utc=start,
        high_block=finalized_number,
        high_block_timestamp_utc=finalized_ts,
        timestamp_cache=timestamp_cache,
    )

    # start 이상인 첫 block과 end 이상인 첫 block을 이진 탐색으로 찾는다.
    from_block = find_first_block_at_or_after(
        client,
        start,
        low_block=search_low,
        high_block=finalized_number,
        timestamp_cache=timestamp_cache,
    )
    end_exclusive = find_first_block_at_or_after(
        client,
        end,
        low_block=from_block,
        high_block=finalized_number,
        timestamp_cache=timestamp_cache,
    )

    # [from_block, end_exclusive) block 범위를 eth_getLogs용 양끝 포함 범위로 바꾼다.
    to_block = end_exclusive - 1
    if from_block > to_block:
        raise BlockRangeError("resolved interval contains no finalized blocks.")

    return IntervalBlockRange(
        interval_start_utc=start,
        interval_end_utc=end,
        finalized_block_number=finalized_number,
        finalized_block_timestamp_utc=finalized_ts,
        from_block=from_block,
        end_exclusive_block=end_exclusive,
        to_block=to_block,
    )


def find_first_block_at_or_after(
    client: BlockLookupClient,
    target_timestamp_utc: datetime,
    *,
    low_block: int = 0,
    high_block: int | None = None,
    timestamp_cache: dict[int, datetime] | None = None,
) -> int:
    """block.timestamp >= target인 첫 block number를 이진 탐색으로 찾는다.

    반환값은 target 시각에 해당하는 block의 시작 경계다.
    target보다 과거인 마지막 block을 찾는 함수가 아니라는 점에 주의한다.
    """
    target = ensure_utc(target_timestamp_utc, "target_timestamp_utc")
    high = high_block
    if high is None:
        high = block_number_from_payload(client.eth_get_finalized_block())
    if high < 0:
        raise BlockRangeError("high_block must be non-negative.")
    if low_block < 0:
        raise BlockRangeError("low_block must be non-negative.")
    if low_block > high:
        return high + 1

    left = low_block
    right = high
    result = high + 1
    cache = {} if timestamp_cache is None else timestamp_cache

    while left <= right:
        mid = (left + right) // 2
        mid_ts = _block_timestamp(client, mid, cache)

        if mid_ts >= target:
            result = mid
            right = mid - 1
        else:
            left = mid + 1

    return result


def estimate_recent_search_low_block(
    *,
    finalized_block_number: int,
    finalized_block_timestamp_utc: datetime,
    target_timestamp_utc: datetime,
) -> int:
    """최근 interval 탐색용 보조 하한을 추정한다.

    이 함수는 현재 resolve_interval_block_range()의 기본 호출 경로에서는 사용하지 않는다.
    provider의 numeric block 조회 허용 범위를 사전에 제한하는 전략을 도입할 때 사용할 수 있다.

    계산은 다음과 같다.
    - finalized와 target의 시간 차이를 구한다.
    - 최소 block time 가정으로 필요한 lookback block 수를 보수적으로 추정한다.
    - 고정 safety block을 추가한다.
    """
    finalized_ts = ensure_utc(finalized_block_timestamp_utc, "finalized_block_timestamp_utc")
    target = ensure_utc(target_timestamp_utc, "target_timestamp_utc")

    age_seconds = max(0, (finalized_ts - target).total_seconds())
    estimated_lookback_blocks = ceil(age_seconds / RECENT_SEARCH_MIN_SECONDS_PER_BLOCK)
    lookback_blocks = estimated_lookback_blocks + RECENT_SEARCH_SAFETY_BLOCKS

    return max(0, finalized_block_number - lookback_blocks)


def find_search_low_block(
    client: BlockLookupClient,
    *,
    target_timestamp_utc: datetime,
    high_block: int,
    high_block_timestamp_utc: datetime,
    timestamp_cache: dict[int, datetime],
) -> int:
    """target 이전의 block을 포함하는 탐색 하한을 찾는다.

    finalized head에서 1, 2, 4, 8 ... block씩 과거로 지수 탐색한다.
    target보다 과거 또는 같은 timestamp를 가진 block을 찾으면 그 block을 반환한다.

    provider가 numeric eth_getBlockByNumber를 과거 구간에서 HTTP 403으로 제한하는 경우:
    1. 마지막으로 조회 가능한 high block을 기준으로 접근 가능 최저 block을 이진 탐색한다.
    2. 그 최저 block조차 target보다 최신이면 provider 범위가 부족하다고 판단한다.
    3. 그렇지 않으면 해당 최저 block을 이진 탐색의 하한으로 사용한다.
    """
    target = ensure_utc(target_timestamp_utc, "target_timestamp_utc")
    high_ts = ensure_utc(high_block_timestamp_utc, "high_block_timestamp_utc")

    if high_ts <= target:
        return high_block

    newest_known_ok = high_block
    step = 1

    while True:
        candidate = max(0, high_block - step)

        try:
            candidate_ts = _block_timestamp(client, candidate, timestamp_cache)
        except NonRetryableRpcError as exc:
            if not _is_forbidden_block_lookup(exc):
                raise

            oldest_accessible = _find_oldest_accessible_block(
                client,
                failed_low_block=candidate,
                known_ok_high_block=newest_known_ok,
                timestamp_cache=timestamp_cache,
            )

            if _block_timestamp(client, oldest_accessible, timestamp_cache) > target:
                raise BlockRangeError(
                    "provider block metadata lookup window does not reach "
                    "interval_start_utc; use a provider that supports older block metadata "
                    "or run a more recent/narrower interval."
                ) from exc

            return oldest_accessible

        newest_known_ok = candidate

        if candidate_ts <= target or candidate == 0:
            return candidate

        step *= 2


def _find_oldest_accessible_block(
    client: BlockLookupClient,
    *,
    failed_low_block: int,
    known_ok_high_block: int,
    timestamp_cache: dict[int, datetime],
) -> int:
    """HTTP 403이 시작되는 provider boundary에서 접근 가능한 최저 block을 찾는다."""
    left = failed_low_block + 1
    right = known_ok_high_block
    oldest_ok = known_ok_high_block

    while left <= right:
        mid = (left + right) // 2

        try:
            _block_timestamp(client, mid, timestamp_cache)
        except NonRetryableRpcError as exc:
            if not _is_forbidden_block_lookup(exc):
                raise
            left = mid + 1
        else:
            oldest_ok = mid
            right = mid - 1

    return oldest_ok


def _is_forbidden_block_lookup(error: NonRetryableRpcError) -> bool:
    """provider가 numeric block metadata 조회를 HTTP 403으로 거부한 경우만 식별한다."""
    return error.detail.method == "eth_getBlockByNumber" and error.detail.http_status == 403


def block_number_from_payload(block: Mapping[str, Any]) -> int:
    """RPC block payload의 hex number를 Python int로 변환한다."""
    number = block.get("number")
    if not isinstance(number, str) or not number.startswith("0x"):
        raise BlockRangeError("block payload missed hex number.")
    return int(number, 16)


def block_timestamp_from_payload(block: Mapping[str, Any]) -> datetime:
    """RPC block payload의 hex timestamp를 timezone-aware UTC datetime으로 변환한다."""
    timestamp = block.get("timestamp")
    if not isinstance(timestamp, str) or not timestamp.startswith("0x"):
        raise BlockRangeError("block payload missed hex timestamp.")
    return datetime.fromtimestamp(int(timestamp, 16), UTC)


def ensure_utc(value: datetime, name: str) -> datetime:
    """naive datetime을 거부하고 timezone-aware 값을 UTC로 정규화한다."""
    if value.tzinfo is None:
        raise BlockRangeError(f"{name} must be timezone-aware.")
    return value.astimezone(UTC)


def _block_timestamp(
    client: BlockLookupClient,
    block_number: int,
    cache: dict[int, datetime],
) -> datetime:
    """block timestamp를 cache 우선으로 조회한다."""
    if block_number not in cache:
        cache[block_number] = block_timestamp_from_payload(
            client.eth_get_block_by_number(block_number, full_transactions=False)
        )
    return cache[block_number]
