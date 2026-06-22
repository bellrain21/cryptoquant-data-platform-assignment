# 문서 목차(Document Table of Contents)

> 이 디렉터리는 CryptoQuant 데이터 플랫폼 사전 과제의 상세 설계와 구현 근거를 관리합니다.
> 저장소 최상단 `README.md`는 저장소 진입점, 이 문서는 전체 문서 지도, 각 과제 하위 디렉터리의 `00_task_XX_index.md`는 과제별 진입점입니다.

## 문서 탐색 구조(Document Navigation)

```text
docs/
├── 00_documentation_index.md
├── 01_system_architecture.md
├── 02_data_contracts.md
├── 03_execution_guide.md
├── 04_failure_retry_backfill_strategy.md
├── 05_validation_evidence.md
├── 06_code_reading_guide.md
├── 07_submission_readiness_report.md
├── 08_ai_usage_transparency_and_validation.md
├── 09_requirement_traceability_matrix.md
├── 10_refactoring_report.md
├── 11_documentation_consistency_report.md
├── 12_legacy_cleanup_report.md
├── 13_evidence_snapshot_ledger.md
├── task_01_bitcoin_velocity/
│   ├── 00_task_01_index.md
│   ├── 01_task_01_scope_and_design_direction.md
│   ├── 02_velocity_metric_definition.md
│   ├── 03_velocity_data_contract_and_calculation.md
│   ├── 04_velocity_daily_batch_pipeline.md
│   └── 05_velocity_quality_reorg_limitations.md
└── task_02_ethereum_log_pipeline/
    ├── 00_task_02_index.md
    ├── 01_ethereum_log_pipeline_design.md
    ├── 02_delta_lake_ingestion_design.md
    ├── 03_dbt_modeling_design.md
    ├── 04_error_incident_change_log.md
    └── 05_error_debugging_timeline.md
```

## 과제 1. Bitcoin Velocity(비트코인 회전율) 지표 파이프라인 설계

| 순서 | 문서 | 범위 | 상태 |
|---:|---|---|---|
| 0 | [00_task_01_index.md](./task_01_bitcoin_velocity/00_task_01_index.md) | 전체 목차, 문서 읽는 순서, 지표 계약 요약 | 설계 문서 정리 완료 |
| 1 | [01_task_01_scope_and_design_direction.md](./task_01_bitcoin_velocity/01_task_01_scope_and_design_direction.md) | 과제 목적, 범위, 제품 참조와 과제 지표 분리, 설계 원칙 | 설계 문서 정리 완료 |
| 2 | [02_velocity_metric_definition.md](./task_01_bitcoin_velocity/02_velocity_metric_definition.md) | Velocity, 이동량, 공급량, 장기 비활성 UTXO, 해석 범위 | 설계 문서 정리 완료 |
| 3 | [03_velocity_data_contract_and_calculation.md](./task_01_bitcoin_velocity/03_velocity_data_contract_and_calculation.md) | 원천 필드, 파생 필드, 계산식, SQL 또는 의사코드, 더미 출력, 결과 테이블 | 설계 문서 정리 완료 |
| 4 | [04_velocity_daily_batch_pipeline.md](./task_01_bitcoin_velocity/04_velocity_daily_batch_pipeline.md) | Airflow, Spark SQL, Delta Lake, 품질 검증, 멱등성, Backfill(과거 구간 재처리) | 설계 문서 정리 완료 |
| 5 | [05_velocity_quality_reorg_limitations.md](./task_01_bitcoin_velocity/05_velocity_quality_reorg_limitations.md) | Reorg(체인 재편성), 재계산, 한계점, 확장 방향 | 설계 문서 정리 완료 |

## 과제 2. Ethereum Log Ingestion(이더리움 로그 수집) 파이프라인 구현

현재 구현 기준 문서는 아래 번호 문서가 우선입니다.

