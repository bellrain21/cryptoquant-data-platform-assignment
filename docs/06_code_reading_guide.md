# 06. Code Reading Guide

> 상태: 코드 검토 안내 문서
> 읽는 법: 아래 순서대로 읽으면 수집 입력부터 최종 집계까지 추적 가능.

목적: Airflow, Delta Lake, dbt, Ethereum JSON-RPC 구현 구조를 검토할 때 권장되는 읽기 순서와 파일별 책임을 정리합니다.

전체 흐름:

```text
Airflow logical interval
-> block range resolution
-> eth_getLogs RPC call
-> raw log normalization
-> Delta Lake write
-> dbt build runner
-> dbt staging
-> erc20_transfers
-> tether_treasury_flow
-> tether_treasury_flow_quality_summary
```

## 실행 증거 같이 읽는 순서

코드를 읽은 뒤 아래 증거를 같은 순서로 확인합니다.

| 확인 대상 | 증거 위치 | 판정 |
|---|---|---|
| Python/pytest/dbt fixture 검증 | `docs/05_validation_evidence.md` | VERIFIED |
| Airflow UI run history | `data/imgs/`, `docs/05_validation_evidence.md` | PARTIALLY VERIFIED |
| Airflow task log와 storage E2E | `airflow/logs/`, `data/delta/ethereum_logs_v2`, `data/analytics/ethereum_analytics_v2.duckdb` | VERIFIED |
| fixture ETL replay와 Delta idempotency | `src/notebooks/03_fixture_etl_replay_idempotency_validation.ipynb` | VERIFIED |
| accumulated local Delta/DuckDB freshness | `src/notebooks/04_accumulated_pipeline_data_freshness_validation.ipynb` | PARTIALLY VERIFIED |
| latest code/schema 기준 real RPC 1시간 E2E | `docs/09_requirement_traceability_matrix.md` | VERIFIED |

## 1. `src/cryptoquant_pipeline/rpc_client.py`

- 무엇을 하는가: Ethereum JSON-RPC request를 보내고 provider 오류를 분류합니다.
- 없으면 무엇이 깨지는가: block 조회와 `eth_getLogs` 호출이 모두 불가능합니다.
- 입력은 어디서 오는가: Airflow task가 만든 method/params와 `ETH_RPC_URL`.
- 출력은 어디로 가는가: block payload는 `block_range.py`, raw logs는 `log_collector.py`.
- 가장 중요한 함수: `eth_get_logs`, `_request`.
- 대표 입력값: `from_block=100`, `to_block=109`, `address=USDT`.
- 대표 출력값: raw log object list.
- 가능한 실패: timeout, 429, 5xx, too many results, malformed JSON.
- 먼저 볼 테스트: `tests/test_rpc_retry.py`의 fake provider.
- 설계 설명 핵심: RPC transport와 오류 분류를 분리해 bounded retry와 range split 판단 가능.

## 2. `src/cryptoquant_pipeline/block_range.py`

- 무엇을 하는가: UTC 시간 구간을 Ethereum block number 범위로 바꿈.
- 없으면 무엇이 깨지는가: Airflow hourly interval을 `eth_getLogs`에 넣을 수 없음.
- 입력은 어디서 오는가: Airflow `data_interval_start`, `data_interval_end`.
- 출력은 어디로 가는가: `log_collector.collect_raw_logs`.
- 가장 중요한 함수: `resolve_interval_block_range`, `find_first_block_at_or_after`.
- 대표 입력값: `2024-01-01T00:00:00Z` ~ `2024-01-01T01:00:00Z`.
- 대표 출력값: `start_block=100`, `end_block=299`.
- 가능한 실패: timezone 없음, interval 역전, block timestamp 누락.
- 먼저 볼 테스트: `tests/test_block_range.py`.
- 설계 설명 핵심: `eth_getLogs`는 시간 조회가 없어 block timestamp binary search로 range 계산.

## 3. `src/cryptoquant_pipeline/log_collector.py`

- 무엇을 하는가: block range를 provider 제한에 맞춰 나누고 `eth_getLogs`를 호출합니다.
- 없으면 무엇이 깨지는가: 큰 range가 provider limit에 걸리면 수집이 실패합니다.
- 입력은 어디서 오는가: `block_range.py`의 start/end block.
- 출력은 어디로 가는가: 이후 `log_normalizer.py`.
- 가장 중요한 함수: `collect_raw_logs`.
- 대표 입력값: `[1, 10]`, USDT contract address.
- 대표 출력값: dedup된 raw log list와 failed subranges.
- 가능한 실패: 단일 block까지 split했는데도 provider가 실패.
- 먼저 볼 테스트: `tests/test_rpc_retry.py`.
- 설계 설명 핵심: too-many-results와 timeout은 재귀 split 대상이며, 단일 block 실패는 숨기지 않습니다.

## 4. `src/cryptoquant_pipeline/log_normalizer.py`

