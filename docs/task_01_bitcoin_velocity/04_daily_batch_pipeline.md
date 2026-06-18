# 9~11. 일 단위 배치, 데이터 품질, 멱등성(Daily Batch, Data Quality, and Idempotency)

> **문서 상태(Status)**: Draft  
> **문서 역할(Role)**: Airflow, Spark SQL, Delta Lake를 사용한 일 단위 생산·검증·재처리 절차를 정의한다.

# 9. 일 단위 배치 파이프라인 설계(Daily Batch Pipeline Design)

## 9.1 전체 처리 흐름(End-to-end Flow)

```text
Airflow data interval
  → resolve requested metric date
  → resolve Best Chain snapshot and policy-confirmed cutoff
  → validate raw block and transaction completeness
  → build or refresh UTXO lifecycle
  → calculate daily volume and daily supply components
  → calculate trailing 365-day velocity variants
  → run quality gates
  → Delta MERGE publish
  → emit audit record and alert
```

## 9.2 Airflow DAG 구조(Airflow DAG Design)

| 순서 | Task | 입력 | 출력 | 실패 시 처리 |
|---:|---|---|---|---|
| 1 | `resolve_data_interval` | Airflow data interval | 대상 `metric_date` 범위 | 설정 오류면 hard fail |
| 2 | `resolve_chain_checkpoint` | node 또는 raw block snapshot | Best Chain tip, cutoff height, required successor blocks | 재시도 후 hard fail |
| 3 | `validate_chain_completeness` | block snapshot | height 연속성·parent hash 검증 결과 | hard fail |
| 4 | `build_utxo_lifecycle` | tx_input, tx_output, Best Chain snapshot | lifecycle view 또는 table | hard fail |
| 5 | `build_daily_components` | lifecycle, tx_output | daily volume·supply component | hard fail |
| 6 | `calculate_velocity` | 365일 date spine와 daily component | metric staging data | hard fail |
| 7 | `run_quality_gates` | staging data | quality status | hard fail 또는 review alert |
| 8 | `publish_metric` | quality-passed staging data | Gold Delta table | transaction retry |
| 9 | `record_audit` | run metadata | audit log·alert event | best-effort, 실패 별도 경보 |

## 9.3 Airflow Data Interval과 Backfill

Airflow의 logical date는 실제 실행 시각이 아니라 data interval의 시작을 나타낸다. 따라서 DAG는 `now()`가 아니라 data interval로 대상 날짜를 결정한다.

```text
scheduled run
= 일 단위 data interval을 처리

manual rerun
= 같은 data interval을 다시 처리

backfill
= 과거 data interval을 같은 DAG와 같은 변환 경로로 처리
```

Backfill용 별도 계산 코드를 만들지 않는다. 같은 DAG에 날짜 범위만 다르게 전달해야 scheduled run과 historical run의 결과 규칙이 갈라지지 않는다.

## 9.4 Successor Block 기반 게시 정책(Policy-confirmation Publication)

Bitcoin은 결정론적 finality를 제공하지 않는다. 따라서 `confirmed_by_policy`는 프로토콜 절대 확정이 아니라 내부 게시 정책을 충족했다는 뜻이다.

```text
required_successor_blocks
= 기준일 종료 block 뒤에 추가로 존재해야 하는 block 수
= block 자신을 포함한 confirmation count와 다른 값

confirmed_cutoff_height
=
observed_best_chain_tip_height
-
required_successor_blocks
```

기준일 종료 block의 height가 이 cutoff 이하일 때만 해당 날짜의 결과를 current Gold에 `confirmed_by_policy` 상태로 게시한다. cutoff 밖의 결과와 reorg로 대체된 이전 결과는 audit history에는 남길 수 있지만 current Gold에는 게시하지 않는다.

## 9.5 Spark SQL 처리 역할(Spark SQL Responsibilities)

Spark SQL은 아래 대량 조인과 window 계산에 사용한다.

- Best Chain block과 거래·출력 join
- `tx_input`과 `tx_output` 기반 UTXO lifecycle 구성
- 일별 이동량·공급량 aggregation
- 365일 rolling window
- staging 중복 검증과 품질 집계
- Delta Lake `MERGE` 대상 준비

로컬 환경에서는 데이터량과 실행 환경에 따라 PySpark local mode를 사용할 수 있다. 설계의 핵심은 Spark 사용 여부 자체가 아니라, 계산 계층을 raw fact·derived lifecycle·gold metric으로 분리하는 것이다.

