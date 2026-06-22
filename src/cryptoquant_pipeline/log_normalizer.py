"""Ethereum RPC log를 Delta raw data contract로 정규화한다.

이 모듈의 책임은 RPC payload 형태를 검증하고, 재처리 가능한 raw row를 만드는 것이다.
`data_raw`는 RPC가 반환한 ABI data 원문 hex를 보존하는 정본이며, uint256으로 해석할 수
있는 경우에는 Python arbitrary-precision int로 정확한 decimal 문자열을 함께 만든다.

중요:
- float/double은 uint256 정밀도를 보장하지 못하므로 저장·검증 경로에서 사용하지 않는다.
- `data_raw`가 정확히 32-byte uint256 word가 아닌 것은 raw log 오류가 아니다.
  예: ERC-721 Transfer는 동일한 topic0을 쓰지만 tokenId가 topic3에 있고 data는 "0x"일 수 있다.
- 일반 RPC payload 자체가 malformed인 경우만 `invalid_log_count`에 포함한다.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from cryptoquant_pipeline.config import TRANSFER_TOPIC0
from cryptoquant_pipeline.exceptions import NormalizationError

# ABI uint256은 32 bytes = 64 hex digits이며, 0x prefix까지 포함하면 66 characters다.
UINT256_WORD_HEX_LENGTH = 66

# DuckDB DECIMAL(38, 0)로 손실 없이 저장할 수 있는 최대 정수값.
# exact decimal text는 이 범위를 넘어도 항상 보존한다.
DECIMAL38_MAX = 10**38 - 1

# Raw Delta contract의 안정적인 상태값. dbt는 이 상태값을 이용해 numeric 파생값의
# NULL이 데이터 유실인지, DECIMAL(38, 0) 표현 범위 초과인지 구분한다.
UINT256_STATUS_DECIMAL38_AVAILABLE = "DECIMAL38_AVAILABLE"
UINT256_STATUS_OUTSIDE_DECIMAL38_RANGE = "OUTSIDE_DECIMAL38_RANGE"
UINT256_STATUS_NOT_UINT256_WORD = "NOT_UINT256_WORD"


@dataclass(frozen=True)
class Uint256DecodeResult:
    """`data_raw`의 uint256 해석 결과.

    `decimal_text`는 uint256 word일 때만 존재하며, Python int에서 생성된 정확한 10진수
    문자열이다. DECIMAL(38, 0) 범위 초과는 decode 실패가 아니라 status로 표현한다.
    """

    decimal_text: str | None
    status: str

    @property
    def fits_decimal38(self) -> bool:
        """fixed-precision SQL numeric 파생값 생성 가능 여부."""
        return self.status == UINT256_STATUS_DECIMAL38_AVAILABLE


@dataclass(frozen=True)
class NormalizationResult:
    """정상 raw row와 malformed RPC payload 수를 함께 보존한다."""

    rows: list[dict[str, object]]
    invalid_log_count: int


def normalize_logs(
    raw_logs: Sequence[Mapping[str, Any]],
    *,
    block_timestamps_utc: Mapping[int, datetime],
    chain_id: int,
    interval_start_utc: datetime,
    interval_end_utc: datetime,
    ingested_at_utc: datetime | None = None,
) -> NormalizationResult:
    """RPC raw log 목록을 Delta raw schema row 목록으로 변환한다.

    malformed RPC payload만 invalid count로 집계한다. `data_raw="0x"`처럼 유효한
    Ethereum log이지만 uint256 word가 아닌 값은 정상 row로 남기고
    `NOT_UINT256_WORD` 상태로 명시한다.
    """
    rows: list[dict[str, object]] = []
    invalid_count = 0
    ingested_at = _ensure_utc(ingested_at_utc or datetime.now(UTC), "ingested_at_utc")
    interval_start = _ensure_utc(interval_start_utc, "interval_start_utc")
    interval_end = _ensure_utc(interval_end_utc, "interval_end_utc")

    for raw_log in raw_logs:
        try:
            rows.append(
                normalize_log(
                    raw_log,
                    block_timestamps_utc=block_timestamps_utc,
                    chain_id=chain_id,
                    interval_start_utc=interval_start,
                    interval_end_utc=interval_end,
                    ingested_at_utc=ingested_at,
                )
            )
        except (KeyError, TypeError, ValueError, NormalizationError):
            invalid_count += 1

    return NormalizationResult(rows=rows, invalid_log_count=invalid_count)


def normalize_log(
    raw_log: Mapping[str, Any],
    *,
    block_timestamps_utc: Mapping[int, datetime],
    chain_id: int,
    interval_start_utc: datetime,
    interval_end_utc: datetime,
    ingested_at_utc: datetime,
) -> dict[str, object]:
    """단일 raw log를 canonical Delta raw schema row로 변환한다.

    반환 row의 uint256 관련 계약:
    - data_raw: RPC data 원문 hex 정본.
    - data_uint256_decimal_text: uint256 word일 때 정확한 10진수 문자열.
    - data_uint256_decode_status: fixed-decimal 파생 가능 여부 또는 non-uint256 shape.
    """
    block_number = hex_quantity_to_int(raw_log["blockNumber"])
    try:
        block_timestamp = _ensure_utc(
            block_timestamps_utc[block_number],
            "block_timestamp_utc",
        )
    except KeyError as exc:
        raise NormalizationError(
            f"missing block timestamp for block {block_number}."
        ) from exc

    topics = raw_log.get("topics", [])
    if not isinstance(topics, list):
        raise NormalizationError("topics must be a list.")
    topic_values = [_topic_or_none(topics, index) for index in range(4)]

    # data_raw는 모든 raw log에서 보존한다. uint256 여부는 별도 상태값으로 모델링해
    # ERC-721 등 같은 event signature를 공유하는 표준을 raw 단계에서 버리지 않는다.
    data_raw = required_hex(raw_log.get("data", "0x"))
    uint256 = decode_uint256_data_raw(data_raw)

    return {
        "chain_id": chain_id,
        "block_number": block_number,
        "block_hash": required_hex(raw_log["blockHash"]),
        "transaction_hash": required_hex(raw_log["transactionHash"]),
        "transaction_index": optional_hex_quantity(raw_log.get("transactionIndex")),
        "log_index": hex_quantity_to_int(raw_log["logIndex"]),
        "contract_address": required_hex(raw_log["address"]),
        "topic0": topic_values[0],
        "topic1": topic_values[1],
        "topic2": topic_values[2],
        "topic3": topic_values[3],
        "data_raw": data_raw,
        "data_uint256_decimal_text": uint256.decimal_text,
        "data_uint256_decode_status": uint256.status,
        "removed": raw_log.get("removed") if isinstance(raw_log.get("removed"), bool) else None,
        "block_timestamp_utc": block_timestamp,
        "block_date_utc": date(
            block_timestamp.year,
            block_timestamp.month,
            block_timestamp.day,
        ),
        "interval_start_utc": _ensure_utc(interval_start_utc, "interval_start_utc"),
        "interval_end_utc": _ensure_utc(interval_end_utc, "interval_end_utc"),
        "ingested_at_utc": _ensure_utc(ingested_at_utc, "ingested_at_utc"),
    }


def is_erc20_transfer_topic(topic0: str | None) -> bool:
    """Transfer event signature 후보인지 판별한다.

    이 signature는 ERC-20과 ERC-721이 공유하므로, True가 ERC-20임을 단독으로 보장하지
    않는다. downstream silver 모델은 topic3 is null 및 uint256 data shape를 함께 확인해야
    ERC-20 Transfer로 해석할 수 있다.
    """
    return topic0 is not None and topic0.lower() == TRANSFER_TOPIC0


def topic_to_address(topic: str | None) -> str | None:
    """indexed address topic의 마지막 20 bytes를 Ethereum address로 변환한다."""
    if topic is None:
        return None
    lowered = required_hex(topic)
    if len(lowered) != UINT256_WORD_HEX_LENGTH:
        raise ValueError("indexed address topic must be 32 bytes.")
    return "0x" + lowered[-40:]


def decode_uint256_data_raw(data_raw: str) -> Uint256DecodeResult:
    """`data_raw`를 손실 없이 uint256 decimal text로 해석한다.

    Python int는 arbitrary precision이므로 최대 uint256까지 정확히 처리할 수 있다.
    DB에는 Python object/int가 아닌 decimal 문자열을 저장해 Delta/Parquet schema를 안정적으로
    유지한다. `NOT_UINT256_WORD`는 raw log 오류가 아니라 uint256 data shape가 아니라는 의미다.
    """
    normalized = required_hex(data_raw)

    if not is_uint256_word(normalized):
        return Uint256DecodeResult(
            decimal_text=None,
            status=UINT256_STATUS_NOT_UINT256_WORD,
        )

    value = int(normalized, 16)
    decimal_text = str(value)
    status = (
        UINT256_STATUS_DECIMAL38_AVAILABLE
        if value <= DECIMAL38_MAX
        else UINT256_STATUS_OUTSIDE_DECIMAL38_RANGE
    )

    return Uint256DecodeResult(decimal_text=decimal_text, status=status)


def is_uint256_word(data_raw: str | None) -> bool:
    """value가 정확히 32-byte ABI uint256 word 형식인지 판별한다."""
    if data_raw is None:
        return False
    try:
        normalized = required_hex(data_raw)
    except ValueError:
        return False
    return len(normalized) == UINT256_WORD_HEX_LENGTH


def decode_uint256_int(data_raw: str) -> int:
    """정확히 32-byte uint256 word인 data를 Python arbitrary-precision int로 변환한다."""
    normalized = required_hex(data_raw)
    if not is_uint256_word(normalized):
        raise ValueError("uint256 data must be exactly 32 bytes.")
    return int(normalized, 16)


def decode_uint256_decimal_text(data_raw: str) -> str:
    """정확히 32-byte uint256 word를 정확한 10진수 문자열로 변환한다."""
    return str(decode_uint256_int(data_raw))


def decode_uint256_decimal(data_raw: str) -> Decimal:
    """기존 notebook/API 호환용 uint256 Decimal 변환 함수.

    파이프라인 저장 경로는 이 Decimal 객체 대신 `data_uint256_decimal_text`를 사용한다.
    """
    return Decimal(decode_uint256_int(data_raw))


def amount_with_decimals(raw_amount: Decimal, decimals: int) -> Decimal:
    """raw 정수 금액을 token decimals 기준의 표시 단위 Decimal로 변환한다."""
    if decimals < 0:
        raise ValueError("decimals must be non-negative.")
    return raw_amount / (Decimal(10) ** decimals)


def hex_quantity_to_int(value: object) -> int:
    """Ethereum JSON-RPC hex quantity를 Python int로 변환한다."""
    if not isinstance(value, str) or not value.startswith("0x"):
        raise ValueError("Expected hex quantity.")
    return int(value, 16)


def optional_hex_quantity(value: object) -> int | None:
    """None 또는 Ethereum JSON-RPC hex quantity를 처리한다."""
    if value is None:
        return None
    return hex_quantity_to_int(value)


def required_hex(value: object) -> str:
    """0x-prefixed hexadecimal string을 lowercase로 정규화한다."""
    if not isinstance(value, str) or not value.startswith("0x"):
        raise ValueError("Expected hex string.")
    int(value[2:] or "0", 16)
    return value.lower()


def _topic_or_none(topics: list[object], index: int) -> str | None:
    if index >= len(topics) or topics[index] is None:
        return None
    return required_hex(topics[index])


def _ensure_utc(value: datetime, name: str) -> datetime:
    """naive datetime을 거부하고 UTC-aware datetime으로 정규화한다."""
    if value.tzinfo is None:
        raise NormalizationError(f"{name} must be timezone-aware.")
    return value.astimezone(UTC)
