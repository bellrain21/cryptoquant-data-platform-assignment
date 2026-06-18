# 과제 2. Ethereum Log Ingestion(이더리움 로그 수집) 파이프라인 구현

## 문서 목적

본 과제는 Ethereum Event Log를 RPC에서 수집해 Delta Lake에 적재하고, dbt로 ERC-20 Transfer와 Tether Treasury 흐름을 모델링하는 구현 과제다.

현재 이 디렉터리의 문서는 **구현 전 설계 계약**이다. 실제 실행 결과, 테스트 결과, 코드 위치는 구현 완료 후에만 완료 상태로 갱신한다.

## 과제 요구사항 매핑

| 요구사항 | 문서 |
|---|---|
| `eth_getLogs` 기반 1시간 단위 수집, 임의 날짜 backfill, block range 자동 계산, retry | [01_pipeline_design.md](./01_pipeline_design.md) |
| Delta Lake 스키마, partition, nullable, type, incremental ingestion, idempotency | [02_delta_lake_ingestion.md](./02_delta_lake_ingestion.md) |
| `ethereum_logs → erc20_transfers → tether_treasury_flow`, incremental dbt model | [03_dbt_modeling.md](./03_dbt_modeling.md) |

## 구현 계약(Implementation Contract)

```text
1. Airflow는 data interval을 기준으로 1시간 수집 구간을 처리한다.
2. 시간 구간은 block number range로 변환하고 provider 제한에 맞춰 chunk한다.
3. 같은 구간 재실행과 backfill은 중복 없는 동일한 적재 경로를 사용한다.
4. Delta Lake는 staging + logical-key merge로 최종 중복을 통제한다.
5. dbt는 source → staging → mart 의존관계를 관리한다.
6. 신규 모델의 의존관계는 Airflow 코드가 아니라 dbt manifest와 dbt build가 관리한다.
```

## 문서 구성

| 순서 | 문서 | 주요 내용 |
|---:|---|---|
| 1 | [01_pipeline_design.md](./01_pipeline_design.md) | RPC 수집, 시간→블록 범위 변환, DAG, retry, backfill |
| 2 | [02_delta_lake_ingestion.md](./02_delta_lake_ingestion.md) | Delta schema, logical key, incremental ingestion, quality |
| 3 | [03_dbt_modeling.md](./03_dbt_modeling.md) | ERC-20 decoding, Treasury flow, incremental dbt, test |

## 참고 자료

- Ethereum JSON-RPC: https://ethereum.org/developers/docs/apis/json-rpc/
- ERC-20 Standard: https://eips.ethereum.org/EIPS/eip-20
- Apache Airflow — DAG Runs: https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/dag-run.html
- dbt — dbt_project.yml: https://docs.getdbt.com/reference/dbt_project.yml
