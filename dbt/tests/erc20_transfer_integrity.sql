-- depends_on: {{ ref('erc20_transfers') }}
-- 목적:
-- silver `erc20_transfers`가 ERC-20 Transfer ABI shape와 분석용 grain을 유지하는지 검증한다.
--
-- 주의:
-- 이 모델은 topic0 + topic3 IS NULL + uint256 data shape로 ERC-20 형태를 분류한다.
-- contract interface 호출로 ERC-20 표준 준수 여부를 별도 판정하지는 않는다.
--
-- 방지 대상:
-- - topic address decode 실패
-- - malformed ABI data 전파
-- - raw amount decimal text 유실
-- - natural-key 필수값 누락

{{ config(tags=['ethereum_hourly']) }}

select
    chain_id,
    transaction_hash,
    log_index,
    contract_address,
    from_address,
    to_address,
    data_raw,
    raw_amount_decimal_text,
    amount_numeric_status
from {{ ref('erc20_transfers') }}
where
    chain_id is null
    or transaction_hash is null
    or log_index is null
    or contract_address is null
    or not regexp_matches(from_address, '^0x[0-9a-f]{40}$')
    or not regexp_matches(to_address, '^0x[0-9a-f]{40}$')
    or data_raw is null
    or not regexp_matches(data_raw, '^0x[0-9a-f]{64}$')
    or raw_amount_decimal_text is null
    or not regexp_matches(
        raw_amount_decimal_text,
        '^(0|[1-9][0-9]*)$'
    )
    or amount_numeric_status not in (
        'DECIMAL38_AVAILABLE',
        'OUTSIDE_DECIMAL38_RANGE'
    )
