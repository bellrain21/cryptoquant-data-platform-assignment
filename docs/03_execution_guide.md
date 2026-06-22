# 03. Execution Guide

> 상태: 실행 가이드
> 읽는 법: Docker Python 검증 -> fixture Delta -> dbt build -> Docker Airflow 순서로 진행.

## 1. 준비

```powershell
Copy-Item .env.example .env
notepad .env
```

`ETH_RPC_URL`에 QuickNode, Alchemy, Infura 등 provider URL을 입력합니다. 실제 key는 Git에 넣지 않습니다.
`.env.example`의 `ETH_RPC_URL`은 비워 둡니다. 예시 placeholder URL을 넣으면 실제
provider로 오인되어 재시도되는 문제가 생기므로, 코드는 placeholder endpoint를
설정 오류로 거부합니다.

## 2. Python 검증

```powershell
docker compose -f docker-compose.yaml -f .devcontainer/docker-compose.devcontainer.yaml build workspace-dev
docker compose -f docker-compose.yaml -f .devcontainer/docker-compose.devcontainer.yaml run --rm --no-deps workspace-dev python --version
docker compose -f docker-compose.yaml -f .devcontainer/docker-compose.devcontainer.yaml run --rm --no-deps workspace-dev python -m pip check
docker compose -f docker-compose.yaml -f .devcontainer/docker-compose.devcontainer.yaml run --rm --no-deps workspace-dev ruff check .
docker compose -f docker-compose.yaml -f .devcontainer/docker-compose.devcontainer.yaml run --rm --no-deps workspace-dev python -m pytest -q
```

개발과 운영 모두 Ubuntu 24.04 기반 Docker 컨테이너의 Python 3.12 실행 경로를 사용합니다.
Airflow 2.10.x와 dbt 1.9+는 `protobuf` 요구 범위가 충돌하므로 같은 이미지 안에서
Airflow 실행 경로(`/opt/airflow/python`)와 project/dbt 실행 경로(`/opt/project/python`)을 분리합니다.

## 3. Fixture Delta 생성

외부 RPC 없이 dbt를 확인하려면 fixture raw log를 Delta에 적재합니다.

```powershell
docker compose -f docker-compose.yaml -f .devcontainer/docker-compose.devcontainer.yaml run --rm --no-deps workspace-dev python scripts/create_dbt_validation_fixture.py --root /workspace/data/tmp/dbt_validation/run2
```

## 4. dbt build

```powershell
docker compose -f docker-compose.yaml -f .devcontainer/docker-compose.devcontainer.yaml run --rm --no-deps -e DELTA_LOGS_PATH=/workspace/data/tmp/dbt_validation/run2/ethereum_logs -e DUCKDB_PATH=/workspace/data/tmp/dbt_validation/run2/ethereum_analytics.duckdb -e DUCKDB_EXTENSION_DIR=/workspace/data/duckdb_extensions workspace-dev dbt build --project-dir dbt --profiles-dir dbt --select tag:ethereum_hourly --vars '{"window_start": "2024-01-01T00:00:00Z", "window_end": "2024-01-01T01:00:00Z"}'
```

## 5. Docker Airflow

Docker Desktop 설치 후:

```powershell
.\scripts\bootstrap.ps1
docker compose up --build airflow-init
docker compose up --build airflow-webserver airflow-scheduler
```

Airflow UI: `http://localhost:8080`

Docker Compose 기본 Airflow raw Delta 경로는 `DELTA_LOGS_PATH=/opt/airflow/data/delta/ethereum_logs`,
DuckDB 경로는 `DUCKDB_PATH=/opt/airflow/data/analytics/ethereum_analytics.duckdb`입니다.
다만 2026-06-22 여러 1시간 scheduled 실행 증거는 `.env` override로 생성된
`/opt/airflow/data/delta/ethereum_logs_v2`와
`/opt/airflow/data/analytics/ethereum_analytics_v2.duckdb` 기준입니다.
문서에서 실행 증거를 해석할 때는 기본 경로와 실제 검증 경로를 혼동하지 않습니다.

## 6. DAG 실행

`ethereum_hourly_logs`는 Airflow UI manual trigger에서 프로젝트를 실제 실행합니다.
`.env.example`은 acceptance 경로를 우선해 `ETH_AIRFLOW_MANUAL_RUN_MODE=data_interval`을
사용합니다. 개발 중 provider 연결만 빠르게 확인하려면 opt-in으로
`recent_finalized` smoke mode를 설정할 수 있습니다.

```powershell
ETH_AIRFLOW_MANUAL_RUN_MODE=recent_finalized
ETH_AIRFLOW_RECENT_WINDOW_SECONDS=120
ETH_AIRFLOW_RECENT_FINALIZED_LAG_SECONDS=0
```

특정 구간을 실행하려면 DAG run conf에 아래처럼 둘 다 넣습니다.

```json
{
  "window_start": "2026-06-20T13:08:00Z",
  "window_end": "2026-06-20T13:10:00Z"
}
```

`ethereum_hourly_logs`는 `@hourly` schedule을 갖지만 `is_paused_upon_creation=True`로
생성됩니다. UI에서 pause를 해제하면 Airflow data interval 기준 scheduled run이 생성됩니다.

