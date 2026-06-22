# 12. Legacy Cleanup Report

> 기준일: 2026-06-22 KST
> 범위: repository 전체의 Python, Airflow, Docker, dbt, SQL, Markdown, test, 설정 파일.

## 1. 정리 범위와 원칙

정리 기준은 삭제량이 아니라 과제 요구사항 증거, 재현성, 멱등성, backfill, retry, incremental 처리, dbt 의존성 자동 반영 구조 보존이다. 삭제는 아래 조건을 만족한 항목만 확정했습니다.

- 현재 Python import, Airflow DAG, Docker Compose, dbt project, test, README/docs에서 참조되지 않습니다.
- Task 1 설계 증거 또는 Task 2 구현/검증 증거로 쓰이지 않습니다.
- backfill, retry, idempotency, reorg 제한 설명, incremental 처리, dbt selector/ref 구조에 필요하지 않습니다.
- 삭제 후 `compileall`, `pytest`, `docker compose config`, Airflow DagBag import, `dbt parse`, `dbt build`가 통과했습니다.

실제 `.env` 내용은 출력하지 않았습니다. `.env.example`은 placeholder와 local demo credential만 남겼고, 실제 RPC URL/API key는 Git 추적 대상으로 만들지 않았습니다.

## 2. DELETE 파일 목록 및 삭제 근거

git diff 기준 삭제 파일은 21개입니다.

| 파일 | 삭제 근거 |
|---|---|
| `airflow/dags/ethereum_logs_pipeline.py` | deprecated DAG shim.<br>active DAG는 `airflow/dags/ethereum_hourly_logs.py` 하나이며 DagBag import에서 `dag_ids=['ethereum_hourly_logs']` 확인 |
| `dbt/models/staging/stg_ethereum_logs.sql` | deprecated compatibility staging view. 현재 canonical staging은 `dbt/models/staging/ethereum_logs.sql`이며 downstream `ref()`가 없음 |
| `dbt/models/tests/erc20_transfer_integrity.sql` | dbt singular test 위치가 `dbt/tests/erc20_transfer_integrity.sql`로 이동됨 |
| `dbt/models/tests/treasury_flow_integrity.sql` | dbt singular test 위치가 `dbt/tests/treasury_flow_integrity.sql`로 이동됨 |
| `dbt/models/tests/unique_log_identity.sql` | dbt singular test 위치가 `dbt/tests/unique_log_identity.sql`로 이동됨 |
| `src/cryptoquant_assignment/__init__.py` | old package namespace. 현재 구현은 `src/cryptoquant_pipeline/` |
| `src/cryptoquant_assignment/common/__init__.py` | old package namespace. 현재 import/test 경로에서 사용되지 않음 |
| `src/cryptoquant_assignment/ethereum/__init__.py` | old package namespace. 현재 import/test 경로에서 사용되지 않음 |
| `src/cryptoquant_assignment/py.typed` | old package marker. 현재 package marker는 `src/cryptoquant_pipeline/py.typed`가 아니라 typed source/test 기준으로 관리 |
| `src/cryptoquant_assignment/settings.py` | old settings scaffold. 현재 config는 `src/cryptoquant_pipeline/config.py`, `provider.py` |
| `src/eth_pipeline/__init__.py` | old package namespace. 현재 실행 경로에 없음 |
| `src/eth_pipeline/block_range.py` | old block range implementation. 현재 `src/cryptoquant_pipeline/block_range.py`와 tests 사용 |
| `src/eth_pipeline/config.py` | old config implementation. 현재 `src/cryptoquant_pipeline/config.py`, `provider.py` 사용 |
| `src/eth_pipeline/delta_writer.py` | old Delta writer. 현재 `src/cryptoquant_pipeline/delta_writer.py` 사용 |
| `src/eth_pipeline/exceptions.py` | old exception namespace. 현재 `src/cryptoquant_pipeline/exceptions.py` 사용 |
| `src/eth_pipeline/log_fetcher.py` | old RPC/log fetcher. 현재 `src/cryptoquant_pipeline/log_collector.py`, `rpc_client.py` 사용 |
| `src/eth_pipeline/normalizer.py` | old normalizer. 현재 `src/cryptoquant_pipeline/log_normalizer.py` 사용 |
| `src/eth_pipeline/quality_checks.py` | old quality helper. 현재 `src/cryptoquant_pipeline/quality_checks.py` 사용 |
| `src/eth_pipeline/rpc_client.py` | old RPC client. 현재 `src/cryptoquant_pipeline/rpc_client.py` 사용 |
| `tests/test_log_fetcher.py` | old API 대상 test. 현재 coverage는 `tests/test_rpc_client.py`, `test_rpc_retry.py`, `test_collection_scope.py` |
| `tests/test_normalizer.py` | old normalizer API 대상 test. 현재 coverage는 `tests/test_log_normalizer.py`, `test_delta_writer.py` |

