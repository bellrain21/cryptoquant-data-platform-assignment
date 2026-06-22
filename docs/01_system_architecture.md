# 01. Architecture

> 상태: 구현 기준 문서
> 읽는 법: data flow -> 책임 경계 -> 동시성 정책 -> 체크리스트 순서로 확인합니다.

## 목적

Ethereum RPC에서 event log를 수집해 raw Delta table로 보존하고, dbt-duckdb로 분석용 모델을 만드는 로컬 재현 구조를 설명합니다.

이 문서는 현재 구현 기준만 다룹니다. `docs/task_02_ethereum_log_pipeline/`의 확장 설계 메모는 참고 자료이며, 현재 실행 기준은 `src/cryptoquant_pipeline/`, `airflow/dags/ethereum_hourly_logs.py`, `dbt/models/`입니다.

## Data flow

```text
Airflow hourly logical interval
  -> airflow/dags/ethereum_hourly_logs.py
  -> src/cryptoquant_pipeline/pipeline.py
  -> src/cryptoquant_pipeline/block_range.py
  -> src/cryptoquant_pipeline/rpc_client.py
  -> src/cryptoquant_pipeline/log_collector.py
  -> src/cryptoquant_pipeline/log_normalizer.py
  -> src/cryptoquant_pipeline/delta_writer.py
  -> src/cryptoquant_pipeline/dbt_runner.py
  -> dbt/models/staging/ethereum_logs.sql
  -> dbt/models/silver/erc20_transfers.sql
  -> dbt/models/gold/tether_treasury_flow.sql
  -> dbt/models/gold/tether_treasury_flow_quality_summary.sql
```

## 책임 경계

| 구성요소 | 책임 |
|---|---|
| Airflow | schedule, retry, logical interval, task dependency, backfill |
| Python modules | RPC 호출, block range 계산, range split, 정규화, Delta write, dbt subprocess 실행 |
| Delta Lake | raw log 저장, `block_date_utc` partition, 재실행 중복 방지 |
| dbt | SQL 변환 graph, ERC-20 decoding, Treasury flow 집계, 품질 요약 view, dbt test |
| DuckDB | local analytics database, `delta_scan()`으로 Delta raw 읽기 |

## Airflow에 business logic을 몰아넣지 않은 이유

Airflow DAG 파일은 실행 그래프를 정의하는 데 집중합니다. RPC 오류 분류, block 이진 탐색, Delta idempotency, dbt subprocess 실행을 DAG 안에 넣으면 단위 테스트와 재사용이 어려워집니다.

현재 DAG는 `pipeline.run_interval(start, end)`만 호출합니다. dbt 실행은 `src/cryptoquant_pipeline/dbt_runner.py`에서 담당하고, DAG는 개별 dbt 모델명을 알지 않습니다.

## External I/O

- RPC: `ETH_RPC_URL`이 있을 때만 실제 호출합니다.
- Delta: local filesystem path `DELTA_LOGS_PATH`.
- DuckDB: local file `DUCKDB_PATH`.
- dbt: `dbt build --select tag:ethereum_hourly --vars '{"window_start": "...", "window_end": "..."}'` 한 번으로 graph를 실행합니다. 개별 모델명은 Airflow DAG에 하드코딩하지 않습니다.

## 실행 증거 해석 기준

현재 실행 증거는 세 층으로 나누어 해석합니다.

| 증거 | 확인 가능한 것 | 확인하지 못하는 것 | 상태 |
|---|---|---|---|
| Docker/pytest/dbt fixture build | Python, dbt graph, idempotency, fixture data contract | provider 장기 운영 SLA | VERIFIED |
| Airflow task log + Delta/DuckDB v2 | 외부 RPC scheduled 수집, Delta 적재, dbt build return code, downstream row count | 운영 환경의 지속 운영성 | VERIFIED |
| Airflow UI screenshot `data/imgs/` | DAG 등록, `@hourly`, success/failed run history | screenshot 단독 row-level data correctness | PARTIALLY VERIFIED |
| Notebook 04 accumulated data check | 최신 v2 Delta/DuckDB pair 선택, DB 추출, freshness, hourly gap 확인 | live RPC 재호출과 누락 interval backfill 완료 | PARTIALLY VERIFIED |

## 동시성 정책

DAG는 `max_active_runs=1`을 사용합니다. 동일 구간 동시 write를 피하기 위한 로컬 실행 전제입니다. Delta writer는 batch 내부 중복과 기존 table unique key 중복을 모두 skip합니다.

## 구현 대응표

