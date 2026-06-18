# 1. 과제 이해 및 설계 방향(Task Understanding and Design Direction)

> **문서 상태(Status)**: Draft  
> **적용 범위(Scope)**: 과제 1. Bitcoin Velocity(비트코인 회전율) 지표 파이프라인 설계  
> **문서 성격(Document Type)**: 과제 전용 설계 정책(Assignment-specific Design Policy)

## 1.1 과제 목적 해석(Task Objective)

본 과제의 핵심은 Bitcoin Velocity(비트코인 회전율) 값을 한 번 계산하는 것이 아니라, 온체인 원천 데이터(On-chain Raw Data)를 바탕으로 일 단위 지표(Daily Metric)를 재현 가능하고 운영 가능하게 생산하는 데이터 파이프라인(Data Pipeline)을 설계하는 데 있다.

과제에서 제공한 전제는 `block`, `tx`, `tx_input`, `tx_output`, `utxo` Delta Lake Table(델타 레이크 테이블)을 이용할 수 있다는 것이다. 본 설계는 전체 원천 스키마(Raw Schema)를 새로 정의하지 않는다. 대신 Velocity(회전율) 계산과 운영 검증에 필요한 최소 필드(Minimum Required Fields), 파생 데이터(Derived Data), 정책 파라미터(Policy Parameter)를 구분한다.

본 문서가 다루는 핵심 질문은 아래와 같다.

1. 어떤 온체인 이동량(On-chain Transfer Flow)을 분자(Numerator)로 사용할 것인가.
2. 어떤 UTXO 공급량(UTXO Supply)을 분모(Denominator)로 사용할 것인가.
3. 일별 재실행(Rerun), 과거 구간 재처리(Backfill), 체인 재편성(Chain Reorganization, Reorg) 이후에도 같은 정의로 결과를 복구할 수 있는가.
4. 원천 사실(Source Fact), 정책 결정(Policy Decision), 구현 가정(Implementation Assumption)을 어떻게 분리해 감사 가능성(Auditability)을 확보할 것인가.

따라서 본 과제의 산출물은 단순 수식 결과가 아니라, 정의·원천·계산 시점·체인 상태·정책 버전을 함께 보존하는 지표 데이터 제품(Metric Data Product)이다.

---

## 1.2 설계 범위와 비범위(Scope and Non-Scope)

### 설계 범위(In Scope)

본 설계의 기본 범위는 Bitcoin 온체인 데이터(On-chain Data)만을 사용한 일 단위 회전율 지표 생산이다.

- 최선 체인(Best Chain) 기준 블록과 거래 처리
- Transaction Output(거래 출력) 및 UTXO(Unspent Transaction Output, 미사용 거래 출력) 기반 이동량과 공급량 산출
- 소비 불가능한 출력(Provably Unspendable Output)과 장기 비활성 UTXO(Dormant UTXO)의 분리
- 데이터 품질 검증(Data Quality Check)
- 멱등성(Idempotency), 재실행(Rerun), 과거 구간 재처리(Backfill)
- 체인 재편성(Reorg) 감지와 영향 구간 재계산

### 비범위(Out of Scope)

아래 정보는 시장 해석에는 중요하지만, 본 과제의 기본 계산식에는 포함하지 않는다.

- 거래소 상장 상태(Listing Status)
- 거래 중지(Trading Suspension)
- 입출금 중단(Deposit and Withdrawal Suspension)
- 호가·유동성 데이터(Order Book and Liquidity Data)
- 주소 소유 주체(Entity Ownership) 또는 거래소 내부 이동(Internal Transfer) 판정
- 외부 주소 라벨(Address Label)만으로 판단한 소각 주소(Burn Address)

이 정보들은 오프체인 메타데이터(Off-chain Metadata) 또는 외부 큐레이션 데이터(External Curation Data)에 해당한다. 향후 확장 시 별도 차원 테이블(Dimension Table) 또는 해석 레이어(Interpretation Layer)로 결합할 수 있으나, 원천 온체인 지표의 기본 계산 규칙에 혼합하지 않는다.

---

## 1.3 공개 제품 참조와 과제 전용 지표의 분리(Product Reference and Assignment Metric Separation)

CryptoQuant는 온체인·오프체인 데이터, 사전 구축 지표(Pre-built Metric), API를 제공하는 데이터 분석 플랫폼이다. 그러나 본 과제에서 구현하는 지표가 CryptoQuant의 공개 제품 지표와 수치적으로 완전히 동일하다고 주장하지 않는다.

