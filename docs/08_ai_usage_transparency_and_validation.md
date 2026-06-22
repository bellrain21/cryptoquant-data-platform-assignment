# 08. AI 활용과 검증 기준

> 기준일: 2026-06-22 KST
> 목적: AI를 사용한 범위와 작성자가 직접 판단한 설계 결정을 분리하여 기록합니다.
> 상태: 문서화 완료. 로컬 Docker Airflow 환경에서 외부 RPC Provider 기반 여러 1시간 scheduled 수집 이력을 확인했습니다.

이 프로젝트에서 AI는 요구사항을 구조화하고 검토 범위를 넓히는 보조 도구로 사용했습니다.
최종 설계 선택, 구현 반영 여부, 검증 상태 판단은 작성자가 코드, 테스트, 정적 분석, 문서 대조 결과를 기준으로 결정했습니다.

AI 출력은 구현 사실이나 검증 결과로 간주하지 않았습니다.
검증하지 못한 제안은 요구사항 추적표와 제한사항에 `PARTIALLY VERIFIED`, `NOT VERIFIED`, `BLOCKED`로 분리했습니다.

## AI 활용 범위

| 구분 | 활용 목적 | 사용자의 판단 또는 결정 | 검증 방식 |
|---|---|---|---|
| 요구사항 분석 | 과제 요구사항을 구현 단위로 분해 | 구현 우선순위와 범위 결정 | 과제 원문, README, `docs/09_requirement_traceability_matrix.md` 대조 |
| 설계 검토 | 멱등성, backfill, retry, incremental 전략의 누락 탐색 | unique key, 재처리 범위, 저장 전략 결정 | 코드 리뷰, `pytest`, 문서 정합성 검사 |
| 코드 보조 | 반복적 구조 초안, 예외 처리 후보, 테스트 초안 생성 | 실제 구조 반영 여부와 최종 코드 선택 | `python -m compileall`, `ruff check`, `pytest` |
| SQL 검토 | ERC-20 decode, incremental 조건, aggregation grain 점검 | 모델 grain과 unique key 결정 | `dbt parse`, `dbt build`, dbt singular test |
| 문서 정리 | 코드·SQL·문서 간 경로 및 용어 불일치 탐지 | 문서 표현과 최종 상태 결정 | Markdown 링크 검사, 실제 파일 경로 대조 |

## AI를 사용한 이유

복잡한 과제 요구사항을 Python, Airflow, Delta Lake, dbt, Bitcoin Velocity 설계 문서로 나누어 누락 없이 추적하기 위해 AI를 사용했습니다.

재실행, 중복 적재, backfill, retry, incremental 처리처럼 운영 중 문제가 되기 쉬운 지점을 더 넓게 점검하기 위해 AI를 사용했습니다.

코드와 문서가 서로 다른 파일명, 모델명, 검증 상태를 말하지 않도록 불일치 후보를 빠르게 찾는 데 AI를 사용했습니다.

## 사용자가 직접 결정한 사항

| 결정 항목 | 최종 판단 |
|---|---|
| 데이터 모델의 grain | `ethereum_logs`는 Ethereum log 1건, `erc20_transfers`는 Transfer log 1건,<br>`tether_treasury_flow`는 `hour_start_utc + direction` 기준으로 정의함 |
| unique key와 idempotency 기준 | raw 로그는 `chain_id + transaction_hash + log_index`를 natural key로 사용함 |
| retry 및 backfill 정책 | Airflow `data_interval` 기준으로 재실행 가능하게 하고, RPC transient failure는 bounded retry 대상으로 분리함 |
| Delta Lake 저장 전략 | raw 로그는 Delta table에 insert-if-not-exists 방식으로 적재하고, canonical reorg replacement는 구현 범위에서 제외함 |
| dbt 모델 구조 | `ethereum_logs -> erc20_transfers -> tether_treasury_flow -> tether_treasury_flow_quality_summary` graph 유지<br>`tag:ethereum_hourly` selector로 실행함 |
| Circulating Supply 정책 | Bitcoin Velocity 설계에서 policy-eligible UTXO supply와 dormancy-adjusted supply를 구분함 |
| Reorg 재처리 범위 | Task 1은 설계 문서에서 재계산 window를 정의하고, Task 2는 finality buffer와 raw `block_hash` 보존까지 구현함 |
| 최종 문서와 코드 반영 여부 | 실행 증거가 있는 항목만 `VERIFIED`로 표시하고, 외부 환경 의존 항목은 제한사항으로 남김 |

