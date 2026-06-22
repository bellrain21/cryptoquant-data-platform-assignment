-- depends_on: {{ ref('erc20_transfers') }}
-- 목적:
-- configured Ethereum Mainnet USDT contract와 Tether Treasury 주소를 기준으로
-- Treasury 유입·유출을 UTC 시간 단위로 집계하는 incremental gold model.
--
-- source: {{ ref('erc20_transfers') }}
-- output grain:
-- chain_id + contract_address + treasury_address + hour_start_utc + direction
--
-- incremental 범위:
-- Airflow가 전달한 UTC [window_start, window_end)만 delete+insert 방식으로 재처리한다.
-- 동일 logical interval을 재실행해도 해당 window의 결과만 결정론적으로 교체된다.
--
-- 데이터 계약 / 변경 의도:
-- 1. 일반 ERC-20의 최대 uint256 값은 silver에서 exact decimal text로 보존되지만,
--    이 gold model은 configured USDT contract만 다룬다.
--
-- 2. USDT의 raw_amount_decimal 또는 amount_usdt가 NULL인 row는 정상으로 간주하지 않는다.
--    해당 상태는 `usdt_amount_numeric_not_null` dbt test가 build를 실패시켜야 한다.
--    이 모델의 NULL filter는 잘못된 값을 합산하지 않기 위한 방어선이며,
--    데이터 품질 오류를 조용히 성공 처리하기 위한 예외 처리가 아니다.
--
-- 3. Treasury -> Treasury self-transfer는 실질적인 외부 유입·유출이 아니다.
--    이를 INFLOW 또는 OUTFLOW에 포함하면 flow를 과대계상하므로 집계에서 제외한다.
--
-- 4. chain_id, contract_address, treasury_address를 output 및 unique key에 포함한다.
--    현재 과제는 단일 Mainnet USDT Treasury config를 사용하지만,
--    config 변경·다중 대상 확장 시 서로 다른 집계가 충돌하지 않게 한다.

{% set usdt_contract_address = var("usdt_contract_address") | lower %}
{% set tether_treasury_address = var("tether_treasury_address") | lower %}

{{
  config(
    materialized='incremental',
    unique_key=[
      'chain_id',
      'contract_address',
      'treasury_address',
      'hour_start_utc',
      'direction'
    ],
    incremental_strategy='delete+insert'
  )
}}

with treasury_transfers as (

    select
        chain_id,
        block_timestamp_utc,
        interval_start_utc,
        transaction_hash,
        log_index,
        contract_address,
        from_address,
        to_address,

        -- silver가 만든 fixed-precision base-unit 값과 human-readable USDT 값.
        raw_amount_decimal,
        amount_usdt,
        amount_numeric_status
    from {{ ref('erc20_transfers') }}

    where
        -- 단순 Treasury address match만으로는 다른 token Transfer가 섞일 수 있다.
        -- configured USDT contract와 함께 제한한다.
        contract_address = '{{ usdt_contract_address }}'

        -- USDT numeric 변환 불변식은 테스트가 검증한다.
        -- 이 조건은 NULL 값이 aggregate에 전파되는 것을 차단하는 방어선이다.
        and amount_numeric_status = 'DECIMAL38_AVAILABLE'
        and raw_amount_decimal is not null
        and amount_usdt is not null

        -- silver가 이미 같은 조건을 적용하지만, gold model도 logical window를 명시한다.
        -- 독립 실행, backfill, 모델 단독 검증에서 incremental 범위를 보장한다.
        and block_timestamp_utc >= cast('{{ var("window_start") }}' as timestamp)
        and block_timestamp_utc < cast('{{ var("window_end") }}' as timestamp)

        -- Treasury가 sender 또는 receiver인 event만 대상이다.
        and (
            from_address = '{{ tether_treasury_address }}'
            or to_address = '{{ tether_treasury_address }}'
        )

        -- self-transfer는 실제 외부 flow가 아니므로 INFLOW/OUTFLOW 어느 쪽에도 집계하지 않는다.
        and not (
            from_address = '{{ tether_treasury_address }}'
            and to_address = '{{ tether_treasury_address }}'
        )
),

classified as (

    select
        chain_id,
        contract_address,
        '{{ tether_treasury_address }}' as treasury_address,

        -- DAG의 1시간 logical interval과 동일한 UTC hour grain.
        date_trunc('hour', block_timestamp_utc) as hour_start_utc,

        case
            when to_address = '{{ tether_treasury_address }}' then 'INFLOW'
            when from_address = '{{ tether_treasury_address }}' then 'OUTFLOW'
        end as direction,

        raw_amount_decimal,
        amount_usdt,
        interval_start_utc,
        transaction_hash,
        log_index
    from treasury_transfers
),

aggregated as (

    select
        chain_id,
        contract_address,
        treasury_address,
        hour_start_utc,
        direction,

        count(*) as transfer_count,

        -- base unit 기준의 원시 합계. USDT라면 6-decimal 적용 전 정수 합계다.
        sum(raw_amount_decimal) as total_amount_raw,

        -- human-readable USDT 합계. float/double을 거치지 않은 DECIMAL 기반 값이다.
        sum(amount_usdt) as total_amount_usdt,

        -- 집계가 어떤 Airflow logical interval에서 계산됐는지 남긴다.
        min(interval_start_utc) as source_interval_start_utc
    from classified
    where direction is not null
    group by
        chain_id,
        contract_address,
        treasury_address,
        hour_start_utc,
        direction
)

select
    chain_id,
    contract_address,
    treasury_address,
    hour_start_utc,
    direction,
    transfer_count,
    total_amount_raw,
    total_amount_usdt,
    source_interval_start_utc,
    current_timestamp as updated_at_utc
from aggregated