| 순서 | 문서 | 범위 | 상태 |
|---:|---|---|---|
| 1 | [01_system_architecture.md](./01_system_architecture.md) | Airflow, Python, Delta, dbt, DuckDB 책임 경계 | 구현 기준 작성 |
| 2 | [02_data_contracts.md](./02_data_contracts.md) | raw schema, key, partition, incremental rule | 구현 기준 작성 |
| 3 | [03_execution_guide.md](./03_execution_guide.md) | PowerShell 실행 순서 | 구현 기준 작성 |
| 4 | [04_failure_retry_backfill_strategy.md](./04_failure_retry_backfill_strategy.md) | RPC 실패, retry, split, backfill, replay | 구현 기준 작성 |
| 5 | [05_validation_evidence.md](./05_validation_evidence.md) | 실제 실행한 명령과 실패/수정 기록 | 구현 기준 작성 |
| 6 | [06_code_reading_guide.md](./06_code_reading_guide.md) | 코드 읽기 순서와 파일별 핵심 질문 | 구현 기준 작성 |
| 7 | [07_submission_readiness_report.md](./07_submission_readiness_report.md) | 제출 전 인벤토리, Task 1 설명성, Task 2 무결성 점검, 보안/운영 리스크 | 제출 준비 점검 |
| 8 | [08_ai_usage_transparency_and_validation.md](./08_ai_usage_transparency_and_validation.md) | AI 활용 범위, 사용자 판단, 대표 프롬프트 원문형 요약, 검증 방식 | 제출 투명성 문서 |
| 9 | [09_requirement_traceability_matrix.md](./09_requirement_traceability_matrix.md) | 공통 안내, Task 1, Task 2 요구사항별 구현/문서 위치와 검증 상태 | 요구사항 추적 |
| 10 | [10_refactoring_report.md](./10_refactoring_report.md) | Python/dbt SQL 리팩토링 범위, 검증 결과, 남은 부채 | 리팩토링 보고 |
| 11 | [11_documentation_consistency_report.md](./11_documentation_consistency_report.md) | 코드·SQL·Markdown 불일치 수정 결과와 링크/체크리스트 상태 | 문서 정합성 보고 |
| 12 | [12_legacy_cleanup_report.md](./12_legacy_cleanup_report.md) | 레거시 삭제/유지/보류/FIX 근거, 검증 결과, diff 요약 | 레거시 정리 보고 |
| 13 | [13_evidence_snapshot_ledger.md](./13_evidence_snapshot_ledger.md) | 실행 증거의 관측 시점, 우선순위, 누적 수치 해석 경계 | 증거 해석 기준 |

기존 `task_02_ethereum_log_pipeline/` 문서는 Reference / exploratory design — not the current implementation source
of truth. Bronze/Silver canonical, token metadata dimension, 별도 netflow 모델 같은 내용은 현재 실행 구현과 다를 수 있습니다.
README와 현재 구현 기준 문서가 제출·실행 기준입니다.

| 순서 | 문서 | 범위 | 상태 |
|---:|---|---|---|
| 0 | [00_task_02_index.md](./task_02_ethereum_log_pipeline/00_task_02_index.md) | 전체 목차, 구현 전 후보 계약 | 레거시 설계 메모이며, 현재 실행 기준은 아님 |
| 1 | [01_ethereum_log_pipeline_design.md](./task_02_ethereum_log_pipeline/01_ethereum_log_pipeline_design.md) | RPC 수집 범위, Block Range(블록 범위) 계산, Airflow DAG, Retry(재시도), Backfill, Reorg state | 레거시 설계 메모이며, 현재 실행 기준은 아님 |
| 2 | [02_delta_lake_ingestion_design.md](./task_02_ethereum_log_pipeline/02_delta_lake_ingestion_design.md) | observation/canonical 스키마, 증분 적재, 키, 멱등성, 품질 규칙 | 레거시 설계 메모이며, 현재 실행 기준은 아님 |
| 3 | [03_dbt_modeling_design.md](./task_02_ethereum_log_pipeline/03_dbt_modeling_design.md) | ERC-20 Transfer, `tether_treasury_flow`, netflow, Incremental Model, dbt Test | 레거시 설계 메모이며, 현재 실행 기준은 아님 |
| 4 | [04_error_incident_change_log.md](./task_02_ethereum_log_pipeline/04_error_incident_change_log.md) | 구현 중 오류, 원인, 변경 기록 | 검증 이력 |
| 5 | [05_error_debugging_timeline.md](./task_02_ethereum_log_pipeline/05_error_debugging_timeline.md) | 디버깅 타임라인과 과거 경로 기록 | 검증 이력 |

## Notebook 검증 보조 자료

`src/notebooks/`는 제출 실행 경로를 대체하지 않는 검증 보조 자료입니다. 03번과 04번은 실행 output을 저장해 현재 Python source code, fixture 흐름,
로컬 canonical data 상태를 점검한 근거로 사용합니다. 실행 output의 관측 시점과 누적 수치 해석은
[13_evidence_snapshot_ledger.md](./13_evidence_snapshot_ledger.md)를 함께 확인합니다.

