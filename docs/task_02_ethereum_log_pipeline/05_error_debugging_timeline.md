# CryptoQuant Task 2 — 디버깅 타임라인 및 검증 기록

> **목적**: Ethereum hourly logs 파이프라인에서 발생한 장애·정상 보호 동작·수정·복구를 시간순으로 기록합니다.
> **대상 경로**: Docker Compose → Airflow → Ethereum RPC → Delta Lake → dbt → DuckDB
> **시간 기준**: 런타임·저장·Airflow logical interval은 UTC. KST는 운영 확인용 보조 표기입니다.
> **마지막 업데이트**: 2026-06-21 세션 증적 반영

> 현재 제출 판정: 이 문서는 historical debugging timeline입니다. 최신 상태 판단은 `docs/05_validation_evidence.md`와 `docs/09_requirement_traceability_matrix.md`를 우선합니다.
> 2026-06-22 기준 Airflow UI screenshot은 run history를 보강하고, `airflow/logs/`, `data/delta/ethereum_logs_v2`, `data/analytics/ethereum_analytics_v2.duckdb` 대조로 외부 RPC scheduled 수집은 `VERIFIED`로 갱신했습니다. 다만 기본 `data/delta/ethereum_logs` accumulated raw Delta는 최신 `delta_writer` schema와 불일치합니다.

---

## 0. 과거 디버깅 기록 한눈에 보기

아래 표는 2026-06-21 당시 관측과 복구 이력입니다. 현재 제출 상태로 그대로 읽지 않습니다.

| 영역 | 당시 상태 | 현재 제출 해석 |
|---|---|---|
| Airflow scheduled execution | **VERIFIED** | screenshot, task log, Delta/DuckDB 산출물 대조 기준 외부 RPC scheduled 수집은 `VERIFIED` |
| Finality-aware retry | **VERIFIED** | historical log와 tests 근거. production-grade provider SLA는 별도 검증 대상 |
| Raw Delta idempotency | **VERIFIED** | fixture/notebook 03 기준 재실행 idempotency는 `VERIFIED` |
| dbt graph / singular tests | **RECOVERED · VERIFIED** | 최신 fixture dbt build는 `PASS=43`으로 갱신 |
| Finality observability log | **VERIFIED** | historical runtime log 근거. 현재 source of truth는 validation evidence |
| Airflow UI served-log 403 | **OPEN** | CLI/local log 우회 가능, UI 영구 보정 미완료 |
| 제출 archive 위생 | **OPEN · P0** | secret·runtime artifact·target/cache 제외 재점검 필요 |

---

## 1. 읽는 법

### 상태 정의

| 상태 | 의미 |
|---|---|
| **VERIFIED** | 로그, CLI, Delta 직접 조회, dbt 결과 중 하나 이상으로 실제 동작을 확인 |
| **RECOVERED** | 장애 원인 수정 후 같은 경로에서 성공 증거를 확보 |
| **EXPECTED GUARD** | 데이터 정확성을 위해 의도적으로 중단·재시도한 상태 |
| **OPEN** | 개선 또는 영구 보정이 남은 상태 |
| **INFERRED** | 코드 실행 순서상 타당하지만, 해당 run의 직접 metric 증거가 없는 해석 |

### 핵심 시간 계약

```text
canonical time: UTC
interval policy: [start, end)
eth_getLogs block range: [from_block, to_block] inclusive
```

예시:

```text
UTC [01:00:00, 02:00:00)
KST [10:00:00, 11:00:00)

02:00:00 UTC는 이전 interval에 포함되지 않습니다.
```

---

## 2. 최신 복구 기록 — dbt singular test 경로 중복

### 2.1 장애 요약

| 항목 | 내용 |
|---|---|
| 발생 run | `manual__2026-06-21T19:45:20.670436+00:00`, attempt 2 |
| 대상 interval | UTC `[2026-06-21 18:00:00, 19:00:00)` |
| finality 상태 | `READY` |
| 실패 단계 | dbt build / test compilation |
| terminal 결과 | Airflow task `FAILED` |
| 원인 | `model-paths=["models"]`와 `test-paths=["models/tests"]`가 겹쳐 singular test SQL이 model과 test로 이중 등록됨 |

