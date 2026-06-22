# 04. Failure And Backfill Strategy

> 상태: 운영/복구 정책 문서
> 읽는 법: RPC 실패 -> range split -> Airflow retry -> backfill/replay 순서로 확인.

## RPC timeout

HTTP timeout은 `ETH_RPC_TIMEOUT_SECONDS`로 제한합니다. timeout은 retryable로 분류하고, `ETH_RPC_MAX_RETRIES` 범위 안에서 먼저 재시도합니다. `eth_getLogs`에서 timeout이 계속되면 block range split 대상입니다.

## Rate limit

HTTP 429 또는 provider message의 rate limit은 retryable error입니다. RPC client의 bounded retry 후에도 실패하면 Airflow task retry가 outer retry로 처리합니다. API key와 full RPC URL은 로그에 남기지 않습니다.

## Too many results

Provider가 `too many results`, `query returned more than allowed`, `range too large`를 반환하면 range를 반으로 나눔.

```text
[100, 199] 실패
  -> [100, 149]
  -> [150, 199]
```

단일 block에서도 실패하면 failed subrange를 기록하고 DAG를 실패시킴.

## Airflow retry

현재 DAG default:

```text
retries=5
retry_delay=5 minutes
retry_exponential_backoff=True
max_active_runs=1
```

RPC client 내부 retry는 짧은 HTTP/transport 흔들림을 처리하고, Airflow retry는 task 전체 재실행 경계입니다. `too many results`, `range too large`는 같은 요청 반복보다 range split이 맞으므로 즉시 상위로 올립니다.

## Backfill

Backfill은 Airflow logical interval 기준입니다. 코드가 현재 시각으로 수집 경계를 만들지 않으므로 과거 구간 재실행이 가능합니다.

```powershell
docker compose run --rm airflow-scheduler airflow dags backfill ethereum_hourly_logs `
  --start-date 2026-06-15T00:00:00+00:00 `
  --end-date 2026-06-16T00:00:00+00:00
```

## Idempotent replay

Delta write는 다음 중복을 skip합니다.

- 같은 batch 내부 중복.
- 기존 Delta table에 이미 있는 `chain_id + transaction_hash + log_index`.

따라서 retry와 backfill이 같은 raw log를 다시 가져와도 row count가 증가하지 않아야 합니다.

## 실행 증거와 해석 한계

| 증거 | 확인 내용 | 상태 |
|---|---|---|
| `tests/test_rpc_retry.py`, `tests/test_pipeline_idempotency.py` | retry, split, replay idempotency의 mock/fixture 검증 | VERIFIED |
| `src/notebooks/03_fixture_etl_replay_idempotency_validation.ipynb` | 같은 fixture batch 재실행 시 `second_inserted_row_count=0`, duplicate key 0 | VERIFIED |
| `data/imgs/task_02_03_image.png` | failed `run_interval` task instance 13건 | PARTIALLY VERIFIED |
| `data/imgs/task_02_04_image.png` | success DAG run 47건 | PARTIALLY VERIFIED |

Airflow UI screenshot은 성공과 실패 이력이 존재한다는 점을 보여줍니다. 그러나 각 실패의 원인, retry 횟수, provider 응답, 최신 raw schema 정합성은 task log, unit test, notebook, dbt build 결과와 함께 확인해야 합니다.

## Finality/reorg 제한

수집 전 `eth_getBlockByNumber("finalized", false)`를 조회합니다. finalized block timestamp가 interval end보다 이르면 `RetryableIntervalNotFinalized`로 실패시켜 Airflow retry가 재처리하게 합니다. 장기 reorg에서 이미 저장된 raw row를 canonical replacement하는 기능은 현재 범위 밖입니다. 이 제한은 숨기지 않고 문서화합니다.

## 구현 및 검증 체크리스트

- [x] retry 가능한 RPC 실패와 즉시 실패해야 하는 계약 오류가 코드에서 분리되어 있습니다.
  - 근거: `src/cryptoquant_pipeline/exceptions.py`, `src/cryptoquant_pipeline/rpc_client.py`, `airflow/dags/ethereum_hourly_logs.py`

- [x] backfill과 replay가 Airflow logical interval 기준으로 설명되어 있습니다.
  - 근거: `airflow/dags/ethereum_hourly_logs.py`, 이 문서의 Backfill 섹션

- [x] Delta replay idempotency가 코드와 테스트에 연결되어 있습니다.
  - 근거: `src/cryptoquant_pipeline/delta_writer.py`, `tests/test_pipeline_idempotency.py`

- [ ] canonical reorg replacement를 구현하고 검증했습니다.
  - 미완료 사유: 현재 구현은 finality buffer와 raw `block_hash` 보존까지입니다.

- [x] 요구사항 추적표 상태를 갱신했습니다.
  - 경로: `docs/09_requirement_traceability_matrix.md`
