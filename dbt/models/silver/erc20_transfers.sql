-- depends_on: {{ ref('ethereum_logs') }}
-- 목적:
-- canonical raw ethereum_logs에서 ERC-20 형태의 Transfer event를 추출하고,
-- indexed topic과 ABI data를 분석용 컬럼으로 정규화하는 incremental silver model.
--
-- source: {{ ref('ethereum_logs') }}
-- grain: chain_id + transaction_hash + log_index
-- incremental 범위: Airflow가 전달한 UTC [window_start, window_end)만 delete+insert 재처리.
--
-- 변경 의도 / 데이터 계약:
-- 1. DuckDB SQL 안에서 0x uint256 hex를 산술로 10진수화하지 않는다.
--    기존 방식은 DECIMAL(38,0)를 초과하는 일반 ERC-20 uint256에서 model 전체를 실패시켰다.
--
-- 2. data_uint256_decimal_text는 Python normalizer가
--    int(data_raw, 16) -> str(...)로 만든 정확한 decimal 문자열이다.
--    따라서 최대 78자리 uint256도 원본 data_raw와 함께 손실 없이 보존된다.
--
-- 3. raw_amount_decimal은 SQL 집계 편의를 위한 선택적 DECIMAL(38,0) 파생값이다.
--    OUTSIDE_DECIMAL38_RANGE 상태의 일반 ERC-20은 raw_amount_decimal이 NULL일 수 있으나,
--    이는 원본 값 유실이 아니라 fixed-precision SQL 수치형의 표현 한계다.
--
-- 4. ERC-20과 ERC-721은 Transfer topic0 signature를 공유할 수 있다.
--    ERC-20 Transfer ABI shape는 indexed topic이 from/to 두 개(topic1/topic2)이고
--    value가 data 32-byte word에 있으므로 topic3 IS NULL 및 uint256 상태값으로 구분한다.
--    이 모델은 ABI shape를 기준으로 분류하며, token metadata 또는 contract interface 호출로
--    ERC-20 표준 준수 여부를 별도 검증하지는 않는다.
--
-- 5. USDT amount는 float/double 나눗셈을 사용하지 않는다.
--    raw decimal 문자열의 소수점 위치를 10^usdt_decimals 기준으로 이동한 뒤
--    DECIMAL(38, usdt_decimals)로 변환하여 base-unit 정밀도를 보존한다.
--
-- 후속 모델 계약:
-- - tether_treasury_flow는 configured USDT contract만 읽는다.
-- - USDT인데 raw_amount_decimal 또는 amount_usdt가 NULL이면 dbt test가 build를 실패시킨다.
-- - 일반 ERC-20의 OUTSIDE_DECIMAL38_RANGE는 정상 데이터이며 silver model 실패 사유가 아니다.

{% set usdt_decimals = var("usdt_decimals") | int %}

{{
  config(
    materialized='incremental',
    unique_key=['chain_id', 'transaction_hash', 'log_index'],
    incremental_strategy='delete+insert'
  )
}}

with source_logs as (

    select
        chain_id,
        block_number,
        block_timestamp_utc,
        block_date_utc,
        interval_start_utc,
        interval_end_utc,
        transaction_hash,
        log_index,
        contract_address,
        topic0,
        topic1,
        topic2,
        topic3,
        data_raw,
        data_uint256_decimal_text,
        data_uint256_decode_status,
        removed,
        ingested_at_utc
    from {{ ref('ethereum_logs') }}

    where
        -- ERC-20 / ERC-721이 공유할 수 있는 Transfer(address,address,uint256) signature.
        topic0 = '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef'

        -- ERC-20 Transfer는 from/to만 indexed이므로 topic3가 없어야 한다.
        -- ERC-721 Transfer의 tokenId는 일반적으로 topic3에 indexed되어 이 단계에서 제외된다.
        and topic1 is not null
        and topic2 is not null
        and topic3 is null

        -- data_raw가 정확한 uint256 word로 해석된 event만 ERC-20 amount model에 포함한다.
        -- NOT_UINT256_WORD는 raw landing 오류가 아니라 decoder_non_match로 취급한다.
        and data_uint256_decode_status in (
            'DECIMAL38_AVAILABLE',
            'OUTSIDE_DECIMAL38_RANGE'
        )

        -- canonical 분석 모델은 reorg로 제거된 log를 집계하지 않는다.
        and coalesce(removed, false) = false

        -- Airflow logical interval과 동일한 half-open UTC 경계를 사용한다.
        and block_timestamp_utc >= cast('{{ var("window_start") }}' as timestamp)
        and block_timestamp_utc < cast('{{ var("window_end") }}' as timestamp)
),

