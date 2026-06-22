# 10. Refactoring Report

> 기준일: 2026-06-22 KST
> 목적: 이번 리팩토링이 과제 요구사항, 멱등성, backfill, incremental 처리, 문서 정합성을 훼손하지 않았는지 기록합니다.

## 리팩토링 목표

이번 작업은 기능 확장보다 구조 개선과 검증 가능성 향상을 우선했습니다.

주요 목표는 다음과 같습니다.

| 목표 | 처리 결과 |
|---|---|
| Airflow DAG의 orchestration 책임 유지 | DAG는 계속 `pipeline.run_interval()`만 호출합니다. |
| dbt 실행 책임 분리 | `src/cryptoquant_pipeline/dbt_runner.py`를 추가해 subprocess, selector, secret masking을 분리했습니다. |
| 설정값과 chunking 연결 | `PipelineSettings.max_blocks_per_log_request`가 `collect_raw_logs()`에 명시적으로 전달됩니다. |
| SQL projection 명확화 | dbt model과 singular test의 `SELECT *`를 제거했습니다. |
| 문서-코드 경로 정합성 | README, architecture, data contract, code reading guide, requirement matrix를 현재 경로와 맞췄습니다. |

## 변경한 Python 파일

| 파일 | 변경 내용 | 요구사항 연결 |
|---|---|---|
| `src/cryptoquant_pipeline/dbt_runner.py` | dbt subprocess 실행, timeout, 로그 tail masking, `tag:ethereum_hourly` selector 실행 책임을 새 모듈로 분리했습니다. | 신규 dbt 모델이 DAG 수정 없이 selector/ref graph로 반영되는 구조를 보존합니다. |
| `src/cryptoquant_pipeline/pipeline.py` | dbt 실행 구현을 제거하고 `run_dbt_build()` import만 사용하도록 정리했습니다. | pipeline orchestration과 dbt runner 책임을 분리합니다. |
| `src/cryptoquant_pipeline/log_collector.py` | `max_blocks` 인자를 추가하고 설정값을 chunk 분할에 전달할 수 있게 했습니다. | provider chunk 상한과 설정 계약의 연결성을 높입니다. |
| `tests/test_dbt_contracts.py` | dbt model/test source에서 `select *`를 금지하는 정적 회귀 테스트를 추가했습니다. | SQL 품질 기준과 실패 row 추적 가능성을 고정합니다. |

## 변경한 SQL 또는 dbt 모델

| 파일 | 변경 내용 | 요구사항 연결 |
|---|---|---|
| `dbt/models/silver/erc20_transfers.sql` | `source_logs`, `typed_amounts`, `usdt_amount_text` CTE의 projection을 explicit column list로 교정했습니다. | ERC-20 decoding grain과 incremental 입력 컬럼을 명확히 합니다. |
| `dbt/models/gold/tether_treasury_flow_quality_summary.sql` | upstream flow와 final summary projection에서 `SELECT *`를 제거했습니다. | dbt graph 자동 반영 검증용 view의 출력 컬럼을 명확히 합니다. |
| `dbt/tests/erc20_transfer_integrity.sql` | 실패 row projection을 검사 대상 컬럼으로 제한했습니다. | 실패 원인을 컬럼 단위로 추적합니다. |
| `dbt/tests/erc20_amount_numeric_status_integrity.sql` | 실패 row projection을 amount/status 컬럼으로 제한했습니다. | uint256 numeric status 계약을 명확히 합니다. |
| `dbt/tests/ethereum_logs_uint256_contract.sql` | 실패 row projection을 raw uint256 계약 컬럼으로 제한했습니다. | raw Delta uint256 보존 계약을 검증합니다. |
| `dbt/tests/non_usdt_amount_usdt_null.sql` | 실패 row projection을 USDT 파생 컬럼으로 제한했습니다. | non-USDT row에 USDT decimals가 적용되지 않도록 검증합니다. |
| `dbt/tests/treasury_flow_integrity.sql` | 실패 row projection을 Treasury flow key/amount 컬럼으로 제한했습니다. | hour/direction grain과 aggregate 계약을 검증합니다. |
| `dbt/tests/usdt_amount_numeric_not_null.sql` | 실패 row projection을 USDT numeric 필수 컬럼으로 제한했습니다. | USDT row의 numeric 변환 실패를 dbt build 실패로 처리합니다. |

