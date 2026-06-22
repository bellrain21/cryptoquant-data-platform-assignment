# 11. Documentation Consistency Report

> 기준일: 2026-06-22 KST
> 목적: 코드, SQL, Markdown 문서, 체크리스트, 요구사항 추적표가 같은 실행 경로를 설명하는지 점검합니다.

## 수정한 Markdown 파일

| 파일 | 수정 내용 |
|---|---|
| `README.md` | 리팩토링/문서 정합성 보고서 링크, 환경변수 요약, 제출 전 체크리스트를 갱신함 |
| `docs/00_documentation_index.md` | 새 보고서 두 개를 문서 트리에 추가함 |
| `docs/01_system_architecture.md` | `dbt_runner.py`와 구현 대응표, 검증 체크리스트를 추가함 |
| `docs/02_data_contracts.md` | dbt model contract, ERC-20 컬럼 계약, `SELECT *` 금지 검증을 추가함 |
| `docs/03_execution_guide.md` | Airflow UI screenshot, task log, Delta/DuckDB 실행 증거를 읽는 방법과 production 검증 한계를 추가함 |
| `docs/04_failure_retry_backfill_strategy.md` | retry/backfill 정책과 screenshot/notebook 실행 증거의 연결 범위를 추가함 |
| `docs/06_code_reading_guide.md` | `run_dbt_build()` 위치와 실행 증거 같이 읽는 순서를 추가함 |
| `docs/07_submission_readiness_report.md` | screenshot, notebook, canonical inspect output을 제출 준비 검증표에 반영함 |
| `docs/08_ai_usage_transparency_and_validation.md` | AI 활용 검증 방식에 screenshot, Airflow task log, Delta/DuckDB, notebook 판독 증거를 추가함 |
| `docs/09_requirement_traceability_matrix.md` | `origin` 열과 readiness layer를 추가하고 direct/core/release/bonus/optional 요구를 분리함 |
| `docs/10_refactoring_report.md` | 이번 리팩토링 범위, screenshot/notebook 검증, 남은 부채를 기록함 |
| `docs/11_documentation_consistency_report.md` | 이 문서임 |
| `docs/12_legacy_cleanup_report.md` | `src/notebooks/`의 현재 역할과 04번 schema mismatch 판정을 반영함 |
| `docs/02_blockchain_concepts_guide.md` | 개인 학습·개념 설명 성격이므로 제출 범위에서 제거함 |
| `docs/14_feynman_concept_map.md` | 파인만식 개인 학습 자료 성격이므로 제출 범위에서 제거함 |
| `docs/task_01_bitcoin_velocity/00_task_01_index.md` | 과제 1 설계 타당성 스캔 결과와 실행 검증 한계를 추가함 |
| `docs/task_02_ethereum_log_pipeline/00_task_02_index.md` | 현재 실행 증거 기준과 historical 문서 경계를 추가함 |
| `docs/task_02_ethereum_log_pipeline/01_ethereum_log_pipeline_design.md` | historical checklist를 현재 Airflow/log/metadata 증거 기준으로 재판정함 |
| `docs/task_02_ethereum_log_pipeline/02_delta_lake_ingestion_design.md` | Bronze/Silver 설계-only 항목과 현재 raw Delta 검증 항목을 분리함 |
| `docs/task_02_ethereum_log_pipeline/03_dbt_modeling_design.md` | dbt 구현 검증 항목과 token metadata/reorg 확장 설계 구현되지 않은 항목을 분리함 |
| `docs/task_02_ethereum_log_pipeline/04_error_incident_change_log.md` | 과거 장애 기록과 현재 제출 판정을 분리함 |
| `docs/task_02_ethereum_log_pipeline/05_error_debugging_timeline.md` | 과거 디버깅 기록과 최신 evidence summary를 분리함 |
| `docs/*.md`, `docs/task_*/*.md` | 루트 `README.md`를 제외한 Markdown 문서를 번호 prefix와 직관적 이름으로 정리함 |

## 발견한 불일치와 수정 결과