decoded_addresses as (

    select
        chain_id,
        block_number,
        block_timestamp_utc,
        block_date_utc,
        interval_start_utc,
        interval_end_utc,
        transaction_hash,
        log_index,
        contract_address,

        -- indexed address는 ABI 32-byte word이며 마지막 20 bytes가 실제 address다.
        {{ decode_ethereum_address('topic1') }} as from_address,
        {{ decode_ethereum_address('topic2') }} as to_address,

        -- 원본 ABI uint256 hex와 Python이 만든 정확한 decimal 문자열을 함께 보존한다.
        data_raw,
        data_uint256_decimal_text as raw_amount_decimal_text,
        data_uint256_decode_status as amount_numeric_status,

        ingested_at_utc
    from source_logs
),

typed_amounts as (

    select
        chain_id,
        block_number,
        block_timestamp_utc,
        block_date_utc,
        interval_start_utc,
        interval_end_utc,
        transaction_hash,
        log_index,
        contract_address,
        from_address,
        to_address,
        data_raw,
        raw_amount_decimal_text,
        amount_numeric_status,
        ingested_at_utc,

        -- 상태가 보장하는 범위 안에서만 DECIMAL(38,0) 파생값을 만든다.
        -- try_cast는 storage/normalizer 계약이 깨졌을 때 dbt query 자체가 죽지 않게 하는
        -- 마지막 방어선이며, USDT의 변환 실패는 별도 dbt test가 실패시킨다.
        case
            when amount_numeric_status = 'DECIMAL38_AVAILABLE'
                then try_cast(raw_amount_decimal_text as decimal(38, 0))
        end as raw_amount_decimal
    from decoded_addresses
),

usdt_amount_text as (

    select
        chain_id,
        block_number,
        block_timestamp_utc,
        block_date_utc,
        interval_start_utc,
        interval_end_utc,
        transaction_hash,
        log_index,
        contract_address,
        from_address,
        to_address,
        data_raw,
        raw_amount_decimal_text,
        amount_numeric_status,
        raw_amount_decimal,
        ingested_at_utc,

        -- USDT는 configured base-unit decimals만큼 decimal point를 문자열에서 이동한다.
        -- DECIMAL 나눗셈이 double로 승격될 가능성을 피하고, 6자리 base-unit 정밀도를 유지한다.
        case
            when contract_address = lower('{{ var("usdt_contract_address") }}')
             and amount_numeric_status = 'DECIMAL38_AVAILABLE'
             and raw_amount_decimal_text is not null
            then
                case
                    when length(raw_amount_decimal_text) <= {{ usdt_decimals }}
                        then '0.' || lpad(
                            raw_amount_decimal_text,
                            {{ usdt_decimals }},
                            '0'
                        )
                    else
                        left(
                            raw_amount_decimal_text,
                            length(raw_amount_decimal_text) - {{ usdt_decimals }}
                        )
                        || '.'
                        || right(raw_amount_decimal_text, {{ usdt_decimals }})
                end
        end as amount_usdt_decimal_text
    from typed_amounts
)

select
    chain_id,
    block_number,
    block_timestamp_utc,
    block_date_utc,
    interval_start_utc,
    interval_end_utc,
    transaction_hash,
    log_index,
    contract_address,
    from_address,
    to_address,

    -- 감사·재처리 가능한 원본 및 손실 없는 raw base-unit 표현.
    data_raw,
    raw_amount_decimal_text,

    -- SQL fixed-precision 집계용 선택적 파생값.
    raw_amount_decimal,
    amount_numeric_status,

    -- configured USDT contract에만 존재하는 exact fixed-scale 표현.
    amount_usdt_decimal_text,
    try_cast(
        amount_usdt_decimal_text as decimal(38, {{ usdt_decimals }})
    ) as amount_usdt,

    ingested_at_utc
from usdt_amount_text

where
    -- source topic이 존재해도 malformed topic이면 address macro가 NULL을 반환한다.
    -- 이는 ERC-20 decoder contract를 만족하지 못한 event이므로 silver 출력에서 제외한다.
    from_address is not null
    and to_address is not null

-- raw table natural key는 원칙적으로 유일하다.
-- 다만 동일 window의 재수집/late-arrival 상황에서 최신 ingestion record 하나만 남겨
-- delete+insert incremental write의 입력 grain을 안정화한다.
qualify row_number() over (
    partition by chain_id, transaction_hash, log_index
    order by ingested_at_utc desc
) = 1
