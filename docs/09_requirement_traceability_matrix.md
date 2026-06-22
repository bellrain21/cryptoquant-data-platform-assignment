# 09. Requirement Traceability Matrix

> 기준일: 2026-06-22 KST
> 목적: CryptoQuant Data Platform Engineer 사전과제 요구사항을 실제 코드, SQL, 문서, 검증 결과와 연결합니다.

과제 PDF의 직접 요구사항, 공통 제출 요구사항, 구현을 성립시키는 최소 파생 불변식을 구분해 이 matrix를 작성했습니다. 각 항목은 실제 코드, SQL, 문서, 테스트, Airflow 로그 증거와 연결합니다.

## 상태와 출처 기준

| 구분 | 의미 |
|---|---|
| `ASSIGNMENT_DIRECT` | 과제 2 직접 요구사항 또는 공통 제출 요구사항입니다. |
| `DERIVED_CORE` | 직접 요구를 성립시키는 최소 파생 불변식입니다. |
| `RELEASE` | 제출 재현성, 보안, 문서, Docker 실행 경계입니다. |
| `BONUS` | 신규 dbt 모델 자동 반영 등 가산점 성격입니다. |
| `OPTIONAL` | 레거시 정리, 보조 노트북, 내부 리팩토링 보고입니다. |

| 상태 | 판단 기준 |
|---|---|
| `VERIFIED` | 코드 또는 문서가 존재하고, 테스트·정적 검증·실행 결과 중 하나 이상으로 현재 경로를 확인했습니다. |
| `PARTIALLY VERIFIED` | 구현 또는 설계는 존재하지만 production 운영 조건, migration, 일부 edge case 검증이 부족합니다. |
| `NOT VERIFIED` | 문서 또는 설계 언급은 있으나 구현 또는 실행 검증 근거가 부족합니다. |
| `BLOCKED` | 외부 credential, provider 권한, 비용, 운영 영향 때문에 해당 범위를 실행하거나 대조하지 못했습니다. |

## Readiness Layers

| 계층 | Origin | 상태 | 근거 | 한계 또는 리스크 |
|---|---|---|---|---|
| CORE FUNCTIONAL READY | ASSIGNMENT_DIRECT + DERIVED_CORE | VERIFIED | Airflow, Python 수집, Delta writer, dbt 필수 모델, pytest/dbt/Airflow log evidence가 연결되어 있습니다. | canonical reorg replacement는 구현하지 않았습니다. |
| SUBMISSION RELEASE READY | RELEASE | PARTIALLY VERIFIED | README, 실행 가이드, validation evidence, AI 사용 요약, secret hygiene가 존재합니다. | 최종 main 커밋과 remote 반영 여부는 Git metadata로 확인해야 합니다. Collaborator 초대는 사용자 확인 기준으로 반영했습니다. |
| BONUS READY | BONUS | VERIFIED | `dbt ls`와 `dbt build`에서 신규 quality summary model이 DAG 수정 없이 `tag:ethereum_hourly` graph에 포함됨을 확인했습니다. | Airflow dynamic task mapping은 구현하지 않았습니다. |
| LEGACY CLEANUP | OPTIONAL | PARTIALLY VERIFIED | canonical path와 legacy path를 분리했습니다. | legacy cleanup은 제출 필수 기능이 아니며, 남은 historical reference는 source of truth가 아닙니다. |

## Common Submission Requirements