## 변경한 Notebook 파일

| 파일 | 변경 내용 | 요구사항 연결 |
|---|---|---|
| `src/notebooks/00_notebook_validation_index.ipynb` | 노트북 실행 순서, 외부 RPC 미실행 경계, 검증 목적을 정리했습니다. | 평가자가 노트북을 학습 기록이 아니라 검증 보조 증거로 읽을 수 있게 합니다. |
| `src/notebooks/01_rpc_provider_connection_smoke_test.ipynb` | 현재 `PipelineSettings`, `EthereumJsonRpcClient` 기준으로 provider 연결 smoke를 재정렬하고 secret 출력 금지 경계를 명시했습니다. | 실제 RPC credential이 있을 때만 연결 검증을 수행합니다. |
| `src/notebooks/02_eth_getlogs_transfer_sample_validation.ipynb` | 현재 decoder helper와 `Transfer` topic0 기준 sample 검증 흐름으로 정리했습니다. | `eth_getLogs` sample 검증과 외부 RPC 비용 경계를 분리합니다. |
| `src/notebooks/03_fixture_etl_replay_idempotency_validation.ipynb` | fixture → normalizer → decode → Delta 재실행 멱등성 흐름을 현재 package 기준으로 갱신하고 실행 output을 저장했습니다. | Python source code와 Delta idempotency 검증 근거를 노트북에서 직접 확인할 수 있습니다. |
| `src/notebooks/04_accumulated_pipeline_data_freshness_validation.ipynb` | `delta_writer.ethereum_logs_schema()`와 실제 canonical Delta/DuckDB 산출물을 비교하는 판정형 노트북으로 정리했습니다. | 로컬 accumulated data가 최신 code contract와 불일치하면 `PARTIALLY VERIFIED`로 드러냅니다. |

## 변경 전 문제점

| 문제 | 영향 | 처리 |
|---|---|---|
| `pipeline.py`가 dbt subprocess 구현까지 포함했습니다. | pipeline callable의 책임이 넓어져 Airflow orchestration, 수집, dbt 실행 경계가 흐려졌습니다. | `dbt_runner.py`로 분리했습니다. |
| `PipelineSettings.max_blocks_per_log_request`가 collector 호출에 직접 전달되지 않았습니다. | 설정 계약과 실제 chunking 호출 사이의 추적성이 약했습니다. | `collect_raw_logs(..., max_blocks=...)`로 연결했습니다. |
| dbt model/test에 `SELECT *`가 남아 있었습니다. | 모델 grain과 실패 row 증거가 컬럼 단위로 추적되지 않았습니다. | explicit projection과 정적 테스트를 추가했습니다. |
| docs가 새 리팩토링 산출물을 가리키지 않았습니다. | README와 문서 목차만 읽으면 변경 근거를 찾기 어려웠습니다. | refactoring/documentation consistency report 링크를 추가했습니다. |
| `src/notebooks/`에 중복 누적 검증 파일과 stale 경로가 섞여 있었습니다. | 평가자가 어떤 노트북이 현재 코드·데이터 검증 기준인지 판단하기 어려웠습니다. | active notebook 5개만 번호화하고 03·04번 실행 output을 최신 상태로 저장했습니다. |

## 변경 후 구조