- 무엇을 하는가: RPC raw log를 Delta raw schema row로 변환합니다.
- 없으면 무엇이 깨지는가: hex quantity, timestamp, topic null 정책이 Delta/dbt와 맞지 않습니다.
- 입력은 어디서 오는가: `raw_logs.json`과 block timestamp 조회 결과.
- 출력은 어디로 가는가: `delta_writer.write_ethereum_logs_insert_only`.
- 가장 중요한 함수: `normalize_logs`, `topic_to_address`, `decode_uint256_decimal`.
- 대표 입력값: `blockNumber="0x64"`, `topic0=Transfer signature`.
- 대표 출력값: `block_number=100`, lowercase contract address, `block_date_utc`.
- 가능한 실패: malformed hex, 필수 field 누락, block timestamp 누락.
- 먼저 볼 테스트: `tests/test_log_normalizer.py`.
- 설계 설명 핵심: raw layer는 data hex를 해석하지 않고 보존해 재처리 가능성 유지.

## 5. `src/cryptoquant_pipeline/delta_writer.py`

- 무엇을 하는가: normalized rows를 Delta Lake raw table에 신규 row만 append합니다.
- 없으면 무엇이 깨지는가: retry/backfill 시 같은 log가 중복 저장될 수 있음.
- 입력은 어디서 오는가: `log_normalizer.py`.
- 출력은 어디로 가는가: Delta table `ethereum_logs`, 이후 dbt `delta_scan()`.
- 가장 중요한 함수: `write_ethereum_logs_insert_only`.
- 대표 입력값: `chain_id=1`, `transaction_hash=0xabc`, `log_index=5`.
- 대표 출력값: `inserted_row_count`, `duplicate_skipped_count`.
- 가능한 실패: Delta dependency 없음, schema mismatch, duplicate filtering 오류.
- 먼저 볼 테스트: `tests/test_delta_idempotency.py`.
- 설계 설명 핵심: raw log identity는 chain_id, transaction_hash, log_index 조합.

## 6. `src/cryptoquant_pipeline/pipeline.py`

- 무엇을 하는가: 한 Airflow interval을 RPC 수집, Delta write, dbt build로 연결합니다.
- 없으면 무엇이 깨지는가: DAG가 orchestration을 넘어 business logic을 직접 갖게 됨.
- 입력은 어디서 오는가: Airflow `data_interval_start`, `data_interval_end`.
- 출력은 어디로 가는가: Delta raw table과 dbt DuckDB 모델.
- 가장 중요한 함수: `run_interval`, `run_recent_finalized_interval`.
- 대표 입력값: UTC half-open 1시간 interval.
- 대표 출력값: `PipelineRunResult`.
- 가능한 실패: chain id mismatch, finalized 미도달, provider 실패, Delta schema mismatch, dbt 실패.
- 먼저 볼 테스트: `tests/test_pipeline_idempotency.py`.
- 설계 설명 핵심: DAG은 얇게 두고 검증 가능한 Python 경계에 로직을 둡니다.

## 7. `src/cryptoquant_pipeline/dbt_runner.py`

- 무엇을 하는가: dbt subprocess를 실행하고 실패 로그 tail에서 secret 값을 마스킹합니다.
- 없으면 무엇이 깨지는가: pipeline이 dbt selector와 환경 변수를 직접 조립해야 합니다.
- 입력은 어디서 오는가: `PipelineSettings`, Airflow logical interval.
- 출력은 어디로 가는가: `PipelineRunResult.dbt_result`, DuckDB analytics database.
- 가장 중요한 함수: `run_dbt_build`.
- 대표 입력값: `window_start`, `window_end`, `DELTA_LOGS_PATH`, `DUCKDB_PATH`.
- 대표 출력값: `{"returncode": 0, "vars": ...}`.
- 가능한 실패: dbt executable 없음, timeout, SQL/test 실패.
- 먼저 볼 테스트: `tests/test_pipeline_idempotency.py`, fixture `dbt build`.
- 설계 설명 핵심: DAG에 dbt 모델명을 하드코딩하지 않고 `tag:ethereum_hourly` selector로 graph 실행.

## 8. `dbt/models/silver/erc20_transfers.sql`

- 무엇을 하는가: raw log 중 ERC-20 Transfer event만 decoding합니다.
- 없으면 무엇이 깨지는가: Treasury flow의 입력 테이블이 없음.
- 입력은 어디서 오는가: `ref('ethereum_logs')`.
- 출력은 어디로 가는가: `ref('tether_treasury_flow')`.
- 가장 중요한 로직: `topic0` Transfer signature filter, topic1/topic2 address decoding.
- 대표 입력값: padded address topic과 uint256 data hex.
- 대표 출력값: `from_address`, `to_address`, `raw_amount_decimal_text`, `amount_usdt`.
- 가능한 실패: topic 형식 오류, 큰 uint256 decimal 변환 제한.
- 먼저 볼 테스트: `dbt/tests/erc20_transfer_integrity.sql`.
- 설계 설명 핵심: Transfer event signature와 ABI padding 규칙으로 token transfer 추출.

## 9. `dbt/models/gold/tether_treasury_flow.sql`