| Origin | 요구사항 | 관련 코드 또는 문서 경로 | 구현 요약 | 검증 방법 | 상태 | 한계 또는 리스크 |
|---|---|---|---|---|---|---|
| ASSIGNMENT_DIRECT | README 실행 방법 | `README.md`, `docs/03_execution_guide.md` | Docker, Airflow, dbt, fixture 실행 명령을 README와 실행 가이드에 분리했습니다. | `docker compose config --quiet`, Markdown local link/path scan, Airflow log evidence | VERIFIED | 실제 secret 값은 문서화하지 않습니다. |
| ASSIGNMENT_DIRECT | 설계 결정과 근거 | `README.md`, `docs/01_system_architecture.md`, `docs/02_data_contracts.md` | logical interval, natural key, Delta idempotency, dbt incremental grain, reorg 한계를 문서화했습니다. | 문서-코드 경로 대조, stale reference scan | VERIFIED | 운영 hardening은 future work입니다. |
| ASSIGNMENT_DIRECT | AI 사용 목적과 인간 검증 방식 | `README.md`, `docs/08_ai_usage_transparency_and_validation.md` | AI 활용 범위, 사용자 판단, 대표 프롬프트 원문형 요약, 검증 방식을 분리했습니다. | 문서 링크와 README 접근성 확인 | VERIFIED | 전체 대화 로그가 아니라 평가에 필요한 대표 프롬프트 5개만 짧게 정리했습니다. |
| ASSIGNMENT_DIRECT | 미해결 항목과 시도한 접근 방식 | `README.md`, `docs/05_validation_evidence.md`, `docs/07_submission_readiness_report.md` | provider limitation, scheduler run, canonical reorg replacement 구현되지 않은 항목을 숨기지 않았습니다. | 검증 결과 문서와 상태 라벨 대조 | VERIFIED | 상태는 새 검증 결과에 따라 갱신해야 합니다. |
| RELEASE | secret 미노출 | `.gitignore`, `.env.example`, `README.md` | `.env`, `.env.*`, local logs/data/cache를 Git 제외 대상으로 유지합니다. | secret-like scan, `.gitignore` 확인 | VERIFIED | 로컬 shell history와 외부 시스템은 검사 범위 밖입니다. |
| RELEASE | Private GitHub 제출 및 Collaborator 초대 안내 | `README.md`, `docs/07_submission_readiness_report.md` | 제출 전 체크리스트에 repository 반영과 collaborator 초대를 남겼습니다. | `git remote -v`, current branch/commit 확인, README 체크리스트 상태 대조, 사용자 초대 완료 확인 | PARTIALLY VERIFIED | 최신 GitHub 반영은 final main commit과 remote push 확인이 필요합니다. Collaborator 초대는 repository 내부 파일로 재검증할 수 없어 사용자 확인을 근거로 기록합니다. |
| ASSIGNMENT_DIRECT | 과제 PDF 직접 요구사항 반영 | `README.md`, `docs/09_requirement_traceability_matrix.md`, `docs/07_submission_readiness_report.md` | PDF의 직접 요구사항과 공통 제출 요구사항을 `ASSIGNMENT_DIRECT`로 분리하고, 파생 불변식은 `DERIVED_CORE`로 분리했습니다. | 요구사항 추적표, README 체크리스트, 구현 경로 대조 | VERIFIED | PDF 전문을 문서에 재게시하지 않고 요구사항 대응과 검증 근거만 제출 문서에 남깁니다. |

## Task 2. Ethereum Log Collection

