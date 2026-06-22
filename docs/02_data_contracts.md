# 02. Data Contract

> 상태: 구현 기준 문서
> 읽는 법: schema -> unique key -> partition -> incremental rule -> dbt model contract 순서로 확인합니다.

## Raw table

Delta table name: `ethereum_logs`

Path: `DELTA_LOGS_PATH`, Docker 기본값 `/opt/airflow/data/delta/ethereum_logs`

## Collection scope

기본 acceptance scope는 `transfer_topic_all_addresses`입니다.

```text
chain_id=1
address_filter=null
topics=[Transfer(address,address,uint256) topic0]
from_address_filter=null
to_address_filter=null
```

`ethereum_logs`는 이 configured `eth_getLogs` query scope가 반환한 raw event log landing table입니다.
전체 Ethereum event log 또는 전체 ERC-20 market coverage를 의미하지 않습니다.
`tether_treasury_flow`에서만 configured USDT contract와 Treasury address를 동시에 적용해 집계 범위를 좁힙니다.

## Schema

아래 schema는 현재 Python writer 계약입니다. `src/cryptoquant_pipeline/delta_writer.py`의 `ethereum_logs_schema()`가 정본입니다.

2026-06-22에 리팩토링한 `src/notebooks/04_accumulated_pipeline_data_freshness_validation.ipynb`는 기본 로컬
`data/delta/ethereum_logs`를 stale candidate로 표시하고, 최신 schema와 downstream row count가 확인되는
`data/delta/ethereum_logs_v2` pair를 선택합니다.
latest direct inspection 기준 `ethereum_logs_v2`는 최신 계약 컬럼, row count `6848937`, duplicate natural key count `0`을 확인했습니다.
따라서 schema 구현과 `ethereum_logs_v2` 실행 산출물은 raw contract 관점에서 `VERIFIED`로 보고, 2026-06-22 12:00 UTC hourly gap과
DuckDB staging view 절대경로 이식성은 notebook 04에서 `PARTIALLY VERIFIED`로 분리합니다.

| column | type | nullable | rule |
|---|---|---:|---|
| chain_id | BIGINT | no | Ethereum mainnet 기본 1 |
| block_number | BIGINT | no | RPC hex quantity를 int로 변환 |
| block_hash | STRING | no | lowercase hex |
| block_timestamp_utc | TIMESTAMP | no | block 조회 결과, UTC |
| block_date_utc | DATE | no | UTC date partition |
| transaction_hash | STRING | no | lowercase hex |
| transaction_index | BIGINT | yes | provider payload에 없을 수 있음 |
| log_index | BIGINT | no | RPC가 제공한 log position/index. 관련 block 또는 transaction execution context 안에서의 식별 값으로만 사용 |
| contract_address | STRING | no | event를 낸 contract address |
| topic0 | STRING | yes | event signature |
| topic1 | STRING | yes | indexed arg 1 |
| topic2 | STRING | yes | indexed arg 2 |
| topic3 | STRING | yes | indexed arg 3 |
| data_raw | STRING | no | 원본 hex string 보존 |
| data_uint256_decimal_text | STRING | yes | `data_raw`가 정확한 uint256 word일 때 Python normalizer가 만든 손실 없는 decimal 문자열 |
| data_uint256_decode_status | STRING | no | `DECIMAL38_AVAILABLE`, `OUTSIDE_DECIMAL38_RANGE`, `NOT_UINT256_WORD` 중 하나 |
| removed | BOOLEAN | yes | provider reorg marker |
| interval_start_utc | TIMESTAMP | no | Airflow data interval start |
| interval_end_utc | TIMESTAMP | no | Airflow data interval end |
| ingested_at_utc | TIMESTAMP | no | 수집 처리 시각 UTC |

## Unique key

```text
chain_id + transaction_hash + log_index
```

Transaction 하나에서 여러 event log가 발생할 수 있으므로 transaction hash 단독 unique key는 맞지 않습니다.
`block_hash`는 raw row에 보존하지만 현재 Delta writer의 dedup key에는 포함하지 않습니다.
따라서 이 key는 retry/backfill 중복 방지에는 사용되지만, reorg replacement를 별도 canonical 상태로 교체하는 key 설계는 아직 구현되지 않았습니다.

