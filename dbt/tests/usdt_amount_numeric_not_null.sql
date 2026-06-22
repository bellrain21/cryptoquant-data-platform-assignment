-- depends_on: {{ ref('erc20_transfers') }}
-- 목적:
-- configured USDT contract는 Treasury 집계 대상이므로 numeric 변환 실패를
-- 일반 ERC-20 범위 초과처럼 허용하지 않고 dbt build를 실패시킨다.
--
-- 실패 시 확인 순서:
-- 1. Python normalizer의 data_uint256_decimal_text 생성
-- 2. Delta writer의 raw schema / uint256 contract 검증
-- 3. erc20_transfers의 DECIMAL(38,0) 파생 및 USDT decimal-scale 변환
--
-- 0 값은 유효하므로 `is null`만 검사한다.

{{ config(tags=['ethereum_hourly']) }}

select
    chain_id,
    transaction_hash,
    log_index,
    contract_address,
    raw_amount_decimal_text,
    amount_numeric_status,
    raw_amount_decimal,
    amount_usdt_decimal_text,
    amount_usdt
from {{ ref('erc20_transfers') }}
where
    contract_address = lower('{{ var("usdt_contract_address") }}')
    and (
        raw_amount_decimal_text is null
        or amount_numeric_status <> 'DECIMAL38_AVAILABLE'
        or raw_amount_decimal is null
        or amount_usdt_decimal_text is null
        or amount_usdt is null
    )
