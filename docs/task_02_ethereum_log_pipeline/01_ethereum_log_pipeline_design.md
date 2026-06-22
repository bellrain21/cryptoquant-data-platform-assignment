# 1. Ethereum 로그 수집 DAG 설계(Ethereum Log Ingestion DAG Design)

> Reference / exploratory design — not the current implementation source of truth.
> 현재 구현은 finality buffer와 idempotent raw append 중심이며, 이 문서의 observation/canonical reorg 전이 설계 전체를 구현했다고 주장하지 않습니다.

> **문서 상태(Status)**: Legacy draft / 구현 전 확장 설계 메모
> **문서 역할(Role)**: `eth_getLogs` 기반 1시간 수집, block range 계산, retry, backfill, reorg 상태 전이 후보를 정리합니다.
> 현재 실행 기준은 `README.md`, `docs/01_system_architecture.md`, `docs/04_failure_retry_backfill_strategy.md`입니다.

## 1.1 수집 범위(Collection Scope)

- 대상 체인: Ethereum mainnet
- 수집 API: `eth_getLogs`
- 기본 처리 단위: 1시간 Airflow data interval
- 초기 실행 범위: 최근 24시간에서 7일 사이의 제한된 기간
- 전체 이력 backfill: 과제 기본 범위에서 제외
- 임의 날짜 backfill: 동일 DAG의 data interval 또는 입력 파라미터로 지원

## 1.2 수집 상한과 안정성 정책(Collection Upper Bound and Stability Policy)

최근 head를 즉시 canonical source로 취급하면 reorg churn과 반복 재처리가 커집니다. 따라서 수집 상한은 아래 우선순위로 결정합니다.

```text
collection_upper_bound
= provider가 지원하는 safe block
  또는 latest block - reorg_lookback_blocks
```

- `safe block`: provider가 `safe` block tag를 지원할 때 사용합니다.
- `reorg_lookback_blocks`: provider의 safe head를 사용할 수 없을 때, 최근 불안정 구간을 재검증하기 위해 latest head에서 제외하는 운영 파라미터입니다.
- backfill: 과거 interval은 위 상한보다 충분히 이전인 경우 그대로 처리합니다. 아직 안정 구간에 들어오지 않은 최신 interval은 다음 scheduled run에서 다시 평가합니다.
- reorg 감지 시에는 일반 lookback보다 넓은 `affected_from_block ~ affected_to_block` 범위를 우선 사용합니다.

## 1.3 시간 구간에서 Block Range로 변환(Time-to-block Range Resolution)

Ethereum 표준 JSON-RPC는 timestamp를 block number로 직접 변환하는 표준 메서드를 제공하지 않습니다. 따라서 아래 절차를 사용합니다.

```text
1. data_interval_start, data_interval_end를 UTC로 확정
2. collection_upper_bound를 확정
3. eth_getBlockByNumber으로 block timestamp 조회
4. binary search 또는 checkpoint index로
   interval start 이상인 첫 block과
   interval end 미만이면서 collection_upper_bound 이하인 마지막 block을 탐색
5. [from_block, to_block]을 provider 허용 범위에 맞춰 chunk
6. 각 chunk에 eth_getLogs 호출
```

검색 결과는 block number 기준으로 정렬하고, 인접 chunk가 겹치거나 비지 않는지 검증합니다.

## 1.4 DAG 처리 흐름(DAG Flow)

```text
resolve_interval
  → resolve_block_range
  → split_block_range
  → fetch_logs_for_chunk
  → normalize_and_deduplicate_observations
  → stage_observations
  → validate_staging_quality
  → append_observations
  → refresh_canonical_log_view
  → post_merge_reconciliation
  → trigger_dbt_build
  → record_audit
```

`validate_staging_quality`는 publish 전 차단용 검증입니다. `post_merge_reconciliation`은 append 및 canonical refresh 이후
row count, canonical uniqueness, 최근 block hash 상태를 확인하는 사후 검증입니다.