### 2.2 실제 관측

```text
Finality check:
status=READY
finalized_timestamp_utc=2026-06-21T19:34:47+00:00
required_interval_end_utc=2026-06-21T19:00:00+00:00
finality_offset_seconds=2087.0

dbt failure:
dbt was unable to infer all dependencies for singular test resources
Done. PASS=25 WARN=0 ERROR=17 SKIP=0 NO-OP=0 TOTAL=42
```

이 run은 finality guard를 통과하고 `Running dbt build` 단계까지 도달했습니다. 파이프라인 구현 순서상 Delta write는 dbt 호출보다 앞선다. 다만 이 실패 attempt 로그에는 해당 interval의 raw insert/duplicate metric이 직접 출력되지 않았으므로, raw 적재 완료 여부는 이 문서에서 **INFERRED**로만 기록합니다.

### 2.3 수정

```text
기존 구조
dbt/
└─ models/
   └─ tests/              # model-paths와 test-paths에 동시에 포함

수정 구조
dbt/
├─ models/
│  ├─ staging/
│  ├─ silver/
│  └─ gold/
└─ tests/                 # singular test SQL 전용
```

`dbt_project.yml`:

```yaml
model-paths: ["models"]
test-paths: ["tests"]
```

추가 조치:

```text
1. dbt/models/tests/*.sql → dbt/tests/*.sql 이동
2. dbt/models/tests 디렉터리 제거
3. dbt/target 제거
4. --no-partial-parse로 parse/build 재검증
```

### 2.4 복구 검증

| 검증 단계 | 결과 |
|---|---|
| `dbt parse --no-partial-parse` | `Found 4 models, 30 data tests, 1 source` |
| `dbt build --select tag:ethereum_hourly` | 2 incremental + 2 view + 30 data tests |
| 최종 결과 | `PASS=34`, `ERROR=0`, `SKIP=0` |

판정:

```text
INC-005 dbt test/model 이중 등록
→ RECOVERED / VERIFIED
```

---

## 3. 주요 이벤트 타임라인

### 3.1 초기 수집·schema 복구

| ID | UTC | 이벤트 | 결과 |
|---|---:|---|---|
| T-01 | 2026-06-20 18:49:13 | 초기 dbt build 실패 확인 | INCIDENT |
| T-02 | 2026-06-20 19:43:25 | provider block metadata lookup 제한 확인 | INCIDENT |
| T-03 | 2026-06-20 22:04:02 | 신규 uint256 contract와 기존 Delta schema mismatch 확인 | INCIDENT |
| T-04 | 2026-06-20 22:15:00 | legacy Delta / DuckDB backup 생성 | CHANGE |
| T-05 | 2026-06-20 22:26:28 | scheduled 1시간 E2E 성공 | RECOVERY VERIFIED |
| T-06 | 2026-06-20 22:28:24 | conf window 1시간 실행 성공 | RECOVERY VERIFIED |
| T-07 | 2026-06-20 22:33:10 | 동일 1시간 replay idempotency 성공 | RECOVERY VERIFIED |

### 3.2 Finality retry 검증

| ID | UTC | 이벤트 | 결과 |
|---|---:|---|---|
| T-08 | 2026-06-21 02:00:01 | scheduled attempt 1 | finality 미도달 → `UP_FOR_RETRY` |
| T-09 | 2026-06-21 02:09:58 | scheduled attempt 2 | finality 미도달 → `UP_FOR_RETRY` |
| T-10 | 2026-06-21 02:11:35 | finalized timestamp가 required end 초과 확인 | retry 조건 해소 |
| T-11 | 2026-06-21 02:29:19 | scheduled attempt 3 | finality 통과 후 E2E 시작 |
| T-12 | 2026-06-21 02:31:06 | Delta + dbt + Airflow 성공 | RECOVERY VERIFIED |

### 3.3 dbt graph 복구

