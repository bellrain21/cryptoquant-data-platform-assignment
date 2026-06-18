# 파인만식 개념 지도(Feynman Concept Map)

> **문서 상태(Status)**: 전체 Markdown 문서 기반 심화 개념 정리  
> **작성 기준(Source Scope)**: 프로젝트 경로 내 기존 Markdown 13개 파일을 읽고 재구성했다.  
> **수정 방향**: 쉬운 용어에서 어려운 용어로, 배경지식에서 후행 개념으로, 필드명에서 파이프라인 설계까지 단계적으로 설명한다.  
> **주의**: 이 문서는 기존 설계 문서를 학습 가능하게 풀어 쓴 해설 문서다. Airflow, Delta Lake, dbt, pytest 실행 검증을 완료했다는 의미가 아니다.

## 0. 읽은 문서 목록

- `README.md`
- `docs/DOCS_README.md`
- `docs/ai_usage_and_validation.md`
- `docs/task_01_bitcoin_velocity/TASK_01_README.md`
- `docs/task_01_bitcoin_velocity/01_understanding_and_design_direction.md`
- `docs/task_01_bitcoin_velocity/02_metric_definition.md`
- `docs/task_01_bitcoin_velocity/03_data_contract_and_calculation.md`
- `docs/task_01_bitcoin_velocity/04_daily_batch_pipeline.md`
- `docs/task_01_bitcoin_velocity/05_quality_reorg_limitations.md`
- `docs/task_02_ethereum_log_pipeline/TASK_02_README.md`
- `docs/task_02_ethereum_log_pipeline/01_pipeline_design.md`
- `docs/task_02_ethereum_log_pipeline/02_delta_lake_ingestion.md`
- `docs/task_02_ethereum_log_pipeline/03_dbt_modeling.md`

## 1. 이 문서를 읽는 순서

이 문서는 일부러 낮은 레벨부터 높은 레벨로 올라간다. 먼저 "컬럼 하나가 무슨 뜻인지"를 이해하고, 그다음 "왜 그 컬럼들이 모여 파이프라인이 되는지"를 설명한다.

```text
L0. 한 문장 목표
L1. 데이터 기본 문법
L2. 블록체인 기본 배경
L3. 데이터 엔지니어링 기본 배경
L4. Bitcoin 원천 필드와 지표 계산
L5. Ethereum 로그 필드와 수집 구조
L6. Delta Lake, dbt, 모델링
L7. Reorg, 멱등성, 감사 이력 심화
L8. 전체 용어 색인
```

이 순서를 지켜야 하는 이유는 간단하다.

```text
field 의미를 모르면
→ key 의미를 모름
→ 중복 방지 의미를 모름
→ 멱등성 의미를 모름
→ Reorg 복구 의미를 모름
```

## 2. L0: 한 문장 목표

이 프로젝트의 본질은 **블록체인 데이터를 이용해 재현 가능하고, 중복 없이, 체인 변경에도 복구 가능한 데이터 제품을 설계하는 것**이다.

숫자를 한 번 만드는 일과 데이터 제품을 만드는 일은 다르다.

```text
숫자 한 번 만들기
= 오늘 계산해서 값 하나 출력

데이터 제품 만들기
= 어떤 원천, 어떤 정책, 어떤 버전, 어떤 체인 상태, 어떤 검증을 거쳐 나온 값인지 설명 가능
```

이 프로젝트는 두 축으로 나뉜다.

| 과제 | 쉬운 설명 | 깊은 의미 |
|---|---|---|
| Bitcoin Velocity | Bitcoin이 공급량 대비 얼마나 움직였는지 계산 | UTXO 기반 지표를 chain revision, policy version, audit history와 함께 설계 |
| Ethereum Log Ingestion | Ethereum 이벤트 로그를 수집해 분석 테이블로 변환 | RPC 수집, Delta Lake 적재, canonical log, dbt incremental model, Reorg 복구 설계 |

## 3. L1: 데이터 기본 문법

### 3.1 데이터셋, 테이블, 행, 컬럼

데이터를 가장 낮은 수준에서 보면 아래 네 가지다.

| 용어 | 쉬운 설명 | 이 프로젝트 예시 |
|---|---|---|
| 데이터셋 | 관련된 데이터 묶음 | Bitcoin raw tables, Ethereum log tables |
| 테이블 | 행과 컬럼으로 된 구조 | `block`, `tx_output`, `bronze.ethereum_log_observations` |
| 행(row) | 하나의 관측 또는 객체 | 블록 1개, 거래 1개, 로그 1개 |
| 컬럼(column) | 행이 가진 속성 | `block_hash`, `value_sats`, `log_index` |

파인만식으로 말하면:

```text
테이블은 명부다.
행은 명부의 한 줄이다.
컬럼은 그 줄에 적힌 항목이다.
```

### 3.2 필드명과 칼럼명의 차이

문서에서는 `field`, `column`, `필드`, `칼럼`이 섞여 나온다. 이 프로젝트에서는 거의 같은 뜻으로 봐도 된다.

다만 뉘앙스는 있다.

| 표현 | 뉘앙스 |
|---|---|
| field | 데이터 객체가 가진 속성이라는 의미 |
| column | 테이블에 물리적으로 존재하는 열이라는 의미 |

예:

```text
RPC log field: blockHash
정규화 테이블 column: block_hash
```

즉 원천 API 필드가 정규화 과정을 거쳐 테이블 컬럼이 된다.

### 3.3 타입(Type)

타입은 컬럼 값이 어떤 종류인지다.

| 타입 | 의미 | 예시 |
|---|---|---|
| STRING | 문자열 | `0xabc...`, `USDT` |
| BIGINT | 큰 정수 | `block_number`, `value_sats` |
| BOOLEAN | 참/거짓 | `is_coinbase`, `removed` |
| TIMESTAMP | 날짜+시간 | `block_timestamp`, `ingested_at` |
| DATE | 날짜 | `block_date`, `metric_date` |
| ARRAY<STRING> | 문자열 배열 | `topics` |

타입을 명확히 해야 하는 이유:

- 숫자 정렬과 문자열 정렬은 다르다.
- timestamp와 date는 grain이 다르다.
- token amount는 float로 다루면 정밀도 문제가 생길 수 있다.

### 3.4 Null

`NULL`은 값이 없거나 알 수 없다는 뜻이다.

중요한 점:

```text
0
≠ NULL
```

예:

- 하루 거래량 0 BTC: 값이 0인 정상 관측
- 하루 거래량 NULL: 계산에 필요한 원천 데이터가 없음

이 둘을 섞으면 데이터 품질 검증이 깨진다.

### 3.5 Key

Key는 행을 구분하는 기준이다.

| key 유형 | 쉬운 설명 | 예시 |
|---|---|---|
| natural key | 원천 데이터 자체로 식별 가능 | `(txid, vout)` |
| logical key | 비즈니스 의미상 하나여야 하는 기준 | `(metric_date, metric_variant, metric_contract_version)` |
| observation key | 같은 관측을 중복 저장하지 않기 위한 기준 | `(chain_id, block_hash, transaction_hash, log_index, observation_state)` |
| unique key | dbt incremental merge 기준 | `chain_id + transaction_hash + log_index` |

Key를 정하지 않으면 같은 데이터를 다시 처리할 때 중복이 생긴다.

