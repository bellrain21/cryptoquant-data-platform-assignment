# CryptoQuant Task 2 — 장애·변경·운영 이슈 기록

> **목적**: 실제 장애, 정상 보호 동작, 변경 이력, 미해결 운영 리스크를 분리해 관리합니다.
> **대상 경로**: Docker Compose → Airflow → Ethereum RPC → Delta Lake → dbt → DuckDB
> **시간 기준**: 런타임과 저장은 UTC.
> **마지막 업데이트**: dbt singular test 경로 복구 결과 반영

> 현재 제출 판정: 이 문서는 historical incident/change log입니다. 최신 source of truth는 `README.md`, `docs/01_system_architecture.md`~`docs/07_submission_readiness_report.md`, `docs/09_requirement_traceability_matrix.md`입니다.
> 2026-06-22 기준 Airflow UI screenshot은 run history를 보여주며, `airflow/logs/`, `data/delta/ethereum_logs_v2`, `data/analytics/ethereum_analytics_v2.duckdb` 대조로 외부 RPC scheduled 수집은 `VERIFIED`로 갱신했습니다. 다만 `src/notebooks/04_accumulated_pipeline_data_freshness_validation.ipynb`는 기본 `data/delta/ethereum_logs` 경로의 accumulated raw Delta schema가 최신 Python 계약과 불일치한다고 판정했습니다.

---

## 0. 과거 운영 기록 상태 보드

아래 표는 당시 장애 복구 기록입니다. 현재 제출 상태는 `docs/05_validation_evidence.md`와 `docs/09_requirement_traceability_matrix.md`를 우선합니다.

| 영역 | 당시 상태 | 현재 제출 해석 |
|---|---|---|
| Provider metadata lookup | **RECOVERED / VERIFIED** | historical run 기록. 2026-06-22 Airflow log 기준 외부 RPC 1시간 scheduled E2E는 `VERIFIED` |
| uint256 overflow | **RECOVERED / VERIFIED** | 현재 code/fixture/dbt tests 기준으로 `VERIFIED` |
| Delta schema mismatch | **RECOVERED / VERIFIED** | 현재 accumulated local Delta는 다시 `PARTIALLY VERIFIED`. fixture path와 구분 필요 |
| Notebook DuckDB lock | **RECOVERED / OPEN** | notebook 04는 query 단위 실행으로 저장 완료. live reader race는 운영 hardening 대상 |
| Finality retry | **EXPECTED BEHAVIOR / VERIFIED** | unit/mock 및 historical 기록 근거. production-grade provider SLA는 별도 검증 대상 |
| dbt singular test path | **RECOVERED / VERIFIED** | 최신 fixture dbt build는 `PASS=43`으로 갱신 |
| UI served-log 403 | **OPEN** | data path 비차단. UI screenshot은 run history 보조 증거 |
| submission archive hygiene | **OPEN / P0** | `.env`, generated data, runtime artifact 제외 필요 |

---

## 1. 공통 데이터·운영 계약

### 1.1 흐름과 실행 주체

```text
Docker Compose
  └─ airflow-scheduler
       ├─ DAG parse
       ├─ scheduled run 생성
       ├─ queued / up_for_retry task 재개
       └─ run_interval
            ├─ finalized head 확인
            ├─ UTC interval → block range
            ├─ eth_getLogs
            ├─ normalize
            ├─ Delta raw write
            └─ dbt build → DuckDB silver / gold
```

> Docker가 직접 DAG을 실행하는 것은 아닙니다. Docker Compose가 scheduler를 기동하고, scheduler가 Airflow metadata와 DAG 정의를 기준으로 schedule·retry를 수행합니다.

### 1.2 시간·grain·idempotency

```text
시간 경계: UTC [start, end)
raw grain: 1 row = 1 EVM event log
raw natural key: chain_id + transaction_hash + log_index
```

- 동일 natural key 재수집 시 append하지 않습니다.
- `max_active_runs=1`은 과제 범위의 single-writer 제약입니다.
- raw Delta commit과 dbt materialization은 하나의 transaction이 아닙니다.
- 따라서 raw success와 analytics success는 별도 증적으로 확인합니다.