| Origin | 요구사항 | 관련 코드 또는 문서 경로 | 구현 요약 | 검증 방법 | 상태 | 한계 또는 리스크 |
|---|---|---|---|---|---|---|
| ASSIGNMENT_DIRECT | Airflow 1시간 단위 수집 구조 | `airflow/dags/ethereum_hourly_logs.py` | DAG ID `ethereum_hourly_logs`, `schedule='@hourly'`, `max_active_runs=1`, task ID `run_interval`을 사용합니다. | Airflow DagBag import, code inspection, Airflow task log | VERIFIED | production deployment hardening은 별도 범위입니다. |
| ASSIGNMENT_DIRECT | `eth_getLogs` 호출 구조 | `src/cryptoquant_pipeline/rpc_client.py`, `src/cryptoquant_pipeline/log_collector.py` | `Transfer` topic0 scope로 10블록 이하 chunk를 호출합니다. | `tests/test_rpc_retry.py`, `tests/test_collection_scope.py`, Airflow task log | VERIFIED | provider plan별 rate limit 여유는 별도 운영 검증 대상입니다. |
| ASSIGNMENT_DIRECT | logical date 또는 execution date 기반 backfill | `airflow/dags/ethereum_hourly_logs.py`, `docs/04_failure_retry_backfill_strategy.md` | Airflow data interval과 DAG run conf `window_start/window_end`를 같은 callable로 처리합니다. | code inspection, 문서 명령 확인 | PARTIALLY VERIFIED | 실제 대량 Airflow backfill은 비용 영향 때문에 실행하지 않았습니다. |
| ASSIGNMENT_DIRECT | 시간 구간에서 block range 자동 계산 | `src/cryptoquant_pipeline/block_range.py` | finalized head 확인 후 timestamp binary search로 `[from_block, to_block]`을 계산합니다. | `tests/test_block_range.py`, compile/import checks | VERIFIED | historical block lookup은 provider 권한에 의존합니다. |
| ASSIGNMENT_DIRECT | 수집 누락 방지 전략 | `src/cryptoquant_pipeline/log_collector.py`, `src/cryptoquant_pipeline/chunking.py` | provider limit 오류 시 chunk를 분할하고 단일 block 실패는 hard fail 처리합니다. | `tests/test_rpc_retry.py`, `tests/test_chunking.py` | VERIFIED | provider partial response semantics는 mock 기준입니다. |
| ASSIGNMENT_DIRECT | retry, retry delay, 재처리 전략 | `airflow/dags/ethereum_hourly_logs.py`, `src/cryptoquant_pipeline/rpc_client.py` | HTTP 429/5xx/timeout은 bounded retry, Airflow는 task retry를 담당합니다. | `tests/test_rpc_retry.py`, Airflow log retry evidence | VERIFIED | 비용 발생 real retry scenario를 의도적으로 반복 실행하지 않았습니다. |
| ASSIGNMENT_DIRECT | 재실행 시 중복 적재 방지 idempotency | `src/cryptoquant_pipeline/delta_writer.py` | `chain_id + transaction_hash + log_index` natural key 기준 insert-if-not-exists를 수행합니다. | `tests/test_delta_idempotency.py`, `tests/test_pipeline_idempotency.py` | VERIFIED | 동시 writer lock은 `max_active_runs=1` 전제입니다. |
| ASSIGNMENT_DIRECT | Delta Lake 적재 구조 | `src/cryptoquant_pipeline/delta_writer.py`, `docs/02_data_contracts.md` | `ethereum_logs` Delta table을 `block_date_utc` partition으로 작성합니다. | fixture 생성, pytest, Delta `_delta_log` metadata 확인 | VERIFIED | local filesystem Delta 기준입니다. |
| ASSIGNMENT_DIRECT | Delta incremental append 또는 merge 기반 전략 | `src/cryptoquant_pipeline/delta_writer.py` | raw Delta는 insert-if-not-exists append입니다. 기존 key는 skip합니다. | `tests/test_delta_writer.py`, `tests/test_delta_idempotency.py` | VERIFIED | canonical replacement merge는 구현하지 않았습니다. |
| ASSIGNMENT_DIRECT | schema, partition, nullable, 타입 선택 근거 | `src/cryptoquant_pipeline/delta_writer.py`, `docs/02_data_contracts.md` | `ethereum_logs_schema()`와 data contract 문서에 컬럼 타입과 nullable 정책을 연결했습니다. | schema unit test, 문서-코드 대조 | VERIFIED | schema drift는 fail-closed입니다. |
| ASSIGNMENT_DIRECT | `ethereum_logs` source/staging | `dbt/models/staging/ethereum_logs.sql`, `dbt/models/sources/ethereum_logs.yml` | Delta raw table을 DuckDB `delta_scan()` view로 노출합니다. | fixture `dbt build` | VERIFIED | local Delta path가 필요합니다. |
| ASSIGNMENT_DIRECT | `erc20_transfers` incremental model | `dbt/models/silver/erc20_transfers.sql` | ERC-20 ABI shape를 만족하는 Transfer event를 `delete+insert` incremental model로 정규화합니다. | fixture `dbt build`, `dbt/tests/erc20_transfer_integrity.sql` | VERIFIED | contract interface 호출로 ERC-20 표준 준수 여부는 확인하지 않습니다. |
| ASSIGNMENT_DIRECT | ERC-20 Transfer topic 및 data decode | `dbt/models/silver/erc20_transfers.sql`, `dbt/macros/decode_ethereum_address.sql` | `topic0`, `topic1`, `topic2`, `topic3`, `data_uint256_decode_status`로 ABI shape를 판별합니다. | `tests/test_log_normalizer.py`, dbt singular tests | VERIFIED | ERC-721과 signature 공유 가능성을 topic3/data shape로만 배제합니다. |
| ASSIGNMENT_DIRECT | `tether_treasury_flow` incremental model | `dbt/models/gold/tether_treasury_flow.sql` | configured USDT contract와 Treasury address를 기준으로 hour/direction grain을 집계합니다. | fixture `dbt build`, `dbt/tests/treasury_flow_integrity.sql` | VERIFIED | address label은 외부 가정입니다. |
| ASSIGNMENT_DIRECT | Tether Treasury 주소 기준 inbound/outbound 집계 | `dbt/dbt_project.yml`, `dbt/models/gold/tether_treasury_flow.sql` | `0x5754284f345afc66a98fbb0a0afe71e0f007b949`가 `to_address`이면 `INFLOW`, `from_address`이면 `OUTFLOW`입니다. | fixture relation count, dbt tests | VERIFIED | self-transfer는 제외합니다. |
| DERIVED_CORE | SQL `SELECT *` 금지 | `dbt/models/`, `dbt/tests/`, `tests/test_dbt_contracts.py` | model/test projection을 explicit column list로 교정했습니다. | `tests/test_dbt_contracts.py::test_dbt_models_and_tests_do_not_use_select_star` | VERIFIED | `dbt/target` 생성물은 검사 대상이 아닙니다. |
| DERIVED_CORE | Reorg 최소 대응 | `src/cryptoquant_pipeline/block_range.py`, `docs/04_failure_retry_backfill_strategy.md` | finalized head 이후 interval만 처리하고 raw `block_hash`, `removed`를 보존합니다. | unit tests, 문서 확인 | PARTIALLY VERIFIED | canonical replacement와 common ancestor reconciliation은 구현되지 않았습니다. |
| RELEASE | 실제 외부 RPC 1시간 end-to-end | `airflow/logs/dag_id=ethereum_hourly_logs`, `data/delta/ethereum_logs_v2`, `data/analytics/ethereum_analytics_v2.duckdb` | Airflow scheduled run이 외부 RPC block range를 수집하고 Delta 적재와 dbt build를 수행했습니다. | successful scheduled run 반환값 33건, latest direct inspection `delta_row_count=6848937`, DuckDB `erc20_transfers=6079379` | VERIFIED | 로컬 Docker 실행 이력 기준입니다. provider SLA, full-history backfill, production monitoring은 별도 검증 대상입니다. |
| RELEASE | Airflow UI 실행 이력 screenshot | `data/imgs/task_02_01_image.png` ~ `task_02_04_image.png`, `docs/05_validation_evidence.md` | DAG 등록, `@hourly`, success/failed run history, failed task instance 목록을 확인했습니다. | 이미지 수동 판독, 문서 증거 링크 확인 | PARTIALLY VERIFIED | UI metadata screenshot은 row-level data correctness나 최신 Git working tree와의 완전한 일치를 단독으로 증명하지 않습니다. |
| BONUS | 신규 dbt 모델 추가 시 DAG 수정 없이 반영 | `src/cryptoquant_pipeline/dbt_runner.py`, `dbt/dbt_project.yml`, `dbt/models/gold/tether_treasury_flow_quality_summary.sql` | Airflow DAG는 모델명을 몰라야 하며, `dbt build --select tag:ethereum_hourly`와 `ref()` graph가 실행 대상을 결정합니다. | fixture `dbt build PASS=43`, DAG model-name 검색, Airflow task log `dbt.returncode=0` | VERIFIED | dynamic task mapping은 구현하지 않았고 selector/ref graph로 처리합니다. |

