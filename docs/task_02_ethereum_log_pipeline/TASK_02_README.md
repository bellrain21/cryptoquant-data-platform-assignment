# 과제 2. Ethereum Log Ingestion(이더리움 로그 수집) 파이프라인 구현

## 문서 목적

본 과제는 Ethereum Event Log를 RPC에서 수집해 Delta Lake에 적재하고, dbt로 ERC-20 Transfer와 Tether Treasury 흐름을 모델링하는 구현 과제다.

현재 이 디렉터리의 문서는 **구현 전 설계 계약**이다. 실제 실행 결과, 테스트 결과, 코드 위치는 구현 완료 후에만 완료 상태로 갱신한다.

## 과제 요구사항 매핑

| 요구사항 | 문서 |
|---|---|
| `eth_getLogs` 기반 1시간 단위 수집, 임의 날짜 backfill, block range 자동 계산, retry | [01_pipeline_design.md](./01_pipeline_design.md) |
| Delta Lake schema, partition, nullable, type, incremental ingestion, idempotency | [02_delta_lake_ingestion.md](./02_delta_lake_ingestion.md) |
| dbt source `ethereum_logs` → `erc20_transfers` → `tether_treasury_flow` → `tether_treasury_netflow`, incremental model | [03_dbt_modeling.md](./03_dbt_modeling.md) |

## 구현 계약(Implementation Contract)

```text
1. Airflow는 data interval을 기준으로 1시간 수집 구간을 처리한다.
2. 시간 구간은 block number range로 변환하고 provider 제한에 맞춰 chunk한다.
3. 동일 구간의 scheduled run, rerun, backfill은 같은 수집·정규화 경로를 사용한다.
4. Bronze observation은 block_hash와 `observation_state(observed | removed)`를 포함한 관측 키로 append하여 reorg 이력을 보존한다.
5. Current canonical log view는 common ancestor 이후 affected range에서 stale orphan row를 제거한 뒤, 현재 Best Chain 기준 event key를 반영한다.
6. dbt는 canonical log view만 source로 사용하고, reorg 시 affected block date를 bounded rebuild하여 source에서 사라진 event가 mart에 잔존하지 않게 한다.
7. ERC-20 대상 판정은 Transfer signature뿐 아니라 enabled token metadata의 유효기간 조인과 1:1 매칭을 통과해야 한다.
8. 과제 요구 모델명 `tether_treasury_flow`는 방향별 상세 집계로 유지하고, 일별 순유입은 별도 `tether_treasury_netflow`로 분리해 grain 충돌을 막는다.
```

## 문서 구성

| 순서 | 문서 | 주요 내용 |
|---:|---|---|
| 1 | [01_pipeline_design.md](./01_pipeline_design.md) | RPC 수집, 시간→블록 범위 변환, DAG, retry, backfill, reorg state |
| 2 | [02_delta_lake_ingestion.md](./02_delta_lake_ingestion.md) | observation/canonical schema, key, incremental ingestion, quality |
| 3 | [03_dbt_modeling.md](./03_dbt_modeling.md) | dbt source `ethereum_logs`, ERC-20 decoding scope, `tether_treasury_flow`, netflow, dbt test |

## 참고 자료

- Ethereum JSON-RPC: https://ethereum.org/developers/docs/apis/json-rpc/
- Geth — Real-time Events: https://geth.ethereum.org/docs/interacting-with-geth/rpc/pubsub
- ERC-20 Standard: https://eips.ethereum.org/EIPS/eip-20
- Tether Supported Protocols and Integration Guidelines: https://tether.to/en/supported-protocols/
- Ethereum Mainnet USDT Token Reference: https://etherscan.io/token/0xdac17f958d2ee523a2206206994597c13d831ec7
- Apache Airflow — DAG Runs: https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/dag-run.html
- dbt — dbt_project.yml: https://docs.getdbt.com/reference/dbt_project.yml