그 이유는 다음과 같다.

- 과제는 Circulating Supply(유통 공급량) 산정 기준을 직접 정의하도록 요구한다.
- 과제에서 제공한 원천 테이블의 실제 전체 스키마와 제품 내부 계산 규칙은 공개되지 않았다.
- 특히 경제적 거래량(Economic Transfer Volume)은 Change Output(거스름 출력), Self-churn(동일 주체 내부 이동), 주소 군집화(Address Clustering) 처리 방식에 따라 달라질 수 있다.
- 본 설계의 V1은 원천 온체인 테이블만으로 재현 가능한 규칙을 우선한다.

따라서 본 문서에서는 아래 두 객체를 분리한다.

```text
Product Reference(제품 참조)
- CryptoQuant 공개 제품과 온체인 데이터 제품이 지향하는 서비스 맥락

Assignment-specific Metric Definition(과제 전용 지표 정의)
- 과제의 raw table 전제와 명시적 정책을 기반으로 재현 가능한 계산 규칙
```

이 구분은 제품 구현을 흉내 내기 위한 것이 아니라, 확인되지 않은 내부 알고리즘을 사실처럼 쓰지 않기 위한 설계 규율이다.

---

## 1.4 일 단위 산출 기준(Daily Publication Cadence)

본 설계의 기본 산출 주기(Publication Cadence)는 일 단위(Daily)다.

```text
metric_date
= UTC 기준 블록 헤더 시간(Block Header Timestamp)으로 구분한 보고 기준일
```

여기서 `metric_date`는 데이터 제품의 집계 기준일(Reporting Convention)이다. 블록 헤더 시간은 거래가 실제로 발생한 정확한 벽시계 시간(Wall-clock Time)을 보장하는 값으로 해석하지 않는다.

본 과제의 기본 지표는 해당 UTC 일자에 생성된 이동량과 해당 일자 종료 시점의 공급량을 사용한다.

```text
daily_velocity_variant(d)
=
daily_gross_spendable_output_volume_btc(d)
/
policy_defined_utxo_supply_btc(d)
```

장기 추세를 완화하기 위한 이동 기간(Rolling Window)은 기본 정의에 암묵적으로 섞지 않는다. 이후 필요 시 `volume_window_days`를 명시한 별도 지표 변형(Metric Variant)으로 추가한다.

```text
예시
- daily_velocity_spendable_utxo_v1
- rolling_365d_velocity_spendable_utxo_v1
```

즉, 일 단위 산출 주기와 이동량 누적 기간은 서로 다른 정책 요소이며, 하나의 단어인 “일별 Velocity”로 혼동하지 않는다.

---

## 1.5 과제 전용 지표 체계(Assignment Metric Family)

본 설계는 하나의 절대적 Circulating Supply(유통 공급량)를 선언하지 않는다. 대신 동일한 온체인 사실 위에서 서로 다른 해석 목적을 가진 공급량 변형(Supply Variant)을 구분한다.

### 1.5.1 일별 총 소비 가능 출력 이동량(Daily Gross Spendable Output Volume)

```text
daily_gross_spendable_output_volume_btc(d)
=
SUM(value_sats of spendable outputs)
WHERE
- transaction is non-coinbase
- block belongs to the best chain at computation time
- output is not provably unspendable
- block timestamp belongs to UTC date d
```

이 값은 Change Output(거스름 출력)과 동일 주체 내부 이동 가능성을 제거하지 않은 총 출력 이동량(Gross Output Flow)이다.

따라서 이 값을 `estimated_transaction_volume` 또는 실제 경제적 거래량(Economic Transfer Volume)으로 부르지 않는다. V1의 목적은 더 정교한 추정을 가장하는 것이 아니라, 원천 테이블만으로 계산 가능하고 재현 가능한 기준선을 만드는 것이다.

### 1.5.2 소비 가능 UTXO 공급량(Spendable UTXO Supply)

```text
spendable_utxo_supply_btc(d)
=
SUM(value_sats of unspent outputs at day-end)
WHERE
- output belongs to the best chain at computation time
- output is not provably unspendable
- output is spendable under the coinbase maturity rule when applicable
```

`spendable_utxo_supply_btc`는 발행 총량(Total Issued Supply)과 동일한 객체가 아니다.

```text
total_issued_supply
= 프로토콜 발행량 관점의 stock

spendable_utxo_supply
= 특정 시점에 실제 소비 가능한 UTXO 관점의 stock
```