### 3.6 Grain

Grain은 테이블 한 행이 의미하는 최소 단위다.

예:

```text
tether_treasury_flow grain
= block_date + treasury_address + token_contract_address + direction

tether_treasury_netflow grain
= block_date + treasury_address + token_contract_address
```

`flow`는 방향이 있으므로 `direction`이 grain에 들어간다. `netflow`는 inflow와 outflow를 합쳐 순유입을 계산하므로 `direction`이 grain에서 빠진다.

Grain이 다르면 같은 테이블에 섞으면 안 된다.

### 3.7 State와 Event

Event는 일어난 일이다. State는 현재 상태다.

| 구분 | 쉬운 설명 | 예시 |
|---|---|---|
| Event | 발생 이력 | Ethereum log observation |
| State | 현재 결과 | `silver.ethereum_logs_canonical` |

이 프로젝트의 중요한 원칙:

```text
이력은 지우지 말고 Bronze/Audit에 남긴다.
현재 소비용 정본은 Silver/Gold에서 유지한다.
```

## 4. L2: 블록체인 기본 배경

### 4.1 블록체인은 append-only 장부처럼 보이지만 완전히 고정된 것은 아니다

블록체인은 블록이 뒤에 계속 붙는 구조다.

```text
block 100 → block 101 → block 102
```

하지만 아주 최근 블록은 다른 branch로 교체될 수 있다. 이것이 Reorg다.

### 4.2 Block

Block은 거래 또는 로그가 들어 있는 묶음이다.

Bitcoin에서 block은 거래 목록을 담는다. Ethereum에서 block은 transaction과 그 transaction이 만든 log를 담는다.

핵심 필드:

| 필드 | 쉬운 설명 | 왜 필요한가 |
|---|---|---|
| `block_hash` | 블록 지문 | 같은 height의 다른 블록 구분 |
| `previous_block_hash` | 이전 블록 지문 | 체인 경로 역추적 |
| `height` / `block_number` | 블록 순서 | range 계산, 확인 깊이, 정렬 |
| `block_time` / `block_timestamp` | 블록 시간 | 날짜 집계 |

### 4.3 Hash

Hash는 데이터의 지문이다.

같은 데이터는 같은 hash를 만들고, 데이터가 조금만 바뀌면 전혀 다른 hash가 나오도록 설계된다. 엄밀히 말하면 cryptographic hash도 이론상 collision 가능성은 있지만, Bitcoin block 식별과 무결성 검증에서는 현실적으로 block hash를 식별자로 사용한다.

### 4.4 Transaction

Transaction은 가치나 상태를 바꾸는 행위다.

Bitcoin에서는 UTXO를 소비하고 새 UTXO를 만든다. Ethereum에서는 account state를 바꾸고 smart contract log를 남길 수 있다.

### 4.5 Best Chain

Best Chain은 관측 시점에 선택한 최선의 체인 경로다.

중요한 점:

```text
Best Chain
≠ 영원한 진실

Best Chain
= observed_at 시점의 선택 결과
```

그래서 `chain_revision_id`를 붙인다.

### 4.6 Reorg

Reorg는 선택된 체인 일부가 다른 branch로 교체되는 상황이다.

쉬운 예:

```text
처음 관측:
100A → 101A → 102A

나중 관측:
100A → 101B → 102B → 103B
```

여기서 100A가 common ancestor이고, 101부터 affected range다.

### 4.7 Canonical

Canonical은 현재 정본으로 인정하는 상태다.

하지만 "절대 불변"이라는 뜻은 아니다. 이 프로젝트에서 canonical은 항상 관측 시점과 체인 revision에 의존한다.

## 5. L3: 데이터 엔지니어링 기본 배경

### 5.1 Pipeline

Pipeline은 데이터를 단계적으로 처리하는 흐름이다.

```text
수집 → 정규화 → 검증 → 적재 → 변환 → 게시
```

### 5.2 ETL과 ELT

| 용어 | 의미 | 이 프로젝트 해석 |
|---|---|---|
| ETL | Extract, Transform, Load | 원천을 변환 후 적재 |
| ELT | Extract, Load, Transform | 먼저 적재 후 dbt 등으로 변환 |

Ethereum 쪽은 Bronze에 먼저 관측 이력을 쌓고, Silver/dbt에서 변환하므로 ELT 성격이 강하다.

### 5.3 Airflow DAG

Airflow DAG는 작업 순서를 정의한 workflow다.

중요한 개념:

| 용어 | 쉬운 설명 |
|---|---|
| DAG | 순환 없는 작업 그래프 |
| Task | DAG 안의 개별 작업 |
| data interval | 이 실행이 처리해야 하는 업무 시간 구간 |
| logical date | Airflow가 run을 식별하는 논리 시각 |

주의:

```text
now()
≠ 처리 대상 시간

data_interval_start / data_interval_end
= 처리 대상 시간
```

이 구분이 있어야 backfill이 가능하다.

### 5.4 Delta Lake

Delta Lake는 파일 기반 데이터 레이크에 transaction log를 붙인 저장 형식이다.

이 프로젝트에서 중요한 기능:

- append
- MERGE
- partition
- schema 관리
- audit와 current table 분리

### 5.5 dbt

dbt는 SQL 모델의 의존관계를 관리하고 실행하는 도구다.

이 프로젝트에서는 Airflow가 모델 하나하나를 하드코딩하지 않고 `dbt build`를 호출하게 설계한다.

```text
Airflow
→ dbt build

dbt
→ source, ref(), manifest로 의존관계 처리
```

### 5.6 Bronze, Silver, Gold, Audit

| 계층 | 쉬운 설명 | 이 프로젝트 예시 |
|---|---|---|
| Bronze | 원천 관측 이력 | `bronze.ethereum_log_observations` |
| Silver | 정규화된 현재 정본 | `silver.ethereum_logs_canonical`, `silver.utxo_lifecycle` |
| Gold | 소비자용 결과 | `gold.daily_bitcoin_velocity` |
| Audit | 실행·변경 이력 | `audit.daily_bitcoin_velocity_history` |

핵심:

```text
Bronze/Audit = 이력 보존
Silver/Gold = 현재 소비 상태
```

### 5.7 Idempotency

멱등성은 같은 작업을 여러 번 해도 최종 상태가 같다는 뜻이다.

예:

```text
같은 RPC 응답을 두 번 수집
→ Bronze에는 같은 observation_state 기준 중복 없음
→ Silver에는 canonical event key 기준 중복 없음
```

### 5.8 Reproducibility

재현성은 같은 입력과 같은 버전이면 같은 결과가 나와야 한다는 뜻이다.

```text
same chain state
+ same metric definition
+ same policy version
+ same code version
= same result
```

## 6. L4: Bitcoin 원천 필드 사전

이 장은 Bitcoin Velocity 계산에 필요한 필드명부터 설명한다. 계산식은 필드를 이해한 뒤에 봐야 한다.

### 6.1 `block` 테이블

`block`은 Bitcoin 블록 1개를 1행으로 표현한 테이블이다.