```text
airflow/dags/ethereum_hourly_logs.py
  -> cryptoquant_pipeline.pipeline.run_interval()
     -> block_range.resolve_interval_block_range()
     -> log_collector.collect_raw_logs(max_blocks=settings.max_blocks_per_log_request)
     -> log_normalizer.normalize_logs()
     -> delta_writer.write_ethereum_logs_insert_only()
     -> dbt_runner.run_dbt_build(--select tag:ethereum_hourly)
```

dbt model graph는 계속 아래 흐름을 사용합니다.

```text
ethereum_logs
-> erc20_transfers
-> tether_treasury_flow
-> tether_treasury_flow_quality_summary
```

Airflow DAG에는 개별 dbt 모델명이 없습니다.

## 주석 보강 기준과 주요 변경

새 Python 모듈의 주석과 docstring은 목적, 불변식, 실패 정책 중심으로 작성했습니다.

| 범위 | 주석 기준 |
|---|---|
| `dbt_runner.py` | dbt selector가 DAG 모델명 하드코딩을 대체한다는 불변식을 남겼습니다. |
| `log_collector.py` | collection scope와 chunk 상한을 함께 적용하는 목적을 짧게 남겼습니다. |
| dbt SQL | `SELECT *` 제거 후 projection이 어떤 grain과 실패 증거를 남기는지 주석을 유지했습니다. |

## 검증 명령과 결과

이번 리팩토링 중 실행한 명령입니다.