## AI가 보조한 사항

| 보조 범위 | 반영 방식 |
|---|---|
| 리팩토링 후보 식별 | DAG, block range, RPC, Delta writer, dbt runner 책임 분리 후보를 점검하는 데 사용함 |
| 테스트 케이스 후보 생성 | block range, retry, idempotency, dbt contract, ERC-20 decode 검증 범위를 점검하는 데 사용함 |
| 예외 처리 및 edge case 점검 | provider limit, malformed log, duplicate replay, `uint256` overflow 가능성을 검토하는 데 사용함 |
| SQL 표현 개선 | ERC-20 topic/data decode, address lowercase normalization, incremental 조건, `SELECT *` 제거 후보를 검토하는 데 사용함 |
| 문서 구조와 체크리스트 정합성 점검 | README, 요구사항 추적표, 리팩토링 보고서, 문서 정합성 보고서의 상태 라벨과 링크를 대조하는 데 사용함 |

## 검증 방식

AI 제안은 그대로 반영하지 않았습니다.
각 제안은 실제 코드 구조, 테스트, 정적 검증, 공식 문서 기준 또는 수동 리뷰 중 하나 이상으로 확인한 뒤 반영했습니다.

검증 증거는 `docs/05_validation_evidence.md`, `docs/10_refactoring_report.md`, `docs/11_documentation_consistency_report.md`,
`docs/09_requirement_traceability_matrix.md`에 분산되어 있습니다.
외부 RPC 환경 검증은 Airflow task log, Airflow UI screenshot, Delta/DuckDB 산출물, 노트북 output을 대조해 반영했습니다.
다만 이 검증은 로컬 Docker 실행 이력 기준이며, production hardening이나 provider 장기 SLA를 의미하지 않습니다.

| 검증 범위 | 사용한 근거 | 상태 |
|---|---|---|
| Python import와 문법 | `python -m compileall src tests scripts airflow/dags` | VERIFIED |
| Python lint와 단위 테스트 | `ruff check .`, `pytest -q` | VERIFIED |
| dbt graph와 SQL test | fixture Delta table 기반 `dbt build --select tag:ethereum_hourly` | VERIFIED |
| Airflow DAG 구조 | DagBag import, DAG ID `ethereum_hourly_logs`, task ID `run_interval` 확인 | VERIFIED |
| Airflow UI 실행 이력 | `data/imgs/` screenshot 수동 판독 | PARTIALLY VERIFIED |
| Airflow 외부 RPC scheduled 수집 | `airflow/logs/`, `data/delta/ethereum_logs_v2`, `data/analytics/ethereum_analytics_v2.duckdb` 확인 | VERIFIED |
| Notebook 기반 코드·데이터 흐름 | `src/notebooks/03_*`, `src/notebooks/04_*` 실행 output | PARTIALLY VERIFIED |
| Markdown 링크와 파일 경로 | Markdown local link 검사, `rg` 기반 경로 대조 | VERIFIED |
| Production-grade provider 안정성 | 지속 무중단 운영, provider SLA, rate limit 여유, alerting은 별도 운영 검증 필요 | NOT VERIFIED |

## 대표 프롬프트 원문형 요약

아래 프롬프트는 전체 대화 로그가 아니라 검토 시 AI 활용 범위를 이해하는 데 필요한 대표 입력만 짧게 정리한 것입니다.
개인 메모, 반복 지시, 중간 시행착오 전문은 제출 문서에 포함하지 않습니다.