## 1.5 RPC 재시도와 Adaptive Chunking

| 실패 유형 | 예시 | 대응 |
|---|---|---|
| 일시적 네트워크 오류 | timeout, connection reset | exponential backoff retry |
| rate limit | HTTP 429 또는 provider-specific error | backoff와 concurrency 감소 |
| block range 제한 | response too large, range too wide | chunk size 축소 후 재시도 |
| 영구 요청 오류 | malformed parameter, invalid chain ID | 즉시 fail 및 설정 검토 |
| 일부 chunk 실패 | 특정 block range failure | 실패 chunk만 재시도·backfill |

retry는 전체 시간 구간을 blind re-run하지 않습니다. 실패한 chunk와 실패 원인을 audit record에 남기고 해당 chunk만 재처리합니다.

## 1.6 멱등성과 Backfill(Idempotency and Backfill)

동일한 시간 구간은 scheduled run, rerun, backfill에서 동일한 변환·적재 경로를 사용합니다.

```text
Airflow data interval
= business range

block range
= data interval을 결정론적으로 변환한 수집 범위

observation_state
= observed | removed

observation key
= chain_id + block_hash + transaction_hash + log_index + observation_state

canonical event key
= chain_id + transaction_hash + log_index
```

동일 RPC 응답의 재수집은 observation key로 중복을 제거합니다. `removed`가 누락되거나 false인 관측은 `observed`, `removed=true` 관측은 `removed`로 정규화합니다. 

따라서, 같은 raw log의 정상 관측과 reorg removal 관측은 서로 다른 audit observation으로 보존되고, 같은 상태의 retry만 중복 제거됩니다.

canonical event는 현재 Best Chain에 속한 `observed` observation만 대상으로 합니다. reorg 영향 범위에서는 단순 MERGE만 수행하지 않고, 해당 범위의 canonical source 전체를 기준으로 stale target row를 삭제한 뒤 현재 event를 반영합니다. 

따라서, retry·backfill은 audit 이력을 잃지 않고 consumer-facing view는 중복 없이 현재 체인 상태로 수렴합니다.

## 1.7 Reorg 고려사항(Reorg State Handling)

Ethereum도 reorg 가능성이 있습니다. observation layer는 `block_hash`, `block_number`, `removed`를 보존하며, canonical view와 분리합니다.

```text
bronze.ethereum_log_observations
= 모든 RPC log observation의 append-only audit layer

silver.ethereum_logs_canonical
= 현재 Best Chain에 속한 log만 제공하는 current view/table
```

과제의 dbt 입력 모델명은 `ethereum_logs`로 두되, 실제 relation은 `silver.ethereum_logs_canonical`으로 매핑합니다.
이 매핑은 요구사항의 모델 체인 표기와 reorg-safe 소비 계층을 동시에 만족시키기 위한 것입니다.

reorg가 감지되면 다음 순서로 처리합니다.

```text
1. 최근 checkpoint의 block_hash와 current chain hash를 비교
2. 불일치 시 common ancestor 탐색
3. affected_from_block = common_ancestor_height + 1
4. affected_to_block = max(previous_canonical_tip_height, current_best_chain_tip_height)
5. affected range의 Best Chain block hash와 log를 다시 조회
6. orphan block 관측값과 removed 관측값은 Bronze에 append-only로 보존
7. affected range의 현재 canonical source 전체를 stage한다
8. Silver target에서 affected range에만 존재하고 stage source에는 없는 stale row를 DELETE한다
9. stage source의 현재 Best Chain event를 canonical event key로 MERGE한다
10. 영향 block_date partition을 dbt incremental rebuild 대상으로 전달한다
```

Silver의 bounded reconciliation은 아래 의미를 가집니다.

```text
MERGE target USING staged_current_canonical_source
ON canonical event key
WHEN MATCHED THEN UPDATE
WHEN NOT MATCHED THEN INSERT
WHEN NOT MATCHED BY SOURCE
  AND target.block_number BETWEEN affected_from_block AND affected_to_block
THEN DELETE
```