| 명령 | 결과 |
|---|---|
| `python -m compileall src tests airflow\dags` | 통과 |
| `python -m pytest tests\test_dbt_contracts.py tests\test_pipeline_idempotency.py tests\test_rpc_retry.py -q` | BLOCKED: 호스트 Python 3.13에 `pytest` 미설치 |
| `docker compose -f docker-compose.yaml -f .devcontainer/docker-compose.devcontainer.yaml config --quiet` | exit 0 |
| `docker compose -f docker-compose.yaml -f .devcontainer/docker-compose.devcontainer.yaml run --rm --no-deps workspace-dev ruff check src tests airflow dbt` | 최초 import 정렬 오류 1건, `ruff check --fix` 후 통과 |
| `docker compose -f docker-compose.yaml -f .devcontainer/docker-compose.devcontainer.yaml run --rm --no-deps workspace-dev python -m pytest tests/test_dbt_contracts.py tests/test_pipeline_idempotency.py tests/test_rpc_retry.py -q` | `12 passed` |
| `docker compose -f docker-compose.yaml -f .devcontainer/docker-compose.devcontainer.yaml run --rm --no-deps workspace-dev python scripts/create_dbt_validation_fixture.py --root /workspace/data/tmp/dbt_validation/refactor_sql` | `{'inserted': 2, 'rows': 2}` |
| `docker compose -f docker-compose.yaml -f .devcontainer/docker-compose.devcontainer.yaml run --rm --no-deps -e DELTA_LOGS_PATH=/workspace/data/tmp/dbt_validation/refactor_sql/ethereum_logs -e DUCKDB_PATH=/workspace/data/tmp/dbt_validation/refactor_sql/ethereum_analytics.duckdb -e DUCKDB_EXTENSION_DIR=/workspace/data/duckdb_extensions workspace-dev dbt build --project-dir dbt --profiles-dir dbt --select tag:ethereum_hourly --vars '{"window_start": "2024-01-01T00:00:00Z", "window_end": "2024-01-01T01:00:00Z"}' --no-partial-parse` | `PASS=43 WARN=0 ERROR=0 SKIP=0 NO-OP=0 TOTAL=43` |
| `docker compose -f docker-compose.yaml -f .devcontainer/docker-compose.devcontainer.yaml run --rm --no-deps workspace-dev python -m pytest -q` | `49 passed` |
| `docker compose -f docker-compose.yaml -f .devcontainer/docker-compose.devcontainer.yaml run --rm --no-deps workspace-dev python scripts/create_dbt_validation_fixture.py --root /workspace/data/tmp/dbt_validation/final_refactor` | `{'inserted': 2, 'rows': 2}` |
| `docker compose -f docker-compose.yaml -f .devcontainer/docker-compose.devcontainer.yaml run --rm --no-deps -e DELTA_LOGS_PATH=/workspace/data/tmp/dbt_validation/final_refactor/ethereum_logs -e DUCKDB_PATH=/workspace/data/tmp/dbt_validation/final_refactor/ethereum_analytics.duckdb -e DUCKDB_EXTENSION_DIR=/workspace/data/duckdb_extensions workspace-dev dbt build --project-dir dbt --profiles-dir dbt --select tag:ethereum_hourly --vars '{"window_start": "2024-01-01T00:00:00Z", "window_end": "2024-01-01T01:00:00Z"}' --no-partial-parse` | `PASS=43 WARN=0 ERROR=0 SKIP=0 NO-OP=0 TOTAL=43` |
| `docker compose -f docker-compose.yaml -f .devcontainer/docker-compose.devcontainer.yaml run --rm --no-deps workspace-dev python scripts/create_dbt_validation_fixture.py --root /workspace/data/tmp/dbt_validation/origin_matrix_check` | `{'inserted': 2, 'rows': 2}` |
| `docker compose -f docker-compose.yaml -f .devcontainer/docker-compose.devcontainer.yaml run --rm --no-deps -e DELTA_LOGS_PATH=/workspace/data/tmp/dbt_validation/origin_matrix_check/ethereum_logs -e DUCKDB_PATH=/workspace/data/tmp/dbt_validation/origin_matrix_check/ethereum_analytics.duckdb -e DUCKDB_EXTENSION_DIR=/workspace/data/duckdb_extensions workspace-dev dbt build --project-dir dbt --profiles-dir dbt --select tag:ethereum_hourly --vars '{"window_start": "2024-01-01T00:00:00Z", "window_end": "2024-01-01T01:00:00Z"}' --no-partial-parse` | `PASS=43 WARN=0 ERROR=0 SKIP=0 NO-OP=0 TOTAL=43` |
| `dbt ls --project-dir dbt --profiles-dir dbt --select erc20_amount_numeric_status_integrity --resource-type test --output json --no-partial-parse` in `workspace-dev` | singular test가 `model.ethereum_analytics.erc20_transfers` 의존성을 가짐 |
| Airflow DagBag import in `/opt/airflow/python` | `import_errors={}`, `dag_ids=['ethereum_hourly_logs']`, `schedule='@hourly'`, `task_ids=['run_interval']` |
| `dbt ls --project-dir dbt --profiles-dir dbt --select tag:ethereum_hourly --output name --no-partial-parse` | 4 models, 39 data tests, 1 source. `tether_treasury_flow_quality_summary` 포함 |
| `nbclient` execution of `src/notebooks/03_fixture_etl_replay_idempotency_validation.ipynb` | output 저장 완료. `second_inserted_row_count=0`, `duplicate_natural_key_count=0` |
| `nbclient` execution of `src/notebooks/04_accumulated_pipeline_data_freshness_validation.ipynb` | output 저장 완료. canonical raw Delta schema는 최신 Python 계약과 불일치하여 `PARTIALLY VERIFIED` |
| `data/imgs/` screenshot manual review | Airflow UI 기준 DAG 등록, `@hourly`, success 47, failed 14, failed task instance 13건 확인. row-level correctness 증거는 아님 |
| Airflow task log parse | successful scheduled run 반환값 33건, 최신 `row_count_after=6082932`, `dbt.returncode=0` |
| Delta/DuckDB direct inspection in `workspace-dev` | `data/delta/ethereum_logs_v2` row count `6082932`, `data/analytics/ethereum_analytics_v2.duckdb`의 `erc20_transfers=5400325`, `tether_treasury_flow=2`, `quality_summary=1` |
| Task 1 Bitcoin Velocity design validity scan | `Velocity formula`, `Raw tables`, `Volume policy`, `Supply policy`, `SQL pseudocode`, `Dummy data`, `Daily batch`, `Reorg` 모두 PASS. Bitcoin production pipeline 실행 검증은 아님 |
| Markdown local link check | `markdown local links ok` |
| secret-like token scan | match 없음 |
| `git diff --check` | exit 0. 줄끝 변환 경고만 출력 |

