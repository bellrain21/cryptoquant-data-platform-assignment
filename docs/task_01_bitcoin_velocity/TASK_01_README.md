# 과제 1. Bitcoin Velocity(비트코인 회전율) 지표 파이프라인 설계

## 문서 목적

본 과제는 Bitcoin Velocity를 단순 계산하는 문제가 아니라, 원천 온체인 데이터에서 재현 가능하고 복구 가능한 지표 데이터 제품을 설계하는 문제다.

이 문서는 다음을 분리한다.

1. **제품 참조(Product Reference)**: CryptoQuant 공개 API가 설명하는 Velocity 개념
2. **과제 전용 지표(Assignment-specific Metric)**: 과제의 원천 테이블과 명시적 정책으로 재현하는 계산 규칙
3. **운영 설계(Operational Design)**: 일 단위 배치, 품질 검증, 재실행, Backfill, Reorg 복구

## 핵심 지표 계약(Metric Contract)

CryptoQuant 공개 API는 Bitcoin Velocity를 다음처럼 설명한다.

```text
CryptoQuant Public Velocity(d)
=
Trailing 1-Year Estimated Transaction Volume(d)
/
Current Total Supply(d)
```

본 과제는 제품 내부의 `estimated transaction volume` 계산 세부 규칙을 공개 자료만으로 재현하지 않는다. 대신 원천 테이블만으로 계산 가능한 아래 지표를 과제 전용 기준선으로 정의한다.

```text
assignment_velocity_365d_policy_eligible_utxo_v1(d)
=
trailing_365d_gross_onchain_output_volume_v1_btc(d)
/
policy_eligible_utxo_supply_v1_btc(d)
```

따라서 본 과제 결과는 CryptoQuant 공개 Velocity와 개념적으로 연관되지만, 수치적 완전 일치를 주장하지 않는다.

## 문서 구성

| 순서 | 문서 | 기존 목차 대응 | 주요 내용 |
|---:|---|---|---|
| 1 | [01_understanding_and_design_direction.md](./01_understanding_and_design_direction.md) | 1 | 과제 목적, 설계 범위, 제품 참조와 과제 정의 분리, 운영 목표 |
| 2 | [02_metric_definition.md](./02_metric_definition.md) | 2 | Network Velocity, Transaction Volume, Circulating Supply, 해석 범위 |
| 3 | [03_data_contract_and_calculation.md](./03_data_contract_and_calculation.md) | 3~8 | 원천 테이블, 필드 명세, 공급 정책, 수식, SQL 또는 의사코드, 더미 출력, 결과 테이블 |
| 4 | [04_daily_batch_pipeline.md](./04_daily_batch_pipeline.md) | 9~11 | Airflow, Spark SQL, Delta Lake, 품질 검증, 멱등성, Backfill |
| 5 | [05_quality_reorg_limitations.md](./05_quality_reorg_limitations.md) | 12~14 | Reorg 대응, 재계산 범위, 한계, 향후 확장 |

## 핵심 용어 교정(Terminology Corrections)

| 이전 표현 | 교정 표현 | 교정 이유 |
|---|---|---|
| Gross Circulating Supply | `policy_eligible_utxo_supply_v1_btc` | 과제 정책상 분모에 포함되는 UTXO라는 의미를 명시 |
| Adjusted Circulating Supply | `dormancy_adjusted_utxo_supply_v1_btc` | 어떤 조정인지 명시 |
| Dormant Reactivated Supply | `dormant_utxo_spent_volume_btc` | 공급량(Stock)이 아니라 기간 내 이동량(Flow) |
| Canonical Block | 관측 시점 기준 Best Chain Block | Reorg 전후 상태가 바뀔 수 있으므로 영구 사실처럼 표현하지 않음 |
| Finality Status | `chain_confidence_status` | Bitcoin은 결정론적 확정성이 아니라 확인 깊이 기반 신뢰도 구조 |
| calculation_version | 정의·정책·코드·체인 상태 버전 분리 | 재계산 결과가 바뀐 원인을 분해하기 위함 |

## 읽는 순서

1. 지표 정의와 공급량 정책을 확인한다.
2. 필요한 원천 필드와 계산 방식을 확인한다.
3. 일 단위 배치와 Delta Lake 갱신 방식을 확인한다.
4. 품질 오류와 Reorg 이후 복구 범위를 확인한다.

## 주요 참고 자료

- CryptoQuant BTC Network Data: https://userguide.cryptoquant.com/api/btc-network-data
- Bitcoin Developer Documentation — Block Chain: https://developer.bitcoin.org/devguide/block_chain.html
- Bitcoin Developer Documentation — Transactions: https://developer.bitcoin.org/examples/transactions.html
