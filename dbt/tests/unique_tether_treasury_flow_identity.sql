-- depends_on: {{ ref('tether_treasury_flow') }}
-- 목적:
-- gold Treasury flow의 incremental unique key가 실제 output grain에서 유일한지 검증한다.
--
-- key:
-- chain_id + contract_address + treasury_address + hour_start_utc + direction
--
-- 이 테스트는 delete+insert incremental replay 뒤에도 동일 hour/direction 집계가
-- 중복되지 않았다는 데이터 증적이다.

{{ config(tags=['ethereum_hourly']) }}

select
    chain_id,
    contract_address,
    treasury_address,
    hour_start_utc,
    direction,
    count(*) as duplicate_count
from {{ ref('tether_treasury_flow') }}
group by 1, 2, 3, 4, 5
having count(*) > 1
