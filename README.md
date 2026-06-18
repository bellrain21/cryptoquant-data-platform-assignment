# CryptoQuant Data Platform Assignment

본 Repository(저장소)는 CryptoQuant Data Platform Engineer 사전과제 제출용입니다.

과제는 두 영역으로 구성됩니다.

1. Bitcoin Velocity(비트코인 회전율) 지표 파이프라인 설계
2. Ethereum Log Ingestion(이더리움 로그 수집) 파이프라인 구현

본 저장소는 단순 계산 결과보다, 데이터 정의·재현성·멱등성·재처리·품질 검증·운영 복구 가능성을 중심으로 구성합니다.

---

## 1. Assignment Scope(과제 범위)

### Task 1. Bitcoin Velocity Metric Pipeline Design

Bitcoin 온체인 원천 데이터가 `block`, `tx`, `tx_input`, `tx_output`, `utxo` Delta Lake Table(델타 레이크 테이블)로 존재한다고 가정하고, Bitcoin Velocity를 안정적으로 생산하기 위한 일 단위 배치 파이프라인을 설계합니다.

주요 설계 범위는 다음과 같습니다.

- Velocity(회전율) 지표 정의
- Transaction Volume(거래 이동량) 정의
- Circulating Supply(유통 공급량) 정책 정의
- SQL 또는 Pseudocode(의사코드)
- Dummy Data(더미 데이터) 기반 출력 예시
- Daily Batch Pipeline(일 단위 배치 파이프라인)
- Idempotency(멱등성) 및 Backfill(과거 구간 재처리)
- Chain Reorganization(Reorg, 체인 재편성) 대응
- 데이터 품질 검증과 한계점 정리

### Task 2. Ethereum Log Ingestion Pipeline

Ethereum RPC Provider를 사용해 `eth_getLogs` 기반 이벤트 로그를 수집하고, Delta Lake에 적재한 뒤 dbt 모델로 분석 가능한 형태를 구성합니다.

주요 구현 범위는 다음과 같습니다.

- Airflow DAG 기반 1시간 단위 로그 수집
- 시간 구간에서 Block Range(블록 범위) 자동 계산
- Retry(재시도), Backfill, 멱등 수집 구조
- Delta Lake 기반 증분 적재
- `ethereum_logs → erc20_transfers → tether_treasury_flow` dbt 모델링
- Tether Treasury 주소 기준 USDT 입출금 집계

---

## 2. Repository Structure(저장소 구조)

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
│   ├── common/
│   ├── bitcoin/
│   └── ethereum/
├── dbt/
│   ├── dbt_project.yml
│   ├── models/
│   └── macros/
├── docs/
│   ├── DOCS_README.md
│   ├── ai_usage_and_validation.md
│   ├── task_01_bitcoin_velocity/
│   │   ├── TASK_01_README.md
│   │   ├── 01_understanding_and_design_direction.md
│   │   ├── 02_metric_definition.md
│   │   ├── 03_data_contract_and_calculation.md
│   │   ├── 04_daily_batch_pipeline.md
│   │   └── 05_quality_reorg_limitations.md
│   └── task_02_ethereum_log_pipeline/
│       ├── TASK_02_README.md
│       ├── 01_pipeline_design.md
│       ├── 02_delta_lake_ingestion.md
│       └── 03_dbt_modeling.md
├── tests/
└── report/
    └── cryptoquant_data_platform_assignment.pdf
```

> 위 구조는 최종 제출 기준 구조입니다. 구현 완료 전에는 일부 파일 또는 디렉터리가 비어 있을 수 있으며, 완료되지 않은 기능은 완료로 표기하지 않습니다.

---

## 3. Documentation(문서)

전체 문서 지도는 아래에서 확인할 수 있습니다.

- [docs/README.md](./docs/README.md)

### Task 1. Bitcoin Velocity

- [Task 1 README](./docs/task_01_bitcoin_velocity/TASK_01_README.md)
- [1. 과제 이해 및 설계 방향](./docs/task_01_bitcoin_velocity/01_understanding_and_design_direction.md)
- [2. Bitcoin Velocity 지표 정의](./docs/task_01_bitcoin_velocity/02_metric_definition.md)
- [3. 데이터 계약과 계산 규칙](./docs/task_01_bitcoin_velocity/03_data_contract_and_calculation.md)
- [4. 일 단위 배치 파이프라인](./docs/task_01_bitcoin_velocity/04_daily_batch_pipeline.md)
- [5. 품질 검증, Reorg, 한계와 확장](./docs/task_01_bitcoin_velocity/05_quality_reorg_limitations.md)

### Task 2. Ethereum Log Ingestion

- [Task 2 README](./docs/task_02_ethereum_log_pipeline/TASK_02_README.md)
- [1. Ethereum 로그 수집 DAG 설계](./docs/task_02_ethereum_log_pipeline/01_pipeline_design.md)
- [2. Delta Lake 적재 설계](./docs/task_02_ethereum_log_pipeline/02_delta_lake_ingestion.md)
- [3. dbt 모델링 설계](./docs/task_02_ethereum_log_pipeline/03_dbt_modeling.md)

### Common

- [AI 활용 및 검증 기록](./docs/ai_usage_and_validation.md)

---

## 4. Key Design Principles(핵심 설계 원칙)

### 4.1 Product Reference와 Assignment Metric 분리

CryptoQuant 공개 API의 Bitcoin Velocity는 제품 참조 기준으로 이해합니다.

```text
CryptoQuant Public Velocity
=
Trailing 1-Year Estimated Transaction Volume
/
Current Total Supply
```

본 과제에서는 내부 제품 알고리즘을 추정하지 않고, 원천 온체인 테이블과 명시적 정책으로 재현 가능한 과제 전용 지표를 정의합니다.

```text
assignment_velocity_365d_policy_eligible_utxo_v1
=
trailing_365d_gross_onchain_output_volume_v1_btc
/
policy_eligible_utxo_supply_v1_btc
```

즉, 공개 제품과 개념적으로 연결되지만 수치적 완전 일치를 주장하지 않습니다.

### 4.2 Source Fact, Policy, Assumption 분리

본 저장소는 아래 세 객체를 구분합니다.

| 구분 | 예시 |
|---|---|
| Source Fact(원천 사실) | block hash, txid, output value, block height |
| Policy Decision(정책 결정) | dormant threshold, confirmation depth, supply policy |
| Implementation Assumption(구현 가정) | raw `utxo` table의 lifecycle 보존 여부 |

### 4.3 Idempotency and Recovery

동일 입력 조건에서는 같은 결과로 수렴해야 하며, Retry·Backfill·Reorg 이후에도 영향 범위를 재계산할 수 있어야 합니다.

```text
same chain state
+ same metric definition
+ same policy version
+ same code version
= same published result
```

### 4.4 Interpretation Honesty

온체인 지표는 시장 해석을 돕는 신호이지, 가격 방향이나 매수·매도 의도를 단독으로 확정하는 지표가 아닙니다.

---

## 5. Environment Variables(환경 변수)

`.env.example` 기준으로 필요한 값을 설정합니다.

```bash
ETH_RPC_URL=
ETH_CHAIN_ID=1