| 필드 | 낮은 수준 의미 | 해석 | 실수하면 생기는 문제 |
|---|---|---|---|
| `block_hash` | 블록의 고유 지문 | 이 블록이 정확히 어떤 블록인지 식별 | 같은 height의 다른 branch를 구분 못함 |
| `previous_block_hash` | 직전 블록의 hash | Best Chain 경로를 뒤로 따라갈 때 사용 | common ancestor 탐색 불가 |
| `height` | 블록 순번 | cutoff, confirmation, 순서 검증 기준 | height gap을 놓침 |
| `block_time` | 블록 헤더 시간 | `metric_date` 산출 기준 | UTC 일자 집계 오류 |
| `observed_at` | 파이프라인이 본 시각 | 어떤 체인 스냅샷에서 봤는지 추적 | Reorg 전후 관측 구분 불가 |

파인만식:

```text
block_hash는 주민등록번호가 아니라 지문에 가깝다.
height는 줄 번호다.
previous_block_hash는 앞 줄을 가리키는 연결고리다.
```

### 6.2 `tx` 테이블

`tx`는 Bitcoin transaction 1개를 1행으로 표현한다.

| 필드 | 낮은 수준 의미 | 해석 | 실수하면 생기는 문제 |
|---|---|---|---|
| `txid` | 거래 식별자 | input/output 연결의 중심 키 | 거래 중복 또는 join 실패 |
| `block_hash` | 거래가 들어간 블록 | 거래를 Best Chain block에 연결 | orphan branch 거래 포함 위험 |
| `tx_index` | 블록 안 거래 순서 | deterministic ordering 보조 | tie-breaker 부족 |
| `is_coinbase` | 채굴 보상 거래 여부 | 일반 거래량 분자에서 제외 | 발행을 이동량으로 오인 |

`is_coinbase`가 중요한 이유:

```text
coinbase transaction
= 새로 발행된 코인과 수수료를 채굴자가 받는 거래

일반 거래 이동량
≠ 새 발행량
```

Bitcoin의 coinbase output은 바로 소비할 수 없다. 이 문서에서 maturity 조건은 `spending_or_cutoff_height - coinbase_created_height >= 100`으로 해석한다. 즉 "100블록 성숙"은 정책 문구가 아니라 공급량 계산 cutoff와 직접 연결되는 height 조건이다.

### 6.3 `tx_input` 테이블

`tx_input`은 어떤 이전 output을 소비했는지를 나타낸다.

| 필드 | 낮은 수준 의미 | 해석 | 실수하면 생기는 문제 |
|---|---|---|---|
| `txid` | 소비하는 현재 거래 | 이 input이 속한 transaction | 소비 이벤트 연결 실패 |
| `input_index` | 거래 안 input 순서 | 동일 거래 내 input 구분 | input 중복 검증 불가 |
| `prev_txid` | 소비되는 과거 거래 | 이전 output의 transaction | UTXO lifecycle 연결 실패 |
| `prev_vout` | 소비되는 과거 output index | 이전 거래의 몇 번째 output인지 | 잘못된 output 소비 처리 |

핵심 연결:

```text
tx_input.prev_txid + tx_input.prev_vout
→ tx_output.txid + tx_output.vout
```

### 6.4 `tx_output` 테이블

`tx_output`은 거래가 새로 만든 output이다.

| 필드 | 낮은 수준 의미 | 해석 | 실수하면 생기는 문제 |
|---|---|---|---|
| `txid` | output을 만든 거래 | output의 부모 거래 | output 소속 불명 |
| `vout` | 거래 안 output 순서 | `(txid, vout)`이 output 자연 키 | UTXO 중복 식별 실패 |
| `value_sats` | satoshi 단위 금액 | 이동량과 공급량 계산의 원천 값 | BTC 변환 오류 |
| `script_pub_key` | 소비 조건 스크립트 | spendable/burn 판정 입력 | OP_RETURN 등 제외 실패 |

`value_sats` 해석:

```text
1 BTC = 100,000,000 sats

value_sats / 100,000,000
= value_btc
```

정수 단위인 sats를 쓰는 이유는 소수점 오차를 피하기 위해서다.

### 6.5 `utxo` 테이블

UTXO는 아직 소비되지 않은 output이다.

| 필드 | 낮은 수준 의미 | 해석 | 실수하면 생기는 문제 |
|---|---|---|---|
| `txid`, `vout` | output 자연 키 | 생성된 UTXO 식별 | 같은 UTXO 중복 |
| `value_sats` | UTXO 금액 | 공급량 합산 대상 | 공급량 오차 |
| `created_block_hash` | 생성 블록 hash | 생성이 Best Chain에 있는지 확인 | orphan output 포함 |
| `created_height` | 생성 블록 height | cutoff 이전 생성 여부 판단 | 기준일 공급량 오류 |
| `created_block_time` | 생성 시각 | UTXO age 계산 | dormant 판정 오류 |
| `spent_txid` | 소비한 거래 | 미소비면 NULL | 소비 여부 판단 |
| `spent_block_hash` | 소비 블록 hash | 소비가 같은 chain revision에 있는지 확인 | reorg 후 소비 상태 오류 |
| `spent_height` | 소비 블록 height | cutoff 이전 소비 여부 판단 | 과거 공급량 오류 |
| `spent_block_time` | 소비 시각 | dormant spent volume 계산 | 소비 일자 오류 |
| `is_spent` | 현재 snapshot의 소비 여부 | 현재 상태 검증 보조 | 과거 공급량 단독 근거로 쓰면 위험 |
| `snapshot_at` | snapshot 관측 시각 | 현재 snapshot의 기준 시점 | 과거 상태와 혼동 |

가장 중요한 금지:

```text
현재 UTXO snapshot을 과거 metric_date 공급량 계산에 그대로 쓰면 안 됨.
```

이유:

```text
오늘 미소비인 UTXO
≠ 과거 그 날짜에도 미소비였던 UTXO
```

### 6.6 Bitcoin 파생 필드

| 필드 | 어디서 생김 | 의미 | 왜 필요한가 |
|---|---|---|---|
| `chain_revision_id` | Silver | 관측 시점별 Best Chain 스냅샷 ID | Reorg 전후 결과 구분 |
| `is_best_chain` | Silver | 해당 revision의 Best Chain 소속 여부 | orphan 제외 |
| `script_class` | Silver | output script 유형 | spendable/burn 분류 |
| `is_provably_unspendable` | Silver | 원천 스크립트상 소비 불가 여부 | 분자·분모 제외 |
| `created_txid`, `created_vout` | Silver | UTXO 생성 output 키 | lifecycle grain |
| `spent_txid`, `spent_input_index` | Silver | UTXO 소비 input 키 | 소비 추적 |
| `utxo_age_days` | Silver | UTXO 나이 | dormant 정책 적용 |
| `metric_cutoff_block_height` | Silver | 기준일 종료 블록 height | day-end supply 계산 |

## 7. L4: Bitcoin 지표 개념

### 7.1 Velocity

Velocity는 공급량 대비 이동량이다.

```text
Velocity = Transfer Volume / Supply
```

이 값은 물리적 속도가 아니다. "공급량 한 단위가 기간 동안 몇 번 움직인 것처럼 보이는가"에 가까운 비율이다.

### 7.2 Flow와 Stock

Bitcoin Velocity를 이해하려면 Flow와 Stock을 먼저 구분해야 한다.

| 개념 | 의미 | 예시 |
|---|---|---|
| Flow | 기간 동안 누적되는 값 | 365일 output volume |
| Stock | 특정 시점의 잔고 | 기준일 종료 시점 UTXO supply |