| 발견 항목 | 영향 | 수정 결과 | 상태 |
|---|---|---|---|
| `pipeline.py`가 dbt subprocess 구현까지 보유했지만 문서는 DAG/dbt 책임 분리를 강조함 | 책임 경계 설명이 코드와 느슨하게 맞았음 | `dbt_runner.py`를 추가하고 architecture/code reading guide를 갱신함 | VERIFIED |
| `PipelineSettings.max_blocks_per_log_request`가 collector 호출에 직접 보이지 않았음 | 설정값과 provider chunking 정책의 추적성이 약함 | `collect_raw_logs(..., max_blocks=...)`로 연결함 | VERIFIED |
| dbt model/test에 `SELECT *`가 남아 있었음 | SQL 품질 기준과 실패 row 추적 기준이 맞지 않았음 | explicit projection으로 교정하고 정적 테스트를 추가함 | VERIFIED |
| `docs/00_documentation_index.md`에 새 리팩토링/정합성 보고서가 없었음 | 변경 근거를 찾기 어려웠음 | 문서 트리와 공통 문서 표에 링크를 추가함 | VERIFIED |
| `docs/06_code_reading_guide.md`가 `run_dbt_build`를 `pipeline.py`의 핵심 함수로 안내함 | 새 책임 분리 후 경로가 어긋났음 | `dbt_runner.py` 섹션을 추가함 | VERIFIED |
| 요구사항 추적표가 사용자 지정 6개 열 형식과 달랐음 | 요구사항-구현-검증 추적성이 부족함 | 6개 열 형식으로 갱신함 | VERIFIED |
| 일부 문서가 번호 없는 인덱스, 오류 기록, 보고서 파일명을 사용함 | 문서 탐색 순서와 역할 파악이 느렸음 | 루트 `README.md`를 제외한 Markdown 파일을 `00_...`, `01_...` 형식으로 정리하고 링크를 갱신함 | VERIFIED |
| AI 활용 문서가 기준 문서와 레거시 문서로 중복됨 | 어느 문서를 기준으로 판단해야 하는지 혼동할 수 있었음 | 레거시 문서의 고유 내용을 `docs/08_ai_usage_transparency_and_validation.md`로 통합하고 중복 파일을 삭제함 | VERIFIED |
| `src/notebooks/`에 중복 누적 검증 파일과 stale notebook명이 남아 있었음 | 노트북이 현재 Python source와 데이터 최신성 검증 근거인지, 과거 smoke 기록인지 구분하기 어려웠음 | active notebook을 `00_`~`04_` 번호와 목적 중심 이름으로 정리하고, 03·04번 실행 output을 저장함 | PARTIALLY VERIFIED |
| README가 notebook smoke output을 현재 검증 경로에서 제외한다고만 설명함 | 03·04번 노트북의 보조 검증 가치와 현재 canonical data mismatch 판정이 문서에 드러나지 않았음 | README와 `docs/05_validation_evidence.md`에 노트북별 역할과 `PARTIALLY VERIFIED` 판정 근거를 추가함 | VERIFIED |
| `data/imgs/` Airflow screenshot이 문서 증거와 연결되지 않음 | Airflow UI 실행 이력 증거를 어느 상태로 해석해야 하는지 알기 어려웠음 | `docs/05_validation_evidence.md`, `docs/09_requirement_traceability_matrix.md`, README,<br>실행 가이드에 이미지 판독 결과를 추가하고 task log와 Delta/DuckDB 산출물 대조까지 연결함 | VERIFIED |
| legacy error timeline의 E2E 성공 표현이 현재 제출 판정처럼 보일 수 있었음 | 과거 운영 기록과 현재 최신 schema 검증 상태가 섞여 overclaim 위험이 있었음 | `docs/task_02_ethereum_log_pipeline/04`, `05`에 historical record 경계와 current evidence summary를 추가함 | PARTIALLY VERIFIED |
| historical Task 2 설계 문서의 체크리스트가 모두 미체크 상태였음 | 이미 검증된 Airflow interval, chunking, raw Delta, dbt build 항목까지 검증하지 않음처럼 보였음 | 01~03 설계 문서 체크리스트를 현재 로그·테스트·Delta/DuckDB metadata 기준으로 재판정하고, Bronze/Silver/reorg 확장 항목은 미완료 사유를 남김 | VERIFIED |
| 과제 1 문서가 설계로는 충분하지만 별도 타당성 검증 결과가 드러나지 않았음 | Velocity 설계의 요구사항 충족 여부를 문서 목차만으로 판단해야 함 | Task 1 validity scan 8개 축 PASS를 `docs/05_validation_evidence.md`,<br>`docs/task_01_bitcoin_velocity/00_task_01_index.md`, 요구사항 추적표에 연결함 | VERIFIED |
| 과제 2 직접 요구와 Docker/release/bonus/optional 요구가 같은 표에서 섞였음 | 과제 직접 요구 충족과 제출 재현성 보강을 혼동할 수 있었음 | 요구사항 추적표에 `ASSIGNMENT_DIRECT`, `DERIVED_CORE`, `RELEASE`, `BONUS`, `OPTIONAL` origin을 추가함 | VERIFIED |
| 제출 범위에 개인 학습 문서가 포함되어 있었음 | 파인만식 개념 지도와 기본 개념 가이드는 5분 평가용 제출 자료보다 개인 학습 자료에 가까웠음 | `docs/02_blockchain_concepts_guide.md`, `docs/14_feynman_concept_map.md`를 제거하고 README에서 제출 제외 원칙을 명시함 | VERIFIED |

