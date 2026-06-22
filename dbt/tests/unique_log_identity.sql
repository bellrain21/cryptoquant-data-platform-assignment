-- depends_on: {{ ref('ethereum_logs') }}
-- 목적:
-- canonical raw ethereum_logs의 natural key 중복을 검증한다.
--
-- key:
-- chain_id + transaction_hash + log_index
--
-- 방지 대상:
-- retry / backfill / 동일 interval replay가 raw log를 중복 적재하여
-- downstream ERC-20 및 Treasury 집계가 부풀어지는 문제.
--
-- 주의:
-- deprecated stg_ethereum_logs가 아니라 canonical staging model인 ethereum_logs를 참조한다.

{{ config(tags=['ethereum_hourly']) }}

select
    chain_id,
    transaction_hash,
    log_index,
    count(*) as duplicate_count
from {{ ref('ethereum_logs') }}
group by 1, 2, 3
having count(*) > 1