- 무엇을 하는가: Ethereum USDT와 Tether Treasury 주소 관련 transfer를 hourly 집계합니다.
- 없으면 무엇이 깨지는가: 최종 hourly INFLOW/OUTFLOW 집계가 없음.
- 입력은 어디서 오는가: `ref('erc20_transfers')`.
- 출력은 어디로 가는가: DuckDB table `tether_treasury_flow`.
- 가장 중요한 로직: token address filter, Treasury inflow/outflow case expression.
- 대표 입력값: USDT transfer row.
- 대표 출력값: `hour_start_utc`, `direction`, `total_amount_raw`, `total_amount_usdt`.
- 가능한 실패: USDT 외 token 혼입, decimals 오설정, amount_numeric null.
- 먼저 볼 테스트: `dbt/tests/treasury_flow_integrity.sql`.
- 설계 설명 핵심: Treasury 주소와 USDT contract 조건을 함께 적용해 token 혼입 방지.

## 10. `dbt/models/gold/tether_treasury_flow_quality_summary.sql`

- 무엇을 하는가: `tether_treasury_flow`의 Airflow/dbt window 결과를 1행 품질 요약 view로 노출합니다.
- 없으면 무엇이 깨지는가: 핵심 flow 집계는 유지되지만 Bonus의 DAG 수정 없는 dbt dependency expansion 증거가 약해짐.
- 입력은 어디서 오는가: `ref('tether_treasury_flow')`.
- 출력은 어디로 가는가: DuckDB view `tether_treasury_flow_quality_summary`.
- 가장 중요한 로직: `window_start`, `window_end` vars와 `source_interval_start_utc` 경계.
- 대표 출력값: `flow_row_count`, `transfer_count`, `total_inflow_usdt`, `total_outflow_usdt`.
- 가능한 실패: upstream flow table 미생성, window vars 불일치.
- 먼저 볼 테스트: `dbt ls --select tether_treasury_flow_quality_summary --output json`.
- 설계 설명 핵심: Airflow DAG는 모델명을 하드코딩하지 않고 `tag:ethereum_hourly` selector를 실행합니다.

## 11. `airflow/dags/ethereum_hourly_logs.py`

- 무엇을 하는가: 전체 작업 순서와 retry/backfill 경계를 정의합니다.
- 없으면 무엇이 깨지는가: 로컬 Docker Airflow에서 자동 실행할 DAG가 없음.
- 입력은 어디서 오는가: Airflow scheduler, `.env` 환경 변수.
- 출력은 어디로 가는가: Delta table, DuckDB table, Airflow logs.
- 가장 중요한 함수: `ethereum_hourly_logs`.
- 대표 입력값: hourly logical interval.
- 대표 출력값: task metadata와 산출물 파일.
- 가능한 실패: `ETH_RPC_URL` 없음, provider 실패, dbt build 실패.
- 먼저 볼 검증: Docker/Airflow `DagBag` import check.
- 설계 설명 핵심: Airflow는 orchestration만 담당. 대량 raw payload는 XCom 대신 파일 전달.

## 12. `tests/`

- 무엇을 하는가: 외부 RPC 없이 핵심 데이터 계약을 검증합니다.
- 없으면 무엇이 깨지는가: API key 없이 idempotency, boundary, decoding 안전성을 확인할 수 없음.
- 입력은 어디서 오는가: `tests/fixtures/rpc_logs.json`과 fake clients.
- 출력은 어디로 가는가: pytest 결과.
- 가장 중요한 테스트: `test_delta_writer_is_idempotent_for_same_raw_batch`.
- 대표 입력값: 중복 log가 포함된 fixture batch.
- 대표 출력값: row count 유지, duplicate key count 0.
- 가능한 실패: unique key 변경, boundary 변경, schema 변경.
- 먼저 볼 테스트: `tests/test_block_range.py` -> `tests/test_delta_idempotency.py`.
- 설계 설명 핵심: 실제 RPC key 없이도 누락/중복/정규화/적재 계약은 fixture로 검증.

## 구현 및 검증 체크리스트

- [x] 코드 읽기 순서가 현재 실행 경로와 일치합니다.
  - 근거: `src/cryptoquant_pipeline/pipeline.py`, `src/cryptoquant_pipeline/dbt_runner.py`

- [x] 새 dbt runner 책임 경계가 문서에 반영되었습니다.
  - 근거: `src/cryptoquant_pipeline/dbt_runner.py`

- [x] dbt 모델과 테스트의 핵심 검증 위치가 연결되어 있습니다.
  - 근거: `dbt/models/`, `dbt/tests/`, `tests/test_dbt_contracts.py`

- [x] 실제 외부 RPC에서 생성된 Airflow task log까지 코드 읽기 순서와 대조했습니다.
  - 근거: `airflow/logs/dag_id=ethereum_hourly_logs`의 scheduled run 반환값과 `data/delta/ethereum_logs_v2`, `data/analytics/ethereum_analytics_v2.duckdb` 산출물을 대조했습니다.
  - 한계: production-grade provider SLA와 full-history backfill은 별도 검증 대상입니다.

- [x] 요구사항 추적표 상태를 갱신했습니다.
  - 경로: `docs/09_requirement_traceability_matrix.md`
