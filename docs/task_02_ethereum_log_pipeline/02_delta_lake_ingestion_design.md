# 2. Delta Lake 적재 설계(Delta Lake Ingestion Design)

> Reference / exploratory design — not the current implementation source of truth.
> 현재 구현은 단일 raw Delta table과 retry/backfill dedup 중심이며, 이 문서의 canonical replacement 설계 전체를 구현했다고 주장하지 않습니다.

> **문서 상태(Status)**: Legacy draft / 구현 전 확장 설계 메모
> **문서 역할(Role)**: Ethereum log observation과 current canonical log 분리 후보를 정리합니다.
> 현재 실행 기준은 raw Delta `ethereum_logs` 단일 table과 `docs/02_data_contracts.md`입니다.

## 2.1 저장 계층(Storage Layers)

```text
bronze.ethereum_log_observations
= RPC에서 받은 log 관측 이력. reorg 전후 block_hash와 removed 상태를 보존.

silver.ethereum_logs_canonical
= 현재 Best Chain 기준으로 소비 가능한 current canonical log.
= dbt source `ethereum_logs`와 분석 모델은 이 계층만 사용.
```

과제 요구사항의 `ethereum_logs`는 dbt source 이름으로 유지하며, physical relation은 이 `silver.ethereum_logs_canonical`이다.
Bronze observation은 감사·복구 입력이고 dbt 분석 source가 아닙니다.

`bronze`는 append-only audit 목적이고, `silver`는 current state 목적이다. 두 역할을 하나의 MERGE key로 통합하지 않습니다.

## 2.2 Bronze Observation Schema

| 컬럼 | 타입 예시 | Null 허용 | 설명 |
|---|---|---:|---|
| `chain_id` | BIGINT | N | chain 식별자 |
| `block_number` | BIGINT | N | 로그가 포함된 block number |
| `block_hash` | STRING | N | 관측 당시 로그가 속한 block hash |
| `block_timestamp` | TIMESTAMP | N | block timestamp |
| `block_date` | DATE | N | partition 및 날짜 필터용 파생 컬럼 |
| `transaction_hash` | STRING | N | transaction hash |
| `transaction_index` | BIGINT | Y | **block 내부** transaction 순서 |
| `log_index` | BIGINT | N | **block 내부** log 순서 |
| `contract_address` | STRING | N | event emitter contract address |
| `topics` | ARRAY<STRING> | N | indexed topic 배열 |
| `data` | STRING | N | non-indexed event data |
| `removed` | BOOLEAN | Y | provider 원본의 reorg removal 플래그. 누락 가능 |
| `observation_state` | STRING | N | 파생 상태. `removed=true`이면 `removed`, 그 외에는 `observed` |
| `source_provider` | STRING | N | RPC provider 식별자 |
| `ingested_at` | TIMESTAMP | N | 적재 시각 |
| `data_interval_start` | TIMESTAMP | N | Airflow 처리 시작 |
| `data_interval_end` | TIMESTAMP | N | Airflow 처리 종료 |
| `schema_version` | STRING | N | schema version |
| `raw_payload` | STRING | Y | 감사·재처리를 위한 원본 JSON |

## 2.3 Silver Canonical Schema

`silver.ethereum_logs_canonical`은 Bronze observation을 현재 Best Chain checkpoint와 조인해 생성합니다.
Bronze의 `contract_address`는 이 계층에서 `token_contract_address`로 rename하지 않습니다.
token 의미는 ERC-20 decoding model에서만 부여합니다.

| 컬럼 | 설명 |
|---|---|
| `chain_id`, `block_number`, `block_hash`, `block_timestamp`, `block_date` | current canonical block metadata |
| `transaction_hash`, `transaction_index`, `log_index` | event 위치 식별자 |
| `contract_address`, `topics`, `data` | event emitter 및 ABI-decoding 입력 |
| `canonical_checked_at`, `chain_revision_id` | canonical 판정 메타데이터 |
| `source_observation_key` | `(chain_id, block_hash, transaction_hash, log_index, observation_state)` 형태의 원천 Bronze 추적 키 |