DELTA_ROOT_PATH=./data/delta
AIRFLOW_UID=50000

DBT_PROFILES_DIR=./dbt
```

실제 `.env` 파일은 Git에 포함하지 않습니다.

---

## 6. Installation(설치)

Python 의존성 설치 예시입니다.

```bash
python -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
```

Windows PowerShell 환경에서는 다음처럼 활성화합니다.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

---

## 7. Execution(실행 방법)

> 구현 완료 전에는 아래 명령을 완료된 실행 결과로 간주하지 않습니다.  
> 최종 제출 전 실제 실행 결과와 README 명령을 대조합니다.

### 7.1 Airflow 실행

```bash
docker compose up --build
```

Airflow Web UI 접속 후 `ethereum_logs_pipeline` DAG를 실행합니다.

```text
http://localhost:8080
```

### 7.2 dbt 실행

```bash
cd dbt

dbt deps
dbt debug
dbt run
dbt test
```

### 7.3 Test 실행

```bash
pytest -q
```

---

## 8. Data Quality and Validation(데이터 품질 검증)

### Task 1

- Best Chain 연속성 검증
- block height 누락 검증
- UTXO lifecycle 정합성 검증
- 365일 rolling window coverage 검증
- Velocity 결과값 null, 음수, 무한대 방지
- Reorg 발생 시 영향 구간 재계산

### Task 2

- RPC block range gap·overlap 검증
- log logical key 중복 검증
- Delta Lake 적재 후 중복 검증
- ERC-20 Transfer topic decoding 검증
- Tether Treasury flow 집계 검증
- dbt test 기반 not null, unique, accepted values 검증

---

## 9. AI Usage Disclosure(AI 활용 공개)

본 과제 수행 과정에서 AI 도구를 사용했습니다.

주요 사용 목적은 다음과 같습니다.

- 과제 요구사항 구조화
- Bitcoin Velocity 지표 정의 검토
- UTXO, dormant, Reorg, idempotency 용어 충돌 탐지
- Airflow, Delta Lake, dbt 설계 대안 비교
- 문서 초안 작성과 누락 항목 점검

AI 출력은 그대로 제출하지 않고, 공식 문서·과제 PDF·실행 결과를 기준으로 검증했습니다. 자세한 내용은 아래 문서에 정리합니다.

- [AI 활용 및 검증 기록](./docs/ai_usage_and_validation.md)

---

## 10. Current Status(진행 상태)

| 영역 | 상태 |
|---|---|
| Task 1 설계 문서 | Draft |
| Task 2 파이프라인 설계 문서 | Draft |
| Airflow DAG 구현 | In Progress |
| Delta Lake 적재 구현 | In Progress |
| dbt 모델 구현 | In Progress |
| 테스트 | In Progress |
| 최종 PDF 보고서 | In Progress |

---

## 11. Submission Checklist(제출 전 체크리스트)

- [x] Private GitHub Repository 생성
- [x] `dev@cryptoquant.com` Collaborator 초대
- [x] README 실행 방법 최신화
- [ ] `.env` 또는 secret 파일 미포함 확인
- [ ] `.env.example` 포함
- [ ] Airflow DAG parse 확인
- [ ] 수집 파이프라인 실행 확인
- [ ] Delta Lake 적재 결과 확인
- [ ] dbt run / dbt test 확인
- [ ] pytest 확인
- [ ] AI 활용 및 검증 기록 작성
- [ ] 최종 PDF 보고서 생성
- [ ] 이메일 전체 회신으로 제출

---

## 12. References(참고 자료)

- CryptoQuant BTC Network Data: https://userguide.cryptoquant.com/api/btc-network-data
- CryptoQuant About: https://cryptoquant.com/ko/about
- Bitcoin Developer Documentation — Block Chain: https://developer.bitcoin.org/devguide/block_chain.html
- Bitcoin Developer Documentation — Transactions: https://developer.bitcoin.org/examples/transactions.html
- Apache Airflow Documentation: https://airflow.apache.org/docs/
- Delta Lake Documentation: https://docs.delta.io/
- dbt Documentation: https://docs.getdbt.com/
- EIP-20 Token Standard: https://eips.ethereum.org/EIPS/eip-20
