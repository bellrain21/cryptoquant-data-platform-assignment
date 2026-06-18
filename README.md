# CryptoQuant 데이터 플랫폼 사전 과제

> CryptoQuant Data Platform Engineer 사전 과제 제출용 Private Repository(비공개 저장소)입니다.  
> Bitcoin Network Velocity(비트코인 네트워크 회전율) 파이프라인 설계와 Ethereum Event Log(이더리움 이벤트 로그) 수집 파이프라인 구현을 다룹니다.

> **표기 규칙**: 본문은 한국어를 기본으로 하며, 주요 기술·도메인 용어는 `English(한글)` 형식으로 병기합니다.

---

## 1. Project Overview(프로젝트 개요)

본 과제의 목표는 단순 계산 결과나 RPC 호출 코드가 아니라, Raw Blockchain Data(블록체인 원천 데이터)를 재현 가능하고 운영 가능한 Data Product(데이터 제품)으로 생산하는 설계와 구현을 제시하는 것입니다.

| 구분 | 내용 | 상태 |
|---|---|---|
| 과제 1 | Bitcoin Network Velocity(비트코인 네트워크 회전율) 지표 파이프라인 설계 | 설계 문서 작성 중 |
| 과제 2 | Ethereum Log(이더리움 로그) 수집·Delta Lake 적재·dbt 모델링 | 구현 예정 |
| 보고서 | 설계 근거, 구현 결과, 테스트, AI 활용·검증 기록 | 작성 예정 |

---

## 2. Assignment Scope(과제 범위)

### 과제 1. Bitcoin Network Velocity(비트코인 네트워크 회전율)

- Delta Lake 원천 테이블(`block`, `tx`, `tx_input`, `tx_output`, `utxo`)에서 필요한 필드(Field)를 선정합니다.
- 거래 이동량(Transaction Volume)과 유통 공급량(Circulating Supply)의 계산·정책 기준을 정의합니다.
- 일 단위 배치(Daily Batch), 멱등성(Idempotency), 재처리(Backfill), 데이터 품질(Data Quality), Chain Reorganization(Reorg, 체인 재편성) 대응을 설계합니다.

### 과제 2. 이더리움 로그 수집(Ethereum Log Ingestion)

- Airflow DAG에서 `eth_getLogs`를 호출하여 시간 단위 로그를 수집합니다.
- Delta Lake에 증분 적재(Incremental Append)하고, 재실행 시 중복을 방지합니다.
- dbt 모델(Model)로 ERC-20 Transfer와 Tether Treasury 흐름(Flow)을 변환·집계합니다.

---

## 3. Key Design Principles(핵심 설계 원칙)

1. **Source Fact(원천 사실)과 Policy(정책)을 분리합니다.**  
   블록, 트랜잭션, 출력(Output), UTXO는 원천 사실로 보존합니다. 공급량 기준, Dormancy Threshold(장기 비활성 기준), 계산 기간은 버전 관리되는 정책으로 취급합니다.

2. **Reproducibility(재현 가능성)을 우선합니다.**  
   동일한 Chain State(체인 상태), Metric Definition Version(정의 버전), Code Version(코드 버전), Data Interval(실행 구간)이 입력되면 동일한 결과가 나와야 합니다.

3. **Idempotency(재실행 안전성)을 보장합니다.**  
   같은 입력을 여러 번 처리해도 중복 적재 없이 최종 결과가 Logical Key(논리 키) 기준으로 하나의 상태에 수렴해야 합니다.

4. **Bitcoin의 확인(Confirmation)과 확정성(Finality)을 구분합니다.**  
   Bitcoin은 Deterministic Finality(결정론적 확정성)이 아니라 Confirmation Depth(확인 깊이)에 따른 신뢰도 구조입니다. 따라서 내부 Publication Policy(게시 정책)과 Reorg 복구 절차를 분리합니다.

5. **Public Product Metric(공개 제품 지표)와 Assignment Metric(과제 지표)를 혼동하지 않습니다.**  
   CryptoQuant 공개 문서의 지표 정의는 Reference(참고 기준)으로 사용합니다. 본 과제의 원천 데이터 기반 결과는 정책이 명시된 별도 Metric Family(지표군)으로 관리하며, 수치적 완전 일치를 주장하지 않습니다.

---

## 4. Task 1 Summary(과제 1 설계 요약)

과제 1은 단일 숫자보다 **Metric Contract(지표 계약)** 을 명확히 하는 데 중점을 둡니다.