## 3. 삭제한 코드, SQL, 설정의 핵심 내용과 삭제 근거

- old Airflow DAG shim: active DAG가 하나로 정리되어 scheduler/import 혼선을 줄입니다. DAG 무수정 dbt expansion 검증은 active DAG와 `dbt_runner.run_dbt_build()` 기준으로 유지.
- old dbt staging/test location: `dbt/models/tests/`는 dbt convention과 현재 `dbt/tests/` 구조가 중복되므로 제거. `dbt build --select tag:ethereum_hourly`로 test coverage 유지 확인.
- unused dbt macro block: `safe_uint256_decimal_string`는 current models/tests에서 참조되지 않고 Python exact decimal text 정책과 맞지 않아 제거.
- old Python packages: `src/eth_pipeline/`, `src/cryptoquant_assignment/`는 current package와 책임이 중복되고 current tests/import에서 참조되지 않습니다.
- old API tests: 삭제된 modules를 테스트하던 파일이라 유지하면 현재 API와 충돌합니다. 동일 요구사항은 current tests에서 검증.

## 4. KEEP 파일 목록과 과제 요구사항상 유지 근거

| 유지 범위 | 유지 근거 |
|---|---|
| `README.md`, `docs/00_documentation_index.md` | 제출 진입점, 실행 방법, 문서 지도 |
| `docs/task_01_bitcoin_velocity/` | Task 1 Velocity 정의, source table, SQL/pseudocode, daily batch, reorg 설계 증거 |
| `docs/01_system_architecture.md` ~ `docs/07_submission_readiness_report.md` | Task 2 현재 구현, 검증, 제한, 제출 점검 source of truth |
| `docs/08_ai_usage_transparency_and_validation.md` | AI 활용 및 인간 검증 요약 |
| `airflow/dags/ethereum_hourly_logs.py` | active Airflow DAG. `@hourly`, `max_active_runs=1`, retry, logical interval/backfill 구조 |
| `src/cryptoquant_pipeline/` | current Python 실행 경로. block range, RPC, chunking, normalization, Delta write, dbt build orchestration |
| `dbt/dbt_project.yml`, `dbt/models/`, `dbt/tests/`, `dbt/macros/` | `ethereum_logs -> erc20_transfers -> tether_treasury_flow -> quality_summary` graph, selector/tag/ref 구조 |
| `tests/`, `tests/fixtures/` | fixture/mock 기반 멱등성, retry, block range, dbt contract 검증 |
| `scripts/create_dbt_validation_fixture.py`, `scripts/inspect_outputs.py`, `scripts/run_rpc_smoke_validation.py` | fixture 생성, 출력 점검, opt-in RPC smoke 검증 |
| `data/imgs/` | Airflow UI screenshot 실행 이력 보조 증거. generated data와 달리 문서에서 명시적으로 참조 |
| `Dockerfile`, `docker-compose.yaml`, `.devcontainer/`, `requirements*.txt`, `pyproject.toml`, `.env.example` | 재현 가능한 Docker/Python/Airflow/dbt 실행 환경 |

## 5. REVIEW 또는 LEGACY_CANDIDATE 목록

| 항목 | 분류 | 이유 |
|---|---|---|
| `src/notebooks/` | REVIEW | 번호 prefix 기준 검증 보조 노트북으로 정리함 현재 실행 source of truth는 아니지만 Python source와 로컬 데이터 최신성 점검 근거로 유지 |
| `docs/task_02_ethereum_log_pipeline/04_error_incident_change_log.md` | REVIEW | 오류 해결 기록과 legacy candidate 기록. 현재 구현 기준 문서는 아니지만 검증 이력 가치 있음 |
| `docs/task_02_ethereum_log_pipeline/05_error_debugging_timeline.md` | REVIEW | debugging timeline. `ethereum_logs_v2`, old dbt path 같은 stale term이 있으나 historical context로 보존 |
| `.env` | 제출 제외 | 실제 local config 가능성이 있어 내용 미출력/미추적 유지 |
| `.venv/`, `dbt/target/`, `data/delta/`, `data/analytics/`, `data/tmp/`, `airflow/logs/` | 제출 제외 | generated/local artifact임 삭제하지 않고 ignore 대상과 보고서 제외 항목으로 분리함 |
| `docs/task_02_ethereum_log_pipeline/*.md` | REVIEW | exploratory design. README/DOCS에서 current source of truth가 아니라고 라벨링 |