1시간 DAG interval을 실제 실행하려면 먼저 provider가 해당 interval start까지
`eth_getBlockByNumber` 조회를 허용하는지 확인해야 합니다. provider가 이 범위를
지원하지 않으면 task가 실패해야 하며, 수집 scope를 USDT-only로 축소하지 않습니다.

```powershell
docker compose up -d --force-recreate airflow-webserver airflow-scheduler
```

과거 Chainstack Basic endpoint에서는 1시간 interval의 block metadata lookup이
HTTP 403으로 실패했습니다. 이후 별도 provider 설정을 사용한 로컬 Docker Airflow
scheduled run은 `airflow/logs/`와 `data/delta/ethereum_logs_v2`에서 검증했습니다.
provider 종류와 plan에 따라 historical block metadata 조회 가능 범위가 다르므로,
새 provider로 재현할 때는 먼저 짧은 interval로 확인합니다.

Airflow DAG 목록의 `Failed` 숫자는 과거 DAG run 이력입니다. DAG를 pause하거나 no-op으로
바꿔도 기존 failed 이력은 자동 삭제되지 않습니다. 새 실패가 생기는지 보려면
`Browse -> DAG Runs`에서 최신 `Run Id`와 `Start Date`를 확인합니다.

### Airflow UI screenshot 증거 읽는 법

`data/imgs/`의 screenshot은 Airflow metadata DB에 남은 UI 실행 이력입니다.

| 파일 | 읽을 수 있는 사실 | 주의 |
|---|---|---|
| `data/imgs/task_02_01_image.png` | DAG `ethereum_hourly_logs`, `@hourly`, success 47, failed 14 | row-level data correctness 증거는 아닙니다. |
| `data/imgs/task_02_02_image.png` | grid 기준 displayed runs 61, success 47, failed 14 | 실패 원인은 task log 확인이 필요합니다. |
| `data/imgs/task_02_03_image.png` | failed `run_interval` task instance 13건 | 실패를 숨기지 않는 운영 이력 |
| `data/imgs/task_02_04_image.png` | success DAG run 47건 | task log와 Delta/DuckDB 산출물 대조가 필요합니다. |

Airflow UI에서 success run이 보이더라도, row-level data correctness는 task log와
Delta/DuckDB 산출물로 별도 확인합니다. 2026-06-22 기준 scheduled 실행 증거는
`data/delta/ethereum_logs_v2`, `data/analytics/ethereum_analytics_v2.duckdb`,
`docs/05_validation_evidence.md`에 연결되어 있습니다.

Backfill 예시:

```powershell
docker compose run --rm airflow-scheduler airflow dags backfill ethereum_hourly_logs `
  --start-date 2026-06-18T00:00:00+00:00 `
  --end-date 2026-06-19T00:00:00+00:00
```

## 7. 실패 확인 포인트

- `ETH_RPC_URL`이 없거나 예시 placeholder만 있는 경우: DAG 실행 실패가 정상입니다. 실제 provider URL을 `.env`에 설정해야 합니다.
- DuckDB Delta extension download 실패: 네트워크 필요합니다.
- Provider too many results: 구현은 항상 10블록 이하로 요청합니다. 단일 block까지 split 후에도 실패하면 provider tier 또는 해당 block log 밀도를 확인합니다.
- Provider HTTP 403 on block metadata lookup: 현재 확인한 Chainstack Basic endpoint는
  `eth_chainId`, finalized block, 최근 짧은 구간 `eth_getLogs`는 통과했지만
  `finalized - 50` 수준의 `eth_getBlockByNumber`부터 HTTP 403을 반환합니다.
  1시간 DAG interval을 실행하려면 최소 해당 interval start까지 block metadata 조회가
  가능한 provider 또는 plan이 필요합니다.

## 구현 및 검증 체크리스트

- [x] Docker, pytest, dbt build 실행 명령이 현재 경로와 일치합니다.
  - 근거: `docker-compose.yaml`, `.devcontainer/docker-compose.devcontainer.yaml`, `dbt/`

- [x] Airflow DAG ID와 backfill 명령이 현재 DAG 파일과 일치합니다.
  - 근거: `airflow/dags/ethereum_hourly_logs.py`

- [x] Delta Lake와 DuckDB 저장 경로가 canonical path를 사용합니다.
  - 근거: `DELTA_LOGS_PATH=/opt/airflow/data/delta/ethereum_logs`, `DUCKDB_PATH=/opt/airflow/data/analytics/ethereum_analytics.duckdb`

- [x] 실제 provider에서 1시간 scheduled run을 완료했습니다.
  - 근거: `airflow/logs/` successful scheduled run 반환값 33건, latest direct inspection 기준 `data/delta/ethereum_logs_v2` row count `6848937`, DuckDB `erc20_transfers=6079379` 확인
  - 한계: production-grade 무중단 운영과 provider SLA는 별도 검증 대상입니다.

- [x] Airflow UI screenshot의 증거 범위와 한계를 문서화했습니다.
  - 근거: `data/imgs/`, `docs/05_validation_evidence.md`

- [x] 요구사항 추적표 상태를 갱신했습니다.
  - 경로: `docs/09_requirement_traceability_matrix.md`