최종 검증 결과는 `docs/05_validation_evidence.md`와 최종 응답의 검증 섹션을 함께 봐야 합니다.

## 검증 불가 항목과 이유

| 항목 | 상태 | 이유 | 대체 검증 |
|---|---|---|---|
| 실제 외부 RPC 1시간 수집 | VERIFIED | Airflow task log에서 successful scheduled run 반환값 33건과 최신 `row_count_after=6082932`, `dbt.returncode=0`을 확인했습니다. | Delta/DuckDB direct inspection |
| Airflow scheduler/UI scheduled run history | VERIFIED | screenshot과 task log를 함께 확인했습니다. UI screenshot 단독 증거가 아니라 task 반환값과 산출물 row count를 대조했습니다. | DagBag import, screenshot evidence, Airflow log evidence |
| 최신 schema 기준 Airflow end-to-end 재실행 | VERIFIED | `data/delta/ethereum_logs_v2`가 최신 schema fields와 row count `6082932`건을 가집니다. | Delta direct inspection, task log |
| canonical reorg replacement | NOT VERIFIED | 현재 구현 범위가 finality buffer와 raw `block_hash` 보존까지입니다. | 문서에서 future hardening으로 분리 |
| multi-provider cross-check | NOT VERIFIED | 단일 provider 설정만 구현했습니다. | `eth_chainId` mismatch 실패 처리 |

## 남은 기술 부채

| 우선순위 | 항목 | 영향 |
|---|---|---|
| P1 | block-hash checkpoint와 common ancestor 기반 reorg replacement | 장기 reorg에서 stale raw/canonical 상태 교정이 자동화되지 않습니다. |
| P1 | Airflow pool 또는 file lock 기반 writer 동시성 통제 | `max_active_runs=1` 외의 Delta writer lock은 없습니다. |
| P1 | provider qualification manifest | provider별 historical block lookup 제한을 실행 전에 기록하지 못합니다. |
| P2 | label provenance registry | Tether Treasury address label의 source/version/validity를 구조화하지 않았습니다. |
| P2 | dependency lock/hash 검증 | requirements pin은 있으나 lockfile hash 검증은 없습니다. |

## 구현 및 검증 체크리스트

- [x] 변경한 Python 파일과 dbt SQL 파일을 요구사항에 연결했습니다.
  - 근거: 이 문서의 변경 파일 표

- [x] `SELECT *` 제거가 테스트로 고정되었습니다.
  - 근거: `tests/test_dbt_contracts.py::test_dbt_models_and_tests_do_not_use_select_star`

- [x] fixture 기반 dbt build가 통과했습니다.
  - 결과: `PASS=43 WARN=0 ERROR=0 SKIP=0 NO-OP=0 TOTAL=43`

- [x] 실제 외부 RPC 환경에서 1시간 end-to-end 수집을 완료했습니다.
  - 근거: `airflow/logs/` successful scheduled run 반환값 33건, `data/delta/ethereum_logs_v2` row count `6082932`, DuckDB downstream relation count 확인
  - 한계: provider SLA, full-history backfill, production monitoring은 별도 검증 대상입니다.

- [x] 과제 1 Bitcoin Velocity 설계 타당성을 별도 검증했습니다.
  - 근거: `docs/05_validation_evidence.md`의 Task 1 validity scan 8개 축 PASS
  - 한계: 설계 문서와 의사 SQL 정합성 검증이며 실제 Bitcoin ETL 실행 검증은 아닙니다.

- [x] 요구사항 추적표 상태를 갱신했습니다.
  - 경로: `docs/09_requirement_traceability_matrix.md`