### 1.3 uint256 raw contract

```text
data_raw
data_uint256_decimal_text
data_uint256_decode_status
```

| status | 의미 |
|---|---|
| `DECIMAL38_AVAILABLE` | exact decimal text 존재, `DECIMAL(38,0)` 파생 가능 |
| `OUTSIDE_DECIMAL38_RANGE` | exact decimal text 존재, fixed precision 범위 초과 |
| `NOT_UINT256_WORD` | 유효 raw log지만 uint256 data word 형태가 아님 |

정책:

```text
일반 ERC-20 범위 초과
→ raw exact text 보존
→ numeric 파생 NULL 허용

configured USDT numeric 변환 실패
→ dbt test로 fail-closed
```

---

## 2. 장애·보호 동작 기록

## INC-001 — RPC provider block metadata lookup 제한

**상태: `RECOVERED / VERIFIED`**

| 구분 | 기록 |
|---|---|
| 증상 | `eth_getBlockByNumber` numeric lookup이 interval start까지 도달하지 못함 |
| 오류 | `provider block metadata lookup window does not reach interval_start_utc` |
| 영향 | UTC 시간→block range 자동 계산 실패 |
| 근본 원인 | 초기 provider가 필요한 block metadata lookup 범위를 제공하지 않음 |
| 조치 | metadata lookup이 가능한 provider configuration으로 전환 |
| 검증 | finalized·numeric probe 및 1시간 scheduled E2E 성공 |

운영 원칙:

```text
provider 제한을 이유로 address/topic scope를 조용히 축소하지 않습니다.
provider capability 또는 처리 가능한 interval 범위를 명시합니다.
```

---

## INC-002 — `DECIMAL(38,0)` overflow로 Silver model 실패

**상태: `RECOVERED / VERIFIED`**

| 구분 | 기록 |
|---|---|
| 증상 | 큰 ERC-20 uint256 입력에서 `erc20_transfers` model 전체 실패 |
| 근본 원인 | uint256은 최대 78자리 decimal, DuckDB `DECIMAL(38,0)`는 38자리 한계 |
| 실패 방식 | raw ABI hex를 DuckDB SQL 산술로 직접 numeric cast |
| 조치 | Python arbitrary-precision int로 exact decimal text 생성 후 status 저장 |
| 검증 | scheduled / conf backfill / replay에서 dbt return code 0 |
| 결과 | raw 값은 보존, SQL numeric 파생값만 범위에 따라 분기 |

---

## INC-003 — 신규 raw contract와 기존 Delta schema mismatch

**상태: `RECOVERED / VERIFIED`**

| 구분 | 기록 |
|---|---|
| 증상 | dbt staging이 새 uint256 컬럼을 참조했으나 기존 Delta schema에 컬럼 없음 |
| 근본 원인 | normalizer/writer/dbt만 새 contract로 바뀌고 기존 Delta table은 구 schema |
| 잘못된 대응 | dbt `--full-refresh`만 수행 |
| 왜 부족한가 | full-refresh는 dbt relation만 재생성하며 raw Delta migration은 수행하지 않음 |
| 조치 | legacy backup 생성 후 raw Delta와 DuckDB clean rebuild |
| 검증 | 새 schema 기준 scheduled / backfill / replay E2E 성공 |

---

## INC-004 — Notebook persistent reader와 DuckDB writer lock 충돌

**상태: `RECOVERED`, 구조적 개선은 `OPEN`**

| 구분 | 기록 |
|---|---|
| 증상 | raw Delta commit 뒤 dbt build가 DuckDB write lock 획득에 실패 |
| 직접 원인 | 초기 validation notebook이 live DuckDB read connection을 지속 보유 |
| 영향 | raw는 commit됐지만 silver/gold가 stale가능 |
| 즉시 복구 | notebook kernel 종료 → writer lock preflight → dbt-only catch-up |
| 개선 | notebook을 query 단위 open/close 방식으로 변경 |
| 남은 리스크 | live DB reader race를 구조적으로 완전히 제거한 것은 아님 |

운영 규칙:

```text
raw Delta commit 성공 ≠ analytics materialization 성공

raw가 이미 commit된 interval은
RPC 재수집보다 dbt-only catch-up을 먼저 검토합니다.
```

---

## STD-GUARD-001 — Finality 대기 및 Airflow retry

**상태: `EXPECTED BEHAVIOR / VERIFIED`**

| 구분 | 기록 |
|---|---|
| 발생 위치 | `resolve_interval_block_range()` finality guard |
| 예외 | `RetryableIntervalNotFinalized` |
| Airflow 상태 | `UP_FOR_RETRY` |
| 보호 목적 | finalized되지 않은 구간의 canonical raw 적재 차단 |
| 허용 조건 | `finalized_block_timestamp_utc >= interval_end_utc` |
| 검증 | retry 2회 후 attempt 3 E2E success |

### 실제 사례

```text
scheduled__2026-06-21T01:00:00+00:00
UTC [01:00, 02:00)

attempt 1 → UP_FOR_RETRY
attempt 2 → UP_FOR_RETRY
attempt 3 → raw 105,719 / dbt rc 0 / SUCCESS
```

### observability 상태

이전에는 finality log 수정안만 존재했습니다. 현재는 아래 runtime log가 실제로 확인됐습니다.

```text
Finality check:
status=READY
finalized_block=25368091
finalized_timestamp_utc=2026-06-21T19:34:47+00:00
required_interval_end_utc=2026-06-21T19:00:00+00:00
finality_offset_seconds=2087.0
```

판정:

```text
CHG-009 finality observability logging
→ VERIFIED
```

---

## INC-005 — dbt singular test SQL의 model/test 이중 등록

**상태: `RECOVERED / VERIFIED`**

| 구분 | 기록 |
|---|---|
| 증상 | `models/tests/*.sql` singular test가 model과 test로 동시에 등록 |
| 직접 오류 | dbt가 test resource를 model로 해석하며 dependency inference compilation error 발생 |
| 영향 | 불필요한 view model 생성, graph 혼동, `dbt build` terminal failure |
| 원인 | `model-paths=["models"]`와 `test-paths=["models/tests"]`의 경로 중첩 |
| 조치 | `dbt/models/tests/*.sql`을 `dbt/tests/*.sql`로 이동 |
| 설정 변경 | `test-paths: ["tests"]` |
| 추가 조치 | `dbt/target` 제거 후 `--no-partial-parse` |
| parse 검증 | `Found 4 models, 30 data tests, 1 source` |
| build 검증 | `PASS=34`, `ERROR=0`, `SKIP=0` |

복구 기준:

```text
실제 model = 4
- staging.ethereum_logs
- staging.stg_ethereum_logs
- silver.erc20_transfers
- gold.tether_treasury_flow

data tests = 30
```

---

## OPS-001 — Airflow Web UI served-log 403

**상태: `OPEN / NON-BLOCKING`**

| 구분 | 기록 |
|---|---|
| 증상 | Web UI task log fetch 403 발생 이력 |
| 데이터 영향 | 없음 scheduler local task log와 CLI direct read 가능 |
| 가능 원인 | component 간 `AIRFLOW__WEBSERVER__SECRET_KEY` 또는 log serving configuration 불일치 |
| 임시 우회 | `/opt/airflow/logs/.../attempt=n.log` 직접 조회 |
| 영구 조치 | 공통 secret key 정합 후 component 재생성, UI log 재검증 |

---

## OPS-002 — Schedule environment flag와 실제 DAG schedule 불일치

**상태: `OPEN / P1`**

| 구분 | 기록 |
|---|---|
| 증상 | `ETH_AIRFLOW_ENABLE_HOURLY_SCHEDULE`가 있어도 DAG가 `@hourly` hard-coded로 동작 |
| 위험 | env false만으로 scheduling이 멈춘다고 오해가능 |
| 선택지 A | flag 제거, Airflow Pause/Unpause를 유일한 운영 스위치로 문서화 |
| 선택지 B | DAG schedule 인자에 env flag를 실제 연결 |
| 권장 | 과제 제출 범위에서는 A가 단순하고 혼동이 적음 |

---