## 2.4 파티션 전략(Partition Strategy)

```text
partition column
= block_date
```

- `chain_id`는 Ethereum mainnet 단일 체인 구현에서 값이 거의 하나이므로 partition key로 쓰지 않습니다.
- `transaction_hash`, `block_hash`, `contract_address`는 고카디널리티라 partition key로 쓰지 않습니다.
- 로컬 과제 데이터는 작은 파일이 과도하게 생기지 않도록 일 단위 partition만 사용합니다.
- 운영 규모에서는 파일 크기와 query pattern을 관찰한 뒤 compaction과 partition policy를 조정합니다.

## 2.5 Key Contracts

```text
Bronze observation state
= observed | removed

Bronze observation key
= (chain_id, block_hash, transaction_hash, log_index, observation_state)

Silver canonical event key
= (chain_id, transaction_hash, log_index)
```

- `observation_state`는 `removed=true`이면 `removed`, `removed`가 false 또는 누락이면 `observed`로 정규화합니다.
- Bronze key는 동일 block hash와 같은 관측 상태에서 같은 RPC log를 중복 append하지 않기 위한 audit key입니다.
- 같은 log의 정상 관측과 reorg removal 관측은 상태가 다르므로 Bronze에서 각각 보존됩니다.
- Silver key는 현재 canonical event view의 중복 방지와 current-state 갱신에 사용합니다.
- 같은 transaction이 reorg 전후 다른 block hash 또는 log index로 관측될 수 있습니다. Silver는 bounded reconciliation 이후 현재 Best Chain observation만 남깁니다.
- Delta table의 데이터베이스 강제 Primary Key에 의존하지 않습니다.

## 2.6 Incremental Ingestion과 Idempotency

과제의 incremental append 요구는 신규 구간을 지속적으로 수집한다는 뜻으로 해석합니다. retry와 backfill에서 blind append만 사용하면 audit layer 자체에도 동일 응답 중복이 생길 수 있습니다.

```text
1. observation staging
- 이번 block range에서 수집한 로그를 정규화
- Bronze observation key 중복 제거
- source completeness 및 필수 형식 검증

2. Bronze append
- 품질 통과 observation만 append
- 기존 Bronze observation key는 재삽입하지 않습니다.

3. canonical refresh와 bounded reconciliation
- 일반 run은 `reorg_lookback_blocks` 범위, reorg 감지 run은 common ancestor 이후 `affected_from_block ~ affected_to_block` 범위를 대상으로 합니다.
- 해당 범위의 current Best Chain block hash와 `observation_state = observed` 조건으로 staged canonical source를 만든다.
- Silver target의 같은 범위에서 stage source에 없는 row는 delete합니다. 이 단계가 없으면 reorg로 orphan이 된 row가 MERGE 후에도 남는다.
- stage source의 event는 canonical event key 기준으로 MERGE합니다.
- orphan block event와 removed observation은 Bronze에만 append-only로 유지합니다.
```

canonical reconciliation 의사 SQL:

```sql
MERGE INTO silver.ethereum_logs_canonical AS target
USING staged_current_canonical_logs AS source
ON  target.chain_id = source.chain_id
AND target.transaction_hash = source.transaction_hash
AND target.log_index = source.log_index
WHEN MATCHED THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *
WHEN NOT MATCHED BY SOURCE
  AND target.block_number BETWEEN :affected_from_block AND :affected_to_block
THEN DELETE;
```

`WHEN NOT MATCHED BY SOURCE ... DELETE`를 지원하지 않는 런타임은 affected range의 Silver row를 먼저 DELETE하고 stage source를
INSERT 또는 MERGE합니다. 삭제 범위는 common ancestor 이후로 한정합니다.