## 수정 완료 항목

- Python/dbt 실행 책임과 문서 책임 경계를 맞췄습니다.
- dbt model/test SQL에서 `SELECT *`를 제거했습니다.
- README와 docs 목차에 리팩토링 보고서와 문서 정합성 보고서를 연결했습니다.
- 요구사항 추적표 상태를 `VERIFIED`, `PARTIALLY VERIFIED`, `NOT VERIFIED`, `BLOCKED`로만 작성했습니다.
- core docs에 구현 대응표와 체크리스트를 추가했습니다.
- `src/notebooks/`를 번호화하고 stale `_task_02_04...v1~v3` notebook을 삭제했습니다.
- `data/imgs/`의 Airflow UI screenshot을 실행 이력 보조 증거로 문서화했습니다.
- `airflow/logs/`, `data/delta/ethereum_logs_v2`, `data/analytics/ethereum_analytics_v2.duckdb`를 외부 RPC scheduled 수집 증거로 문서화했습니다.
- 과제 1 Bitcoin Velocity 설계 타당성 스캔 결과를 문서화했습니다.
- historical Task 2 체크리스트를 현재 구현 증거와 설계-only 항목으로 재분류했습니다.
- 요구사항 추적표에 origin 분류를 추가했습니다.
- 개인 학습용 Markdown 문서 2개를 제출 범위에서 제거했습니다.

## 남은 불일치 또는 구현되지 않은 항목

| 항목 | 상태 | 사유 |
|---|---|---|
| legacy `docs/task_02_ethereum_log_pipeline/`의 확장 설계와 현재 구현 차이 | PARTIALLY VERIFIED | 해당 디렉터리는 reference/exploratory design으로 라벨링되어 있으며 source of truth가 아님 |
| accumulated raw Delta freshness와 hourly continuity | PARTIALLY VERIFIED | `src/notebooks/04_accumulated_pipeline_data_freshness_validation.ipynb`가 최신 v2 pair를 선택해 schema current,<br>duplicate key 0을 확인했지만 2026-06-22 12:00 UTC hourly gap을 감지함 |
| DuckDB staging view 경로 이식성 | PARTIALLY VERIFIED | `ethereum_analytics_v2.duckdb`의 downstream materialized tables는 조회됨<br>`main.ethereum_logs` view는 `/opt/airflow/...` 절대경로에 묶여 `workspace-dev`에서 query error가 발생함 |
| production-grade provider 안정성 | NOT VERIFIED | 로컬 Docker Airflow의 여러 1시간 scheduled 수집 이력은 확인했지만 provider SLA, alerting, full-history backfill은 별도 운영 검증 대상임 |
| canonical reorg replacement 구현 문서 | NOT VERIFIED | 현재 구현하지 않았고 제한사항으로 분리함 |
| Private GitHub 최신 반영 및 Collaborator 초대 | PARTIALLY VERIFIED | local remote와 branch는 확인함 Collaborator 초대는 사용자 확인을 반영함 최신 GitHub 반영은 final main commit과 remote push 확인이 필요 |
| 과제 PDF 요구사항 반영 | VERIFIED | PDF 직접 요구사항과 공통 제출 요구사항을 요구사항 추적표의 `ASSIGNMENT_DIRECT` 항목으로 분리함 |

## Markdown 링크 검사 결과

최종 링크 검사는 로컬 Markdown 링크 대상으로 수행했습니다. 외부 URL 실접속 검사는 수행하지 않았습니다.

검사 대상 예시는 다음과 같습니다.

| 링크 대상 | 존재 여부 |
|---|---|
| `docs/10_refactoring_report.md` | 존재 |
| `docs/11_documentation_consistency_report.md` | 존재 |
| `docs/09_requirement_traceability_matrix.md` | 존재 |
| `docs/08_ai_usage_transparency_and_validation.md` | 존재 |
| `src/cryptoquant_pipeline/dbt_runner.py` | 존재 |
| `dbt/models/silver/erc20_transfers.sql` | 존재 |
| `dbt/models/gold/tether_treasury_flow.sql` | 존재 |
| `src/notebooks/04_accumulated_pipeline_data_freshness_validation.ipynb` | 존재 |
| `data/imgs/task_02_01_image.png` | 존재 |

검사 결과:

```text
markdown local links ok
```

## 요구사항 추적표 갱신 결과

`docs/09_requirement_traceability_matrix.md`는 아래 열로 갱신했습니다.