`WHEN NOT MATCHED BY SOURCE ... DELETE`를 지원하지 않는 실행 환경에서는 같은 영향을 갖도록 affected range의 Silver row를 먼저 DELETE한 뒤 stage source를 INSERT 또는 MERGE합니다. 

전 테이블 삭제는 금지하고, 반드시 common ancestor 이후 범위로 한정합니다.

provider가 `removed=true`를 제공하면 이를 `removed` observation state로 보존합니다. 그러나 polling 기반 `eth_getLogs` 수집에서는 이 플래그만을 reorg 감지의 유일한 근거로 사용하지 않고 block hash reconciliation을 함께 사용합니다.

## 1.8 구현 검증 체크리스트

아래 체크리스트는 historical 확장 설계와 현재 구현 증거를 대조한 결과입니다. 현재 구현의 source of truth는 `airflow/dags/ethereum_hourly_logs.py`,
`src/cryptoquant_pipeline/`, `docs/05_validation_evidence.md`입니다.

- [x] 1시간 data interval이 UTC 기준으로 고정됨
  - 근거: `airflow/dags/ethereum_hourly_logs.py`, Airflow task log `scheduled__2026-06-20T21:00:00+00:00`부터
    `scheduled__2026-06-22T08:00:00+00:00`까지 successful scheduled 반환값 33건.
- [x] 시간 범위가 연속된 block range로 변환됨
  - 근거: `src/cryptoquant_pipeline/block_range.py`, `tests/test_block_range.py`, task log의 `from_block`/`to_block`.
- [x] provider range limit 오류 시 chunk가 축소됨
  - 근거: `src/cryptoquant_pipeline/log_collector.py`, `tests/test_rpc_retry.py`, `tests/test_chunking.py`.
- [x] 동일 구간 재실행 시 raw Delta natural key 중복이 없습니다.
  - 근거: `src/cryptoquant_pipeline/delta_writer.py`, `tests/test_delta_idempotency.py`, `tests/test_pipeline_idempotency.py`.
- [ ] 같은 raw log의 observed / removed 관측이 각각 감사 이력으로 보존됨
  - 미완료 사유: 현재 구현은 Bronze observation history layer를 만들지 않고 raw `removed`, `block_hash` 필드를 보존합니다.
- [ ] canonical view에서 canonical event key 중복이 없습니다.
  - 미완료 사유: 현재 구현은 별도 Silver canonical view가 아니라 raw Delta natural key와 dbt incremental unique key를 사용합니다.
- [ ] reorg 영향 범위에서 source에 없는 orphan canonical row가 Silver에서 제거됨
  - 미완료 사유: common ancestor 기반 canonical replacement는 구현하지 않았습니다.
- [x] 임의 과거 interval backfill이 같은 DAG 경로를 사용합니다
  - 근거: `airflow/dags/ethereum_hourly_logs.py`가 `data_interval_start`/`data_interval_end`와 DAG run conf
    `window_start`/`window_end`를 같은 `run_interval()` 경로로 처리합니다. 실제 대량 backfill은 비용 영향 때문에 실행하지 않았습니다.
- [ ] reorg fixture 또는 block hash mismatch로 canonical refresh를 검증했습니다
  - 미완료 사유: reorg replacement fixture와 canonical refresh 구현이 없습니다.
- [x] RPC key와 endpoint가 `.env`에서 주입되고 Git에 포함되지 않음
  - 근거: `.gitignore`, `.env.example`, `docs/05_validation_evidence.md`의 secret 미노출 검증.

## 참고 자료

- Ethereum JSON-RPC: https://ethereum.org/developers/docs/apis/json-rpc/
- Geth — Real-time Events: https://geth.ethereum.org/docs/interacting-with-geth/rpc/pubsub
- Apache Airflow — DAG Runs: https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/dag-run.html
- Apache Airflow — Backfill: https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/backfill.html
