# AI 활용 및 검증 기록(AI Usage and Validation Record)

> **문서 상태(Status)**: Draft  
> **목적(Purpose)**: AI 활용 범위와 최종 검증 책임을 명확히 한다.

## 1. 활용 원칙(Usage Principles)

AI는 문서 구조화, 용어 충돌 탐지, 설계 누락 점검의 보조 도구로 사용했다. AI 출력은 사실 또는 정답으로 간주하지 않았으며, 최종 정의·정책 선택·구현 판단은 작성자가 과제 원문, 공식 문서, 실행 결과를 기준으로 검증했다.

```text
AI의 역할
- 초안 구조화
- 대안 비교를 위한 반례·누락 점검
- 용어와 문서 일관성 점검

작성자의 역할
- 요구사항 해석
- 근거 확인
- 정책 선택
- 구현과 테스트
- 최종 책임
```

## 2. 검증 기준(Validation Criteria)

### 2.1 문서 검증

- [x] 과제 필수 요구사항과 문서 목차 대조
- [x] 공개 제품 참조와 과제 전용 지표 정의 분리
- [x] 원천 사실·정책 결정·구현 가정 분리
- [x] 문서 내 상대 링크와 파일명 표기 대조
- [x] 완료되지 않은 구현을 완료로 표기하지 않음

### 2.2 도메인·플랫폼 검증

- [x] CryptoQuant 공개 Velocity 정의 확인
- [x] Bitcoin UTXO, coinbase maturity, chain reorganization 개념 확인
- [x] Airflow data interval·backfill 개념 확인
- [x] Delta Lake MERGE 및 partition 전략 확인
- [x] Ethereum JSON-RPC log field와 reorg handling 확인
- [x] ERC-20 Transfer event와 dbt source/model 구조 확인

### 2.3 구현 검증 — 구현 완료 후 갱신

- [ ] Airflow DAG parse 및 scheduled run
- [ ] RPC 수집 결과와 block range 대조
- [ ] Bronze observation 및 Silver canonical 중복 방지 검증
- [ ] dbt run 및 dbt test
- [ ] Reorg 또는 synthetic reorg fixture 기반 복구 테스트
- [ ] README 실행 명령과 실제 실행 결과 대조

## 3. 주요 설계 판단(Selected Decisions)

| 항목 | 판단 | 이유 |
|---|---|---|
| CryptoQuant 제품 Velocity를 그대로 재현 | 폐기 | 내부 `estimated transaction volume` 세부 규칙이 공개되지 않음 |
| 365일 후행 window | 채택 | 공개 Velocity 설명과 개념적으로 정합 |
| Dormant UTXO를 lost coin으로 간주 | 폐기 | 장기 미사용은 영구 분실 증명이 아님 |
| blind append | 폐기 | retry·backfill에서 중복 가능 |
| Bitcoin current Gold와 reorg audit | 분리 | 현재 소비 결과와 이전 체인 revision 이력의 역할이 다름 |
| Ethereum observation과 canonical view | 분리 | reorg 전후 관측 이력 보존과 current event uniqueness를 동시에 만족 |
| ERC-20 topic0 단독 판정 | 폐기 | Transfer signature만으로 token standard를 단정할 수 없음 |

## 4. 참고 자료(Validation Sources)

- CryptoQuant BTC Network Data: https://userguide.cryptoquant.com/api/btc-network-data
- Bitcoin Developer Documentation — Block Chain: https://developer.bitcoin.org/devguide/block_chain.html
- Bitcoin Developer Documentation — Transactions: https://developer.bitcoin.org/examples/transactions.html
- Apache Airflow — DAG Runs: https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/dag-run.html
- Apache Airflow — Backfill: https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/backfill.html
- Delta Lake — MERGE: https://docs.delta.io/delta-update/
- Delta Lake — Constraints: https://docs.delta.io/delta-constraints/
- Ethereum JSON-RPC: https://ethereum.org/developers/docs/apis/json-rpc/
- Geth — Real-time Events: https://geth.ethereum.org/docs/interacting-with-geth/rpc/pubsub
- EIP-20: https://eips.ethereum.org/EIPS/eip-20
- dbt — dbt_project.yml: https://docs.getdbt.com/reference/dbt_project.yml
