# 2. Bitcoin Velocity 지표 개요(Bitcoin Velocity Metric Overview)

> **문서 상태(Status)**: Draft  
> **적용 범위(Scope)**: 과제 1. Bitcoin Velocity(비트코인 회전율) 지표 파이프라인 설계  
> **선행 문서(Previous Document)**: [1. 과제 이해 및 설계 방향](./01_task_understanding_and_design_direction.md)  
> **문서 목적(Purpose)**: Network Velocity(네트워크 회전율), Transaction Volume(거래 이동량), Circulating Supply(유통 공급량)의 객체 경계를 정의하고, 본 과제에서 사용할 지표 해석 범위를 고정한다.

---

## 2.1 Network Velocity 정의(Network Velocity Definition)

Network Velocity(네트워크 회전율)는 특정 기간 동안 Bitcoin(비트코인)이 공급량 대비 얼마나 이동했는지를 나타내는 비율형 On-chain Metric(온체인 지표)이다.

과제에서 제시된 기본 개념은 아래와 같다.

```text
Network Velocity
=
Transaction Volume
/
Circulating Supply
```

이 값은 물리학의 속도(Speed)가 아니다. 특정 기간에 관측된 이동량(Flow)을 같은 시점 또는 정책 기준의 공급량(Stock)으로 나눈 회전율(Turnover Ratio)이다.

```text
분자(Numerator)
= 기간 동안 발생한 Bitcoin 이동량

분모(Denominator)
= 특정 시점 또는 정책 기준의 Bitcoin 공급량

결과(Result)
= 공급량 대비 관측된 이동 활동의 상대적 크기
```

### 2.1.1 본 과제의 지표 정의 원칙(Assignment Metric Definition Principle)

Network Velocity는 단일한 시장 표준 수치가 아니다. 분자의 이동량 정의, 분모의 공급량 정의, 기간(Window), Change Output(거스름 출력) 및 Dormant UTXO(장기 비활성 UTXO) 처리 방식에 따라 값이 달라질 수 있다.

따라서 본 과제는 공개 제품의 내부 계산 규칙을 추정하거나 동일한 수치라고 주장하지 않는다. 대신 과제에서 가정한 `block`, `tx`, `tx_input`, `tx_output`, `utxo` 원천 테이블(Raw Table)을 바탕으로 재현 가능한 과제 전용 지표 체계(Assignment-specific Metric Family)를 정의한다.

```text
Product Reference(제품 참조)
= CryptoQuant와 같은 데이터 제품이 제공하는 온체인 지표의 서비스 맥락

Assignment-specific Metric(과제 전용 지표)
= 원천 테이블과 명시적 정책으로 재현 가능한 계산 규칙
```

### 2.1.2 산출 주기(Cadence)와 계산 기간(Window)의 분리

본 파이프라인의 산출 주기(Publication Cadence)는 일 단위(Daily)다.

```text
metric_date
= UTC 기준 블록 헤더 시간(Block Header Timestamp)으로 구분한 보고 기준일
```

그러나 일 단위로 지표를 게시한다고 해서 분자가 반드시 하루치 이동량이어야 하는 것은 아니다. 산출 주기와 계산 기간은 서로 다른 정책 요소다.

```text
Daily Velocity
= 당일 이동량 / 당일 종료 시점 공급량

Rolling Velocity
= 최근 N일 누적 이동량 / 기준일 공급량
```

본 과제의 기본 산출물은 일 단위 Daily Velocity(일별 회전율)로 정의한다. 장기 추세를 완화하기 위한 Rolling Window(이동 기간)는 `volume_window_days`를 결과에 명시한 별도 변형 지표(Metric Variant)로 추가할 수 있다.

```text
예시
- daily_velocity_spendable_utxo_v1
- rolling_365d_velocity_spendable_utxo_v1
```

이렇게 분리하면 “일별 산출”과 “365일 누적 분자”를 같은 뜻으로 혼동하지 않는다.

---

## 2.2 Transaction Volume 정의(Transaction Volume Definition)

Bitcoin에서 Transaction(거래)은 이전 Transaction Output(거래 출력)을 Input(입력)으로 소비하고, 새로운 Output을 생성하는 구조다. 아직 소비되지 않은 Output은 UTXO(Unspent Transaction Output, 미사용 거래 출력)로 남으며, 이후 다른 거래의 Input으로 사용될 수 있다.

따라서 Transaction Volume(거래 이동량)은 단순히 “모든 거래의 금액”이라고 정의하면 불명확하다. 특히 일반적인 Bitcoin 거래에는 수취인에게 전달되는 출력과, 남은 금액을 송신자 측에 반환하는 Change Output(거스름 출력)이 함께 존재할 수 있다.