| 순서 | 대표 프롬프트 | 사용 목적 | 반영 전 검증 |
|---:|---|---|---|
| 1 | “현재 Repository의 Python 코드와 SQL 또는 dbt SQL을 리팩토링하고, 코드 주석·Markdown 문서·체크리스트·요구사항 추적표까지 함께 최신화하라.” | 코드·SQL·문서 정합성 점검 범위 설정 | `compileall`, `pytest`, `dbt build`, Markdown link check |
| 2 | “AI 활용 투명성과 채용 가능성 균형 원칙을 지키고, AI가 확장한 검토 범위와 사용자가 책임진 최종 판단을 분리해서 보여줘.” | AI 사용 기록의 문체와 책임 경계 정의 | README, 이 문서, 요구사항 추적표 대조 |
| 3 | “`/workspace/src/notebooks` 하위 주피터 노트북 파일에서 내용 확인하고, 파이썬 소스 코드 검증 및 데이터 확인에 주안점을 두어 리팩토링해줘.” | 노트북을 학습 기록이 아니라 코드·데이터 검증 보조 증거로 정리 | `nbclient` 실행 output, notebook JSON parse |
| 4 | “`/workspace/data/imgs` 하위 이미지 파일을 분석하고 Markdown 문서에 실행 증거로 명시해줘.” | Airflow UI screenshot을 실행 증거 범위에 연결 | 이미지 수동 판독, Airflow task log와 Delta/DuckDB 증거 대조 |
| 5 | “검증되지 않은 항목과 체크 안 된 사항들을 로그와 메타데이터로 재고하고, 과제 1의 타당성도 별도 검증해서 문서 최신화해줘.” | 체크리스트 재판정과 Task 1 설계 타당성 확인 | Airflow logs, Delta metadata, Task 1 정적 스캔 |

## 대표 활용 예시

### 예시 1. Airflow 수집 DAG의 backfill과 idempotency 점검

- 목적: Airflow 수집 DAG의 backfill 및 idempotency 누락 가능성을 점검했습니다.
- AI 입력: logical date 기반 수집 구간, block range 변환, Delta Lake 적재 구조를 제공하고 재실행 시 중복 가능성을 검토하도록 요청했습니다.
- 사용자 판단: `chain_id`, `transaction_hash`, `log_index` 조합을 고유 식별자로 채택했습니다.
- 검증: `tests/test_delta_idempotency.py`, `tests/test_pipeline_idempotency.py`, Delta writer 코드 리뷰로 확인했습니다.
- 결과: 중복 적재 방지 기준과 문서 설명을 코드와 요구사항 추적표에 반영했습니다.

### 예시 2. ERC-20 Transfer decode와 Treasury flow grain 점검

- 목적: ERC-20 Transfer event decode와 Tether Treasury inbound/outbound 집계 기준을 점검했습니다.
- AI 입력: `topic0`, `topic1`, `topic2`, `data` 필드와 Treasury 주소 비교 조건을 제공하고 SQL edge case를 검토하도록 요청했습니다.
- 사용자 판단: Transfer log 1건을 `erc20_transfers` grain으로 두고, Treasury flow는 `hour_start_utc + direction` grain으로 집계했습니다.
- 검증: dbt model SQL, singular tests, fixture 기반 `dbt build` 결과로 확인했습니다.
- 결과: lowercase normalization, unique key, data decode status, USDT contract filter를 문서화했습니다.

### 예시 3. Bitcoin Velocity 설계 문서의 과장 표현 제거

- 목적: CryptoQuant production metric을 재현한 것처럼 보이는 표현을 줄이고 과제용 지표 정의를 분리했습니다.
- AI 입력: Transaction Volume, Circulating Supply, dormant UTXO, Reorg 재처리 설명의 충돌 가능성을 검토하도록 요청했습니다.
- 사용자 판단: 공개 지표는 참고 배경으로만 사용하고, `assignment_velocity_365d_policy_eligible_utxo_v1`을 별도 정의했습니다.
- 검증: Task 1 문서와 요구사항 추적표를 대조했습니다.
- 결과: Task 1이 설계 문서 산출물이며 production pipeline 구현물이 아니라는 점을 README와 docs에 반영했습니다.