Velocity는 Flow를 Stock으로 나눈다.

### 7.3 Transaction Volume

이 프로젝트의 V1 분자는 `Gross On-chain Output Volume`이다.

```text
daily_gross_onchain_output_volume_v1_btc
= non-coinbase transaction의 spendable output value 합계
```

왜 `gross`인가:

- Change Output을 제거하지 않는다.
- Self-churn을 제거하지 않는다.
- 주소 라벨이나 entity clustering을 쓰지 않는다.

그래서 `estimated economic transfer volume`이라고 부르지 않는다.

### 7.4 Change Output

Bitcoin 거래는 입력 UTXO를 통째로 소비하고 새 output을 만든다. 남은 돈은 송신자에게 거스름 output으로 돌아간다.

예:

```text
10 BTC UTXO 사용
상대에게 2 BTC
내 change address로 7.999 BTC
수수료 0.001 BTC
```

원천 output 합계는 9.999 BTC지만 경제적 이전은 2 BTC일 수 있다.

### 7.5 Circulating Supply

문서의 핵심 판단:

```text
Circulating Supply는 단일 원천 필드가 아니다.
정책으로 정의해야 한다.
```

세 공급량을 분리한다.

| 공급량 | 의미 |
|---|---|
| `total_issued_supply_btc` | 누적 발행량 |
| `policy_eligible_utxo_supply_v1_btc` | V1 정책상 분모에 포함하는 UTXO 합 |
| `dormancy_adjusted_utxo_supply_v1_btc` | 장기 비활성 UTXO를 제외한 보조 분모 |

### 7.6 Policy-eligible UTXO Supply

기본 분모다.

포함:

- Best Chain의 미소비 UTXO
- 소비 불가능으로 판정되지 않은 output
- 성숙한 coinbase output

제외:

- `is_provably_unspendable = true`
- 미성숙 coinbase output
- orphan branch output

계산 직관:

```text
기준일 종료 block까지 만들어졌고
기준일 종료 block까지 소비되지 않았고
정책상 제외 대상이 아닌 UTXO의 합
```

### 7.7 Dormant UTXO

Dormant UTXO는 오래 움직이지 않은 UTXO다.

중요한 해석:

```text
오래 안 움직임
≠ 분실 확정
```

그래서 기본 분모에서 곧바로 빼지 않고, 민감도 분석용 보조 분모로 둔다.

### 7.8 Burn

V1에서 burn으로 제외하는 것은 원천 스크립트로 소비 불가능함을 판별할 수 있는 output이다.

예:

- OP_RETURN 기반 null-data output

외부 라벨만으로 burn address라고 알려진 주소는 V1에서 자동 제외하지 않는다. 별도 registry와 신뢰도 정책이 필요하다.

### 7.9 Date Spine과 365일 Window

Date spine은 연속 날짜 목록이다.

왜 필요한가:

```text
NULL 날짜를 먼저 제거하고 365행 rolling window를 잡으면
중간 날짜가 빠져도 365개 행처럼 보일 수 있음.
```

그래서 먼저 날짜 축을 유지하고 아래를 따로 검증한다.

| 검증 | 의미 |
|---|---|
| `calendar_days_in_window = 365` | 달력상 365일이 있음 |
| `volume_source_days_in_window = 365` | 이동량 원천 집계가 365일 있음 |
| `supply_source_days_in_window = 365` | 공급량 원천 집계가 365일 있음 |

### 7.10 Bitcoin 결과 테이블 칼럼 해석

#### `gold.daily_bitcoin_velocity`

| 컬럼 | 의미 | 해석 방법 |
|---|---|---|
| `metric_date` | UTC 기준 지표일 | 어느 날짜의 지표인지 |
| `metric_variant` | 지표 변형 | 기본 분모인지 dormancy 조정 분모인지 |
| `metric_contract_version` | 지표 계약 버전 | 같은 날짜라도 계약 버전이 다르면 다른 지표 |
| `volume_window_days` | 이동량 누적 기간 | 기본 365 |
| `trailing_365d_gross_onchain_output_volume_v1_btc` | 365일 분자 | gross output 기준, economic transfer 아님 |
| `policy_eligible_utxo_supply_v1_btc` | 기본 분모 | V1 정책상 포함 가능한 UTXO 합 |
| `dormant_utxo_supply_v1_btc` | 장기 비활성 공급량 | 분실 확정 아님 |
| `dormancy_adjusted_utxo_supply_v1_btc` | 보조 분모 | 기본 분모에서 dormant를 뺀 값 |
| `dormant_utxo_spent_volume_v1_btc` | 장기 비활성 UTXO 소비량 | stock이 아니라 flow |
| `denominator_supply_btc` | 실제 분모 | variant별 선택된 공급량 |
| `velocity` | 최종 비율 | 분자 / 분모 |
| `volume_definition_version` | 분자 정의 버전 | Change Output 처리 여부 등과 연결 |
| `supply_policy_version` | 분모 정책 버전 | burn, maturity, dormant 기준과 연결 |
| `pipeline_code_version` | 코드 버전 | 구현 추적용, 논리 key에는 없음 |
| `metric_cutoff_block_height` | 기준일 종료 block height | 공급량 계산 cutoff |
| `metric_cutoff_block_hash` | 기준일 종료 block hash | cutoff block 식별 |
| `as_of_best_chain_tip_height` | 관측 시점 tip height | 확인 깊이 계산 기준 |
| `as_of_best_chain_tip_hash` | 관측 시점 tip hash | 체인 스냅샷 추적 |
| `required_successor_blocks` | 게시 전 요구 후속 block 수 | finality가 아니라 내부 확인 정책 |
| `chain_confidence_status` | 체인 신뢰 상태 | current Gold에서는 `confirmed_by_policy` |
| `chain_revision_id` | 계산 체인 스냅샷 ID | Reorg 전후 구분 |
| `calculated_at` | 계산 시각 | 파이프라인 실행 추적 |

#### `audit.daily_bitcoin_velocity_history`

| 컬럼 | 의미 | 해석 방법 |
|---|---|---|
| `audit_run_id` | 실행 식별자 | 같은 metric이라도 실행 이력 구분 |
| `metric_date` | 지표일 | 결과 대상 날짜 |
| `metric_variant` | 지표 변형 | Gold와 같은 identity 구성 요소 |
| `metric_contract_version` | 지표 계약 버전 | 결과 의미 고정 |
| `chain_revision_id` | 사용한 체인 revision | Reorg 전후 이력 추적 |
| `chain_confidence_status` | pending, confirmed, superseded | 현재 게시 여부와 대체 여부 |
| `superseded_at` | 대체된 시각 | Reorg로 이전 관측이 밀린 시점 |
| `published_at` | Gold 반영 시각 | 아직 미게시면 NULL |
| `metric_payload_hash` | 결과 payload hash | 결과 값 변경 감사 |
| `calculated_at` | 계산 시각 | 실행 추적 |

## 8. L5: Bitcoin 계산 흐름을 필드 중심으로 다시 보기

### 8.1 Best Chain Snapshot

필요한 필드:

- `block_hash`
- `previous_block_hash`
- `height`
- `observed_at`
- `chain_revision_id`

흐름:

```text
tip.block_hash에서 시작
→ previous_block_hash를 따라 뒤로 이동
→ 이 경로를 chain_revision_id로 저장
```

이걸 하는 이유는 Reorg 후에도 "그때 우리가 본 체인"을 설명하기 위해서다.

### 8.2 Daily Volume

필요한 필드:

- `block.block_time`
- `tx.block_hash`
- `tx.is_coinbase`
- `tx_output.txid`
- `tx_output.vout`
- `tx_output.value_sats`
- `is_provably_unspendable`

해석:

```text
Best Chain에 있는 일반 거래의 spendable output 값을 날짜별로 합산
```

### 8.3 Daily Supply

필요한 필드:

- `created_height`
- `spent_height`
- `value_sats`
- `is_coinbase`
- `is_provably_unspendable`
- `metric_cutoff_block_height`
- `chain_revision_id`

해석:

```text
cutoff 이전에 생성되고
cutoff까지 소비되지 않았고
정책상 제외되지 않은 UTXO 합
```

### 8.4 Velocity

필요한 값:

- 365일 daily volume
- 기준일 supply

계산:

```text
velocity
= trailing_365d_gross_onchain_output_volume_v1_btc
  / denominator_supply_btc
```

## 9. L4: Ethereum 로그 원천 필드 사전

Ethereum 쪽은 먼저 RPC log가 무엇인지 이해해야 한다.

### 9.1 Ethereum Log의 낮은 수준 구조

Smart contract는 transaction 실행 중 event를 남길 수 있다. 그 event가 log다.

Transfer event 예:

```solidity
event Transfer(address indexed _from, address indexed _to, uint256 _value)
```

Ethereum log는 대략 아래처럼 생겼다.

```text
block metadata
+ transaction 위치
+ contract address
+ topics
+ data
```

### 9.2 Bronze Observation Schema

`bronze.ethereum_log_observations`는 RPC에서 받은 log 관측 이력을 저장한다. 이 계층은 append-only audit 성격이다.

Ethereum JSON-RPC 원문 log 객체의 contract 필드는 보통 `address`라는 이름으로 온다. 이 문서의 `contract_address`는 그 원문 `address`를 분석 테이블에서 의미가 드러나도록 정규화한 컬럼명이다.

| 컬럼 | 타입 | 쉬운 의미 | 해석 | Null 정책 |
|---|---|---|---|---|
| `chain_id` | BIGINT | 체인 번호 | Ethereum mainnet이면 1 | N |
| `block_number` | BIGINT | 블록 순번 | 수집 range와 정렬 기준 | N |
| `block_hash` | STRING | 블록 지문 | Reorg 전후 branch 구분 | N |
| `block_timestamp` | TIMESTAMP | 블록 시간 | interval 검증, block_date 생성 | N |
| `block_date` | DATE | 블록 날짜 | partition, dbt rebuild 단위 | N |
| `transaction_hash` | STRING | transaction 지문 | event 위치 key 일부 | N |
| `transaction_index` | BIGINT | 블록 내 transaction 순서 | ordering 보조, 일부 provider에서 null 가능 | Y |
| `log_index` | BIGINT | 블록 내 log 순서 | transaction 안 event 식별 | N |
| `contract_address` | STRING | event를 발생시킨 contract | ERC-20 token 후보 식별 | N |
| `topics` | ARRAY<STRING> | indexed event 값 배열 | Transfer signature, from, to decoding | N |
| `data` | STRING | non-indexed event data | Transfer amount decoding | N |
| `removed` | BOOLEAN | provider 원본 removal flag | Reorg removal 관측 | Y |
| `observation_state` | STRING | 정규화 상태 | `observed` 또는 `removed` | N |
| `source_provider` | STRING | RPC 제공자 | 장애·품질 추적 | N |
| `ingested_at` | TIMESTAMP | 적재 시각 | 수집 지연 추적 | N |
| `data_interval_start` | TIMESTAMP | Airflow 구간 시작 | 재실행·backfill 기준 | N |
| `data_interval_end` | TIMESTAMP | Airflow 구간 종료 | 처리 범위 추적 | N |
| `schema_version` | STRING | 스키마 버전 | 컬럼 계약 변경 추적 | N |
| `raw_payload` | STRING | 원본 JSON | 감사·재처리 표본 확인 | Y |

핵심:

```text
Bronze는 현재 정본이 아니라 관측 기록이다.
```

표준 JSON-RPC log 객체는 pending log에서 `blockHash`, `blockNumber`, `transactionHash`, `transactionIndex`, `logIndex`가 null일 수 있다. 이 과제 설계는 `eth_getLogs`를 확정된 block range에 대해 호출하는 구조이므로, canonical 분석 경로에서는 `transaction_hash`와 `log_index`를 필수값으로 본다. `transaction_index`를 Bronze에서 nullable로 둔 것은 provider 차이와 raw 보존을 감안한 방어적 선택이다.

### 9.3 `removed`와 `observation_state`

provider가 `removed=true`를 줄 수 있다. 하지만 누락될 수도 있다.

정규화 정책:

```text
removed = true
→ observation_state = removed

removed = false or missing
→ observation_state = observed
```

왜 둘 다 필요한가:

- `removed`는 provider 원본 필드다.
- `observation_state`는 파이프라인이 쓰는 표준 상태다.

### 9.4 Bronze Observation Key

```text
Bronze observation key
= chain_id + block_hash + transaction_hash + log_index + observation_state
```

각 요소 의미:

| 요소 | 왜 key에 필요한가 |
|---|---|
| `chain_id` | 여러 체인을 지원할 수 있음 |
| `block_hash` | Reorg 전후 다른 block에 같은 transaction이 있을 수 있음 |
| `transaction_hash` | transaction 식별 |
| `log_index` | transaction/block 내 log 식별 |
| `observation_state` | observed와 removed를 별도 이력으로 보존 |

이 key는 같은 RPC 응답을 다시 받아도 Bronze 중복을 막는다.

### 9.5 Silver Canonical Schema

`silver.ethereum_logs_canonical`은 현재 Best Chain 기준으로 분석 가능한 log만 담는다.

| 컬럼 | 의미 | 해석 |
|---|---|---|
| `chain_id` | 체인 ID | mainnet이면 1 |
| `block_number` | canonical block 순번 | range, rebuild, ordering 기준 |
| `block_hash` | 현재 Best Chain block hash | orphan row 제거 검증 |
| `block_timestamp` | block 시간 | 모델 시간 기준 |
| `block_date` | block 날짜 | partition 및 dbt rebuild 단위 |
| `transaction_hash` | transaction 식별 | canonical event key 일부 |
| `transaction_index` | block 내 transaction 순서 | ordering 보조 |
| `log_index` | log 순서 | canonical event key 일부 |
| `contract_address` | event emitter contract | ERC-20 decoding 입력 |
| `topics` | indexed event data | topic0, from, to 추출 |
| `data` | non-indexed event data | amount 추출 |
| `canonical_checked_at` | canonical 판정 시각 | Silver refresh 추적 |
| `chain_revision_id` | 체인 스냅샷 ID | Reorg 후 source 추적 |
| `source_observation_key` | Bronze 원천 관측 key | Silver row의 원천 추적 |

주의:

```text
Silver의 contract_address를 token_contract_address로 바로 바꾸지 않는다.
```