- Numerator(분자): Change Output(변경 출력)을 포함할 수 있는 Gross On-chain Output Flow(총 온체인 이동량)을 과제용 정의로 명시합니다.
- Denominator(분모): Total Issued Supply(발행 총량), Spendable UTXO Supply(소비 가능 UTXO 공급량), Dormancy-Adjusted Supply(장기 비활성 조정 공급량)을 구분합니다.
- Dormant UTXO(장기 비활성 UTXO): Lost Coin(영구 분실 코인)으로 단정하지 않으며, Liquidity Sensitivity(유동성 민감도) 분석을 위한 정책 변수로 관리합니다.
- Dormant UTXO Spent(장기 비활성 UTXO 재소비): Supply(공급량)이 아니라 기간 내 Flow(흐름량)으로 추적합니다.
- Burn(소각): 온체인에서 Provably Unspendable Output(소비 불가능함이 증명되는 출력)과 Address Label(외부 주소 라벨) 기반 추정을 구분합니다.
- Reorg: Common Ancestor(공통 조상) 이후의 UTXO 상태와 영향을 받은 지표 구간을 재계산합니다.

세부 정의, SQL 또는 Pseudocode(의사코드), Dummy Data(더미 데이터), 결과 테이블 계약은 아래 문서에 작성합니다.

- [`docs/00_table_of_contents.md`](docs/00_table_of_contents.md)
- [`docs/task_01_bitcoin_velocity/01_metric_definition.md`](docs/task_01_bitcoin_velocity/01_metric_definition.md)
- [`docs/task_01_bitcoin_velocity/02_batch_pipeline.md`](docs/task_01_bitcoin_velocity/02_batch_pipeline.md)
- [`docs/task_01_bitcoin_velocity/03_reorg_quality_limitations.md`](docs/task_01_bitcoin_velocity/03_reorg_quality_limitations.md)

---

## 5. Architecture(전체 구조)

```text
Raw Layer(Raw Layer(원천 계층))
block / tx / tx_input / tx_output / utxo / Ethereum RPC response
        │
        ▼
Silver Layer(Silver Layer(정규화·검증 계층))
best-chain state / UTXO lifecycle / normalized Ethereum logs
        │
        ▼
Gold Layer(Gold Layer(데이터 제품 계층))
Bitcoin Velocity variants / ERC-20 transfers / Tether Treasury flow
        │
        ▼
Serving Layer(Serving Layer(서빙·분석 계층))
Chart / API / downstream analytics / report
```

---

## 6. Repository Structure(저장소 구조)

```text
.
├── README.md
├── .env.example
├── requirements.txt
├── docker-compose.yml
├── airflow/
│   └── dags/
│       └── ethereum_logs_pipeline.py
├── src/
│   ├── bitcoin/
│   ├── ethereum/
│   └── common/
├── dbt/
│   ├── models/
│   └── macros/
├── docs/
│   ├── 00_table_of_contents.md
│   ├── task_01_bitcoin_velocity/
│   │   ├── 01_metric_definition.md
│   │   ├── 02_batch_pipeline.md
│   │   └── 03_reorg_quality_limitations.md
│   └── task_02_ethereum_log_pipeline/
│       ├── 01_pipeline_design.md
│       ├── 02_delta_lake_ingestion.md
│       └── 03_dbt_modeling.md
├── tests/
└── report/
    └── cryptoquant_data_platform_assignment.pdf
```

> 위 구조는 Target Repository Structure(최종 제출 기준 구조)입니다. 현재는 과제 1 설계 문서부터 순차적으로 작성합니다. 구현되지 않은 파일이나 실행되지 않은 기능은 완료로 표시하지 않습니다.

---

## 7. Documentation(문서 안내)

| 문서 | 내용 |
|---|---|
| `docs/00_table_of_contents.md` | 전체 문서 목차, 과제별 문서 연결, 작성·검증 범위 |
| `docs/task_01_bitcoin_velocity/01_metric_definition.md` | 지표 정의, 원천 필드, 공급량 정책, SQL 또는 의사코드, 더미 출력 |
| `docs/task_01_bitcoin_velocity/02_batch_pipeline.md` | 일 단위 배치 처리, Airflow, Delta Lake, 멱등성, Backfill 설계 |
| `docs/task_01_bitcoin_velocity/03_reorg_quality_limitations.md` | Reorg, Confirmation Policy(확인 정책), 품질 검증, 한계, 확장 |
| `docs/task_02_ethereum_log_pipeline/01_pipeline_design.md` | RPC 수집 범위, Block Range(블록 범위) 계산, DAG 설계, Retry(재시도)·Backfill 전략 |
| `docs/task_02_ethereum_log_pipeline/02_delta_lake_ingestion.md` | Delta Lake 스키마, 증분 적재, 논리 키, 멱등성, 품질 검증 |
| `docs/task_02_ethereum_log_pipeline/03_dbt_modeling.md` | ERC-20 Transfer 모델, Tether Treasury Flow 모델, Incremental Model, dbt Test |

---

## 8. Prerequisites(실행 환경)