## 보조 검토 범위 상세

아래 표는 원문 대화 로그가 아니라 AI를 이용해 점검한 범위와 최종 처리 방식을 요약한 기록입니다.
AI 제안은 초안 후보로만 취급했고, 반영 여부는 과제 원문, 공식 문서, 코드 실행 결과, 설계 일관성을 기준으로 판단했습니다.

| 검토 범위 | 검토 질문 요약 | 보조 산출물 사용 방식 | 최종 검증 및 처리 |
|---|---|---|---|
| 과제 요구사항 매핑 | 요구사항과 Markdown 산출물이 맞는지 평가 | 요구사항 대비 문서 누락과 명칭 불일치 후보 추출 | Task 1·2 요구사항과 요구사항 추적표를 대조함 |
| Task 1 정책 설계 검토 | Bitcoin Velocity의 volume, circulating supply, Reorg 영향을 반례 중심으로 검토 | dormant UTXO, burn, coinbase maturity, current snapshot 사용 위험 후보 비교 | 분실 코인 단정은 폐기하고 policy-eligible supply와 dormancy-adjusted supply를 분리함 |
| 계산 SQL 검토 | 365일 window의 결측과 재처리 조건을 SQL 또는 의사코드로 점검 | NULL 제거 후 row window 적용 시 연속 날짜를 오인할 위험 식별 | date spine 유지와 calendar/source completeness 검증 기준을 문서화함 |
| Task 2 모델 계약 검토 | `eth_getLogs`, Delta Lake, dbt incremental, reorg 삭제 범위의 멱등성 검토 | Bronze/Silver 분리, canonical reconcile, bounded rebuild 후보 비교 | 현재 구현은 raw Delta insert-if-not-exists와 natural key idempotency 중심으로 제한함 |
| USDT Treasury 범위 검토 | ERC-20 Transfer decoding과 Tether Treasury USDT 집계의 대상 식별 조건 점검 | topic0 단독 판정의 오탐 가능성과 token metadata 조건 후보를 확인함 | USDT contract address와 Treasury address 설정값으로 범위를 제한하고, token metadata dimension은 구현되지 않은 항목으로 분리함 |
| 문서 표현 교정 | 완료되지 않은 구현을 완료처럼 보이지 않게 상태와 체크리스트를 교정 | 상태 표기와 체크리스트 불일치 후보 추출 | 설계 문서 완료와 구현·실행 검증 대기 상태를 분리함 |

## 검증 기준 상세

### 문서 검증

- [x] 과제 필수 요구사항과 문서 목차를 대조했습니다.
- [x] 공개 제품 참조와 과제 전용 지표 정의를 분리했습니다.
- [x] 원천 사실, 정책 결정, 구현 가정을 분리했습니다.
- [x] 문서 내 상대 링크와 파일명 표기를 대조했습니다.
- [x] 완료되지 않은 구현을 완료로 표기하지 않았습니다.

### 도메인과 플랫폼 검증

- [x] CryptoQuant 공개 Velocity 정의를 참고 배경으로 확인했습니다.
- [x] Bitcoin UTXO, coinbase maturity, chain reorganization 개념을 확인했습니다.
- [x] Airflow data interval과 backfill 개념을 확인했습니다.
- [x] Delta Lake MERGE와 partition 전략을 검토했습니다.
- [x] Ethereum JSON-RPC log field와 reorg handling 필드를 확인했습니다.
- [x] ERC-20 Transfer event와 dbt source/model 구조를 확인했습니다.

### 구현 검증

- [x] Raw Delta natural key 중복 방지 fixture를 검증했습니다.
- [x] dbt build와 dbt test를 fixture 기반으로 검증했습니다.
- [x] README 실행 명령 일부와 실제 실행 결과를 대조했습니다.
- [x] 최신 raw schema 기준의 실제 Airflow scheduler 여러 1시간 실행 이력을 확인했습니다.
  - 근거: `airflow/logs/dag_id=ethereum_hourly_logs`에서 successful scheduled run 반환값 33건을 확인했고, latest direct
    inspection에서 `data/delta/ethereum_logs_v2` row count `6848937`, duplicate key `0`을 확인했습니다.
