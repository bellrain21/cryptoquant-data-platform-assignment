# 2. Delta Lake 적재 설계(Delta Lake Ingestion Design)

> **문서 상태(Status)**: Draft / 구현 전 설계  
> **문서 역할(Role)**: Ethereum log observation과 current canonical log를 분리하고, schema, partition, key, incremental ingestion, data quality를 정의한다.

## 2.1 저장 계층(Storage Layers)

```text
bronze.ethereum_log_observations
= RPC에서 받은 log 관측 이력. reorg 전후 block_hash와 removed 상태를 보존.

silver.ethereum_logs_canonical
= 현재 Best Chain 기준으로 소비 가능한 current canonical log.
= dbt source와 분석 모델은 이 계층만 사용.
```

`bronze`는 append-only audit 목적이고, `silver`는 current state 목적이다. 두 역할을 하나의 MERGE key로 통합하지 않는다.

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
| `removed` | BOOLEAN | Y | provider가 제공하는 경우 reorg removal 표시 |
| `source_provider` | STRING | N | RPC provider 식별자 |
| `ingested_at` | TIMESTAMP | N | 적재 시각 |
| `data_interval_start` | TIMESTAMP | N | Airflow 처리 시작 |
| `data_interval_end` | TIMESTAMP | N | Airflow 처리 종료 |
| `schema_version` | STRING | N | schema version |
| `raw_payload` | STRING | Y | 감사·재처리를 위한 원본 JSON |

## 2.3 Silver Canonical Schema

`silver.ethereum_logs_canonical`은 Bronze observation을 현재 Best Chain checkpoint와 조인해 생성한다. Bronze의 `contract_address`는 이 계층에서 `token_contract_address`로 rename하지 않는다. token 의미는 ERC-20 decoding model에서만 부여한다.

| 컬럼 | 설명 |
|---|---|
| `chain_id`, `block_number`, `block_hash`, `block_timestamp`, `block_date` | current canonical block metadata |
| `transaction_hash`, `transaction_index`, `log_index` | event 위치 식별자 |
| `contract_address`, `topics`, `data` | event emitter 및 ABI-decoding 입력 |
| `canonical_checked_at`, `chain_revision_id` | canonical 판정 메타데이터 |
| `source_observation_key` | 원천 Bronze observation 추적 키 |

## 2.4 파티션 전략(Partition Strategy)

```text
partition column
= block_date
```

- `chain_id`는 Ethereum mainnet 단일 체인 구현에서 값이 거의 하나이므로 partition key로 쓰지 않는다.
- `transaction_hash`, `block_hash`, `contract_address`는 고카디널리티라 partition key로 쓰지 않는다.
- 로컬 과제 데이터는 작은 파일이 과도하게 생기지 않도록 일 단위 partition만 사용한다.
- 운영 규모에서는 파일 크기와 query pattern을 관찰한 뒤 compaction과 partition policy를 조정한다.

## 2.5 Key Contracts

```text
Bronze observation key
= (chain_id, block_hash, transaction_hash, log_index)

Silver canonical event key
= (chain_id, transaction_hash, log_index)
```

- Bronze key는 동일 block hash에서 같은 RPC log를 중복 append하지 않기 위한 audit key다.
- Silver key는 현재 canonical event view의 중복 방지와 current-state MERGE에 사용한다.
- 같은 transaction이 reorg 전후 다른 block hash에서 관측되면 Bronze에는 별도 observation이 남을 수 있다. Silver에는 현재 Best Chain observation 하나만 남는다.
- Delta table의 데이터베이스 강제 Primary Key에 의존하지 않는다.

## 2.6 Incremental Ingestion과 Idempotency

과제의 incremental append 요구는 신규 구간을 지속적으로 수집한다는 뜻으로 해석한다. retry와 backfill에서 blind append만 사용하면 audit layer 자체에도 동일 응답 중복이 생길 수 있다.

```text
1. observation staging
- 이번 block range에서 수집한 로그를 정규화
- Bronze observation key 중복 제거
- source completeness 및 필수 형식 검증

2. Bronze append
- 품질 통과 observation만 append
- 기존 Bronze observation key는 재삽입하지 않음

3. canonical refresh
- 최근 lookback 또는 reorg 영향 range의 Best Chain block hash를 갱신
- current canonical event key 기준 MERGE
- orphan block event는 Silver에서 제외하고 Bronze에만 유지
```

이 방식은 새 log observation의 incremental 적재를 유지하면서도, reorg 감사 이력과 consumer-facing canonical uniqueness를 동시에 보장한다.

## 2.7 품질 규칙(Data Quality Rules)

| 검증 | 실패 조건 | 처리 |
|---|---|---|
| block range 완전성 | chunk 간 gap 또는 overlap | hard fail |
| Bronze observation key 유일성 | staging key 중복 | hard fail |
| Silver canonical event key 유일성 | canonical refresh 결과 key 중복 | hard fail |
| 필수 필드 | block hash, tx hash, log index, address null | hard fail |
| block hash 정합성 | 같은 canonical height에 current Best Chain hash와 다른 row가 남음 | reorg recovery |
| topic format | topic이 `0x` + 64 hex 형식이 아님 | hard fail |
| timestamp | block timestamp가 interval과 불일치 | review alert |

## 2.8 구현 검증 체크리스트

- [ ] Bronze / Silver table 생성 및 schema 확인
- [ ] 동일 block range 두 번 실행 후 Bronze observation key 중복 0건
- [ ] canonical refresh 후 Silver canonical event key 중복 0건
- [ ] 1시간 단위 신규 구간 적재
- [ ] 실패 chunk 재시도
- [ ] block_date partition 기반 조회
- [ ] raw payload와 정규화 컬럼의 표본 대조
- [ ] reorg fixture에서 Bronze 이력 보존과 Silver 교체를 함께 검증

## 참고 자료

- Ethereum JSON-RPC: https://ethereum.org/developers/docs/apis/json-rpc/
- Geth — Real-time Events: https://geth.ethereum.org/docs/interacting-with-geth/rpc/pubsub
- Delta Lake — MERGE: https://docs.delta.io/delta-update/
- Delta Lake — Constraints: https://docs.delta.io/delta-constraints/
- Delta Lake — Partitioning Best Practices: https://docs.delta.io/best-practices/
