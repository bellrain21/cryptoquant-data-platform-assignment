# 1. Ethereum 로그 수집 DAG 설계(Ethereum Log Ingestion DAG Design)

> **문서 상태(Status)**: Draft / 구현 전 설계  
> **문서 역할(Role)**: `eth_getLogs` 기반 1시간 수집, block range 계산, retry, backfill 계약을 정의한다.

## 1.1 수집 범위(Collection Scope)

- 대상 체인: Ethereum mainnet
- 수집 API: `eth_getLogs`
- 기본 처리 단위: 1시간 Airflow data interval
- 초기 실행 범위: 최근 24시간에서 7일 사이의 제한된 기간
- 전체 이력 backfill: 과제 기본 범위에서 제외
- 임의 날짜 backfill: 동일 DAG의 data interval 또는 입력 파라미터로 지원

## 1.2 시간 구간에서 Block Range로 변환(Time-to-block Range Resolution)

Ethereum 표준 JSON-RPC는 timestamp를 block number로 직접 변환하는 표준 메서드를 제공하지 않는다. 따라서 아래 절차를 사용한다.

```text
1. data_interval_start, data_interval_end를 UTC로 확정
2. eth_blockNumber으로 현재 상한 block 확인
3. eth_getBlockByNumber으로 block timestamp 조회
4. binary search 또는 checkpoint index로
   interval start 이상인 첫 block과
   interval end 미만인 마지막 block을 탐색
5. [from_block, to_block]을 provider 허용 범위에 맞춰 chunk
6. 각 chunk에 eth_getLogs 호출
```

검색 결과는 block number 기준으로 정렬하고, 인접 chunk가 겹치거나 비지 않는지 검증한다.

## 1.3 DAG 처리 흐름(DAG Flow)

```text
resolve_interval
  → resolve_block_range
  → split_block_range
  → fetch_logs_for_chunk
  → normalize_and_deduplicate
  → stage_delta_rows
  → merge_delta_rows
  → run_quality_checks
  → trigger_dbt_build
  → record_audit
```

## 1.4 RPC 재시도와 Adaptive Chunking

| 실패 유형 | 예시 | 대응 |
|---|---|---|
| 일시적 네트워크 오류 | timeout, connection reset | exponential backoff retry |
| rate limit | HTTP 429 또는 provider-specific error | backoff와 concurrency 감소 |
| block range 제한 | response too large, range too wide | chunk size 축소 후 재시도 |
| 영구 요청 오류 | malformed parameter, invalid chain ID | 즉시 fail 및 설정 검토 |
| 일부 chunk 실패 | 특정 block range failure | 실패 chunk만 재시도·backfill |

retry는 전체 시간 구간을 blind re-run하지 않는다. 실패한 chunk와 실패 원인을 audit record에 남기고 해당 chunk만 재처리한다.

## 1.5 멱등성과 Backfill(Idempotency and Backfill)

동일한 시간 구간은 scheduled run, rerun, backfill에서 동일한 변환·적재 경로를 사용한다.

```text
Airflow data interval
= business range

block range
= data interval을 결정론적으로 변환한 수집 범위

logical event key
= chain_id + transaction_hash + log_index
```

각 staging batch에서 key 중복을 먼저 제거하고, Delta target에는 logical key 기준으로 MERGE한다. 재실행은 같은 로그를 새로 append하는 것이 아니라 기존 논리 이벤트를 갱신하거나 유지하는 방식으로 최종 상태를 수렴시킨다.

## 1.6 Reorg 고려사항

과제 요구의 핵심은 log 수집·중복 방지지만, Ethereum도 reorg 가능성이 있다. 따라서 raw log에는 최소한 `block_hash`와 `block_number`를 보존한다.

```text
current canonical event key
= chain_id + transaction_hash + log_index

observed log audit key
= chain_id + block_hash + transaction_hash + log_index
```

재조직이 감지되면 canonical target은 current event key 기준으로 block metadata를 갱신하고, 이전 block hash 관측 기록은 audit layer에 보존한다.

## 1.7 구현 검증 체크리스트

- [ ] 1시간 data interval이 UTC 기준으로 고정됨
- [ ] 시간 범위가 연속된 block range로 변환됨
- [ ] provider range limit 오류 시 chunk가 축소됨
- [ ] 동일 구간 재실행 시 target duplicate가 없음
- [ ] 임의 과거 interval backfill이 같은 DAG 경로를 사용함
- [ ] RPC key와 endpoint가 `.env`에서 주입되고 Git에 포함되지 않음

## 참고 자료

- Ethereum JSON-RPC: https://ethereum.org/developers/docs/apis/json-rpc/
- Apache Airflow — DAG Runs: https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/dag-run.html
- Apache Airflow — Backfill: https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/backfill.html