- [x] 실제 RPC 수집 결과와 여러 scheduled interval의 block range를 대조했습니다.
  - 근거: Airflow task log에서 `from_block`, `to_block`, `raw_log_count`, `inserted_row_count`가 1시간 interval별로
    기록되어 있고, notebook 04가 latest v2 raw의 hourly series와 2026-06-22 12:00 UTC gap을 표시합니다.
- [ ] Reorg 또는 synthetic reorg fixture 기반 복구 테스트를 완료했습니다.
  - 미완료 사유: 현재 구현은 finality buffer와 raw `block_hash` 보존까지입니다.

## 주요 설계 판단

| 항목 | 판단 | 이유 |
|---|---|---|
| CryptoQuant 제품 Velocity를 그대로 재현 | 폐기 | 내부 `estimated transaction volume` 세부 규칙이 공개되지 않음 |
| 365일 후행 window | 채택 | 공개 Velocity 설명과 개념적으로 정합함 |
| Dormant UTXO를 lost coin으로 간주 | 폐기 | 장기 미사용은 영구 분실 증명이 아님 |
| Blind append | 폐기 | retry와 backfill에서 중복 가능성이 있음 |
| Bitcoin current Gold와 reorg audit | 분리 | 현재 소비 결과와 이전 chain revision 이력의 역할이 다릅니다 |
| Ethereum observation과 canonical view | 현재 구현에서 미채택 | 과제 범위와 로컬 실행 가능성을 우선해 raw Delta natural key idempotency로 제한함 |
| ERC-20 `topic0` 단독 판정 | 폐기 | Transfer signature만으로 token standard를 단정불가 |

## 한계와 후속 검증

외부 RPC Provider 기반 여러 1시간 scheduled 수집은 로컬 Docker Airflow 실행 이력으로 확인했습니다.
확인 근거는 `airflow/logs/`, `data/imgs/`, `data/delta/ethereum_logs_v2`, `data/analytics/ethereum_analytics_v2.duckdb`,
`src/notebooks/03_*`, `src/notebooks/04_*`입니다.

다만 비용이 큰 full-history backfill, provider SLA 검증, 지속 무중단 운영, alerting, secret rotation, production Airflow 배포는 이 저장소에서 검증하지 않았습니다.
이 범위는 운영 환경 검증 전에는 `VERIFIED`로 표기하지 않습니다.

AI가 제안한 canonical reorg replacement, token metadata dimension, address label provenance registry는 현재 구현하지 않았습니다.
관련 내용은 future hardening 또는 설계 한계로만 남깁니다.

## 참고 자료

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

## AI 활용 및 검증 체크리스트

- [x] AI 활용 목적을 요구사항 분석, 설계 검토, 코드 보조, 테스트 보완, 문서 정합성 검토로 구분했습니다.

- [x] 최종 설계 결정과 구현 반영 기준을 작성자가 판단한 것으로 기록했습니다.

- [x] AI 제안 중 실제 코드 또는 테스트로 검증한 항목만 반영했습니다.

- [x] 로컬 Docker Airflow에서 외부 RPC Provider 기반 여러 1시간 scheduled 수집 이력을 검증했습니다.
  - 근거: Airflow task log에서 successful scheduled run 반환값 33건, Airflow UI screenshot에서 success 47건, Delta
    `ethereum_logs_v2` row count `6848937`, DuckDB `erc20_transfers` row count `6079379`건을 확인했습니다.
  - 한계: 로컬 Docker 실행 이력 기준이며 production-grade 무중단 운영과 provider SLA는 별도 검증 대상입니다.

- [x] 검증하지 못한 항목을 VERIFIED로 표기하지 않았습니다.

- [x] 전체 프롬프트 전문 대신 대표 프롬프트 5개와 목적, 판단, 검증 방식 중심으로 요약했습니다.
