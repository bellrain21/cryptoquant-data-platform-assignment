-- depends_on: {{ ref('ethereum_logs') }}
-- 목적:
-- raw Delta -> staging 모델 경계에서 uint256 보존 계약이 깨지지 않았는지 검증한다.
--
-- 검증 범위:
-- - status는 정의된 세 값 중 하나여야 한다.
-- - NOT_UINT256_WORD는 decimal text를 가지면 안 된다.
-- - DECIMAL38_AVAILABLE / OUTSIDE_DECIMAL38_RANGE는 정확한 양의 정수 또는 0의
--   canonical decimal 문자열을 가져야 한다.
-- - DECIMAL38_AVAILABLE는 최대 38자리, OUTSIDE_DECIMAL38_RANGE는 39자리 이상이어야 한다.
--
-- 한계:
-- DuckDB SQL은 이 환경에서 0x uint256을 arbitrary-precision 정수로 재변환하지 않는다.
-- raw hex와 decimal text의 수치적 동치 검증은 Python normalizer / Delta writer unit test가 담당한다.
-- 이 테스트는 Delta에 저장된 상태값과 문자열 표현의 논리적 일관성을 검증한다.

{{ config(tags=['ethereum_hourly']) }}

select
    chain_id,
    transaction_hash,
    log_index,
    data_raw,
    data_uint256_decimal_text,
    data_uint256_decode_status
from {{ ref('ethereum_logs') }}
where
    data_uint256_decode_status not in (
        'DECIMAL38_AVAILABLE',
        'OUTSIDE_DECIMAL38_RANGE',
        'NOT_UINT256_WORD'
    )
    or (
        data_uint256_decode_status = 'NOT_UINT256_WORD'
        and data_uint256_decimal_text is not null
    )
    or (
        data_uint256_decode_status in (
            'DECIMAL38_AVAILABLE',
            'OUTSIDE_DECIMAL38_RANGE'
        )
        and (
            data_uint256_decimal_text is null
            or not regexp_matches(
                data_uint256_decimal_text,
                '^(0|[1-9][0-9]*)$'
            )
        )
    )
    or (
        data_uint256_decode_status = 'DECIMAL38_AVAILABLE'
        and length(data_uint256_decimal_text) > 38
    )
    or (
        data_uint256_decode_status = 'OUTSIDE_DECIMAL38_RANGE'
        and length(data_uint256_decimal_text) <= 38
    )