최종 구현 기준의 실행 환경입니다.

| 구분 | 기준 |
|---|---|
| Python | 3.11 이상 |
| Orchestration(오케스트레이션) | Apache Airflow |
| Storage(저장소) | Delta Lake (`deltalake` 또는 PySpark Local Mode) |
| Transformation(변환) | dbt-duckdb 또는 dbt-spark |
| Container(컨테이너) | Docker Desktop, Docker Compose v2 |
| Node(이더리움 노드) | QuickNode, Alchemy, Infura 등 RPC Provider |

### Environment Variables(환경 변수)

Secret(비밀값)은 커밋하지 않습니다.

```bash
cp .env.example .env
```

```dotenv
ETH_RPC_URL=https://<provider-endpoint>
ETH_CHAIN_ID=1
BTC_CONFIRMATION_DEPTH=6
BTC_DORMANCY_THRESHOLD_DAYS=3650
BTC_METRIC_DEFINITION_VERSION=assignment_velocity_v1
DELTA_LAKE_PATH=./data/delta
```

---

## 9. Execution and Validation(실행 및 검증)

> 현재 저장소는 과제 1 설계 우선 단계입니다. 아래 명령은 과제 2 구현 완료 후 실제 실행 결과로 검증해 확정할 Target Execution Contract(실행 계약)입니다.

```bash
# 1. 가상환경 생성 및 의존성 설치
python -m venv .venv
source .venv/bin/activate  # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 2. Airflow 및 의존 서비스 실행
# docker compose up --build

# 3. dbt 변환 및 테스트
# cd dbt && dbt run && dbt test

# 4. 단위 테스트
# pytest -q
```

최종 제출 전 검증 기준은 다음과 같습니다.

- Airflow DAG 재실행 및 Backfill에서 중복 적재가 발생하지 않는지 확인
- 블록 또는 로그 구간 누락, 중복, 논리 키 위반을 탐지하는지 확인
- Delta Lake 결과 테이블이 예상 스키마와 Constraint(품질 제약)을 만족하는지 확인
- dbt incremental model 결과와 테스트(Test) 통과 여부 확인
- README의 명령과 실제 실행 절차가 일치하는지 확인

---

## 10. AI Usage and Validation(AI 활용 및 검증)

AI 도구는 설계 보조와 반박 검토(Design Review)에 활용합니다. AI 출력은 사실 또는 정답으로 취급하지 않으며, 공식 문서·실행 결과·테스트로 교차 검증합니다.

| 활용 목적 | 검증 방식 |
|---|---|
| 과제 요구사항 분해 | 과제 PDF와 항목별 대조 |
| 용어·정의 검토 | CryptoQuant, Bitcoin, Delta Lake, Airflow, dbt 공식 문서 대조 |
| 설계 반박 | 공급량 정책, Change Output, Reorg, 멱등성의 맹점 재검토 |
| 코드 보조 | 실제 실행, Unit Test(단위 테스트), 데이터 품질 검증 |
| 문서화 | 구현 상태와 문서 상태의 수동 대조 |

대표 프롬프트, 검증 근거, 최종 반영 또는 폐기 판단은 본 README와 최종 보고서(PDF)에 기록합니다. 문서별 진행 상태와 연결은 [`docs/00_table_of_contents.md`](docs/00_table_of_contents.md)에서 관리합니다.

---

## 11. Security and Submission Checklist(보안 및 제출 점검)

- [o] 저장소를 Private로 설정했습니다.
- [o] `dev@cryptoquant.com`을 Collaborator로 초대했습니다.
- [ ] `.env`, RPC Key, PII(개인정보), Secret(비밀값)을 커밋하지 않았습니다.
- [ ] 보고서(PDF)에 과제 1과 과제 2의 설계·구현·검증 결과를 반영했습니다.
- [ ] README의 실행 방법과 실제 실행 명령이 일치합니다.
- [ ] AI 활용 목적, 대표 프롬프트, 검증 방식, 최종 판단을 기록했습니다.
- [ ] Reply All(이메일 전체 회신)으로 보고서 PDF를 제출하고 `dev@cryptoquant.com` 포함 여부를 확인했습니다.

---

## 12. References(참고 자료)

- [CryptoQuant API Documentation](https://docs.cryptoquant.com/)
- [Bitcoin Developer Documentation](https://developer.bitcoin.org/)
- [Delta Lake Documentation](https://docs.delta.io/)
- [Apache Airflow Documentation](https://airflow.apache.org/docs/)
- [dbt Documentation](https://docs.getdbt.com/)

> 검증 가능한 사실(Source Fact), Policy Decision(정책 결정), Future Assumption(향후 확장 가정)을 분리해 기록합니다. 공개 문서에 없는 구현 규칙은 사실처럼 단정하지 않습니다.
