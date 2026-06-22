-- depends_on: {{ ref('tether_treasury_flow') }}
-- 목적:
-- tether_treasury_flow의 현재 Airflow window 결과를 검증자가 빠르게 확인할 수 있는
-- 품질 요약 view로 노출한다.
--
-- 이유:
-- 신규 dbt 모델이 dbt_project.yml의 `tag:ethereum_hourly`와 `ref()` graph만으로
-- DAG 수정 없이 자동 실행 대상에 들어가는지 검증하되, 무의미한 dummy mart를 남기지 않는다.
--
-- 불변:
-- source는 `tether_treasury_flow` ref() 하나이며, Airflow와 같은 UTC
-- [window_start, window_end) 경계를 사용한다.

{{ config(materialized='view') }}

with flow as (

    select
        hour_start_utc,
        direction,
        transfer_count,
        total_amount_raw,
        total_amount_usdt,
        source_interval_start_utc
    from {{ ref('tether_treasury_flow') }}
    where
        source_interval_start_utc >= cast('{{ var("window_start") }}' as timestamp)
        and source_interval_start_utc < cast('{{ var("window_end") }}' as timestamp)
),

summary as (

    select
        cast('{{ var("window_start") }}' as timestamp) as window_start_utc,
        cast('{{ var("window_end") }}' as timestamp) as window_end_utc,

        count(*) as flow_row_count,
        coalesce(sum(transfer_count), 0) as transfer_count,
        count(distinct direction) as direction_count,

        min(hour_start_utc) as first_hour_start_utc,
        max(hour_start_utc) as last_hour_start_utc,

        coalesce(
            sum(
                case
                    when direction = 'INFLOW' then total_amount_raw
                    else cast(0 as decimal(38, 0))
                end
            ),
            cast(0 as decimal(38, 0))
        ) as total_inflow_raw,

        coalesce(
            sum(
                case
                    when direction = 'OUTFLOW' then total_amount_raw
                    else cast(0 as decimal(38, 0))
                end
            ),
            cast(0 as decimal(38, 0))
        ) as total_outflow_raw,

        coalesce(
            sum(
                case
                    when direction = 'INFLOW' then total_amount_usdt
                    else cast(0 as decimal(38, 6))
                end
            ),
            cast(0 as decimal(38, 6))
        ) as total_inflow_usdt,

        coalesce(
            sum(
                case
                    when direction = 'OUTFLOW' then total_amount_usdt
                    else cast(0 as decimal(38, 6))
                end
            ),
            cast(0 as decimal(38, 6))
        ) as total_outflow_usdt
    from flow
)

select
    window_start_utc,
    window_end_utc,
    flow_row_count,
    transfer_count,
    direction_count,
    first_hour_start_utc,
    last_hour_start_utc,
    total_inflow_raw,
    total_outflow_raw,
    total_inflow_usdt,
    total_outflow_usdt
from summary