## 6. FIX 처리한 문서, 코드, 경로, 설정 목록

- `.env.example`: `ETH_RPC_URL` blank, Airflow secret placeholder, canonical Delta/DuckDB path 유지.
- `docker-compose.yaml`, `.devcontainer/docker-compose.devcontainer.yaml`, `dbt/dbt_project.yml`, `scripts/inspect_outputs.py`: canonical path를 `data/delta/ethereum_logs`, `data/analytics/ethereum_analytics.duckdb` 기준으로 정렬.
- `dbt/macros/decode_ethereum_address.sql`: unused `safe_uint256_decimal_string` macro block 제거.
- `dbt/models/silver/erc20_transfers.sql`, `dbt/models/gold/tether_treasury_flow.sql`, `dbt/models/gold/tether_treasury_flow_quality_summary.sql`, `dbt/tests/*.sql`: `-- depends_on: {{ ref(...) }}` 추가로 dbt parser graph를 명시.
- `dbt/models/schema.yml`: 신규 quality summary view와 not-null tests 반영.
- `tests/test_environment.py`, `tests/test_block_range.py`, `tests/test_delta_idempotency.py`, `tests/test_quality_checks.py`, `tests/test_rpc_client.py`: current `cryptoquant_pipeline` API 기준으로 갱신.
- `src/cryptoquant_pipeline/exceptions.py`, `quality_checks.py`: current validation helper import/API 정합성 보정.
- `README.md`, `docs/01_system_architecture.md`, `docs/02_data_contracts.md`, `docs/03_execution_guide.md`, `docs/05_validation_evidence.md`, `docs/06_code_reading_guide.md`, `docs/07_submission_readiness_report.md`, `docs/task_02_ethereum_log_pipeline/*.md`: stale path, stale dbt graph, stale validation count, legacy/current 경계 보정.
- `docs/09_requirement_traceability_matrix.md`: 요구사항별 구현/문서 위치와 검증 상태 신규 작성.
- `src/notebooks/`: stale `_task_02_04...v1~v3` 중복 notebook 삭제, active notebook 5개를 `00_`~`04_` 번호와 목적 중심 이름으로 정리.

## 7. 검증 명령과 결과

| 명령 | 결과 |
|---|---|
| `docker compose -f docker-compose.yaml -f .devcontainer/docker-compose.devcontainer.yaml config --quiet` | exit 0 |
| `docker compose -f docker-compose.yaml -f .devcontainer/docker-compose.devcontainer.yaml run --rm --no-deps workspace-dev python -m compileall src tests scripts airflow/dags` | exit 0 |
| `docker compose -f docker-compose.yaml -f .devcontainer/docker-compose.devcontainer.yaml run --rm --no-deps workspace-dev ruff check .` | `All checks passed!` |
| `docker compose -f docker-compose.yaml -f .devcontainer/docker-compose.devcontainer.yaml run --rm --no-deps workspace-dev python -m pytest -q` | `49 passed` |
| `docker compose -f docker-compose.yaml -f .devcontainer/docker-compose.devcontainer.yaml run --rm --no-deps workspace-dev python scripts/create_dbt_validation_fixture.py --root /workspace/data/tmp/dbt_validation/legacy_cleanup` | `{'inserted': 2, 'rows': 2}` |
| `dbt parse --project-dir dbt --profiles-dir dbt --no-partial-parse` in `workspace-dev` with validation env | exit 0 |
| `dbt ls --project-dir dbt --profiles-dir dbt --select tag:ethereum_hourly --output name --no-partial-parse` in `workspace-dev` | `Found 4 models, 39 data tests, 1 source, 486 macros`; 신규 `tether_treasury_flow_quality_summary` 포함 |
| `dbt ls --select tether_treasury_flow_quality_summary --output json --no-partial-parse` in `workspace-dev` | `tags=["ethereum_hourly"]`, `depends_on.nodes=["model.ethereum_analytics.tether_treasury_flow"]` |
| `dbt build --project-dir dbt --profiles-dir dbt --select tag:ethereum_hourly --vars "{window_start: 2024-01-01T00:00:00Z, window_end: 2024-01-01T01:00:00Z}" --no-partial-parse` in `workspace-dev` | `PASS=43 WARN=0 ERROR=0 SKIP=0 NO-OP=0 TOTAL=43` |
| DuckDB relation count query | `{'ethereum_logs': 2, 'erc20_transfers': 2, 'tether_treasury_flow': 1, 'tether_treasury_flow_quality_summary': 1}` |
| Airflow DagBag import with `/opt/airflow/python/bin/python` | `import_error_count=0`, `dag_ids=['ethereum_hourly_logs']`, `schedule='@hourly'`,<br>`max_active_runs=1`, `task_ids=['run_interval']` |
| stale reference scan with `rg` excluding generated/notebook paths | stale terms only in REVIEW error timeline or explicit deletion context |
| secret-like placeholder scan excluding `.env` contents | `.env.example` placeholders and documented local demo credentials only |
| `nbclient` execution of `src/notebooks/03_fixture_etl_replay_idempotency_validation.ipynb` | 실행 output 저장 완료, error가 없음 |
| custom code-cell execution of `src/notebooks/04_accumulated_pipeline_data_freshness_validation.ipynb` | `latest_v2_local`, raw `6848937`, duplicate key `0`, schema current.<br>12:00 UTC hourly gap과 DuckDB staging view 절대경로 문제로 `PARTIALLY VERIFIED` |
| `data/imgs/` screenshot manual review | Airflow UI DAG 등록, `@hourly`, success 47, failed 14, failed task instance 13건을 확인함 최신 data contract 증거는 아님 |