## Task 1. Bitcoin Velocity

| Origin | 요구사항 | 관련 코드 또는 문서 경로 | 구현 요약 | 검증 방법 | 상태 | 한계 또는 리스크 |
|---|---|---|---|---|---|---|
| ASSIGNMENT_DIRECT | Velocity = Transaction Volume / Circulating Supply 정의 | `docs/task_01_bitcoin_velocity/02_velocity_metric_definition.md`, `README.md` | 과제용 V1 지표를 `Transaction Volume / Circulating Supply` 계열로 정의하고 CryptoQuant production metric 복제 주장은 제외했습니다. | Task 1 validity scan `Velocity formula: PASS` | VERIFIED | 설계 문서 산출물이며 production metric 재현이 아닙니다. |
| ASSIGNMENT_DIRECT | `block`, `tx`, `tx_input`, `tx_output`, `utxo` 데이터 명세 | `docs/task_01_bitcoin_velocity/03_velocity_data_contract_and_calculation.md` | 원천 테이블 역할과 UTXO lifecycle 관계를 명시했습니다. | Task 1 validity scan `Raw tables: PASS` | VERIFIED | 실행 DB schema는 구현하지 않았습니다. |
| ASSIGNMENT_DIRECT | SQL 또는 의사코드, 더미 데이터, 일 단위 배치, Reorg 전략 | `docs/task_01_bitcoin_velocity/03_velocity_data_contract_and_calculation.md`, `04_velocity_daily_batch_pipeline.md`, `05_velocity_quality_reorg_limitations.md` | 계산 흐름, 더미 예시, daily batch, common ancestor 이후 재계산 전략을 문서화했습니다. | Task 1 validity scan 8개 축 PASS | VERIFIED | 실제 Bitcoin ETL 실행 검증이 아니라 문서와 의사 SQL 정합성 검증입니다. |

