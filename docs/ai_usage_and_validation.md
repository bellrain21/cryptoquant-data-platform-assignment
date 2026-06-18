# AI 활용 및 검증 기록(AI Usage and Validation Record)

> **문서 상태(Status)**: Draft  
> **목적(Purpose)**: 과제 수행에서 AI를 사용한 범위, 검증 방식, 최종 판단 책임을 투명하게 기록한다.

## 1. 활용 원칙(Usage Principles)

AI는 초안 생성, 용어 충돌 탐지, 설계 대안 비교, 문서 구조 점검에 사용했다. 
AI 출력은 사실 또는 정답으로 간주하지 않았으며, 최종 정의와 구현 판단은 공식 문서·과제 원문·실행 결과로 검증했다.

```text
AI의 역할
- 초안 검토
- 논리적 비약 사항 검토 및 반박자
- 누락 점검 도구
- 문서 구조 정리 도구

작성자의 역할
- 요구사항 해석
- 가치 판단
- 근거 확인
- 정책 선택
- 구현과 테스트
- 최종 책임
```

## 2. AI 활용 범위(Usage Scope)

| 구분 | 사용 목적 | 최종 검증 방식 |
|---|---|---|
| 과제 구조화 | 과제 1·2 문서 목차와 디렉터리 구조 초안 | 과제 PDF 요구사항과 파일 경로 대조 |
| 용어 검토 | Velocity, UTXO, dormant, reorg, idempotency 용어 충돌 탐지 | CryptoQuant·Bitcoin·Delta·Airflow 공식 문서 확인 |
| 설계 대안 | Supply policy, Reorg recovery, Delta merge 방식 비교 | 원천 데이터 재현성·운영 리스크 기준으로 선택 |
| 문서 초안 | 한국어 중심 설계 문서 초안 작성 | 작성자 검토 후 사실·정책·가정 분리 |
| 코드 보조 | 구현 단계의 오류 원인 분석 및 테스트 항목 도출 | 실제 실행·단위 테스트·통합 테스트 |

## 3. 대표 프롬프트 범주(Representative Prompt Categories)

실제 대화 전체를 복제하지 않고, 사용 목적을 재현 가능한 수준으로 요약한다.

```text
- Bitcoin Velocity의 분자·분모를 raw table만으로 재현 가능하게 정의하라.
- Dormant UTXO와 lost coin을 혼동하지 않는 공급 정책을 설계하라.
- Chain Reorganization이 UTXO supply와 rolling metric에 미치는 영향을 검토하라.
- Delta Lake에서 retry와 backfill 중복을 막는 논리 키와 MERGE 전략을 검토하라.
- Airflow data interval 기반 backfill 구조를 설계하라.
- ERC-20 Transfer event를 logs topic/data에서 decoding하는 모델 계약을 작성하라.
```

## 4. 검증 절차(Validation Procedure)

### 4.1 문서 검증

- [x] 과제 PDF의 필수 요구사항과 문서 목차를 대조
- [x] 공개 제품 참조와 과제 전용 지표 정의를 분리
- [x] 원천 사실·정책 결정·구현 가정을 분리
- [x] 문서 내 상대 링크와 파일명 구조를 일치시킴
- [x] 완료되지 않은 구현을 완료로 표기하지 않음

### 4.2 도메인·플랫폼 검증

- [x] CryptoQuant 공개 API의 Velocity 정의 확인
- [x] Bitcoin UTXO, coinbase maturity, change output 특성 확인
- [x] Airflow data interval·backfill 개념 확인
- [x] Delta Lake MERGE와 constraints 문서 확인
- [x] ERC-20 Transfer event 정의 확인
- [x] dbt project 설정 파일 및 source/model 구조 확인

### 4.3 구현 검증 — 구현 완료 후 갱신

- [ ] Airflow DAG parse 및 scheduled run
- [ ] RPC 수집 결과와 block range 대조
- [ ] Delta Lake 중복 적재 방지 검증
- [ ] dbt run 및 dbt test
- [ ] Reorg 또는 synthetic reorg fixture 기반 복구 테스트
- [ ] README 실행 명령과 실제 실행 결과 대조

## 5. 채택·폐기 판단(Adoption and Rejection Decisions)

| 항목 | 판단 | 이유 |
|---|---|---|
| CryptoQuant 제품 Velocity를 그대로 재현 | 폐기 | 내부 `estimated transaction volume` 세부 규칙이 공개되지 않음 |
| 365일 후행 window | 채택 | CryptoQuant 공개 Velocity의 제품 참조와 정합 |
| 하루치 분자를 기본 Velocity로 사용 | 폐기 | 일 단위 배치와 지표 window를 혼동할 위험 |
| Dormant UTXO를 lost coin으로 간주 | 폐기 | 장기 미사용은 영구 분실 증명이 아님 |
| `dormant_reactivated_supply` 명칭 | 폐기 | 공급량이 아니라 기간 내 소비 흐름 |
| blind append | 폐기 | retry·backfill에서 중복 가능 |
| logical key + Delta MERGE | 채택 | 재실행·backfill의 최종 상태 수렴 |
| 외부 burn address label을 V1에서 차감 | 폐기 | 원천 온체인 데이터만으로 소비 불가능을 증명하기 어려움 |

## 6. 참고 자료(Validation Sources)

- CryptoQuant BTC Network Data: https://userguide.cryptoquant.com/api/btc-network-data
- CryptoQuant About: https://cryptoquant.com/ko/about
- Bitcoin Developer Documentation — Block Chain: https://developer.bitcoin.org/devguide/block_chain.html
- Bitcoin Developer Documentation — Transactions: https://developer.bitcoin.org/examples/transactions.html
- Apache Airflow — DAG Runs: https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/dag-run.html
- Apache Airflow — Backfill: https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/backfill.html
- Delta Lake — MERGE: https://docs.delta.io/delta-update/
- Delta Lake — Constraints: https://docs.delta.io/delta-constraints/
- EIP-20: https://eips.ethereum.org/EIPS/eip-20
- dbt — dbt_project.yml: https://docs.getdbt.com/reference/dbt_project.yml