이유:

- 모든 contract log가 token log는 아니다.
- token 의미는 ERC-20 decoding과 metadata join 후에 부여된다.

### 9.6 Silver Canonical Event Key

```text
Silver canonical event key
= chain_id + transaction_hash + log_index
```

이 key는 현재 소비용 정본에서 event가 하나만 있어야 함을 보장한다.

Bronze key와 다른 이유:

```text
Bronze
= 이력 보존
= block_hash와 observation_state까지 포함

Silver
= 현재 정본
= 현재 Best Chain event만 하나로 수렴
```

## 10. L5: Ethereum 수집 흐름

### 10.1 1시간 Airflow Data Interval

과제 요구는 1시간 단위 수집이다.

```text
data_interval_start = 2026-06-19 01:00:00 UTC
data_interval_end   = 2026-06-19 02:00:00 UTC
```

이 구간에 속한 block log를 수집한다.

### 10.2 Time-to-block Range

Ethereum JSON-RPC에는 timestamp를 block number로 바로 바꾸는 표준 메서드가 없다.

그래서 해야 하는 일:

```text
시간 구간 확정
→ block timestamp 조회
→ 시작 시간 이상 첫 block 탐색
→ 종료 시간 미만 마지막 block 탐색
→ [from_block, to_block] 확정
```

### 10.3 Collection Upper Bound

너무 최신 블록은 Reorg 가능성이 높다.

그래서 수집 상한을 둔다.

```text
collection_upper_bound
= safe block
or latest block - reorg_lookback_blocks
```

`safe`와 `finalized`는 Ethereum JSON-RPC의 block parameter tag로 문서화되어 있다. 다만 모든 provider·라이브러리 조합이 같은 방식으로 지원한다고 가정하면 안 되므로, 구현에서는 provider 호환성을 확인하고 지원되지 않으면 `latest - reorg_lookback_blocks` 같은 보수적 fallback을 사용한다.

### 10.4 Chunk

RPC provider는 한 번에 너무 넓은 block range를 거부할 수 있다.

그래서 range를 chunk로 나눈다.

```text
[1000, 1999]
→ [1000, 1199]
→ [1200, 1399]
→ ...
```

실패한 chunk만 재시도하면 전체 구간을 blind rerun하지 않아도 된다.

### 10.5 Adaptive Chunking

Adaptive chunking은 실패 유형에 따라 chunk size를 줄이는 전략이다.

| 실패 유형 | 대응 |
|---|---|
| timeout | retry with backoff |
| rate limit | backoff, concurrency 감소 |
| response too large | chunk size 축소 |
| malformed parameter | retry하지 않고 fail |

### 10.6 Canonical Refresh와 Bounded Reconciliation

Bronze에 관측을 쌓은 뒤 Silver current state를 갱신한다.

일반 MERGE만 하면 안 되는 이유:

```text
Reorg로 source에서 사라진 orphan event가
target Silver에 남을 수 있음.
```

그래서 affected range 안에서 source에 없는 target row를 삭제해야 한다.

```text
WHEN NOT MATCHED BY SOURCE
  AND target.block_number BETWEEN affected_from_block AND affected_to_block
THEN DELETE
```

이것이 bounded reconciliation이다.

## 11. L6: dbt 모델링 필드 사전

### 11.1 `stg_ethereum_logs`

Staging model은 Silver canonical log를 분석하기 좋게 표준화한다.

주요 역할:

- hex string 표준화
- address lower-case 통일
- 필수 필드 null 검증
- canonical event key 보존

### 11.2 `erc20_transfers`

`erc20_transfers`는 ERC-20 Transfer event만 승격한 모델이다.

대상 판정 조건:

```text
topic0 = Transfer signature
topics length = 3
data = 32-byte uint256
contract_address가 enabled token metadata와 정확히 1건 매칭
block_timestamp가 metadata 유효기간 안에 있음
```

ERC-20 `Transfer(address,address,uint256)`의 topic0 상수는 아래 값이다.

```text
0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef
```

필드 해석:

| 필드 | 어디서 오나 | 의미 |
|---|---|---|
| `chain_id` | Silver log | 체인 식별 |
| `transaction_hash` | Silver log | transaction 식별 |
| `log_index` | Silver log | event 식별 |
| `block_number` | Silver log | ordering, incremental 기준 |
| `block_timestamp` | Silver log | metadata 유효기간 판정 |
| `block_date` | Silver log | partition, 집계 날짜 |
| `token_contract_address` | `contract_address`에서 승격 | token contract |
| `from_address` | `topics[1]` 마지막 20 bytes | 송신 주소 |
| `to_address` | `topics[2]` 마지막 20 bytes | 수신 주소 |
| `amount_raw` | `data` uint256 decode | decimals 적용 전 정수 |
| `amount_normalized` | `amount_raw / 10^decimals` | 사람이 읽는 token 수량 |
| `symbol` | metadata | token symbol |
| `decimals` | metadata | 소수점 자리수 |

중요:

```text
topic0만 맞는다고 ERC-20으로 단정하지 않는다.
metadata join이 필요하다.
```

### 11.3 `dim_token_metadata`

Token metadata는 contract가 어떤 token인지 알려주는 dimension이다.

| 필드 | 의미 | 해석 |
|---|---|---|
| `chain_id` | 체인 식별 | Ethereum mainnet은 1 |
| `token_contract_address` | token contract 주소 | USDT contract 등 |
| `symbol` | token 심볼 | USDT |
| `decimals` | 소수점 자리수 | USDT는 6 |
| `token_standard` | token 표준 | ERC-20 |
| `is_enabled` | 분석 대상 여부 | false면 제외 |
| `valid_from` | metadata 유효 시작 | 분석 정책상 시작 |
| `valid_to` | metadata 유효 종료 | NULL이면 현재까지 유효 |
| `metadata_source` | 출처 | Tether guide, on-chain decimals 검증 등 |

유효기간이 겹치면 안 되는 이유:

```text
하나의 log가 metadata 2행과 매칭
→ amount_normalized가 중복 생성
→ Treasury 집계가 2배가 될 수 있음
```

### 11.4 USDT Selector

과제의 Treasury 집계 대상은 Ethereum mainnet USDT다.

```text
chain_id = 1
token_contract_address = 0xdac17f958d2ee523a2206206994597c13d831ec7
symbol = USDT
decimals = 6
```

Tether 공식 supported protocols 문서는 Ethereum USDt contract 주소를 Etherscan 링크로 제시한다. Etherscan의 token page는 해당 contract를 `WITH 6 Decimals`로 표시한다. 구현 검증에서는 가능하면 `eth_call(decimals())`로 on-chain 값을 확인하고, 문서·explorer·on-chain 값이 불일치하면 metadata 적재를 hard fail로 처리한다.

이 조건을 명확히 둬야 metadata에 다른 token이 추가되어도 집계 범위가 넓어지지 않는다.

### 11.5 `tether_treasury_flow`

방향별 상세 집계 모델이다.

Grain:

```text
block_date
+ treasury_address
+ token_contract_address
+ direction
```

필드 해석:

| 필드 | 의미 |
|---|---|
| `block_date` | 집계 날짜 |
| `treasury_address` | 과제 지정 Tether Treasury 주소 |
| `token_contract_address` | USDT contract |
| `direction` | `inflow` 또는 `outflow` |
| `amount_raw` | 방향별 raw amount 합 |
| `amount_normalized` | 방향별 normalized amount 합 |
| `transaction_count` | 방향별 Transfer event 수 |

방향 판정:

```text
inflow  = to_address = treasury_address
outflow = from_address = treasury_address
```

### 11.6 `tether_treasury_netflow`

일별 순유입 모델이다.

Grain:

```text
block_date
+ treasury_address
+ token_contract_address
```

필드 해석:

| 필드 | 의미 |
|---|---|
| `inflow_amount_raw` | inflow raw 합 |
| `outflow_amount_raw` | outflow raw 합 |
| `netflow_amount_raw` | inflow raw - outflow raw |
| `inflow_amount_normalized` | inflow normalized 합 |
| `outflow_amount_normalized` | outflow normalized 합 |
| `netflow_amount_normalized` | inflow normalized - outflow normalized |
| `inflow_transaction_count` | inflow event 수 |
| `outflow_transaction_count` | outflow event 수 |

`flow`와 `netflow`를 분리하는 이유:

```text
flow는 direction별 상세.
netflow는 direction을 합친 결과.
grain이 다르므로 한 테이블에 섞지 않음.
```

## 12. L7: 어려운 개념 심화

### 12.1 Product Reference vs Assignment Metric

CryptoQuant 공개 제품은 다음처럼 설명된다.

```text
Trailing 1-Year Estimated Transaction Volume
/
Current Total Supply
```

하지만 과제에서는 내부 `estimated transaction volume` 계산 규칙이 제공되지 않았다.

따라서 문서의 선택:

```text
공개 제품 정의
= 개념 참조

과제 지표
= 원천 테이블과 명시 정책으로 재현 가능한 별도 정의
```

이것은 회피가 아니라 검증 불가능한 내부 알고리즘을 사실처럼 쓰지 않기 위한 것이다.

### 12.2 Source Fact vs Policy Decision vs Assumption

| 구분 | 예시 | 바뀌면 어떤 영향인가 |
|---|---|---|
| Source Fact | `block_hash`, `value_sats` | 원천 데이터나 체인 상태 변경 |
| Policy Decision | dormant threshold, required successor blocks | 지표 정의나 게시 정책 변경 |
| Assumption | provider safe block 지원 여부 | 구현 경로 변경 |

이 셋을 섞으면 결과가 왜 바뀌었는지 설명할 수 없다.

### 12.3 Incremental Append vs Idempotent Upsert

Incremental append는 새 데이터를 계속 추가한다는 뜻이다.

하지만 retry/backfill에서는 단순 append만 쓰면 중복이 생긴다.

그래서 계층별 전략이 다르다.

| 계층 | 전략 |
|---|---|
| Bronze observation | append 성격, 단 observation key로 같은 상태 중복 방지 |
| Silver canonical | canonical event key 기준 MERGE + bounded delete |
| Gold metric | logical key 기준 MERGE |
| Audit history | 실행 관측 append |

### 12.4 Reorg가 Bitcoin에 미치는 영향

Bitcoin Reorg는 분자와 분모 모두 바꾼다.

분자 영향:

- 교체된 block의 transaction이 달라짐
- output 합계가 달라짐
- affected date가 포함된 365일 window가 달라짐

분모 영향:

- UTXO 생성·소비 lifecycle이 달라짐
- fork 이후 day-end supply가 계속 달라질 수 있음

그래서 안전한 복구 범위는:

```text
affected_start_date
→ latest_confirmed_metric_date
```

단, 365일 window 계산에는 `affected_start_date - 364`부터 입력을 다시 읽어야 한다.

### 12.5 Reorg가 Ethereum에 미치는 영향

Ethereum Reorg는 canonical log를 바꾼다.

문제:

```text
orphan block에 있던 Transfer event가
Silver와 dbt mart에 남을 수 있음.
```

복구:

```text
common ancestor 탐색
→ affected block range 산정
→ Bronze에는 관측 이력 보존
→ Silver affected range bounded reconciliation
→ dbt affected block_date bounded rebuild
```

### 12.6 Confirmation과 Finality

Bitcoin 문서에서 `confirmed_by_policy`는 절대 finality가 아니다.

```text
confirmed_by_policy
= 내부 게시 정책상 충분한 후속 block이 쌓였다고 판단
```

`required_successor_blocks`는 기준 block 뒤에 필요한 후속 block 수다. block 자신까지 포함하는 confirmation count와 혼동하면 안 된다.

### 12.7 Canonical 삭제가 필요한 이유

MERGE는 보통 source에 있는 row를 insert/update한다. 하지만 source에서 사라진 row를 자동 삭제하지 않을 수 있다.

Reorg에서는 "사라진 row"가 중요하다.

```text
Reorg 전 orphan event
→ 새 canonical source에는 없음
→ target에서 삭제해야 함
```

그래서 `WHEN NOT MATCHED BY SOURCE ... DELETE` 또는 affected range delete 후 insert가 필요하다.

Delta Lake는 MERGE로 중복 방지와 upsert를 처리할 수 있다. `WHEN NOT MATCHED BY SOURCE` 계열 동작은 런타임과 버전에 따라 지원 여부가 달라질 수 있으므로, 이 문서의 설계는 해당 구문을 지원하지 않는 실행 환경에서는 affected range를 먼저 delete한 뒤 stage source를 insert 또는 merge하는 fallback을 둔다.

### 12.8 dbt Incremental과 Reorg

dbt incremental model은 일반적으로 새 데이터만 읽는다.

하지만 Reorg에서는 기존 row가 사라질 수 있다.

따라서:

```text
normal run
= overlap lookback + merge

reorg run
= affected_block_dates delete 후 rebuild
```

## 13. 전체 흐름 압축

### 13.1 Bitcoin

```text
raw.block
+ raw.tx
+ raw.tx_input
+ raw.tx_output
+ raw.utxo
→ Best Chain snapshot
→ output classification
→ UTXO lifecycle
→ daily gross volume
→ daily policy-eligible supply
→ 365-day window completeness 검증
→ velocity 계산
→ Gold MERGE
→ Audit append
```

### 13.2 Ethereum

```text
Airflow data interval
→ time-to-block range
→ chunked eth_getLogs
→ normalized observations
→ Bronze observation append
→ Silver canonical bounded reconciliation
→ dbt source ethereum_logs
→ stg_ethereum_logs
→ erc20_transfers
→ tether_treasury_flow
→ tether_treasury_netflow
```

## 14. 쉬운 용어에서 어려운 용어로 보는 색인

### 14.1 기초 데이터 용어

| 용어 | 의미 |
|---|---|
| table | 행과 컬럼의 묶음 |
| row | 하나의 관측 또는 객체 |
| column | 속성 |
| field | 객체 속성. column과 거의 같은 의미로 사용 |
| type | 값의 종류 |
| null | 값 없음 또는 알 수 없음 |
| key | 행을 구분하는 기준 |
| grain | 한 행이 의미하는 최소 단위 |
| state | 현재 상태 |
| event | 발생 이력 |

### 14.2 블록체인 용어