## 8. 검증 실패 또는 실행할 수 없는 항목과 이유

| 항목 | 상태 | 원인 | 영향 | 우회 검증 |
|---|---|---|---|---|
| Airflow scheduler/UI run history | VERIFIED | `data/imgs/` screenshot에서 success/failed run history를 확인하고 task log로 보강함 | UI screenshot 단독 row-level correctness는 아님 | Airflow task log, Delta/DuckDB 산출물 대조 |
| 최신 schema 기준 Airflow end-to-end 재실행 | PARTIALLY VERIFIED | `airflow/logs/` successful scheduled 반환값 33건과 latest direct inspection row count `6848937`을 확인함<br>2026-06-22 12:00 UTC hourly gap은 남아 있음 | production SLA, full-history backfill, 누락 interval 원인은 검증하지 않음 | task log, Delta direct inspection, DuckDB relation count, notebook 04 |
| real 1-hour historical RPC scheduled collection | PARTIALLY VERIFIED | 1시간 scheduled 수집은 확인. full-history backfill과 provider qualification manifest는 구현되지 않음 | provider plan별 historical lookup 권한 차이 가능 | block range, retry, chunking, idempotency tests로 보강 |
| reorg canonical replacement | NOT VERIFIED | 현재 구현 범위가 finality buffer와 raw `block_hash` 보존까지임 | long reorg stale canonical row replacement는 구현되지 않음 | 문서에서 design-only/future hardening으로 분리 |
| generated/local artifact cleanup | PARTIALLY VERIFIED | `.env`, `.venv`, `data/delta/`, `data/analytics/`, `data/tmp/`, `dbt/target/`는 삭제하지 않고 제출 제외로 분리 | 로컬 디스크에는 남을 수 있음 | `.gitignore`, report, README에서 제출 제외 명시 |

## 9. 발견했지만 삭제하지 않은 위험 요소

- `.env`가 local ignored file로 존재합니다. 비밀값 유출 방지를 위해 내용은 읽거나 출력하지 않았고, Git 추적 대상으로 만들지 않았습니다.
- `src/notebooks/04_accumulated_pipeline_data_freshness_validation.ipynb`는 최신 v2 raw Delta의 schema와 duplicate key는 통과하지만 2026-06-22 12:00 UTC hourly gap과 DuckDB staging view 절대경로 문제를 `PARTIALLY VERIFIED`로 판정합니다. 이 항목은 로컬 accumulated data freshness 리스크이며, fixture 검증 성공과 별개로 남겨야 합니다.
- `data/imgs/`는 Airflow UI screenshot 증거로 보존합니다. success run history는 task log와 Delta/DuckDB 산출물 대조 후에만 외부 RPC scheduled 수집 이력으로 해석합니다.
- `data/delta/ethereum_logs_v2`와 `data/analytics/ethereum_analytics_v2.duckdb`는 Airflow scheduled 실행 증거로 확인했지만 generated/local artifact이므로 제출 source file로 보지 않습니다.
- error timeline 문서는 과거 command/path를 포함할 수 있습니다. 현재 source of truth는 README와 `docs/01`~`docs/08`로 제한했습니다.
- `data/delta/`, `data/analytics/`, `data/tmp/`, `dbt/target/`, `.venv/`는 generated artifact이므로 삭제하지 않았습니다. 제출물에 포함하면 stale output 오해 위험이 있습니다.
- Airflow local default credential과 port mapping은 demo 편의 설정이다. 운영 보안 통제로 주장하지 않습니다.
- Tether Treasury address label provenance/version registry는 구현하지 않았습니다. external assumption으로 문서화했습니다.