이 방식은 새 log observation의 incremental 적재를 유지하면서도, reorg 감사 이력과 consumer-facing canonical uniqueness를 동시에 만족시키는 것을 목표로 합니다.

## 2.7 품질 규칙(Data Quality Rules)

| 검증 | 실패 조건 | 처리 |
|---|---|---|
| block range 완전성 | chunk 간 gap 또는 overlap | hard fail |
| Bronze observation key 유일성 | 같은 observation state의 staging key 중복 | hard fail |
| observation state 정규화 | `removed`와 `observation_state`가 불일치 | hard fail |
| Silver canonical event key 유일성 | canonical refresh 결과 key 중복 | hard fail |
| 필수 필드 | block hash, tx hash, log index, address null | hard fail |
| block hash 정합성 | 같은 canonical height에 current Best Chain hash와 다른 row가 남아 있음 | reorg recovery |
| topic format | topic이 `0x` + 64 hex 형식이 아님 | hard fail |
| timestamp | block timestamp가 interval과 불일치 | review alert |

## 2.8 구현 검증 체크리스트

아래 체크리스트는 historical Bronze/Silver 설계와 현재 raw Delta 구현을 분리해 판정합니다.

- [ ] Bronze / Silver table 생성 및 schema 확인
  - 미완료 사유: 현재 구현은 `ethereum_logs` raw Delta table과 dbt 모델 계층을 사용하며 별도 Bronze/Silver Delta table을 만들지 않습니다.
- [ ] 동일 block range 두 번 실행 후 같은 observation state의 Bronze observation key 중복 0건
  - 미완료 사유: Bronze observation key는 구현하지 않았습니다. 현재 검증된 중복 방지 기준은 `chain_id + transaction_hash + log_index`입니다.
- [ ] 같은 raw log의 observed / removed 관측을 Bronze에 각각 보존
  - 미완료 사유: observation history table은 없습니다. raw `removed` 필드는 schema에 보존합니다.
- [ ] canonical refresh 후 Silver canonical event key 중복 0건
  - 미완료 사유: Silver canonical refresh layer가 없습니다. dbt `unique_log_identity.sql`과 incremental unique key로 downstream 중복을 검증합니다.
- [ ] reorg fixture에서 affected range의 orphan Silver row가 실제로 삭제됨
  - 미완료 사유: canonical replacement와 orphan delete는 구현하지 않았습니다.
- [x] 1시간 단위 신규 구간 적재
  - 근거: Airflow task log 기준 successful scheduled 반환값 33건, 최신 `row_count_after=6082932`.
- [x] 실패 chunk 재시도
  - 근거: `tests/test_rpc_retry.py`, `src/cryptoquant_pipeline/log_collector.py`.
- [x] block_date partition 기반 조회
  - 근거: `src/cryptoquant_pipeline/delta_writer.py`의 `PARTITION_COLUMNS = ["block_date_utc"]`, `docs/02_data_contracts.md`.
- [x] raw payload와 정규화 컬럼의 표본 대조
- 근거: `src/notebooks/03_fixture_etl_replay_idempotency_validation.ipynb`,
  `src/notebooks/04_accumulated_pipeline_data_freshness_validation.ipynb`,
  `tests/test_log_normalizer.py`.
- [ ] reorg fixture에서 Bronze 이력 보존과 Silver 교체를 함께 검증
  - 미완료 사유: Bronze/Silver reorg fixture는 구현하지 않았습니다.

## 참고 자료

- Ethereum JSON-RPC: https://ethereum.org/developers/docs/apis/json-rpc/
- Geth — Real-time Events: https://geth.ethereum.org/docs/interacting-with-geth/rpc/pubsub
- Delta Lake — MERGE: https://docs.delta.io/delta-update/
- Delta Lake — Constraints: https://docs.delta.io/delta-constraints/
- Delta Lake — Partitioning Best Practices: https://docs.delta.io/best-practices/