### 2.2.1 경제적 거래량과 원천 데이터 기반 이동량의 구분

```text
Economic Transfer Volume(경제적 거래량)
= 실제 소유 주체 간 경제적 가치 이전을 추정한 이동량

Gross Output Volume(총 출력 이동량)
= 거래가 생성한 출력 값의 합계

둘은 항상 같지 않다.
```

Gross Output Volume에는 Change Output과 동일 주체 내부 이동(Self-churn)이 포함될 수 있다. 따라서 Change Address Heuristic(거스름 주소 추론), Address Clustering(주소 군집화), Entity Label(주체 라벨) 없이 `tx_output` 합계만 계산한 값은 경제적 거래량을 정확히 의미하지 않는다.

본 과제의 V1은 외부 주소 라벨이나 휴리스틱에 의존하지 않고, 원천 온체인 테이블만으로 재현 가능한 기준선을 우선한다.

### 2.2.2 V1 분자: 일별 총 소비 가능 출력 이동량(Daily Gross Spendable Output Volume)

본 과제의 기본 분자는 아래와 같이 정의한다.

```text
daily_gross_spendable_output_volume_btc(d)
=
SUM(value_sats of transaction outputs)
WHERE
- transaction is non-coinbase
- block belongs to the best chain at computation time
- output is not provably unspendable
- block header timestamp belongs to UTC date d
```

용어 정의는 아래와 같다.

| 용어 | 정의 | 본 과제에서의 처리 |
|---|---|---|
| Coinbase Transaction(코인베이스 거래) | 블록 보상과 거래 수수료를 수령하기 위해 블록 첫 거래로 생성되는 특수 거래 | 일반 사용자 간 이동이 아니므로 V1 분자에서 제외 |
| Spendable Output(소비 가능 출력) | 스크립트 조건상 소비 가능성이 있는 거래 출력 | V1 분자에 포함 |
| Provably Unspendable Output(증명 가능한 소비 불가능 출력) | 스크립트 조건상 소비가 불가능하다고 판별되는 출력 | V1 분자에서 제외 |
| Change Output(거스름 출력) | 입력 합계에서 수취 금액과 수수료를 뺀 잔여 금액을 송신자 측에 돌려주는 출력 | V1에서 제거하지 않음 |
| Self-churn(자체 순환 이동) | 동일 경제 주체가 통제하는 주소 간 이동 | V1에서 제거하지 않음 |

따라서 V1의 분자 명칭은 다음을 사용한다.

```text
daily_gross_spendable_output_volume_btc
```

아래 표현은 사용하지 않는다.

```text
금지 표현
- estimated_transaction_volume_btc
- economic_transaction_volume_btc
- actual_transfer_volume_btc

사유
- Change Output, Self-churn, 주소 군집화 처리 규칙을
  본 과제 V1에서 검증하거나 구현하지 않았기 때문
```

### 2.2.3 Transaction Volume 해석 시 주의점

`daily_gross_spendable_output_volume_btc`가 증가했다는 것은 온체인 출력 이동이 증가했다는 사실을 뜻한다. 그러나 아래를 직접 증명하지는 않는다.

```text
직접 증명하지 않는 것
- 실제 신규 투자 수요 증가
- 서로 다른 경제 주체 간 순수 이전 증가
- 거래소 매수·매도 증가
- 시장 가격 상승 또는 하락
```

즉 V1 분자는 정확한 원천 기반 활동량(Activity Proxy)이지, 경제적 의미가 완전히 정제된 거래량이 아니다.

---

## 2.3 Circulating Supply 정의(Circulating Supply Definition)

Circulating Supply(유통 공급량)는 단일한 프로토콜 필드가 아니다. 발행 총량(Total Issued Supply), 현재 소비 가능한 UTXO 공급량(Spendable UTXO Supply), 장기 비활성 물량을 제외한 조정 공급량(Dormancy-adjusted Supply)은 서로 다른 객체다.

본 과제는 이들을 혼용하지 않는다.

```text
Total Issued Supply
≠ Spendable UTXO Supply
≠ Dormancy-adjusted UTXO Supply
```

### 2.3.1 발행 총량(Total Issued Supply)

```text
total_issued_supply_btc(d)
=
누적 coinbase issuance를 기준으로 한 프로토콜 발행량 stock
```

발행 총량은 Bitcoin 공급 스케줄 관점의 Stock(저량)이다. 이 값은 특정 UTXO가 현재 소비 가능한지, 장기 비활성 상태인지, 소비 불가능한 스크립트인지와 별개의 객체다.

