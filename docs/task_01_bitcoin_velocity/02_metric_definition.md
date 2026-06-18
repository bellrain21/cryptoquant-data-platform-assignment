# 2. Bitcoin Velocity 지표 개요(Bitcoin Velocity Metric Overview)

> **문서 상태(Status)**: Draft  
> **문서 역할(Role)**: Network Velocity, Transaction Volume, Circulating Supply, 해석 범위의 객체 경계를 정의한다.

## 2.1 Network Velocity 정의(Network Velocity Definition)

Network Velocity는 특정 기간 동안 관측된 Bitcoin 이동량(Flow)을 특정 시점의 공급량(Stock)으로 나눈 회전율형 온체인 지표다.

```text
Velocity
=
Transfer Volume
/
Supply
```

이 값은 물리적 속도가 아니라 공급량 대비 이동 활동의 상대적 크기를 나타낸다.

### 2.1.1 CryptoQuant 공개 제품 참조(Product Reference)

CryptoQuant 공개 API는 Bitcoin Velocity를 아래와 같이 설명한다.

```text
CryptoQuant Public Velocity(d)
=
Trailing 1-Year Estimated Transaction Volume(d)
/
Current Total Supply(d)
```

API의 `window=day`, `window=hour`, `window=block`은 반환 데이터의 시간 해상도이며, 공개 정의의 후행 1년 분자를 하루치 분자로 바꾸는 뜻으로 해석하지 않는다.

### 2.1.2 과제 전용 지표(Assignment-specific Metric)

과제는 공급량 정책을 직접 정의하도록 요구한다. 또한 제품 내부의 `estimated transaction volume` 추정 규칙이 제공되지 않았다. 따라서 본 과제의 기본 지표는 아래와 같이 별도로 정의한다.

```text
assignment_velocity_365d_policy_eligible_utxo_v1(d)
=
trailing_365d_gross_onchain_output_volume_v1_btc(d)
/
policy_eligible_utxo_supply_v1_btc(d)
```

보조 민감도 지표는 아래와 같다.

```text
assignment_velocity_365d_dormancy_adjusted_utxo_v1(d)
=
trailing_365d_gross_onchain_output_volume_v1_btc(d)
/
dormancy_adjusted_utxo_supply_v1_btc(d)
```

두 값 모두 CryptoQuant 공개 제품의 수치와 동일하다고 주장하지 않는다.

## 2.2 Transaction Volume 정의(Transaction Volume Definition)

Bitcoin 거래는 기존 UTXO를 입력으로 소비하고 새 출력을 생성한다. 일반 거래는 수취인에게 전달되는 출력 외에 잔여 금액을 송신자 측에 되돌리는 Change Output(거스름 출력)을 포함할 수 있다.

따라서 아래 두 개념은 동일하지 않다.

```text
Economic Transfer Volume(경제적 거래량)
= 실제 경제 주체 간 가치 이전을 추정한 이동량

Gross On-chain Output Volume(총 온체인 출력 이동량)
= 거래가 생성한 output value의 합계에 가까운 원천 기반 이동량
```

### 2.2.1 V1 분자 정의

본 과제 V1은 주소 군집화, Change Address Heuristic, Entity Label을 사용하지 않는다. 따라서 분자는 아래처럼 정의한다.

```text
daily_gross_onchain_output_volume_v1_btc(d)
=
SUM(tx_output.value_sats) / 100,000,000
WHERE
- transaction is non-coinbase
- block belongs to the best chain at observation time
- output is not classified as provably unspendable
- block header timestamp belongs to UTC date d
```

후행 365일 분자는 다음과 같다.

```text
trailing_365d_gross_onchain_output_volume_v1_btc(d)
=
SUM(daily_gross_onchain_output_volume_v1_btc(t))
for t in [d - 364 days, d]
```

### 2.2.2 V1 분자의 한계

V1 분자는 Change Output과 Self-churn(동일 주체 내부 이동)을 포함할 수 있다. 따라서 아래 표현은 사용하지 않는다.

```text
사용하지 않음
- estimated_transaction_volume_btc
- economic_transaction_volume_btc
- actual_transfer_volume_btc
```

V1 분자는 **원천 온체인 데이터만으로 재현 가능한 Gross On-chain Output Volume**이다.

## 2.3 Circulating Supply 정의(Circulating Supply Definition)

Circulating Supply는 단일 프로토콜 필드가 아니다. 본 과제는 발행 총량, 정책상 포함 가능한 UTXO 공급량, 장기 비활성 조정 공급량을 분리한다.

