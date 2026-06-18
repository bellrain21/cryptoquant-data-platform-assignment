# AI 활용 및 검증 기록(AI Usage and Validation Record)

> **문서 상태(Status)**: 문서 검증 기록 정리 완료 / 구현 실행 검증은 완료 후 갱신  
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

## 2. AI 입력 기록(Prompt Record)

아래 표는 전체 대화 원문을 재현하는 로그가 아니라, 실제 사용 목적·입력 의도·검증 방법을 평가자가 재현 가능하게 확인할 수 있도록 정리한 대표 프롬프트 요약이다. AI의 제안은 초안 후보이며, 반영 여부는 과제 원문과 공식 문서·설계 일관성으로 별도 판단했다.

| 사용 목적 | 대표 요청 또는 프롬프트 요약 | AI 출력의 사용 방식 | 작성자 검증 및 최종 처리 |
|---|---|---|---|
| 과제 요구사항 매핑 | `요구사항 문서와 Markdown 산출물이 상합하는지 평가` | 요구사항 대비 문서 누락·명칭 불일치 후보 추출 | 과제 PDF의 Task 1·2 항목과 1:1 대조. Task 2 구현 공백은 문서에서 완료로 표기하지 않음 |
| Task 1 정책 설계 검토 | `Bitcoin Velocity의 volume·circulating supply 정책과 Reorg 영향을 반례 중심으로 검토` | dormant UTXO, burn, coinbase maturity, current snapshot 사용의 위험 후보 비교 | 분실 코인 단정은 폐기. policy-eligible supply와 dormancy-adjusted supply를 분리. lifecycle snapshot 계약을 명시 |
| 계산 SQL 검토 | `365일 window의 결측·재처리 조건을 SQL 또는 의사코드로 점검` | NULL 제거 후 row window 적용 시 발생하는 연속 날짜 오인 위험 식별 | date spine 유지, calendar/source completeness를 각각 365일 검증하는 형태로 교정 |
| Task 2 모델 계약 검토 | `eth_getLogs, Delta Lake, dbt incremental, reorg 삭제 범위의 멱등성 검토` | Bronze/Silver 분리, canonical reconcile, bounded rebuild 후보 비교 | Bronze audit append와 Silver current canonical을 분리. reorg 시 source에서 사라진 row를 삭제하는 bounded reconciliation을 채택 |
| USDT Treasury 범위 검토 | `ERC-20 Transfer decoding과 Tether Treasury USDT 집계의 대상 식별 조건 점검` | topic0 단독 판정의 오탐 가능성과 token metadata 조건 제안 | Tether 공식 계약 주소·on-chain decimals 검증을 metadata 계약에 명시. 모든 enabled token을 USDT로 집계하는 설계는 폐기 |
| 문서 표현 교정 | `완료되지 않은 구현을 완료처럼 보이지 않게 문서 상태와 체크리스트를 교정` | 상태 표기·체크리스트 불일치 후보 추출 | 설계 문서 완료와 구현·실행 검증 대기를 분리 표기 |

## 3. 검증 기준(Validation Criteria)


### 3.1 문서 검증

- [x] 과제 필수 요구사항과 문서 목차 대조
- [x] 공개 제품 참조와 과제 전용 지표 정의 분리
- [x] 원천 사실·정책 결정·구현 가정 분리
- [x] 문서 내 상대 링크와 파일명 표기 대조
- [x] 완료되지 않은 구현을 완료로 표기하지 않음

### 3.2 도메인·플랫폼 검증

- [x] CryptoQuant 공개 Velocity 정의 확인
- [x] Bitcoin UTXO, coinbase maturity, chain reorganization 개념 확인
- [x] Airflow data interval·backfill 개념 확인
- [x] Delta Lake MERGE 및 partition 전략 확인
- [x] Ethereum JSON-RPC log field와 reorg handling 확인
- [x] ERC-20 Transfer event와 dbt source/model 구조 확인

### 3.3 구현 검증 — 구현 완료 후 갱신

- [ ] Airflow DAG parse 및 scheduled run
- [ ] RPC 수집 결과와 block range 대조
- [ ] Bronze observation 및 Silver canonical 중복 방지 검증
- [ ] dbt run 및 dbt test
- [ ] Reorg 또는 synthetic reorg fixture 기반 복구 테스트
- [ ] README 실행 명령과 실제 실행 결과 대조

## 4. 주요 설계 판단(Selected Decisions)

| 항목 | 판단 | 이유 |
|---|---|---|
| CryptoQuant 제품 Velocity를 그대로 재현 | 폐기 | 내부 `estimated transaction volume` 세부 규칙이 공개되지 않음 |
| 365일 후행 window | 채택 | 공개 Velocity 설명과 개념적으로 정합 |
| Dormant UTXO를 lost coin으로 간주 | 폐기 | 장기 미사용은 영구 분실 증명이 아님 |
| blind append | 폐기 | retry·backfill에서 중복 가능 |
| Bitcoin current Gold와 reorg audit | 분리 | 현재 소비 결과와 이전 체인 revision 이력의 역할이 다름 |
| Ethereum observation과 canonical view | 분리 | reorg 전후 관측 이력 보존과 current event uniqueness를 동시에 만족 |
| ERC-20 topic0 단독 판정 | 폐기 | Transfer signature만으로 token standard를 단정할 수 없음 |

## 5. 참고 자료(Validation Sources)

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
- Tether Supported Protocols and Integration Guidelines: https://tether.to/en/supported-protocols/
- Ethereum Mainnet USDT Token Reference: https://etherscan.io/token/0xdac17f958d2ee523a2206206994597c13d831ec7
- dbt — dbt_project.yml: https://docs.getdbt.com/reference/dbt_project.yml