| 요구사항 | 관련 코드 또는 문서 경로 | 구현 요약 | 검증 방법 | 상태 | 한계 또는 리스크 |
|---|---|---|---|---|---|

상태 라벨은 네 가지로 제한했습니다.

- `VERIFIED`
- `PARTIALLY VERIFIED`
- `NOT VERIFIED`
- `BLOCKED`

## 체크리스트 갱신 결과

| 문서 | 체크리스트 상태 |
|---|---|
| `docs/01_system_architecture.md` | 구현 대응표와 검증 체크리스트 추가 |
| `docs/02_data_contracts.md` | model contract와 검증 체크리스트 추가 |
| `docs/06_code_reading_guide.md` | 코드 읽기 순서 체크리스트 추가 |
| `docs/10_refactoring_report.md` | 리팩토링 검증 체크리스트 추가 |
| `README.md` | 제출 전 체크리스트 갱신 완료 |
| `docs/09_requirement_traceability_matrix.md` | origin 열과 readiness layer 추가 |
| `docs/task_01_bitcoin_velocity/00_task_01_index.md` | 과제 1 타당성 스캔 PASS 결과와 실행 검증 한계 추가 |
| `docs/task_02_ethereum_log_pipeline/01_ethereum_log_pipeline_design.md` | Airflow/log/chunking 검증 항목은 체크하고 canonical reorg 설계-only 항목은 미체크 사유 추가 |
| `docs/task_02_ethereum_log_pipeline/02_delta_lake_ingestion_design.md` | raw Delta 검증 항목은 체크하고 Bronze/Silver 설계-only 항목은 미체크 사유 추가 |
| `docs/task_02_ethereum_log_pipeline/03_dbt_modeling_design.md` | dbt 구현 검증 항목은 체크하고 metadata/reorg 확장 항목은 미체크 사유 추가 |
| `docs/task_02_ethereum_log_pipeline/04_error_incident_change_log.md`, `05_error_debugging_timeline.md` | historical checklist를 2026-06-22 기준으로 재판정하고, 완료·미완료·부분 검증 사유를 표로 추가 |
| `src/notebooks/00_notebook_validation_index.ipynb` | notebook 검증 순서와 검증하지 않음 경계 안내 추가 |
| `data/imgs/` | Airflow UI screenshot 증거 범위와 한계를 문서에 연결 |
| `airflow/logs/`, `data/delta/ethereum_logs_v2`, `data/analytics/ethereum_analytics_v2.duckdb` | 외부 RPC scheduled 수집, Delta 적재, dbt downstream 산출물 증거로 연결 |

## 문서상 VERIFIED이지만 실제 검증이 부족한 위험 항목

| 항목 | 위험 | 처리 |
|---|---|---|
| Airflow 1시간 DAG 구조 | DagBag import, screenshot, task log, Delta/DuckDB 산출물은 확인됐지만 production SLA는 별도임 | 구조와 로컬 Docker E2E는 `VERIFIED`, production hardening은 별도 한계로 분리함 |
| dbt graph 자동 반영 | fixture `dbt build`와 Airflow task log의 `dbt.returncode=0`은 확인됐지만 dynamic task mapping은 구현하지 않음 | selector/ref graph 방식은 `VERIFIED`, dynamic task mapping 구현되지 않은 항목은 문서화함 |
| notebook 기반 accumulated data freshness | 04번 노트북은 실행됐지만 현재 raw Delta가 최신 schema가 아니므로 완전한 data freshness 증거가 아님 | `PARTIALLY VERIFIED`로 기록하고 fixture 기반 build와 구분함 |
| Airflow UI screenshot 기반 success run history | screenshot은 success 47건을 보여주며 task log와 Delta/DuckDB 증거로 보강됨 | screenshot 단독은 `PARTIALLY VERIFIED`, task log/storage 대조 후 E2E는 `VERIFIED`로 분리함 |
| Task 1 설계 문서 | 문서 요구사항은 확인했지만 실행 pipeline은 없음 | 설계-only임을 반복 명시함 |

## 최종 문서 구조 트리

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

## 구현 및 검증 체크리스트

- [x] 수정한 Markdown 파일 목록을 기록했습니다.
  - 근거: 이 문서의 수정 파일 표

- [x] 코드·SQL·문서 불일치 발견 목록과 수정 결과를 기록했습니다.
  - 근거: 발견한 불일치와 수정 결과 표

- [x] Markdown 전체 로컬 링크 검사를 실행했습니다.
  - 결과: `markdown local links ok`

- [x] 요구사항 추적표 상태를 갱신했습니다.
  - 경로: `docs/09_requirement_traceability_matrix.md`