## Partition key

`block_date_utc`만 사용합니다.

선택 이유:

- hourly/daily backfill 영향 범위를 날짜로 좁힐 수 있습니다.
- `transaction_hash`는 cardinality가 너무 높습니다.
- `block_number` partition은 작은 파일과 과도한 partition을 만들 가능성이 큼.

## Normalization rule

- `contract_address`, `transaction_hash`, `topics`는 lowercase.
- topic이 4개보다 적으면 누락 topic은 null.
- `data_raw`는 hex 원문 보존.
- `block_timestamp_utc`는 log payload가 아니라 block 조회 결과 사용.
- `block_date_utc`는 UTC 기준.

## Incremental write rule

1. batch 내부 unique key 중복 제거.
2. 기존 Delta table unique key 조회.
3. 기존 key와 겹치는 row skip.
4. 새 row만 append.

동시 write는 DAG `max_active_runs=1`로 제한합니다.

## dbt incremental rule

`erc20_transfers`와 `tether_treasury_flow`는 `max(block_number)` 또는 recent lookback을 사용하지 않습니다.
Airflow가 넘긴 `window_start`, `window_end` vars를 기준으로 `[window_start, window_end)`만 처리합니다.
재실행 시 `unique_key`와 `delete+insert` 전략으로 동일 grain 중복을 방지합니다.

## Uint256 amount policy

`data_raw`는 항상 보존합니다. Python normalizer는 32-byte uint256 word를 `int(data_raw, 16)`으로 해석해 `data_uint256_decimal_text`에 손실 없는 decimal 문자열을 저장합니다.
dbt의 `raw_amount_decimal`은 SQL 집계 편의를 위한 `DECIMAL(38,0)` 파생값이므로 38자리를 넘는 일반 ERC-20 값은 `OUTSIDE_DECIMAL38_RANGE`로 남기고 실패 처리하지 않습니다.

`amount_usdt`는 configured USDT contract 행에만 채웁니다. 전체 Transfer scope에 들어온 다른 token row는 token-specific decimals를 알 수 없으므로 `null`로 둡니다.
USDT 행에서 numeric 변환이 실패하면 dbt test가 build를 실패시킵니다.

## dbt Model Contracts

| 모델명 | Grain | Unique Key | Source | Incremental 기준 | 목적 | 불변식 |
|---|---|---|---|---|---|---|
| `ethereum_logs` | Ethereum raw log 1건 | `chain_id + transaction_hash + log_index` | Delta `ethereum_logs` | view | raw Delta table을 DuckDB `delta_scan()`으로 노출함 | raw 원본과 uint256 decode 상태를 변형하지 않고 노출해야 함 |
| `erc20_transfers` | ERC-20 ABI shape를 만족한 Transfer log 1건 | `chain_id + transaction_hash + log_index` | `ref('ethereum_logs')` | `block_timestamp_utc`가 Airflow `[window_start, window_end)`에 속한 row | topic/data를 분석용 transfer row로 정규화함 | `topic0`, `topic1`, `topic2`, `topic3`, `data_uint256_decode_status` 조건이 ERC-20 ABI shape와 일치해야 함 |
| `tether_treasury_flow` | `chain_id + contract_address + treasury_address + hour_start_utc + direction` | 동일 | `ref('erc20_transfers')` | Airflow `[window_start, window_end)` | configured USDT contract와 Tether Treasury 주소 기준 시간별 inflow/outflow를 집계함 | Treasury가 `to_address`이면 `INFLOW`, `from_address`이면 `OUTFLOW`임 |
| `tether_treasury_flow_quality_summary` | Airflow/dbt window 1행 | `window_start_utc + window_end_utc` | `ref('tether_treasury_flow')` | view | 신규 dbt 모델이 DAG 수정 없이 selector/ref graph로 편입되는지 검증 가능한 요약을 제공함 | DAG가 모델명을 하드코딩하지 않아야 함 |

## ERC-20 Transfer Column Contract