### 2.3.2 소비 가능 UTXO 공급량(Spendable UTXO Supply)

본 과제의 기본 공급량 분모는 UTXO 관점의 소비 가능 공급량이다.

```text
spendable_utxo_supply_btc(d)
=
SUM(value_sats of unspent outputs at day-end)
WHERE
- output belongs to the best chain at computation time
- output is not provably unspendable
- output satisfies the coinbase maturity rule when applicable
```

이 값은 기준일 종료 시점에 다음 조건을 만족하는 UTXO의 합이다.

| 포함 또는 제외 | 기준 |
|---|---|
| 포함 | 아직 소비되지 않은 일반 UTXO |
| 포함 | 장기 비활성 상태이지만 스크립트상 소비 가능한 UTXO |
| 제외 | 소비 불가능하다고 증명되는 출력 |
| 제외 | 아직 성숙 조건을 만족하지 못한 coinbase UTXO |
| 제외 | 관측 시점의 best chain에서 이탈한 branch에 속한 출력 |

Coinbase Transaction의 UTXO는 최소 100개 블록이 추가되기 전에는 소비할 수 없다. 그러므로 `spendable_utxo_supply_btc`는 발행 총량과 다르다.

### 2.3.3 장기 비활성 UTXO 공급량(Dormant UTXO Supply)

Dormant UTXO(장기 비활성 UTXO)는 일정 기간 동안 소비되지 않은 UTXO를 뜻한다.

```text
dormant_utxo_supply_btc(d)
=
SUM(value_sats of unspent spendable UTXOs at day-end)
WHERE
utxo_age_days >= dormant_threshold_days
```

여기서 `dormant_threshold_days`는 온체인 사실이 아니라 정책 파라미터다.

```text
예시
dormant_threshold_days = 3650
supply_policy_version = dormant_10y_v1
```

중요한 해석 원칙은 아래와 같다.

```text
Dormant UTXO
≠ Lost Coin(영구 분실 코인)

Dormant UTXO
= 오랜 기간 소비되지 않았다는 관측 상태
```

장기 비활성 UTXO는 향후 다시 소비될 수 있으므로, 이를 영구적으로 시장에서 사라진 공급량으로 단정하면 안 된다.

### 2.3.4 장기 비활성 조정 UTXO 공급량(Dormancy-adjusted UTXO Supply)

장기 비활성 물량을 제외한 공급량은 유동성 민감도를 보기 위한 보조 분모로 정의한다.

```text
dormancy_adjusted_utxo_supply_btc(d)
=
spendable_utxo_supply_btc(d)
-
dormant_utxo_supply_btc(d)
```

이 값은 “실제 유통 공급량의 유일한 정답”이 아니다. 장기 비활성 공급이 시장에서 당장 움직일 가능성이 낮다는 가정을 반영한 정책 기반 해석값이다.

### 2.3.5 소비 불가능한 출력과 Burned Supply(소각 공급량)

본 과제 V1은 온체인 데이터만으로 판별 가능한 Provably Unspendable Output만 공급량에서 제외한다.

```text
V1 Exclusion
- OP_RETURN 기반 Null-data Output 등
  스크립트 조건상 소비가 불가능한 출력
```

아래 항목은 V1에서 자동 제외하지 않는다.

```text
V1 Non-exclusion
- 외부 라벨만으로 Burn Address라고 분류된 주소
- 개인키가 없다고 추정되는 주소
- 소유권 또는 소비 가능성을 원천 온체인 데이터만으로 증명할 수 없는 주소
```

이들은 외부 큐레이션(External Curation)과 신뢰도 정책(Confidence Policy)이 필요한 객체다. 향후 확장 시 Versioned Burn Registry(버전 관리되는 소각 레지스트리)로 분리할 수 있지만, V1 기본 분모에 섞지 않는다.

### 2.3.6 장기 비활성 UTXO 소비 이동량(Dormant UTXO Spent Volume)

장기 비활성 UTXO가 다시 소비된 양은 공급량이 아니라 흐름량이다.

```text
dormant_utxo_spent_volume_btc(d)
=
SUM(previous_output_value_sats)
WHERE
- spending date = d
- age_at_spend_days >= dormant_threshold_days
```

따라서 아래 명칭을 사용한다.

```text
권장
dormant_utxo_spent_volume_btc

사용하지 않음
dormant_reactivated_supply_btc
```

`dormant_utxo_spent_volume_btc`는 장기 보유된 UTXO가 다시 이동하기 시작하는 상황을 보조적으로 추적하기 위한 지표다. 이 값은 공급량을 새로 증가시키는 값이 아니라, 기존 UTXO가 소비된 활동 흐름이다.

---