| 용어 | 의미 |
|---|---|
| block | 거래 또는 로그 묶음 |
| hash | 데이터 지문 |
| transaction | 상태나 가치를 바꾸는 행위 |
| height / block_number | 블록 순서 |
| Best Chain | 관측 시점의 최선 체인 경로 |
| Reorg | 체인 일부가 다른 branch로 교체됨 |
| common ancestor | Reorg 전후 공통 마지막 블록 |
| orphan | 현재 Best Chain에서 이탈한 블록 또는 이벤트 |
| canonical | 현재 정본 |
| chain_revision_id | 체인 스냅샷 식별자 |

### 14.3 Bitcoin 용어

| 용어 | 의미 |
|---|---|
| UTXO | 아직 소비되지 않은 output |
| tx_output | 새 UTXO 후보를 만드는 output |
| tx_input | 이전 output을 소비하는 input |
| vout | transaction 안 output 순번 |
| value_sats | satoshi 단위 금액 |
| coinbase | 채굴 보상 거래 |
| coinbase maturity | coinbase output 소비 전 필요한 100블록 성숙 |
| gross volume | output 합계 기반 이동량 |
| economic volume | 경제적 실질 이전량 추정 |
| dormant UTXO | 오래 소비되지 않은 UTXO |
| burn | 소비 불가능하거나 소각된 물량 |
| metric_contract_version | 지표 의미를 고정하는 버전 |

### 14.4 Ethereum 용어

| 용어 | 의미 |
|---|---|
| RPC Provider | Ethereum node 접근 제공자 |
| eth_getLogs | log 조회 메서드 |
| log | smart contract event 기록 |
| topic | indexed event field |
| topic0 | event signature hash |
| data | non-indexed event data |
| removed | provider 원본 Reorg removal flag |
| observation_state | observed/removed 표준 상태 |
| Bronze | 관측 이력 계층 |
| Silver | 현재 정본 계층 |
| bounded reconciliation | 영향 범위만 삭제·갱신 |

### 14.5 dbt와 모델링 용어

| 용어 | 의미 |
|---|---|
| source | dbt 외부 입력 테이블 등록 |
| staging | 표준화 중간 모델 |
| mart | 분석 소비 모델 |
| ref | 모델 의존관계 선언 |
| manifest | dbt 의존관계 메타데이터 |
| incremental model | 새 구간 또는 영향 구간만 처리 |
| full refresh | 전체 재생성 |
| unique key | incremental merge 기준 |
| dbt test | 모델 계약 검증 |

### 14.6 USDT Treasury 용어

| 용어 | 의미 |
|---|---|
| ERC-20 | Ethereum token 표준 |
| Transfer event | token 이동 이벤트 |
| token metadata | token contract, symbol, decimals 정보 |
| decimals | token 소수점 자리수 |
| amount_raw | decimals 적용 전 정수 |
| amount_normalized | decimals 적용 후 수량 |
| treasury_address | 과제 지정 Tether Treasury 주소 |
| inflow | Treasury로 들어온 이동 |
| outflow | Treasury에서 나간 이동 |
| netflow | inflow - outflow |

## 15. 현재 문서 기준 미검증 항목

이 문서는 개념 해설 문서다. 아래 항목은 완료로 주장하지 않는다.

- Airflow DAG parse
- Ethereum RPC 실제 수집
- Delta Lake 실제 table 생성
- dbt run
- dbt test
- pytest
- synthetic Reorg fixture 검증
- 최종 PDF 생성

위 항목은 구현과 실행 검증 단계에서 별도 증거가 필요하다.

## 16. 공식 출처 기반 정합성 검증 메모

이 장은 문서 내 전문지식과 용어를 공식 문서·표준 문서에 대조한 결과다. "검증됨"은 해당 설명의 방향이 공식 문서와 일치한다는 뜻이지, 이 저장소의 구현이 실행 검증됐다는 뜻은 아니다.

| 검증 대상 | 근거 | 판정 |
|---|---|---|
| Bitcoin block은 ordered/timestamped transaction ledger이며 previous block hash로 연결됨 | [Bitcoin Developer Guide - Block Chain](https://developer.bitcoin.org/devguide/block_chain.html) | 정합 |
| 같은 height에 여러 block이 있을 수 있고, block hash가 식별자로 필요함 | [Bitcoin Developer Guide - Block Height And Forking](https://developer.bitcoin.org/devguide/block_chain.html#block-height-and-forking) | 정합 |
| UTXO는 아직 소비되지 않은 output이며 transaction input은 이전 output을 소비함 | [Bitcoin Developer Guide - Transactions](https://developer.bitcoin.org/devguide/transactions.html) | 정합 |
| Coinbase output은 최소 100 blocks 동안 소비 불가 | [Bitcoin Developer Guide - Transaction Data](https://developer.bitcoin.org/devguide/block_chain.html#transaction-data) | 정합. height 조건 문구 보강 |
| CryptoQuant 공개 Velocity는 trailing 1-year estimated transaction volume / current supply | [CryptoQuant BTC Network Data - Velocity](https://userguide.cryptoquant.com/api/btc-network-data) | 정합. 과제 지표와 제품 지표 분리 유지 |
| `eth_getLogs`는 filter object로 log를 반환하고 `fromBlock`, `toBlock`, `address`, `topics`를 사용함 | [ethereum.org JSON-RPC - eth_getLogs](https://ethereum.org/developers/docs/apis/json-rpc/#eth_getlogs) | 정합 |
| `safe`, `finalized` block tag 존재 | [ethereum.org JSON-RPC - Block parameter](https://ethereum.org/developers/docs/apis/json-rpc/#the-block-parameter) | 정합. provider fallback 문구 보강 |
| JSON-RPC log의 `removed`는 reorg removal 상태를 표현함 | [ethereum.org JSON-RPC - log object](https://ethereum.org/developers/docs/apis/json-rpc/#eth_getfilterchanges) | 정합 |
| Solidity event에서 non-anonymous event topic0은 event signature hash, indexed args는 topics, non-indexed args는 data에 들어감 | [Solidity ABI Specification - Events](https://docs.soliditylang.org/en/latest/abi-spec.html#events) | 정합 |
| ERC-20 Transfer event signature는 `Transfer(address indexed _from, address indexed _to, uint256 _value)` | [EIP-20 - Events](https://eips.ethereum.org/EIPS/eip-20#events) | 정합 |
| Ethereum USDT contract 주소 | [Tether Supported Protocols and Integration Guidelines](https://tether.to/en/supported-protocols/) | 정합 |
| Ethereum USDT decimals = 6 | [Etherscan USDT token page](https://etherscan.io/token/0xdac17f958d2ee523a2206206994597c13d831ec7); 구현 시 on-chain `decimals()` 재검증 필요 | 정합하나 실행 미검증 |
| Airflow data interval과 logical date 설명 | [Airflow Dag Runs - Data Interval](https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/dag-run.html#data-interval) | 정합 |
| dbt source, `ref()`, incremental model의 기본 설명 | [dbt source](https://docs.getdbt.com/docs/build/sources), [dbt ref](https://docs.getdbt.com/reference/dbt-jinja-functions/ref), [dbt incremental models](https://docs.getdbt.com/docs/build/incremental-models) | 정합 |
| Delta MERGE를 통한 dedup/upsert 및 runtime별 delete fallback 필요성 | [Delta Lake update, delete, and merge](https://docs.delta.io/delta-update/) | 정합. fallback 문구 보강 |