| 컬럼 | 타입 | Nullable | 의미 | 산출 근거 |
|---|---|---:|---|---|
| `transaction_hash` | string | false | 트랜잭션 식별자 | RPC log 응답 |
| `log_index` | bigint | false | 트랜잭션 내 로그 순번 | RPC log 응답 |
| `contract_address` | string | false | token contract address | RPC log `address` |
| `from_address` | string | false | 송신 주소 | `topic1` 마지막 20 bytes |
| `to_address` | string | false | 수신 주소 | `topic2` 마지막 20 bytes |
| `data_raw` | string | false | ABI data 원본 hex | RPC log `data` |
| `raw_amount_decimal_text` | string | false | token base-unit uint256 값의 정확한 10진 문자열 | Python normalizer |
| `raw_amount_decimal` | decimal(38,0) | true | DuckDB 집계용 fixed-precision 파생값 | `amount_numeric_status='DECIMAL38_AVAILABLE'` |
| `amount_usdt` | decimal(38,6) | true | configured USDT contract에만 적용한 표시 단위 금액 | `DBT_USDT_DECIMALS` |

## 구현 대응표

| 문서 설명 대상 | 실제 파일 경로 | 핵심 함수·모델·테이블 | 검증 위치 | 상태 |
|---|---|---|---|---|
| raw Delta schema | `src/cryptoquant_pipeline/delta_writer.py` | `ethereum_logs_schema()` | `tests/test_delta_writer.py` | VERIFIED |
| raw natural key | `src/cryptoquant_pipeline/delta_writer.py` | `NATURAL_KEY_COLUMNS` | `tests/test_delta_idempotency.py`, `dbt/tests/unique_log_identity.sql` | VERIFIED |
| uint256 decode status | `src/cryptoquant_pipeline/log_normalizer.py` | `decode_uint256_data_raw()` | `tests/test_log_normalizer.py`, `dbt/tests/ethereum_logs_uint256_contract.sql` | VERIFIED |
| ERC-20 Transfer decode | `dbt/models/silver/erc20_transfers.sql`, `dbt/macros/decode_ethereum_address.sql` | `erc20_transfers` | `dbt/tests/erc20_transfer_integrity.sql` | VERIFIED |
| Treasury flow 집계 | `dbt/models/gold/tether_treasury_flow.sql` | `tether_treasury_flow` | `dbt/tests/treasury_flow_integrity.sql` | VERIFIED |
| external RPC raw Delta schema | `data/delta/ethereum_logs_v2` | Airflow scheduled run 산출물 | Delta direct inspection, `docs/05_validation_evidence.md` | VERIFIED |
| accumulated local raw Delta freshness | `src/notebooks/04_accumulated_pipeline_data_freshness_validation.ipynb`,<br>`data/delta/ethereum_logs_v2`, `data/analytics/ethereum_analytics_v2.duckdb` | 최신 v2 pair의 schema, duplicate key, DB extraction, hourly gap 비교 | notebook code-cell execution output | PARTIALLY VERIFIED |

## 구현 및 검증 체크리스트

- [x] raw table과 dbt model grain이 문서에 명시되어 있습니다.
  - 근거: `ethereum_logs`, `erc20_transfers`, `tether_treasury_flow` 계약 표

- [x] unique key와 incremental 전략이 코드 또는 SQL과 연결되어 있습니다.
  - 근거: `NATURAL_KEY_COLUMNS`, dbt `unique_key`, `incremental_strategy='delete+insert'`

- [x] `SELECT *` 없이 dbt model/test projection을 컬럼 단위로 명시했습니다.
  - 검증: `tests/test_dbt_contracts.py::test_dbt_models_and_tests_do_not_use_select_star`

- [x] 실제 외부 RPC에서 생성한 1시간 raw Delta table을 이 계약으로 검증했습니다.
  - 근거: `data/delta/ethereum_logs_v2` row count `6848937`, duplicate key `0`, 최신 schema fields 확인

- [x] 현재 accumulated local Delta가 최신 schema와 일치하는지 확인했습니다.
  - 결과: schema와 duplicate key는 통과. 다만 2026-06-22 12:00 UTC hourly gap과 DuckDB staging view 절대경로 문제 때문에 notebook 04 최종 판정은 `PARTIALLY VERIFIED`입니다.

- [x] 요구사항 추적표 상태를 갱신했습니다.
  - 경로: `docs/09_requirement_traceability_matrix.md`