## SEC-001 — 제출 archive 보안·위생

**상태: `OPEN / P0`**

| 구분 | 기록 |
|---|---|
| 확인 이력 | `.env`, runtime data, Airflow/dbt logs, target artifact, analytics DB 등이 archive에 포함된 적 있음 |
| 위험 | secret 노출, 제출물 비대화, stale artifact와 source 혼동 |
| 필수 제외 | `.env`, `airflow.cfg`, `data/delta/`, `data/analytics/`, `data/tmp/`, `airflow/logs/`,<br>`dbt/logs/`, `dbt/target/`, cache. `data/imgs/`는 screenshot evidence로 별도 보존 |
| 노출 대응 | endpoint/API key가 외부에 공유된 적이 있다면 provider key rotate |

---

## CLEANUP-001 — legacy Python package 정리

**상태: `OPEN / P1`**

| 구분 | 기록 |
|---|---|
| canonical source | `src/cryptoquant_pipeline/` |
| legacy candidate | `src/eth_pipeline/` |
| runtime 판정 | Airflow 실행은 `cryptoquant_pipeline.*` import를 사용 |
| 사전 조건 | scripts/tests/docs의 `eth_pipeline` 참조를 current package 기준으로 제거 |
| 확인이 필요 | `git grep -n "eth_pipeline"` 및 `pytest -q` |
| 목표 | source-of-truth를 하나로 유지하고 reviewer 혼동 방지 |

---

## 3. 변경 이력

| ID | 변경 | 검증 | 상태 |
|---|---|---|---|
| CHG-001 | uint256 exact decimal text + status 도입 | dbt E2E | VERIFIED |
| CHG-002 | DuckDB SQL hex 산술 제거 | scheduled / conf / replay | VERIFIED |
| CHG-003 | ERC-20 ABI shape filter | integrity test | VERIFIED |
| CHG-004 | USDT 전용 decimals 적용 | dbt test | VERIFIED |
| CHG-005 | Treasury self-transfer 제외·gold key 확장 | model / test | VERIFIED |
| CHG-006 | legacy backup + clean rebuild | E2E success | VERIFIED |
| CHG-007 | conf window backfill path | `mode=conf_window` | VERIFIED |
| CHG-008 | 동일 interval replay | insert=0 / duplicate>0 | VERIFIED |
| CHG-009 | finality observability log | runtime `Finality check` 출력 | VERIFIED |
| CHG-010 | singular test path 분리 | 4 models / 30 tests / PASS=34 | VERIFIED |

---

## 4. 잠재 위험

| ID | 위험 | 상태 | 권장 방향 |
|---|---|---|---|
| PI-01 | Delta dedupe가 전체 raw key를 Python set으로 materialize | POTENTIAL | interval/date 범위 scan 또는 merge/ledger 검토 |
| PI-02 | dbt tests가 매시간 history 전체 scan 가능 | POTENTIAL | hourly validation과 daily full audit 분리 |
| PI-03 | raw write와 dbt build 비원자적 | CONFIRMED / OPEN | raw / dbt / freshness task 분리, interval ledger |
| PI-04 | notebook live DuckDB direct read | PARTIALLY MITIGATED | immutable snapshot 또는 exported parquet |
| PI-05 | cold environment Delta extension cache/network 의존 | POTENTIAL | image preinstall 또는 preflight 문서화 |
| PI-06 | legacy `eth_pipeline`과 canonical `cryptoquant_pipeline` 공존 | OPEN | legacy package·문서 참조 정리 |
| PI-07 | canonical publish fence 구현되지 않음 | OPEN ARCHITECTURE | run-id staging → all-success promotion |
| PI-08 | error policy와 run manifest 분산 | OPEN ARCHITECTURE | reason code / retryable / recovery action 계약화 |

---

## 5. 제출 전 우선순위

### P0 — 제출 차단 가능 항목

```text
[ ] .env / API key / secret / runtime data / logs / dbt target-cache 제외
[ ] clean checkout 또는 clean archive에서 README 실행 경로 검증
[ ] raw commit과 dbt 실패가 분리될 가능성을 validation 문서에 명시합니다.
[ ] archive 생성 직전 git status / git ls-files 재확인
```