| 문서 설명 대상 | 실제 파일 경로 | 핵심 함수·모델·테이블 | 검증 위치 | 상태 |
|---|---|---|---|---|
| Ethereum 수집 DAG | `airflow/dags/ethereum_hourly_logs.py` | DAG ID `ethereum_hourly_logs`, task ID `run_interval` | Airflow DagBag import, `tests/test_pipeline_idempotency.py` | VERIFIED |
| Airflow 외부 RPC 실행 이력 | `airflow/logs/dag_id=ethereum_hourly_logs`, `data/delta/ethereum_logs_v2`, `data/analytics/ethereum_analytics_v2.duckdb` | scheduled run, `raw_log_count`, `inserted_row_count`, dbt return code | task log parse, Delta/DuckDB direct inspection | VERIFIED |
| Airflow UI 실행 이력 | `data/imgs/task_02_01_image.png` ~ `task_02_04_image.png` | `@hourly`, success/failed run history | screenshot 수동 판독, `docs/05_validation_evidence.md` | PARTIALLY VERIFIED |
| RPC block range 계산 | `src/cryptoquant_pipeline/block_range.py` | `resolve_interval_block_range()` | `tests/test_block_range.py` | VERIFIED |
| RPC 호출과 chunk 분할 | `src/cryptoquant_pipeline/rpc_client.py`, `src/cryptoquant_pipeline/log_collector.py` | `eth_get_logs()`, `collect_raw_logs()` | `tests/test_rpc_retry.py`, `tests/test_chunking.py` | VERIFIED |
| Delta Lake 적재 | `src/cryptoquant_pipeline/delta_writer.py` | `write_ethereum_logs_insert_only()` | `tests/test_delta_writer.py`, `tests/test_delta_idempotency.py` | VERIFIED |
| dbt graph 실행 | `src/cryptoquant_pipeline/dbt_runner.py`, `dbt/dbt_project.yml` | `run_dbt_build()`, `tag:ethereum_hourly` | fixture `dbt build`, `tests/test_dbt_contracts.py` | VERIFIED |
| ERC-20 Transfer 모델 | `dbt/models/silver/erc20_transfers.sql` | `erc20_transfers` | `dbt/tests/erc20_transfer_integrity.sql` | VERIFIED |
| Treasury flow 모델 | `dbt/models/gold/tether_treasury_flow.sql` | `tether_treasury_flow` | `dbt/tests/treasury_flow_integrity.sql` | VERIFIED |
| Accumulated local data freshness | `src/notebooks/04_accumulated_pipeline_data_freshness_validation.ipynb`,<br>`data/delta/ethereum_logs_v2`, `data/analytics/ethereum_analytics_v2.duckdb` | 최신 raw Delta schema, DB extraction, hourly gap 비교 | notebook code-cell execution output | PARTIALLY VERIFIED |
| Bitcoin Velocity 계산 설계 | `docs/task_01_bitcoin_velocity/` | 설계 SQL 또는 의사코드 | Task 1 타당성 스캔, 문서 구조와 요구사항 추적표 | VERIFIED |

## 구현 및 검증 체크리스트

- [x] 설명 대상 코드 또는 SQL 경로가 연결되어 있습니다.
  - 근거: `src/cryptoquant_pipeline/`, `airflow/dags/ethereum_hourly_logs.py`, `dbt/models/`, `tests/`

- [x] DAG ID, task ID, dbt model명, table명이 실제 구현과 일치합니다.
  - 검증: `rg "ethereum_hourly_logs|run_interval|erc20_transfers|tether_treasury_flow"`

- [x] dbt 모델명은 Airflow DAG에 하드코딩되어 있지 않습니다.
  - 근거: `src/cryptoquant_pipeline/dbt_runner.py`의 `--select tag:ethereum_hourly`

- [x] 실제 외부 RPC 환경에서 1시간 scheduled DAG end-to-end 검증을 완료했습니다.
  - 근거: `airflow/logs/` successful scheduled run 반환값 33건, 최신 direct inspection 기준 `data/delta/ethereum_logs_v2` row count `6848937`, `data/analytics/ethereum_analytics_v2.duckdb`의 `erc20_transfers=6079379`
  - 한계: production-grade 무중단 운영과 full-history backfill은 별도 검증 대상입니다.

- [x] Airflow UI screenshot을 실행 이력 보조 증거로 연결했습니다.
  - 근거: `data/imgs/`, `docs/05_validation_evidence.md`

- [x] 요구사항 추적표 상태를 갱신했습니다.
  - 경로: `docs/09_requirement_traceability_matrix.md`