Coinbase Transaction(코인베이스 거래)의 출력은 생성 직후 바로 소비할 수 없으므로, 해당 일자 종료 시점에 성숙 조건(Maturity Condition)을 충족하지 못한 coinbase UTXO는 소비 가능 UTXO 공급량에서 제외한다.

### 1.5.3 장기 비활성 UTXO 공급량(Dormant UTXO Supply)

```text
dormant_utxo_supply_btc(d)
=
SUM(value_sats of unspent spendable UTXOs at day-end)
WHERE
utxo_age_days >= dormant_threshold_days
```

장기 비활성 UTXO는 오랫동안 이동하지 않았다는 관측 사실을 뜻한다. 이는 영구 분실 코인(Lost Coin)이라는 판정이 아니다.

`dormant_threshold_days`는 온체인 사실이 아니라 정책 파라미터다. 예를 들어 10년 기준을 채택한다면 `dormant_threshold_days = 3650` 및 `supply_policy_version = dormant_10y_v1`로 결과에 남긴다.

### 1.5.4 장기 비활성 조정 UTXO 공급량(Dormancy-adjusted UTXO Supply)

```text
dormancy_adjusted_utxo_supply_btc(d)
=
spendable_utxo_supply_btc(d)
-
dormant_utxo_supply_btc(d)
```

이 값은 유동성 민감도(Liquidity Sensitivity)를 보기 위한 해석용 분모다. 장기 비활성 UTXO가 영구적으로 시장에서 사라졌다고 주장하는 값이 아니다.

### 1.5.5 장기 비활성 UTXO 소비 이동량(Dormant UTXO Spent Volume)

```text
dormant_utxo_spent_volume_btc(d)
=
SUM(previous_output_value_sats)
WHERE
- spending date = d
- age_at_spend_days >= dormant_threshold_days
```

기존의 `dormant_reactivated_supply_btc`라는 이름은 사용하지 않는다. 해당 값은 특정 시점에 남아 있는 공급량(Supply, Stock)이 아니라, 특정 기간 동안 장기 비활성 UTXO가 소비된 이동량(Volume, Flow)이기 때문이다.

이 보조 지표는 장기 비활성 공급이 실제로 다시 이동하기 시작했는지를 추적한다.

---

## 1.6 소비 불가능한 출력과 소각 처리(Provably Unspendable Output and Burn Treatment)

본 설계의 V1은 원천 온체인 데이터만으로 명확히 판별 가능한 소비 불가능한 출력만 기본 공급량에서 제외한다.

```text
V1 Exclusion
- script 조건상 소비가 불가능하다고 판별되는 Provably Unspendable Output
- 예: OP_RETURN 기반 Null-data Output
```

반면 아래 대상은 V1에서 자동 제외하지 않는다.

```text
V1 Non-exclusion
- 외부 라벨만으로 Burn Address라고 분류된 주소
- 개인키가 없다고 추정되는 주소
- 소유권 또는 소비 가능성을 온체인 데이터만으로 증명할 수 없는 주소
```

주소가 “소각 주소”로 불리는지 여부는 외부 라벨과 운영 정책이 필요할 수 있다. 그러므로 주소 라벨 기반 Burned Supply(소각 공급량) 차감은 V2 이후의 별도 정책으로 분리하며, `burn_registry_version`, `classification_source`, `confidence` 같은 메타데이터를 함께 관리한다.

---

## 1.7 체인 상태와 재현성(Chain State and Reproducibility)

Bitcoin에서 블록이 항상 영구적으로 확정되는 것은 아니다. 경쟁 블록 또는 체인 재편성(Reorg)으로 인해 이전에 선택된 블록 경로가 다른 경로로 대체될 수 있다.

따라서 본 문서에서 사용하는 `best_chain`은 아래처럼 정의한다.

```text
best_chain
= 파이프라인이 특정 관측 시점(observed_at)에 선택한 체인 경로
```

`canonical` 또는 `finalized`를 절대적·영구적 상태처럼 사용하지 않는다. 대신 확인 깊이(Confirmation Depth)를 이용해 내부 게시 정책(Internal Publication Policy)을 적용한다.

```text
chain_confidence_status
- pending_confirmation
- confirmed_by_policy
- superseded_by_reorg
```

각 지표 결과에는 최소한 아래의 체인 체크포인트(Chain Checkpoint)를 보존한다.

