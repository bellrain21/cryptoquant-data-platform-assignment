# 1. 과제 이해 및 설계 방향(Task Understanding and Design Direction)

> **문서 상태(Status)**: Draft  
> **문서 역할(Role)**: 과제의 목적, 범위, 설계 원칙을 고정한다.  
> **제외 범위(Out of Scope)**: 분자·분모의 상세 정의와 수식은 [02_metric_definition(지표_정의).md](./02_metric_definition(지표_정의).md)에서 다룬다.

## 1.1 과제 목적 해석(Task Objective)

본 과제의 핵심은 Bitcoin Velocity 값을 한 번 계산하는 것이 아니라, `block`, `tx`, `tx_input`, `tx_output`, `utxo` Delta Lake 테이블을 바탕으로 일 단위 지표를 안정적으로 생산하는 데이터 파이프라인을 설계하는 데 있다.

따라서 산출물은 단순한 비율값이 아니라 아래 메타데이터를 함께 보존하는 지표 데이터 제품이다.

```text
- 어떤 원천 체인 상태에서 계산했는가
- 어떤 지표 정의와 공급 정책을 사용했는가
- 어떤 기준일과 확인 깊이를 적용했는가
- 재실행, Backfill, Reorg 이후 어떻게 복구하는가
```

## 1.2 핵심 설계 질문(Key Design Questions)

1. 어떤 원천 사실을 분자와 분모 계산에 사용할 것인가.
2. 어떤 공급량을 과제 전용 분모로 정의할 것인가.
3. 같은 입력을 재실행해도 결과가 중복 없이 수렴하는가.
4. 체인 상태가 변경되었을 때 영향을 받은 결과를 어떻게 추적하고 재계산하는가.
5. 공개 제품 참조와 과제 전용 구현을 어떻게 구분해 과장 없이 설명하는가.

## 1.3 설계 범위(Scope)

### 포함 범위(In Scope)

- 관측 시점 기준 Best Chain(최선 체인) 블록과 거래 처리
- 원천 출력(Output) 및 UTXO 생명주기 기반 이동량·공급량 계산
- 소비 불가능 출력(Provably Unspendable Output)과 장기 비활성 UTXO 분리
- 일 단위 배치, 품질 검증, 멱등성, Backfill, Reorg 복구
- 지표 정의·정책·체인 체크포인트의 버전 및 추적 정보 보존

### 제외 범위(Out of Scope)

- 거래소 상장 상태, 거래 중지, 입출금 중단, 호가·유동성 등 오프체인 데이터
- 주소 소유 주체(Entity Ownership) 판정과 동일 주체 내부 이동 제거
- 외부 주소 라벨만으로 소각 주소를 확정하는 처리
- CryptoQuant 내부의 비공개 `estimated transaction volume` 산출 규칙 재현

제외 범위는 가치가 없어서 제외하는 것이 아니다. 이번 과제의 기본 계산을 온체인 원천 사실로 재현 가능하게 유지하기 위해 별도 해석 레이어로 분리한다.

## 1.4 공개 제품 참조와 과제 전용 지표 분리(Product Reference vs Assignment Metric)

CryptoQuant 공개 API는 Bitcoin Velocity를 후행 1년의 추정 거래 이동량을 현재 총 공급량으로 나눈 값으로 설명한다.

```text
Product Reference
=
Trailing 1-Year Estimated Transaction Volume
/
Current Total Supply
```

그러나 과제는 Circulating Supply 정책을 직접 정의하도록 요구하며, 제품 내부의 추정 이동량 계산 규칙과 전체 원천 스키마를 제공하지 않는다. 따라서 본 과제는 아래 원칙을 채택한다.

```text
공개 제품 정의
= 제품 맥락과 용어를 이해하기 위한 참조

과제 전용 정의
= 제공된 원천 테이블과 명시적 정책으로 재현 가능한 계산 규칙
```

이 구분은 제품 정의를 회피하는 것이 아니라, 확인되지 않은 내부 알고리즘을 사실처럼 작성하지 않기 위한 설계 규율이다.

## 1.5 일 단위 배치와 365일 후행 지표(Daily Batch and Trailing Window)

일 단위 배치(Daily Batch)는 **실행·게시 주기**다. Velocity의 분자가 하루치라는 뜻이 아니다.

본 과제의 기본 지표는 매일 아래 값을 다시 계산해 게시한다.

```text
assignment_velocity_365d_policy_eligible_utxo_v1(d)
=
최근 365개 UTC 날짜의 gross on-chain output volume 합계
/
기준일 종료 시점의 policy-eligible UTXO supply
```

즉 다음 두 개념을 분리한다.

```text
Publication Cadence(게시 주기)
= Daily

Volume Window(이동량 누적 기간)
= Trailing 365 calendar days
```

## 1.6 설계 원칙(Design Principles)

### 원천 사실, 정책, 구현 가정의 분리

| 구분 | 예시 | 관리 방식 |
|---|---|---|
| 원천 사실(Source Fact) | block hash, height, txid, output value | 원천 또는 정규화 계층에 보존 |
| 정책 결정(Policy Decision) | dormant threshold, 최소 확인 깊이, 분모 정의 | 명시적 버전 관리 |
| 구현 가정(Implementation Assumption) | UTXO lifecycle 필드 제공 여부 | 문서와 코드 설정에 기록 |

### 재현성(Reproducibility)

동일한 체인 상태, 지표 정의 버전, 정책 버전, 코드 버전, 데이터 구간을 입력하면 동일한 결과가 생성돼야 한다.

### 추적성(Traceability)

각 결과는 최소한 아래를 추적할 수 있어야 한다.

```text
metric_date
metric_definition_version
supply_policy_version
pipeline_code_version
metric_cutoff_block_height
metric_cutoff_block_hash
as_of_best_chain_tip_height
as_of_best_chain_tip_hash
observed_at
```

### 복구 가능성(Recoverability)

실패, 수동 재실행, Backfill, Reorg 발생 시 별도 임시 로직이 아니라 동일한 변환 경로로 영향 구간을 재계산한다.

## 1.7 운영 목표(Operational Goal)

| 목표 | 의미 |
|---|---|
| 재현성 | 같은 입력은 같은 결과 |
| 멱등성 | 같은 입력을 여러 번 실행해도 중복 없는 최종 상태 |
| 완전성 | 필요한 블록·거래·UTXO 생명주기 데이터가 빠지지 않음 |
| 복구 가능성 | 실패 및 Reorg 이후 영향 범위를 다시 계산 가능 |
| 해석 정직성 | 온체인 사실과 정책 기반 추정을 섞지 않음 |

## 1.8 다음 문서

다음 문서에서는 Velocity의 분자·분모·보조 지표를 정의하고, CryptoQuant 공개 Velocity와 과제 전용 지표의 차이를 명시한다.

- [02_metric_definition.md](./02_metric_definition.md)
