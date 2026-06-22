# 과제 2. Ethereum Log Ingestion(이더리움 로그 수집) 파이프라인 구현

> Reference / exploratory design — not the current implementation source of truth.
> 현재 구현 기준은 저장소 루트 `README.md`, `docs/01_system_architecture.md`부터 `docs/07_submission_readiness_report.md`, `src/cryptoquant_pipeline/`, `airflow/dags/`, `dbt/models/`임.

## 문서 목적

본 과제는 Ethereum Event Log를 RPC에서 수집해 Delta Lake에 적재하고, dbt로 ERC-20 Transfer와 Tether Treasury 흐름을 모델링하는 구현 과제다.

현재 이 디렉터리의 문서는 **구현 전 확장 설계 메모**다. 실제 구현 기준은 저장소 루트 `README.md`와 `docs/01_system_architecture.md`부터 `docs/06_code_reading_guide.md`까지를 우선한다.

주의: 아래 문서에는 Bronze/Silver canonical 분리, token metadata dimension, 별도 `tether_treasury_netflow` 모델처럼 현재 코드에 구현되지 않은 후보 설계가 포함됨. 채용 과제 제출 기준으로는 현재 구현된 raw Delta `ethereum_logs`, dbt `erc20_transfers`, `tether_treasury_flow`, fixture 검증 증거를 우선함.

## 현재 실행 증거 기준

| 증거 | 현재 판정 | 해석 |
|---|---|---|
| fixture Delta + dbt build | VERIFIED | 최신 schema 기준 dbt graph와 tests는 `docs/05_validation_evidence.md`의 `PASS=43` 결과를 기준으로 판단 |
| Airflow UI screenshot `data/imgs/` | PARTIALLY VERIFIED | DAG 등록, `@hourly`, success/failed run history 확인. screenshot 단독으로 row-level correctness를 증명하지 않음 |
| Airflow task log + Delta/DuckDB metadata | VERIFIED | `airflow/logs/`, `data/delta/ethereum_logs_v2`, `data/analytics/ethereum_analytics_v2.duckdb` 대조로 외부 RPC scheduled 수집과 downstream 산출을 확인 |
| accumulated local Delta notebook | PARTIALLY VERIFIED | `src/notebooks/04_*`가 현재 `data/delta/ethereum_logs`의 구 schema를 감지 |
| historical incident/timeline docs | REFERENCE | 04/05 문서는 과거 장애·복구 기록이며 현재 제출 source of truth가 아님 |

## 과제 요구사항 매핑

| 요구사항 | 문서 |
|---|---|
| `eth_getLogs` 기반 1시간 단위 수집, 임의 날짜 backfill, block range 자동 계산, retry | [01_ethereum_log_pipeline_design.md](./01_ethereum_log_pipeline_design.md) |
| Delta Lake schema, partition, nullable, type, incremental ingestion, idempotency | [02_delta_lake_ingestion_design.md](./02_delta_lake_ingestion_design.md) |
| dbt source `ethereum_logs` → `erc20_transfers` → `tether_treasury_flow`, incremental model | 현재 구현 기준: [../02_data_contracts.md](../02_data_contracts.md), 레거시 후보 설계: [03_dbt_modeling_design.md](./03_dbt_modeling_design.md) |

## 현재 구현 기준과 다른 후보 설계

```text
현재 구현함:
1. Airflow는 data interval을 기준으로 1시간 수집 구간을 처리한다.
2. 시간 구간은 block number range로 변환하고 provider 제한에 맞춰 chunk한다.
3. 동일 구간의 scheduled run, rerun, backfill은 같은 수집·정규화 경로를 사용한다.
4. Raw Delta `ethereum_logs`는 `chain_id + transaction_hash + log_index`로 중복 적재를 막는다.
5. dbt는 `ethereum_logs` -> `erc20_transfers` -> `tether_treasury_flow` -> `tether_treasury_flow_quality_summary`를 fixture Delta 기준으로 검증했다.

현재 구현하지 않음:
1. Bronze observation / Silver canonical 이중 계층.
2. common ancestor 기반 stale orphan row 삭제.
3. token metadata dimension과 on-chain `decimals()` 자동 검증.
4. 별도 `tether_treasury_netflow` 모델.
```

## 문서 구성

| 순서 | 문서 | 주요 내용 |
|---:|---|---|
| 1 | [01_ethereum_log_pipeline_design.md](./01_ethereum_log_pipeline_design.md) | RPC 수집, 시간→블록 범위 변환, DAG, retry, backfill, reorg state |
| 2 | [02_delta_lake_ingestion_design.md](./02_delta_lake_ingestion_design.md) | observation/canonical schema, key, incremental ingestion, quality |
| 3 | [03_dbt_modeling_design.md](./03_dbt_modeling_design.md) | dbt source `ethereum_logs`, ERC-20 decoding scope, `tether_treasury_flow`, netflow, dbt test |

## 참고 자료

- Ethereum JSON-RPC: https://ethereum.org/developers/docs/apis/json-rpc/
- Geth — Real-time Events: https://geth.ethereum.org/docs/interacting-with-geth/rpc/pubsub
- ERC-20 Standard: https://eips.ethereum.org/EIPS/eip-20
- Tether Supported Protocols and Integration Guidelines: https://tether.to/en/supported-protocols/
- Ethereum Mainnet USDT Token Reference: https://etherscan.io/token/0xdac17f958d2ee523a2206206994597c13d831ec7
- Apache Airflow — DAG Runs: https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/dag-run.html
- dbt — dbt_project.yml: https://docs.getdbt.com/reference/dbt_project.yml