## 10. 과제 요구사항 추적표 링크

- [Requirement Traceability Matrix](./09_requirement_traceability_matrix.md)

## 11. 최종 Repository 구조 트리

```text
.
├── README.md
├── Dockerfile
├── docker-compose.yaml
├── requirements.txt
├── requirements-runtime.txt
├── pyproject.toml
├── .env.example
├── .devcontainer/
│   ├── devcontainer.json
│   └── docker-compose.devcontainer.yaml
├── airflow/
│   └── dags/
│       └── ethereum_hourly_logs.py
├── dbt/
│   ├── dbt_project.yml
│   ├── profiles.yml.example
│   ├── macros/
│   ├── models/
│   │   ├── sources/ethereum_logs.yml
│   │   ├── staging/ethereum_logs.sql
│   │   ├── silver/erc20_transfers.sql
│   │   └── gold/
│   │       ├── tether_treasury_flow.sql
│   │       └── tether_treasury_flow_quality_summary.sql
│   └── tests/
├── docs/
│   ├── 00_documentation_index.md
│   ├── 01_system_architecture.md
│   ├── 02_data_contracts.md
│   ├── 03_execution_guide.md
│   ├── 04_failure_retry_backfill_strategy.md
│   ├── 05_validation_evidence.md
│   ├── 06_code_reading_guide.md
│   ├── 07_submission_readiness_report.md
│   ├── 08_ai_usage_transparency_and_validation.md
│   ├── 09_requirement_traceability_matrix.md
│   ├── 10_refactoring_report.md
│   ├── 11_documentation_consistency_report.md
│   ├── 12_legacy_cleanup_report.md
│   ├── task_01_bitcoin_velocity/
│   │   ├── 00_task_01_index.md
│   │   ├── 01_task_01_scope_and_design_direction.md
│   │   ├── 02_velocity_metric_definition.md
│   │   ├── 03_velocity_data_contract_and_calculation.md
│   │   ├── 04_velocity_daily_batch_pipeline.md
│   │   └── 05_velocity_quality_reorg_limitations.md
│   └── task_02_ethereum_log_pipeline/
│       ├── 00_task_02_index.md
│       ├── 01_ethereum_log_pipeline_design.md
│       ├── 02_delta_lake_ingestion_design.md
│       ├── 03_dbt_modeling_design.md
│       ├── 04_error_incident_change_log.md
│       └── 05_error_debugging_timeline.md
├── scripts/
├── src/
│   └── cryptoquant_pipeline/
└── tests/
```

## 12. git diff 요약

이 보고서는 커밋 전 git diff 산정 기준으로 아래 변경 범위를 기록합니다.

```text
삭제 파일: 21
수정 파일: 30
주요 신규 파일/디렉터리:
- airflow/dags/ethereum_hourly_logs.py
- src/cryptoquant_pipeline/
- dbt/models/staging/ethereum_logs.sql
- dbt/models/sources/ethereum_logs.yml
- dbt/tests/
- dbt/models/gold/tether_treasury_flow_quality_summary.sql
- tests/test_chunking.py
- tests/test_collection_scope.py
- tests/test_dbt_contracts.py
- tests/test_delta_writer.py
- tests/test_log_normalizer.py
- tests/test_pipeline_idempotency.py
- tests/test_provider_config.py
- tests/test_rpc_retry.py
- docs/09_requirement_traceability_matrix.md
- docs/12_legacy_cleanup_report.md
```

`git diff --stat` 요약: tracked files 기준 51 files changed, 1525 insertions, 4410 deletions. 신규 untracked source/test/dbt files는 stat에 포함되지 않을 수 있습니다.