2026-06-22 재판정:

| 항목 | 상태 | 근거 또는 미완료 사유 |
|---|---|---|
| secret/runtime artifact 제외 | VERIFIED | `.gitignore`, `.env.example`, secret-like scan, `data/delta/`, `data/analytics/`, `airflow/logs/`, `dbt/target/` ignore 확인 |
| clean checkout 또는 clean archive 검증 | NOT VERIFIED | 현재 작업트리가 변경 중이며 clean clone/archive에서 재실행하지 않음 |
| raw commit과 dbt 실패 분리 문서화 | VERIFIED | `docs/05_validation_evidence.md`, `docs/07_submission_readiness_report.md`,<br>`docs/11_documentation_consistency_report.md`에 raw Delta, dbt, UI 증거 경계를 분리함 |
| archive 직전 `git status` / `git ls-files` 재확인 | NOT VERIFIED | archive 생성 단계가 아니므로 최종 제출 직전에 다시 실행해야 함 |

### P1 — 신뢰도·운영성 강화

```text
[ ] 다음 Airflow run에서 dbt.returncode=0 + Airflow SUCCESS 확인
[ ] Airflow UI served-log 403 영구 보정
[ ] schedule env flag 제거 또는 실제 DAG 동작 연결
[ ] dbt/project default path의 v2 통일 여부 확인
[ ] legacy eth_pipeline package / docs / scripts 참조 정리
```

2026-06-22 재판정:

| 항목 | 상태 | 근거 또는 미완료 사유 |
|---|---|---|
| 다음 Airflow run 성공 확인 | VERIFIED | Airflow task log에서 successful scheduled run 반환값 33건과 최신 `dbt.returncode=0` 확인 |
| Airflow UI served-log 403 영구 보정 | NOT VERIFIED | UI served-log 설정 자체는 제출 핵심 기능이 아니며 영구 보정 작업을 수행하지 않음 |
| schedule env flag 정리 | PARTIALLY VERIFIED | active DAG는 `@hourly` schedule을 코드로 가짐 legacy env flag 존재 여부는 제출 차단 기능이 아니라 문서상 historical risk로 남김 |
| dbt/project default path의 v2 통일 | PARTIALLY VERIFIED | 실행 증거는 `ethereum_logs_v2`에서 확인했지만 기본 `DELTA_LOGS_PATH`는 clean fixture/dbt 검증 경로와 분리되어 있음 |
| legacy `eth_pipeline` 참조 정리 | PARTIALLY VERIFIED | canonical 경로는 `src/cryptoquant_pipeline/`로 정리함 현재 작업트리의 삭제/추가 변경이 아직 remote에 반영되지 않음 |

### P2 — 확장성 개선

```text
[ ] full-key Python set dedupe 개선
[ ] incremental hourly test와 full-history audit 분리
[ ] interval ledger / watermark / repair command
[ ] canonical publish fence
```

2026-06-22 재판정: 위 네 항목은 제출 core 요구사항이 아니라 운영 hardening입니다. 현재 구현은 natural key 기반 insert-if-not-exists, fixture/dbt test, Airflow retry, task log evidence까지 검증했으며, interval ledger와 canonical publish fence는 `NOT VERIFIED`로 유지합니다.

---

## 6. 최종 상태 스냅샷

```text
VERIFIED
- scheduled run 생성 및 retry 재개
- finality guard와 finality observability logging
- finality 통과 후 raw → Delta → dbt E2E
- scheduled / conf backfill / replay idempotency
- dbt graph: 4 models / 30 data tests
- dbt build: PASS=34 / ERROR=0

RECOVERED
- provider metadata lookup 제한
- uint256 DECIMAL(38,0) overflow
- raw contract와 기존 Delta schema mismatch
- persistent notebook reader의 DuckDB writer lock
- dbt singular test SQL의 model/test 이중 등록

OPEN
- submission hygiene
- Airflow UI served-log 403
- schedule env flag 실제 적용 여부
- raw/dbt/freshness task 분리
- notebook live reader race의 완전 제거
- legacy eth_pipeline cleanup
```
