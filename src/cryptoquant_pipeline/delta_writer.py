"""Ethereum canonical raw log용 insert-only Delta Lake writer.

이 모듈은 ``ethereum_logs`` 테이블의 저장 계층 데이터 계약을 책임진다.
계약상 RPC가 반환한 ``data_raw`` hex 원문과, 해당 값이 정확히 하나의 ABI
uint256 word일 때 Python normalizer가 생성한 정확한 10진수 문자열을 함께 저장한다.
따라서 Delta/Parquet에는 Python arbitrary-precision 객체, float, 또는 손실 가능한
고정 정밀도 대체값을 저장하지 않는다.

핵심 불변식:
- ``data_raw``는 변경하지 않는 RPC/ABI 원본 증적이다.
- ``data_uint256_decimal_text``는 값이 32-byte word일 때 uint256 전체를 정확히
  보존한다. 최대 78자리 10진수 문자열이 될 수 있다.
- ``data_uint256_decode_status``는 downstream에서 ``DECIMAL(38, 0)`` 파생값을
  만들 수 있는지 설명한다. SQL decimal 파생값이 NULL이라고 해서 raw 값이
  유실된 것으로 해석하면 안 된다.
- writer는 natural key 기준 insert-only다. 이미 commit된 interval을 재실행해도
  같은 log를 두 번째로 append할 수 없다.
- schema drift는 fail-closed로 처리한다. 이전 계약으로 만들어진 테이블은 명시적으로
  migration하거나 재구성해야 한다. 자동 schema merge는 과거 행의 uint256 상태를
  비워 계약을 약화시킬 수 있으므로 허용하지 않는다.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cryptoquant_pipeline.exceptions import DeltaWriteError
from cryptoquant_pipeline.log_normalizer import (
    DECIMAL38_MAX,
    UINT256_STATUS_DECIMAL38_AVAILABLE,
    UINT256_STATUS_NOT_UINT256_WORD,
    UINT256_STATUS_OUTSIDE_DECIMAL38_RANGE,
    decode_uint256_data_raw,
)

# Ethereum receipt log의 식별자는 동일 체인 안에서 안정적이다.
# raw 저장의 멱등성 경계이자 downstream dbt incremental key의 기준으로 사용한다.
NATURAL_KEY_COLUMNS = ("chain_id", "transaction_hash", "log_index")

# event-time UTC 날짜로 partition하면 1시간 dbt window가 읽는 raw data 양을 줄이면서
# 같은 UTC 날짜의 행을 함께 배치할 수 있다.
PARTITION_COLUMNS = ["block_date_utc"]

# 상태값 상수는 normalizer에서 직접 import한다.
# 생산자와 저장 계층 검증기가 서로 다른 상태 문자열을 쓰는 drift를 막기 위함이다.
UINT256_DECODE_STATUSES = frozenset(
    {
        UINT256_STATUS_DECIMAL38_AVAILABLE,
        UINT256_STATUS_OUTSIDE_DECIMAL38_RANGE,
        UINT256_STATUS_NOT_UINT256_WORD,
    }
)

# 같은 natural key가 한 write batch에 두 번 나타날 때 반드시 같아야 하는 불변 필드다.
# ``ingested_at_utc``는 제외한다. 재시도는 같은 불변 log를 다른 수집 시각에 다시
# 관측할 수 있지만, 그 사실이 이벤트 자체를 바꾸지는 않기 때문이다.
IMMUTABLE_LOG_COLUMNS = (
    "chain_id",
    "block_number",
    "block_hash",
    "transaction_hash",
    "transaction_index",
    "log_index",
    "contract_address",
    "topic0",
    "topic1",
    "topic2",
    "topic3",
    "data_raw",
    "data_uint256_decimal_text",
    "data_uint256_decode_status",
    "removed",
    "block_timestamp_utc",
    "block_date_utc",
    "interval_start_utc",
    "interval_end_utc",
)


@dataclass(frozen=True)
class DeltaWriteResult:
    """insert-if-not-exists 결과와 멱등성 검증에 필요한 row count를 보존한다."""

    table_path: Path
    inserted_row_count: int
    duplicate_skipped_count: int
    row_count_before: int
    row_count_after: int


def write_ethereum_logs_insert_only(
    rows: Iterable[Mapping[str, Any]],
    *,
    table_path: str | Path,
) -> DeltaWriteResult:
    """Natural key 기준으로 신규 canonical raw log만 Delta table에 추가한다.

    처리 순서:
    1. 입력 row가 현재 raw schema와 uint256 상태 계약을 만족하는지 검증한다.
    2. 동일 batch 안의 natural-key duplicate를 제거하되, 불변 payload 충돌은 실패 처리한다.
    3. 기존 Delta snapshot과 비교해 이미 저장된 key는 append 대상에서 제외한다.
    4. 신규 행을 append하거나, 빈 interval이면 schema-only table을 생성한다.

    기존 Delta schema가 현재 계약과 다르면 자동 merge/overwrite하지 않는다. 특히
    uint256 관련 새 컬럼이 없는 과거 테이블에 append하면 historical row의 status가
    NULL이 되어 downstream 의미가 모호해진다. 따라서 명시적 migration 또는 clean
    rebuild가 먼저 이뤄져야 한다.
    """
    pa, deltalake = _load_dependencies()
    path = Path(table_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    schema = ethereum_logs_schema(pa)

    input_rows = [dict(row) for row in rows]
    _validate_input_rows(input_rows, schema)
    unique_rows, batch_duplicates = _dedupe_rows(input_rows)

    table_exists = (path / "_delta_log").exists()
    before_count = 0
    existing_keys: set[tuple[object, ...]] = set()

    if table_exists:
        try:
            table = deltalake.DeltaTable(str(path))
            _validate_schema(table.schema().to_pyarrow(), schema)
            key_table = table.to_pyarrow_table(columns=list(NATURAL_KEY_COLUMNS))
        except DeltaWriteError:
            raise
        except Exception as exc:  # pragma: no cover - 외부 Delta library 경계
            raise DeltaWriteError(f"Failed to open Delta table at {path}.") from exc

        before_count = key_table.num_rows
        existing_keys = _keys_from_arrow_table(key_table)

    insert_rows = [row for row in unique_rows if _row_key(row) not in existing_keys]
    duplicate_skipped = batch_duplicates + (len(unique_rows) - len(insert_rows))

    try:
        if insert_rows:
            arrow_table = pa.Table.from_pylist(insert_rows, schema=schema)
            deltalake.write_deltalake(
                str(path),
                arrow_table,
                mode="append" if table_exists else "overwrite",
                partition_by=PARTITION_COLUMNS if not table_exists else None,
            )
        elif not table_exists:
            # 빈 interval도 재현 가능한 정상 파이프라인 산출물이다.
            # 같은 run에서 dbt가 안정적인 schema를 읽을 수 있도록 빈 테이블을 생성한다.
            arrow_table = pa.Table.from_pylist([], schema=schema)
            deltalake.write_deltalake(
                str(path),
                arrow_table,
                mode="overwrite",
                partition_by=PARTITION_COLUMNS,
            )
    except Exception as exc:  # pragma: no cover - 외부 Delta runtime 경계
        raise DeltaWriteError(
            "Failed to write canonical ethereum_logs Delta rows. "
            "No successful task should be reported until this write completes."
        ) from exc

    after_count = count_rows(path)
    return DeltaWriteResult(
        table_path=path,
        inserted_row_count=len(insert_rows),
        duplicate_skipped_count=duplicate_skipped,
        row_count_before=before_count,
        row_count_after=after_count,
    )


def count_rows(table_path: str | Path) -> int:
    """현재 Delta snapshot의 row count를 반환한다.

    전체 wide row를 materialize하지 않고 natural key의 첫 컬럼 하나만 읽어 count를
    계산한다. 과제 규모에서는 충분하며, replay 검증에서 row count 변화 여부를 확인하는
    근거로 사용한다.
    """
    _, deltalake = _load_dependencies()
    path = Path(table_path)
    if not (path / "_delta_log").exists():
        return 0

    try:
        table = deltalake.DeltaTable(str(path))
        return table.to_pyarrow_table(columns=[NATURAL_KEY_COLUMNS[0]]).num_rows
    except Exception as exc:  # pragma: no cover - 외부 Delta runtime 경계
        raise DeltaWriteError(f"Failed to count Delta rows at {path}.") from exc


def count_duplicate_natural_keys(table_path: str | Path) -> int:
    """현재 Delta snapshot에서 natural key가 중복된 row 수를 계산한다."""
    _, deltalake = _load_dependencies()
    path = Path(table_path)
    if not (path / "_delta_log").exists():
        return 0

    try:
        key_table = deltalake.DeltaTable(str(path)).to_pyarrow_table(
            columns=list(NATURAL_KEY_COLUMNS)
        )
    except Exception as exc:  # pragma: no cover - 외부 Delta runtime 경계
        raise DeltaWriteError(
            f"Failed to read natural keys from Delta table at {path}."
        ) from exc

    return key_table.num_rows - len(_keys_from_arrow_table(key_table))


def ethereum_logs_schema(pa: Any) -> Any:
    """`ethereum_logs` canonical raw Delta schema를 반환한다.

    ``data_uint256_decimal_text``는 string이어야 한다. uint256 전체는
    ``DECIMAL(38, 0)``보다 클 수 있고, Python arbitrary-precision int/Decimal 객체를
    Arrow object column으로 저장하면 reader 간 schema 안정성이 깨질 수 있다.
    """
    return pa.schema(
        [
            pa.field("chain_id", pa.int64(), nullable=False),
            pa.field("block_number", pa.int64(), nullable=False),
            pa.field("block_hash", pa.string(), nullable=False),
            pa.field("transaction_hash", pa.string(), nullable=False),
            pa.field("transaction_index", pa.int64(), nullable=True),
            pa.field("log_index", pa.int64(), nullable=False),
            pa.field("contract_address", pa.string(), nullable=False),
            pa.field("topic0", pa.string(), nullable=True),
            pa.field("topic1", pa.string(), nullable=True),
            pa.field("topic2", pa.string(), nullable=True),
            pa.field("topic3", pa.string(), nullable=True),
            # 모든 raw log에 대해 변경하지 않는 RPC/ABI 원문 증적.
            pa.field("data_raw", pa.string(), nullable=False),
            # data_raw가 정확히 uint256 word일 때만 저장하는 정확한 10진수 표현.
            pa.field("data_uint256_decimal_text", pa.string(), nullable=True),
            # NULL decimal text의 의미가 dbt에서 모호해지지 않도록 non-null 상태값을 저장한다.
            # 가능한 상태값은 UINT256_DECODE_STATUSES를 따른다.
            pa.field("data_uint256_decode_status", pa.string(), nullable=False),
            pa.field("removed", pa.bool_(), nullable=True),
            pa.field("block_timestamp_utc", pa.timestamp("us", tz="UTC"), nullable=False),
            pa.field("block_date_utc", pa.date32(), nullable=False),
            pa.field("interval_start_utc", pa.timestamp("us", tz="UTC"), nullable=False),
            pa.field("interval_end_utc", pa.timestamp("us", tz="UTC"), nullable=False),
            pa.field("ingested_at_utc", pa.timestamp("us", tz="UTC"), nullable=False),
        ]
    )


def _load_dependencies() -> tuple[Any, Any]:
    """Delta writer에 필요한 선택적 runtime dependency를 필요 시점에 import한다."""
    try:
        import deltalake
        import pyarrow as pa
    except ImportError as exc:
        raise DeltaWriteError(
            "pyarrow and deltalake are required for Delta writes."
        ) from exc
    return pa, deltalake


def _validate_input_rows(rows: list[dict[str, Any]], schema: Any) -> None:
    """Arrow write 전에 raw contract와 uint256 의미 불변식을 검증한다."""
    expected_columns = {field.name for field in schema}

    for index, row in enumerate(rows):
        actual_columns = set(row)
        missing = expected_columns - actual_columns
        unexpected = actual_columns - expected_columns
        if missing or unexpected:
            raise DeltaWriteError(
                "ethereum_logs row does not match the canonical raw contract. "
                f"row_index={index} missing={sorted(missing)} "
                f"unexpected={sorted(unexpected)}"
            )

        _validate_uint256_contract(row, row_index=index)


def _validate_uint256_contract(row: Mapping[str, Any], *, row_index: int) -> None:
    """Normalizer가 생성한 exact uint256 text/status 관계를 fail-closed로 검증한다."""
    status = row["data_uint256_decode_status"]
    decimal_text = row["data_uint256_decimal_text"]

    if status not in UINT256_DECODE_STATUSES:
        raise DeltaWriteError(
            "Unknown data_uint256_decode_status in ethereum_logs row. "
            f"row_index={row_index} status={status!r}"
        )

    # 호출자가 준 decimal text/status 조합만 신뢰하지 않는다.
    # 변경 불가한 data_raw에서 다시 계산해, 잘못된 normalizer 변경이나 수동 backfill이
    # 수치적으로 불일치한 raw event를 저장하지 못하게 한다.
    try:
        decoded = decode_uint256_data_raw(row["data_raw"])
    except (TypeError, ValueError) as exc:
        raise DeltaWriteError(
            "data_raw must be a valid 0x-prefixed hexadecimal string. "
            f"row_index={row_index}"
        ) from exc

    if (decimal_text, status) != (decoded.decimal_text, decoded.status):
        raise DeltaWriteError(
            "data_uint256 decimal text/status does not match immutable data_raw. "
            f"row_index={row_index} expected_status={decoded.status!r} "
            f"actual_status={status!r}"
        )

    if status == UINT256_STATUS_NOT_UINT256_WORD:
        # 위 비교만으로 decimal_text가 None임은 이미 보장된다.
        # 이 분기는 저장 계층에서 계약을 읽기 쉽게 명시적으로 남긴다.
        return

    if not _is_canonical_non_negative_decimal_text(decimal_text):
        raise DeltaWriteError(
            "uint256 rows must contain a canonical non-negative decimal text value. "
            f"row_index={row_index} status={status!r} value={decimal_text!r}"
        )

    value = int(decimal_text)
    if status == UINT256_STATUS_DECIMAL38_AVAILABLE and value > DECIMAL38_MAX:
        raise DeltaWriteError(
            "DECIMAL38_AVAILABLE value exceeds DECIMAL(38, 0) range. "
            f"row_index={row_index}"
        )
    if status == UINT256_STATUS_OUTSIDE_DECIMAL38_RANGE and value <= DECIMAL38_MAX:
        raise DeltaWriteError(
            "OUTSIDE_DECIMAL38_RANGE value fits DECIMAL(38, 0). "
            f"row_index={row_index}"
        )


def _is_canonical_non_negative_decimal_text(value: object) -> bool:
    """Python ``str(int(uint256))`` 형태의 canonical decimal text인지 판별한다."""
    if not isinstance(value, str) or not value.isdecimal():
        return False
    return value == "0" or not value.startswith("0")


def _dedupe_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """동일 batch의 duplicate를 제거하고 immutable raw payload 충돌을 차단한다."""
    seen: dict[tuple[object, ...], dict[str, Any]] = {}
    result: list[dict[str, Any]] = []
    duplicate_count = 0

    for row in rows:
        key = _row_key(row)
        prior = seen.get(key)
        if prior is None:
            seen[key] = row
            result.append(row)
            continue

        if not _same_immutable_log_payload(prior, row):
            raise DeltaWriteError(
                "Conflicting immutable payloads share one ethereum log natural key. "
                f"key={key!r}"
            )
        duplicate_count += 1

    return result, duplicate_count


def _same_immutable_log_payload(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
) -> bool:
    """재수집 시각을 제외한 Ethereum log 불변 필드가 같은지 비교한다."""
    return all(left[column] == right[column] for column in IMMUTABLE_LOG_COLUMNS)


def _row_key(row: Mapping[str, Any]) -> tuple[object, ...]:
    """insert-only 저장과 dbt incremental이 공유하는 raw event natural key를 반환한다."""
    return tuple(row[column] for column in NATURAL_KEY_COLUMNS)


def _keys_from_arrow_table(table: Any) -> set[tuple[object, ...]]:
    """Arrow natural-key columns를 Python set으로 변환한다."""
    columns = [table.column(column).to_pylist() for column in NATURAL_KEY_COLUMNS]
    return {tuple(values) for values in zip(*columns, strict=True)}


def _validate_schema(existing_schema: Any, expected_schema: Any) -> None:
    """기존 Delta table이 현재 canonical raw contract와 완전히 같은지 검증한다.

    자동 schema merge는 의도적으로 사용하지 않는다. 새 non-null status column이 없는
    historical row가 만들어지면 dbt가 raw text NULL의 의미를 복원할 수 없기 때문이다.
    """
    existing = {
        field.name: (str(field.type), field.nullable)
        for field in existing_schema
    }
    expected = {
        field.name: (str(field.type), field.nullable)
        for field in expected_schema
    }
    if existing != expected:
        raise DeltaWriteError(
            "Existing Delta schema does not match the canonical ethereum_logs "
            "contract. Run an explicit backfill migration or rebuild the local "
            "Delta path before appending. "
            f"existing={existing} expected={expected}"
        )
