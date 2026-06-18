# 2. Delta Lake 적재 설계(Delta Lake Ingestion Design)

> **문서 상태(Status)**: Draft / 구현 전 설계  
> **문서 역할(Role)**: Ethereum log schema, partition, logical key, incremental ingestion, data quality를 정의한다.

## 2.1 대상 테이블(Target Table)

```text
bronze.ethereum_logs
```

이 테이블은 RPC 원본 로그에서 분석에 필요한 필드를 정규화한 Bronze layer다. 원본 JSON 전체는 필요에 따라 `raw_payload`에 보존할 수 있으나, 분석 필드는 별도 컬럼으로 분리한다.

## 2.2 스키마(Schema)

| 컬럼 | 타입 예시 | Null 허용 | 설명 |
|---|---|---:|---|
| `chain_id` | BIGINT | N | chain 식별자 |
| `block_number` | BIGINT | N | 로그가 포함된 block number |
| `block_hash` | STRING | N | block hash |
| `block_timestamp` | TIMESTAMP | N | block timestamp |
| `block_date` | DATE | N | partition 및 날짜 필터용 파생 컬럼 |
| `transaction_hash` | STRING | N | transaction hash |
| `transaction_index` | BIGINT | Y | transaction 내 순서 |
| `log_index` | BIGINT | N | transaction 내 log 순서 |
| `contract_address` | STRING | N | event emitter contract |
| `topics` | ARRAY<STRING> | N | indexed topic 배열 |
| `data` | STRING | N | non-indexed event data |
| `removed` | BOOLEAN | Y | provider가 제공하는 경우 reorg removal 표시 |
| `source_provider` | STRING | N | RPC provider 식별자 |
| `ingested_at` | TIMESTAMP | N | 적재 시각 |
| `data_interval_start` | TIMESTAMP | N | Airflow 처리 시작 |
| `data_interval_end` | TIMESTAMP | N | Airflow 처리 종료 |
| `schema_version` | STRING | N | schema version |
| `raw_payload` | STRING | Y | 감사·재처리를 위한 원본 JSON |

## 2.3 파티션 전략(Partition Strategy)

```text
partition column
= block_date
```

- `chain_id`는 Ethereum mainnet 단일 체인 구현에서 값이 거의 하나이므로 partition key로 쓰지 않는다.
- `transaction_hash`, `block_hash`, `contract_address`는 고카디널리티라 partition key로 쓰지 않는다.
- 로컬 과제 데이터는 작은 파일이 과도하게 생기지 않도록 일 단위 partition만 사용한다.
- 운영 규모에서는 파일 크기와 query pattern을 관찰한 뒤 compaction과 partition policy를 조정한다.

## 2.4 논리 키(Logical Key)와 감사 키(Audit Key)

```text
current canonical event logical key
=
(chain_id, transaction_hash, log_index)

observed log audit key
=
(chain_id, block_hash, transaction_hash, log_index)
```

- logical key는 현재 canonical event view의 중복 방지와 upsert에 사용한다.
- audit key는 reorg 전후 block location 관측을 보존하는 데 사용한다.
- Delta table의 데이터베이스 강제 Primary Key에 의존하지 않는다.

## 2.5 Incremental Ingestion과 Idempotency

과제의 incremental append 요구는 신규 구간을 지속적으로 수집한다는 뜻으로 해석한다. 그러나 retry와 backfill에서 blind append만 사용하면 중복이 생긴다.

따라서 아래 2단계로 구성한다.

```text
1. staging
- 이번 block range에서 수집한 로그를 정규화
- logical key 중복 제거
- source completeness 확인

2. target merge
- target logical key와 matching
- 기존 event는 update 또는 유지
- 신규 event만 insert
```

이 방식은 신규 데이터가 중심인 incremental ingestion을 유지하면서도 재실행 시 중복을 막는다.

## 2.6 품질 규칙(Data Quality Rules)

| 검증 | 실패 조건 | 처리 |
|---|---|---|
| block range 완전성 | chunk 간 gap 또는 overlap | hard fail |
| event key 유일성 | staging logical key 중복 | hard fail |
| 필수 필드 | block hash, tx hash, log index, address null | hard fail |
| chain consistency | 동일 block number에 예상 밖의 hash 충돌 | review 또는 reorg recovery |
| topic format | topic이 `0x` + 64 hex 형식이 아님 | hard fail |
| timestamp | block timestamp가 interval과 불일치 | review alert |

## 2.7 구현 검증 체크리스트

- [ ] Delta table 생성 및 스키마 확인
- [ ] 동일 block range 두 번 실행 후 logical key 중복 0건
- [ ] 1시간 단위 신규 구간 적재
- [ ] 실패 chunk 재시도
- [ ] block_date partition 기반 조회
- [ ] raw payload와 정규화 컬럼의 표본 대조

## 참고 자료

- Delta Lake — MERGE: https://docs.delta.io/delta-update/
- Delta Lake — Constraints: https://docs.delta.io/delta-constraints/
- Delta Lake — Partitioning Best Practices: https://docs.delta.io/best-practices/
