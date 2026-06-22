-- depends_on: {{ ref('tether_treasury_flow') }}
-- 목적:
-- configured USDT Treasury flow gold model의 key, direction, 금액 집계 계약을 검증한다.
--
-- 방지 대상:
-- - 다른 chain / token / treasury 주소의 혼입
-- - direction 오타
-- - 음수 또는 NULL aggregate 전파
-- - 비어 있는 집계를 정상 row로 기록
--
-- self-transfer는 gold model에서 이미 제외하므로, 이 output test에는 나타나지 않아야 한다.

{{ config(tags=['ethereum_hourly']) }}

select
    chain_id,
    contract_address,
    treasury_address,
    hour_start_utc,
    direction,
    transfer_count,
    total_amount_raw,
    total_amount_usdt,
    source_interval_start_utc
from {{ ref('tether_treasury_flow') }}
where
    chain_id <> 1
    or contract_address <> lower('{{ var("usdt_contract_address") }}')
    or treasury_address <> lower('{{ var("tether_treasury_address") }}')
    or hour_start_utc is null
    or source_interval_start_utc is null
    or direction not in ('INFLOW', 'OUTFLOW')
    or transfer_count is null
    or transfer_count <= 0
    or total_amount_raw is null
    or total_amount_raw < 0
    or total_amount_usdt is null
    or total_amount_usdt < 0