```text
Total Issued Supply
≠ Policy-eligible UTXO Supply
≠ Dormancy-adjusted UTXO Supply
```

### 2.3.1 Total Issued Supply(발행 총량)

```text
total_issued_supply_btc(d)
=
누적 coinbase issuance를 기준으로 한 프로토콜 발행량
```

이는 발행량 관점의 Stock이며, 현재 UTXO가 정책상 분모에 포함되는지와는 다른 객체다.

### 2.3.2 Policy-eligible UTXO Supply(정책상 포함 가능한 UTXO 공급량)

본 과제의 기본 분모는 아래와 같다.

```text
policy_eligible_utxo_supply_v1_btc(d)
=
SUM(value_sats of UTXOs at day-end)
WHERE
- output is in the best chain at observation time
- output is unspent at the cutoff block
- output is not provably unspendable
- coinbase output satisfies the 100-block maturity rule
```

`policy-eligible`은 모든 지갑·스크립트 조건에서 즉시 소비 가능함을 증명한다는 뜻이 아니다. 본 과제의 V1 정책상 유통 공급량 계산에 포함된다는 뜻이다.

### 2.3.3 Dormant UTXO Supply(장기 비활성 UTXO 공급량)

```text
dormant_utxo_supply_v1_btc(d)
=
SUM(value_sats of policy-eligible UTXOs at day-end)
WHERE
utxo_age_days >= dormant_threshold_days
```

`dormant_threshold_days`는 원천 사실이 아니라 정책 파라미터다.

```text
예시
dormant_threshold_days = 3650
supply_policy_version = dormant_10y_v1
```

Dormant UTXO는 오랜 기간 소비되지 않았다는 관측 상태일 뿐 영구 분실 코인이라는 판정이 아니다.

### 2.3.4 Dormancy-adjusted UTXO Supply(장기 비활성 조정 UTXO 공급량)

```text
dormancy_adjusted_utxo_supply_v1_btc(d)
=
policy_eligible_utxo_supply_v1_btc(d)
-
dormant_utxo_supply_v1_btc(d)
```

이 값은 장기 비활성 물량을 분모에서 제외했을 때의 유동성 민감도 분석을 위한 보조 분모다. 절대적 유통 공급량의 유일한 정답으로 취급하지 않는다.

### 2.3.5 Burn 처리(Burn Treatment)

V1은 원천 온체인 데이터로 판별 가능한 소비 불가능 출력만 기본 공급량에서 제외한다.

```text
V1 exclusion
- OP_RETURN 기반 null-data output 등
  스크립트 조건상 소비가 불가능하다고 판별되는 output
```

외부 라벨만으로 burn address라고 부르는 주소, 개인키가 없다고 추정되는 주소는 V1에서 자동 제외하지 않는다. 이들은 외부 큐레이션과 신뢰도 정책이 필요한 대상이며 향후 버전 관리되는 burn registry로 분리한다.

### 2.3.6 Dormant UTXO Spent Volume(장기 비활성 UTXO 소비 이동량)

```text
dormant_utxo_spent_volume_v1_btc(d)
=
SUM(previous_output_value_sats) / 100,000,000
WHERE
- spending date = d
- age_at_spend_days >= dormant_threshold_days
```

이 값은 특정 시점에 남아 있는 공급량이 아니라 특정 기간에 발생한 이동량이다. 따라서 `dormant_reactivated_supply`라는 이름을 사용하지 않는다.

## 2.4 지표 해석 범위(Metric Interpretation Scope)

### 해석 가능한 범위

- 동일한 정의와 정책 버전 내에서의 온체인 이동 활동 변화
- 기본 분모와 장기 비활성 조정 분모의 차이에 따른 민감도
- 장기 비활성 UTXO가 실제로 소비되기 시작하는 흐름 변화
- 원천 데이터 품질과 체인 상태 변경이 결과에 미치는 영향

### 단독으로 결론내리면 안 되는 범위

- 가격 상승·하락
- 매수세·매도세 우위
- 신규 투자 수요 증가
- 거래소 입출금 증가
- 특정 기관 또는 국가의 활동 증가
- 장기 보유자의 매도 확정

이 결론에는 주소 라벨, 거래소 흐름, Change Output 처리, 시장 가격·유동성 등 별도 데이터가 필요하다.

## 참고 자료(References)

- CryptoQuant BTC Network Data: https://userguide.cryptoquant.com/api/btc-network-data
- Bitcoin Developer Documentation — Block Chain: https://developer.bitcoin.org/devguide/block_chain.html
- Bitcoin Developer Documentation — Transactions: https://developer.bitcoin.org/examples/transactions.html