```text
source_confirmed_tip_height
source_confirmed_tip_hash
confirmation_depth
observed_at
chain_revision_id
```

동일한 `metric_date`라도 체인 상태가 바뀌면 결과가 달라질 수 있다. 이는 멱등성 위반이 아니라 입력 체인 상태가 달라진 재계산(Recomputation with Changed Input)이다.

---

## 1.8 데이터 계층과 운영 목표(Data Layers and Operational Goal)

본 설계는 아래 계층 분리를 전제로 한다.

```text
Raw Layer(원천 계층)
block, tx, tx_input, tx_output, utxo

Silver Layer(정규화·파생 계층)
- best-chain selection history
- UTXO lifecycle
- script classification
- daily chain checkpoint
- daily output volume and supply components

Gold Layer(지표 계층)
- daily velocity variants
- policy versions
- quality status
- chain checkpoint metadata
```

`utxo` 테이블이 현재 상태(Current State)만 보존하는 경우에는 과거 `metric_date` 기준 공급량을 직접 복원할 수 없다. 이 경우 `tx_output`과 `tx_input`을 이용해 UTXO 생명주기(UTXO Lifecycle)를 재구성하거나, UTXO 상태 이력(State History)이 존재한다는 구현 가정을 명시해야 한다.

운영 목표는 아래 네 가지다.

1. **재현성(Reproducibility)**: 같은 원천 체인 상태와 같은 정책 버전이면 같은 결과를 재생성한다.  
2. **추적성(Traceability)**: 각 결과가 어떤 블록 범위, 체인 상태, 정책, 코드 버전에서 생성됐는지 확인할 수 있다.  
3. **복구 가능성(Recoverability)**: 실패, 재실행, Backfill, Reorg 이후 영향 구간을 안전하게 재계산한다.  
4. **해석 정직성(Interpretive Honesty)**: 온체인 사실과 정책적 추정, 원천 지표와 보조 해석 지표를 섞지 않는다.  

---

## 1.9 설계 결정 요약(Design Decision Summary)

| 구분 | 결정 | 근거 |
|---|---|---|
| 산출 주기 | 일 단위(Daily) | 과제의 일 단위 배치 요구와 정합 |
| 시간 기준 | UTC 기준 블록 헤더 시간 | 재현 가능한 집계 규칙 |
| 분자 | `daily_gross_spendable_output_volume_btc` | 원천 데이터만으로 계산 가능한 V1 기준선 |
| 분모 1 | `spendable_utxo_supply_btc` | 현재 소비 가능 UTXO 기준 공급량 |
| 분모 2 | `dormancy_adjusted_utxo_supply_btc` | 장기 비활성 물량에 대한 민감도 해석 |
| 보조 흐름 | `dormant_utxo_spent_volume_btc` | 장기 비활성 UTXO의 실제 재이동 추적 |
| Burn 처리 | Provably unspendable output만 V1에서 제외 | 외부 주소 라벨 의존 최소화 |
| 체인 상태 | Best chain at observation time | Reorg 전후 상태 추적 |
| 신뢰도 | Confirmation depth 기반 게시 정책 | Bitcoin의 확률적 체인 안정성 반영 |
| 제품 정합성 | 공개 제품 지표와 과제 지표를 분리 | 미확인 내부 알고리즘에 대한 과장 방지 |

---

## 1.10 다음 문서 연결(Next Document)

이 문서의 설계 방향을 기준으로 다음 절에서 아래 내용을 구체화한다.

1. 원천 테이블별 필드 명세(Field Specification)와 선택 근거  
2. 일별 이동량·공급량·Velocity Variant 계산식  
3. SQL 또는 의사코드(Pseudocode)  
4. 결과 테이블 스키마(Result Table Schema)와 논리 키(Logical Key)  
5. Daily Batch(일 단위 배치), 품질 검증, 멱등성, Reorg 대응 전략  

---

## 검증 근거(Verification Basis)

- CryptoQuant Data Engineer 사전 과제 PDF: 과제 목적, 원천 테이블 가정, Circulating Supply 정책 직접 정의 요구
- Bitcoin Developer Documentation: Transaction Output, Change Output, UTXO, Coinbase Maturity, Block Chain, Confirmation
- Delta Lake Documentation: Delta `MERGE` 기반 증분 갱신과 제약 조건의 범위
- CryptoQuant 공식 소개 페이지: 온체인·오프체인 데이터 및 제품화된 지표·API 제공 맥락
