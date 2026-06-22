-- depends_on: {{ ref('erc20_transfers') }}
-- 목적:
-- 일반 ERC-20 uint256의 exact decimal text와 optional DECIMAL(38,0) 파생값의
-- 관계가 상태값과 일치하는지 검증한다.
--
-- 데이터 계약:
-- - DECIMAL38_AVAILABLE:
--   raw_amount_decimal_text는 존재하고 raw_amount_decimal도 존재해야 한다.
--
-- - OUTSIDE_DECIMAL38_RANGE:
--   raw_amount_decimal_text는 정확히 보존되지만 raw_amount_decimal은 NULL이어야 한다.
--   이는 데이터 유실이 아니라 DuckDB DECIMAL(38,0) 표현 범위 밖이라는 뜻이다.
--
-- 이 테스트는 일반 ERC-20의 범위 초과를 실패로 취급하지 않는다.

{{ config(tags=['ethereum_hourly']) }}

select
    chain_id,
    transaction_hash,
    log_index,
    contract_address,
    raw_amount_decimal_text,
    raw_amount_decimal,
    amount_numeric_status
from {{ ref('erc20_transfers') }}
where
    (
        amount_numeric_status = 'DECIMAL38_AVAILABLE'
        and (
            raw_amount_decimal is null
            or length(raw_amount_decimal_text) > 38
        )
    )
    or (
        amount_numeric_status = 'OUTSIDE_DECIMAL38_RANGE'
        and (
            raw_amount_decimal is not null
            or length(raw_amount_decimal_text) <= 38
        )
    )
    or raw_amount_decimal < 0