| ID | 런타임 시각 | 이벤트 | 결과 |
|---|---:|---|---|
| T-13 | 2026-06-21 19:50:56 | `Finality check: READY` 확인 | 수집 진행 가능 |
| T-14 | 2026-06-21 19:52:41 | dbt build 시작 | downstream 단계 진입 |
| T-15 | 2026-06-21 19:52:59 | singular test dependency compilation 오류 | Airflow terminal failure |
| T-16 | 2026-06-21 20:05~20:07 | test path 분리 후 parse/build 실행 | graph 재구성 |
| T-17 | 2026-06-21 20:07:20 | dbt build 성공 | `PASS=34`, `ERROR=0` |

> T-16~T-17은 container dbt console 출력 기준이다. 출력 자체에 timezone suffix가 없으므로, 이 문서에서는 KST 환산값을 단정하지 않습니다.

---

## 4. Finality-aware retry 기준 사례

### 처리 대상

```text
run_id:
scheduled__2026-06-21T01:00:00+00:00

UTC interval:
[2026-06-21 01:00:00, 02:00:00)

KST interval:
[2026-06-21 10:00:00, 11:00:00)
```

### 동작 규칙

```text
finalized_block_timestamp_utc >= interval_end_utc
→ block range 계산 및 수집 진행

finalized_block_timestamp_utc < interval_end_utc
→ RetryableIntervalNotFinalized
→ Airflow UP_FOR_RETRY
→ eth_getLogs / Delta / dbt 실행하지 않았습니다
```

### attempt 판정

| attempt | KST 시작 | 결과 | 수집·Delta·dbt |
|---|---:|---|---|
| 1 | 11:00:01 | finality 미도달 | 실행하지 않음 |
| 2 | 11:09:58 | finality 미도달 | 실행하지 않음 |
| 3 | 11:29:19 | finality 통과 | 실행 및 성공 |

### attempt 3 결과

```text
from_block=25362542
to_block=25362841
raw_log_count=105719
normalized_log_count=105719
invalid_log_count=0
inserted_row_count=105719
duplicate_skipped_count=0
row_count_after=948159
dbt.returncode=0
Airflow=SUCCESS
```

Delta 직접 조회:

```text
raw_rows=105719
min(block_number)=25362542
max(block_number)=25362841
max(block_timestamp_utc)=2026-06-21 01:59:59 UTC
```

---

## 5. 검증된 실행 증적

| 경로 | UTC interval | 핵심 결과 |
|---|---|---|
| scheduled | `[2026-06-20 21:00, 22:00)` | raw 210,480 / invalid 0 / inserted 210,480 / dbt rc 0 / SUCCESS |
| conf backfill | `[2026-06-20 20:00, 21:00)` | raw 228,965 / invalid 0 / inserted 228,965 / dbt rc 0 / SUCCESS |
| replay | 동일 `[2026-06-20 20:00, 21:00)` | insert 0 / duplicate skip 228,965 / dbt rc 0 / SUCCESS |
| scheduled | `[2026-06-20 23:00, 2026-06-21 00:00)` | raw 134,475 / invalid 0 / inserted 134,475 / dbt rc 0 / SUCCESS |
| finality retry case | `[2026-06-21 01:00, 02:00)` | retry 2회 후 raw 105,719 / dbt rc 0 / SUCCESS |
| dbt-only catch-up | `[2026-06-21 18:00, 19:00)` | dbt `PASS=34 / ERROR=0`; raw result metric은 이 실행 로그에 없음 |

---

## 6. 운영 확인 명령

### dbt graph 확인

```cmd
docker compose exec airflow-scheduler sh -lc "cd /opt/airflow/dbt && dbt parse --profiles-dir /opt/airflow/dbt --no-partial-parse && dbt ls --resource-type model && dbt ls --resource-type test"
```

정상 기준:

```text
Found 4 models, 30 data tests
```

### 동일 window dbt-only catch-up