## Repository Integrity

| Origin | 요구사항 | 관련 코드 또는 문서 경로 | 구현 요약 | 검증 방법 | 상태 | 한계 또는 리스크 |
|---|---|---|---|---|---|---|
| RELEASE | Markdown 문서와 코드 경로 정합성 | `docs/11_documentation_consistency_report.md` | 수정한 문서와 남은 제한사항을 보고서에 기록합니다. | Markdown local link/path scan | VERIFIED | 외부 URL 실접속 검사는 수행하지 않았습니다. |
| RELEASE | Docker canonical execution boundary | `Dockerfile`, `docker-compose.yaml`, `.devcontainer/docker-compose.devcontainer.yaml`, `docs/03_execution_guide.md` | host Python과 분리된 local execution environment를 사용합니다. | `docker compose config --quiet`, Docker `pytest -q` 49 passed, fixture `dbt build PASS=43` | VERIFIED | release 전체는 remote push와 제출 권한 확인이 끝난 뒤 확정할 수 있습니다. |
| OPTIONAL | 노트북 기반 코드·데이터 흐름 검증 | `src/notebooks/03_fixture_etl_replay_idempotency_validation.ipynb`, `src/notebooks/04_accumulated_pipeline_data_freshness_validation.ipynb` | 노트북을 current Python source와 Delta/DuckDB data freshness, DB extraction, hourly gap 확인 보조 증거로 정리했습니다. | 04번 code-cell execution, notebook JSON parse, direct output inspection | PARTIALLY VERIFIED | 03번 fixture flow는 기존 실행 완료. 04번은 최신 v2 schema와 중복 key를 통과하지만 2026-06-22 12:00 UTC gap과 DuckDB staging view 절대경로 문제가 남습니다. |
| OPTIONAL | 레거시 경로 정합성 | `docs/12_legacy_cleanup_report.md` | 삭제된 구 패키지와 deprecated DAG/model 경로를 현재 source of truth와 분리했습니다. | stale reference scan | PARTIALLY VERIFIED | legacy cleanup은 제출 필수 기능이 아니며 current source of truth와 혼동되지 않으면 release blocker가 아닙니다. |
