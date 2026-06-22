-- 목적:
-- Delta Lake의 canonical raw `ethereum_logs`를 dbt 모델 그래프에 연결하는 staging view.
--
-- 이 모델은 원본 로그의 값을 변환하거나 업무 규칙으로 필터링하지 않는다.
-- 수집 단계에서 확정된 원본 값·정확도·해석 상태를 그대로 노출하며,
-- ERC-20 Transfer 판별과 금액 파생은 하위 silver 모델인
-- `erc20_transfers`에서 수행한다.
--
-- 원본 로그 grain:
-- chain_id + transaction_hash + log_index
--
-- uint256 데이터 계약:
-- - data_raw:
--   RPC Provider가 반환한 ABI data 원본 hex 값.
--   재처리·감사·디코딩 검증의 변경 불가능한 정본이다.
--
-- - data_uint256_decimal_text:
--   data_raw가 정확히 32-byte uint256 word일 때,
--   Python arbitrary-precision int로 변환한 정확한 10진수 문자열이다.
--   uint256 최대값처럼 DECIMAL(38,0)을 초과하는 값도 손실 없이 보존한다.
--
-- - data_uint256_decode_status:
--   decimal text의 생성 가능 여부와 SQL fixed-precision 집계 가능 여부를 설명하는
--   non-null 상태값이다.
--
--   DECIMAL38_AVAILABLE:
--     정확한 decimal text가 존재하고 DECIMAL(38,0) 파생도 가능함.
--
--   OUTSIDE_DECIMAL38_RANGE:
--     정확한 decimal text는 존재하지만 DECIMAL(38,0) 범위를 초과함.
--     원본 값은 유실되지 않으며, numeric 집계용 파생값만 NULL이 될 수 있음.
--
--   NOT_UINT256_WORD:
--     data_raw가 ERC-20 value 형태의 32-byte uint256 word가 아님.
--     예: ERC-721 형태의 Transfer event 또는 일반 raw event.
--
-- 주의:
-- 이 view는 새 raw Delta schema를 전제로 한다.
-- 기존 Delta table에 `data_uint256_decimal_text`,
-- `data_uint256_decode_status` 컬럼이 없으면 명시적 schema migration 또는
-- 로컬 Delta 경로 초기화 후 재수집을 먼저 수행해야 한다.
--
-- 컬럼 부재를 NULL로 임시 처리하면 과거 row의 uint256 상태를 구분할 수 없어
-- downstream 모델의 데이터 의미와 검증 기준이 약화된다.

{{ config(materialized='view') }}

select
    cast(chain_id as bigint) as chain_id,
    cast(block_number as bigint) as block_number,
    lower(cast(block_hash as varchar)) as block_hash,
    lower(cast(transaction_hash as varchar)) as transaction_hash,
    cast(transaction_index as bigint) as transaction_index,
    cast(log_index as bigint) as log_index,
    lower(cast(contract_address as varchar)) as contract_address,

    -- topic은 raw ABI hex이므로 lower-case로 정규화만 수행한다.
    lower(cast(topic0 as varchar)) as topic0,
    lower(cast(topic1 as varchar)) as topic1,
    lower(cast(topic2 as varchar)) as topic2,
    lower(cast(topic3 as varchar)) as topic3,

    -- 원본 ABI data와 Python이 생성한 손실 없는 decimal text를 함께 보존한다.
    lower(cast(data_raw as varchar)) as data_raw,
    cast(data_uint256_decimal_text as varchar) as data_uint256_decimal_text,
    cast(data_uint256_decode_status as varchar) as data_uint256_decode_status,

    cast(removed as boolean) as removed,
    cast(block_timestamp_utc as timestamp) as block_timestamp_utc,
    cast(block_date_utc as date) as block_date_utc,
    cast(interval_start_utc as timestamp) as interval_start_utc,
    cast(interval_end_utc as timestamp) as interval_end_utc,
    cast(ingested_at_utc as timestamp) as ingested_at_utc
from delta_scan('{{ var("delta_logs_path") }}')
