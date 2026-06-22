-- depends_on: {{ ref('erc20_transfers') }}
-- 목적:
-- 전체 Transfer-topic 수집 범위에서 configured USDT 외 token에
-- USDT 표시 단위(10^usdt_decimals)를 적용하지 않도록 검증한다.
--
-- 이 테스트는 token decimals metadata를 일반화하지 않는다.
-- 현재 파이프라인의 gold 집계 대상은 configured USDT contract 하나다.

{{ config(tags=['ethereum_hourly']) }}

select
    chain_id,
    transaction_hash,
    log_index,
    contract_address,
    amount_usdt_decimal_text,
    amount_usdt
from {{ ref('erc20_transfers') }}
where
    contract_address <> lower('{{ var("usdt_contract_address") }}')
    and (
        amount_usdt_decimal_text is not null
        or amount_usdt is not null
    )
