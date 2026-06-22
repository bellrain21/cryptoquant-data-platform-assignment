"""Static dbt contract checks for collection scope and Treasury business filtering."""

from __future__ import annotations

from pathlib import Path


def test_usdt_contract_filter_lives_only_in_treasury_gold_model() -> None:
    """Silver decodes Transfer scope broadly; Gold applies USDT + Treasury business rule."""
    root = Path(__file__).resolve().parents[1]
    silver_sql = (root / "dbt" / "models" / "silver" / "erc20_transfers.sql").read_text()
    gold_sql = (root / "dbt" / "models" / "gold" / "tether_treasury_flow.sql").read_text()

    assert "and contract_address = lower('{{ var(\"usdt_contract_address\") }}')" not in silver_sql
    assert "when contract_address = lower('{{ var(\"usdt_contract_address\") }}')" in silver_sql
    assert "{% set usdt_contract_address = var(\"usdt_contract_address\") | lower %}" in gold_sql
    assert "contract_address = '{{ usdt_contract_address }}'" in gold_sql


def test_dbt_models_and_tests_do_not_use_select_star() -> None:
    """목적: 모델 grain과 실패 row 증거가 컬럼 단위로 추적 가능해야 함."""
    root = Path(__file__).resolve().parents[1]
    sql_paths = [
        *sorted((root / "dbt" / "models").rglob("*.sql")),
        *sorted((root / "dbt" / "tests").rglob("*.sql")),
    ]

    offenders = [
        str(path.relative_to(root))
        for path in sql_paths
        if ("select " + "*") in path.read_text(encoding="utf-8").lower()
    ]

    assert offenders == []