```cmd
docker compose exec airflow-scheduler sh -lc "cd /opt/airflow/dbt && dbt build --profiles-dir /opt/airflow/dbt --select tag:ethereum_hourly --vars '{"window_start":"<UTC_START>","window_end":"<UTC_END>"}' --no-partial-parse"
```

### 최신 Airflow attempt log

```cmd
docker compose exec airflow-scheduler sh -lc "f=$(find /opt/airflow/logs/dag_id=ethereum_hourly_logs -path '*task_id=run_interval*' -type f -printf '%T@ %p
' | sort -n | tail -1 | cut -d' ' -f2-); echo LOG_FILE=$f; tail -n 160 $f"
```

### Delta interval 물리 검증

```cmd
docker compose exec airflow-scheduler python -c "from deltalake import DeltaTable; import duckdb; p='/opt/airflow/data/delta/ethereum_logs_v2'; t=DeltaTable(p); c=duckdb.connect(); c.register('raw_logs', t.to_pyarrow_dataset()); print(c.execute("select interval_start_utc, interval_end_utc, count(*) as raw_rows, min(block_number), max(block_number), max(block_timestamp_utc) from raw_logs group by 1,2 order by interval_start_utc desc limit 5").fetchall()); c.close()"
```

---

## 7. 남은 확인 항목

```text
[ ] dbt-only catch-up 대상 [18:00,19:00) UTC raw interval의 insert/duplicate metric을 Delta 직접 조회로 보강
[ ] 다음 Airflow scheduled/manual run에서 dbt.returncode=0 및 Airflow SUCCESS 확인
[ ] Airflow UI served-log 403 영구 보정
[ ] ETH_AIRFLOW_ENABLE_HOURLY_SCHEDULE 제거 또는 실제 DAG 동작과 연결
[ ] dbt_project.yml / profiles.yml의 v2 default path 통일 여부 재검증
[ ] 제출 archive에서 .env, key, logs, target, runtime DB, cache 제외
```

2026-06-22 재판정:

| 항목 | 상태 | 근거 또는 미완료 사유 |
|---|---|---|
| dbt-only catch-up 대상 interval metric 보강 | PARTIALLY VERIFIED | 최신 Airflow successful scheduled run과 Delta/DuckDB row count는 확인함 특정 `[18:00,19:00)` UTC catch-up interval만 별도 조회하지는 않았음 |
| 다음 Airflow scheduled/manual run 성공 확인 | VERIFIED | `airflow/logs/`에서 최신 successful scheduled run `row_count_after=6082932`, `dbt.returncode=0`을 확인함 |
| Airflow UI served-log 403 영구 보정 | NOT VERIFIED | UI log serving 설정 보정은 현재 제출 core 기능이 아니며 수행하지 않음 |
| `ETH_AIRFLOW_ENABLE_HOURLY_SCHEDULE` 정리 | PARTIALLY VERIFIED | active DAG는 `schedule='@hourly'`임 historical env flag cleanup은 legacy cleanup 범위로 남김 |
| dbt/project default path의 v2 통일 | PARTIALLY VERIFIED | v2 실행 증거와 fixture dbt 검증은 확인함 notebook 04는 최신 v2 pair를 선택하지만 2026-06-22 12:00 UTC hourly gap과 DuckDB staging view 절대경로 문제를 `PARTIALLY VERIFIED`로 판정함 |
| 제출 archive secret/runtime artifact 제외 | PARTIALLY VERIFIED | `.gitignore`, `.env.example`, secret-like scan은 확인함 실제 archive 생성 직전 `git ls-files` 재확인은 남아 있음 |

---

## 8. 결론

이 파이프라인의 재시도는 두 가지 성격으로 분리됩니다.

```text
1. finality retry
   → canonicality 보호를 위한 정상 guard
   → finality 충족 후 동일 interval E2E 성공으로 검증

2. dbt graph failure
   → singular test SQL의 path 중복 등록
   → tests 경로 분리 후 dbt parse/build 성공으로 복구 검증
```

현재 핵심 수집·적재·변환 경로는 검증됐고,
남은 작업은 운영 관측성과 제출 위생을 닫는 것입니다.