| 순서 | 파일 | 범위 | 상태 |
|---:|---|---|---|
| 0 | `src/notebooks/00_notebook_validation_index.ipynb` | 노트북 실행 순서와 외부 RPC 검증 경계 | 안내 문서 |
| 1 | `src/notebooks/01_rpc_provider_connection_smoke_test.ipynb` | provider 연결 smoke | `ETH_RPC_URL` 없으면 BLOCKED |
| 2 | `src/notebooks/02_eth_getlogs_transfer_sample_validation.ipynb` | `eth_getLogs` Transfer sample 확인 | 외부 RPC 실호출은 실행하지 않음 |
| 3 | `src/notebooks/03_fixture_etl_replay_idempotency_validation.ipynb` | fixture ETL, ERC-20 decode, Delta 재실행 멱등성 | 실행 완료 |
| 4 | `src/notebooks/04_accumulated_pipeline_data_freshness_validation.ipynb` | Delta/DuckDB 후보 인벤토리, 최신 v2 pair DB 추출 DataFrame, 시간대별 적재 추이, freshness, hourly gap 확인 | 실행 완료, PARTIALLY VERIFIED |

## Airflow UI Screenshot 증거

`data/imgs/`는 Airflow UI에서 관측한 실행 이력 screenshot입니다. 이 이미지는 DAG 등록과 run history를 보여주는 보조 증거이며, 최신 raw Delta
schema나 row-level data correctness를 단독으로 증명하지 않습니다.

| 파일 | 관측 내용 | 현재 판정 |
|---|---|---|
| `data/imgs/task_02_01_image.png` | DAG `ethereum_hourly_logs`, `@hourly`, success 47, failed 14 | PARTIALLY VERIFIED |
| `data/imgs/task_02_02_image.png` | DAG grid의 displayed runs 61, success 47, failed 14 | PARTIALLY VERIFIED |
| `data/imgs/task_02_03_image.png` | failed `run_interval` task instance 13건 | PARTIALLY VERIFIED |
| `data/imgs/task_02_04_image.png` | success DAG run 47건 | PARTIALLY VERIFIED |

## 공통 문서(Common Documentation)

| 문서 | 범위 | 상태 |
|---|---|---|
| [08_ai_usage_transparency_and_validation.md](./08_ai_usage_transparency_and_validation.md) | AI 활용 범위, 사용자 판단, 대표 프롬프트 원문형 요약, 검증 방식 | 제출 투명성 문서 |
| [09_requirement_traceability_matrix.md](./09_requirement_traceability_matrix.md) | 과제 요구사항별 추적표 | 검증 상태 기록 |
| [10_refactoring_report.md](./10_refactoring_report.md) | 이번 리팩토링 범위와 검증 결과 | 검증 상태 기록 |
| [11_documentation_consistency_report.md](./11_documentation_consistency_report.md) | 문서-코드 정합성 점검 결과 | 검증 상태 기록 |
| [12_legacy_cleanup_report.md](./12_legacy_cleanup_report.md) | 레거시 정리 범위, 삭제 근거, 검증 결과 | 검증 상태 기록 |
| [13_evidence_snapshot_ledger.md](./13_evidence_snapshot_ledger.md) | 실행 증거의 관측 시점과 해석 우선순위 | 증거 해석 기준 |

## 문서 작성 규칙(Document Convention)

- 원천 사실(Source Fact), 정책 결정(Policy Decision), 구현 가정(Implementation Assumption)을 구분합니다.
- 공개 제품 정의(Product Reference)와 과제 전용 정의(Assignment-specific Definition)를 같은 계산값으로 주장하지 않습니다.
- 완료되지 않은 기능과 실행하지 않은 테스트는 완료로 표기하지 않습니다.
- 외부 문서에 없는 세부 구현은 사실이 아니라 설계 선택으로 명시합니다.
- 링크 대상 파일은 이 문서 구조에 실제 존재하는 파일만 사용합니다.
- 주요 기술·도메인 용어는 첫 등장에만 `English(한글)` 병기 후 일관된 용어를 사용합니다.
- 실행 증거의 누적 수치는 관측 시점이 다른 historical snapshot일 수 있으므로, 수치만으로 현재 상태 또는 모순 여부를 판단하지 않습니다.