## 9.6 Delta Lake 저장 및 갱신 전략(Delta Lake Write Strategy)

### 저장 계층

```text
Raw
- block, tx, tx_input, tx_output, utxo

Silver
- best_chain_history
- utxo_lifecycle
- daily_gross_onchain_output_volume
- daily_policy_eligible_utxo_supply

Gold
- daily_bitcoin_velocity (현재 confirmed 결과)

Audit
- daily_bitcoin_velocity_history (pending·superseded·run observation)
```

### 갱신 규칙

```text
일반 scheduled run
- 새로 게시 가능한 날짜의 staging 결과를 논리 키 기준 MERGE

rerun 또는 backfill
- 동일 metric contract logical key의 결과를 재계산 후 current Gold에 MERGE하고 audit observation을 append

reorg recovery
- 영향 날짜 범위를 staging에서 전체 재생성 후 검증하고 current Gold에 MERGE하며, 대체 전 revision을 audit history에 superseded 상태로 기록
```

단순 blind append는 retry·backfill 시 중복을 만들 수 있으므로 사용하지 않는다. 이 설계에서 “incremental”은 새 날짜 또는 영향 날짜만 계산 대상으로 삼는다는 뜻이며, 최종 적재는 논리 키 기반 upsert로 통제한다.

# 10. 데이터 품질 검증(Data Quality Validation)

## 10.1 Hard Fail 규칙

| 검증 | 실패 조건 | 처리 |
|---|---|---|
| Best Chain 연속성 | height 누락 또는 parent hash 불일치 | 게시 중단 |
| Best Chain 유일성 | 동일 `chain_revision_id`와 height에 block 2개 이상 | 게시 중단 |
| 거래·출력 키 유일성 | `(txid, vout)` 중복 | 게시 중단 |
| UTXO lifecycle | spend height가 create height 이하 | 게시 중단 |
| 기준일 공급량 | null, 음수, 0 이하 | 게시 중단 |
| rolling coverage | 365개 UTC 날짜 미충족 | 게시 중단 |
| 논리 키 중복 | Gold publish key 중복 | 게시 중단 |

## 10.2 Review Alert 규칙

| 검증 | 예시 | 처리 |
|---|---|---|
| 전일 대비 volume 급변 | 기준 임계치 초과 | alert와 검토 대상 생성 |
| 공급량 변동 이상 | 예상 발행량과 큰 차이 | alert와 검토 대상 생성 |
| dormant spent volume 급증 | 장기 미활성 UTXO 소비 급증 | alert와 해석 보조 정보 기록 |

급변은 실제 시장·온체인 이벤트일 수 있으므로 자동 hard fail이 아니라 review alert로 분리한다.

# 11. 멱등성 및 재계산 전략(Idempotency and Recomputation)

## 11.1 멱등성 정의

멱등성은 같은 `metric_date`만을 뜻하지 않는다. 아래 입력이 동일한 경우 최종 게시 상태가 하나로 수렴해야 한다.

```text
- Best Chain snapshot
- metric_definition_version
- supply_policy_version
- pipeline_code_version
- Airflow data interval
```

Reorg가 발생해 체인 상태가 바뀌면 결과가 달라지는 것은 멱등성 위반이 아니라 입력 변경에 따른 정상 재계산이다.

## 11.2 버전 분리(Version Separation)

| 버전 | 변경 대상 |
|---|---|
| `metric_definition_version` | Velocity 공식·window·variant |
| `volume_definition_version` | 분자 산정 규칙 |
| `supply_policy_version` | burn·dormancy·분모 규칙 |
| `pipeline_code_version` | 구현 로직 |
| `chain_revision_id` | 관측 체인 스냅샷 |

`calculation_version` 하나에 모든 변경 원인을 넣지 않는다. 그래야 재계산 결과가 왜 달라졌는지 분해할 수 있다.

## 11.3 게시 전 staging과 감사 로그

```text
staging
- 재계산 결과와 품질 결과를 임시 보관

publish
- 품질 통과 결과만 Gold Delta table에 MERGE

audit
- 실행 ID, input checkpoint, version, row count, quality result,
  변경된 날짜 범위, reorg 여부 기록
```

## 참고 자료(References)

- Apache Airflow — DAG Runs and Data Intervals: https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/dag-run.html
- Apache Airflow — Backfill: https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/backfill.html
- Delta Lake — MERGE: https://docs.delta.io/delta-update/
- Delta Lake — Constraints: https://docs.delta.io/delta-constraints/
