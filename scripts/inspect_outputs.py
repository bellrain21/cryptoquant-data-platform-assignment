from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cryptoquant_pipeline.delta_writer import (
    count_duplicate_natural_keys,
    count_rows,
)


def main() -> None:
    """
    목적:
        현재 로컬 Delta/DuckDB 산출물의 최소 상태를 출력함.
    왜 필요한가:
        README의 검증 명령 후 row count가 실제로 있는지 확인하기 위함.
    입력값:
        환경 변수 `DELTA_LOGS_PATH`, `DUCKDB_PATH`.
    반환값:
        없음. stdout에 key=value 형태로 출력함.
    정상 입력 예시:
        data/delta/ethereum_logs data/analytics/ethereum_analytics.duckdb 존재.
    정상 출력 예시:
        delta_duplicate_natural_key_count=0.
    실패 또는 경계 사례:
        DuckDB 파일이 없으면 exists=false를 출력하고 analytics 조회는 건너뜀.
    호출하는 모듈:
        운영자 또는 검증자가 PowerShell에서 직접 실행.
    다음 단계:
        출력값을 docs/05_validation_evidence.md에 검증 증거로 기록 가능함.
    불변식:
        이 스크립트는 데이터를 수정하지 않고 조회만 함.
    """

    delta_path = Path(
        os.environ.get("DELTA_LOGS_PATH", "data/delta/ethereum_logs")
    )
    duckdb_path = Path(
        os.environ.get(
            "DUCKDB_PATH",
            "data/analytics/ethereum_analytics.duckdb",
        )
    )

    print(f"delta_path={delta_path}")
    print(f"delta_row_count={count_rows(delta_path)}")
    print(
        "delta_duplicate_natural_key_count="
        f"{count_duplicate_natural_keys(delta_path)}"
    )

    if not duckdb_path.exists():
        print(f"duckdb_path={duckdb_path} exists=false")
        return

    print(f"duckdb_path={duckdb_path} exists=true")

    import duckdb

    with duckdb.connect(str(duckdb_path), read_only=True) as con:
        for table_name in ("erc20_transfers", "tether_treasury_flow"):
            try:
                count = con.execute(
                    f"select count(*) from main.{table_name}"
                ).fetchone()[0]
            except duckdb.CatalogException:
                print(f"{table_name}_row_count=UNAVAILABLE")
                continue

            print(f"{table_name}_row_count={count}")


if __name__ == "__main__":
    main()