## 2.4 지표 해석 범위(Metric Interpretation Scope)

Velocity는 온체인 활동의 상대적 크기를 보여주는 보조 지표다. 가격 방향, 투자자 의도, 실제 경제 활동을 단독으로 판정하는 지표가 아니다.

### 2.4.1 해석 가능한 범위(Inference Scope)

본 과제의 V1 기준 Velocity는 아래를 관찰하는 데 사용할 수 있다.

```text
- 특정 기간에 관측된 온체인 출력 이동량의 상대적 변화
- 동일한 공급량 정의 내에서의 시간 경과에 따른 활동도 변화
- Spendable UTXO Supply와 Dormancy-adjusted UTXO Supply 간
  분모 차이가 해석에 미치는 민감도
- 장기 비활성 UTXO가 실제로 소비되는 흐름의 변화
```

### 2.4.2 단독으로 해석하면 안 되는 범위(Non-inference Scope)

Velocity가 높거나 낮다는 사실만으로 아래를 결론내리면 안 된다.

```text
직접 결론 불가
- 매수세 또는 매도세가 우세하다
- 가격이 상승하거나 하락한다
- 신규 사용자 또는 실제 결제 사용량이 증가했다
- 거래소 유입 또는 유출이 증가했다
- 장기 보유자가 매도했다
- 특정 국가·기관·거래소의 활동이 증가했다
```

그 이유는 V1 분자에 Change Output과 Self-churn이 포함될 수 있고, 주소 또는 엔터티(Entity) 수준의 의미를 V1에서 식별하지 않기 때문이다.

### 2.4.3 해석 보강에 필요한 보조 데이터(Complementary Data)

Velocity 해석을 강화하려면 별도 지표 또는 레이어와 결합해야 한다.

| 보조 데이터 | 보강하는 해석 |
|---|---|
| Exchange Flow(거래소 입출금 흐름) | 거래소로의 이동과 보관 이동 구분 |
| Address 또는 Entity Label(주소 또는 주체 라벨) | 동일 주체 내부 이동과 주체 간 이동 구분 |
| Change Output Heuristic(거스름 출력 추론) | Gross Output Volume의 과대계산 완화 |
| Dormant UTXO Spent Volume(장기 비활성 UTXO 소비 이동량) | 장기 보유 물량의 실제 재이동 추적 |
| Market Price 및 Liquidity Data(시장 가격 및 유동성 데이터) | 온체인 활동과 시장 반응의 관계 분석 |
| Off-chain Metadata(오프체인 메타데이터) | 상장 상태, 입출금 중단, 거래 제한 등 외부 이벤트 해석 |

이 보조 데이터는 기본 Velocity 계산식에 혼합하지 않는다. 원천 온체인 지표와 해석 레이어를 분리해야 계산의 재현성(Reproducibility)과 해석의 정직성(Interpretive Honesty)을 함께 유지할 수 있다.

### 2.4.4 요약(Section Summary)

```text
Network Velocity
= 이동량과 공급량 정의에 따라 달라지는 정책 기반 비율 지표

V1 Transaction Volume
= Change Output을 포함할 수 있는 Gross Spendable Output Volume

V1 Supply
= Spendable UTXO Supply와 Dormancy-adjusted UTXO Supply를 분리

Dormant UTXO
= 영구 분실 코인이 아니라 장기 미소비 상태

Dormant UTXO Spent Volume
= 장기 비활성 UTXO가 다시 소비된 흐름량

Interpretation
= 온체인 활동도 보조 지표이며,
  가격·수급·의도를 단독으로 확정하지 않음
```

---

## 다음 절 연결(Next Section)

다음 절에서는 본 개요에서 정의한 객체를 기준으로 다음 내용을 구체화한다.

1. 원천 테이블(`block`, `tx`, `tx_input`, `tx_output`, `utxo`)별 최소 필드 명세  
2. 원천 사실(Raw Fact)과 파생 필드(Derived Field)의 구분  
3. 각 필드가 분자·분모·품질 검증·Reorg 대응에 필요한 이유  
4. 과거 `metric_date` 기준 UTXO 공급량을 계산하기 위한 UTXO Lifecycle(UTXO 생명주기) 전제  

---

## 검증 근거(Verification Basis)

- CryptoQuant Data Engineer 사전 과제 PDF: Network Velocity 기본식과 Circulating Supply 정책을 직접 정의하라는 요구사항
- Bitcoin Developer Documentation: Transaction Output, UTXO, Change Output, Coinbase Transaction, Coinbase Maturity, best-chain 특성
- CryptoQuant 공식 소개 페이지: 온체인·오프체인 데이터 및 제품화된 차트·API 제공 맥락
