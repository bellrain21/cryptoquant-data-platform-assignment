# 3. dbt 모델링 설계(dbt Modeling Design)

> Reference / exploratory design — not the current implementation source of truth.
> 현재 구현 기준 dbt graph는 `ethereum_logs` -> `erc20_transfers` -> `tether_treasury_flow` ->
> `tether_treasury_flow_quality_summary`이며, 이 문서의 확장 모델 후보 전체가 구현된 것은 아닙니다.

> **문서 상태(Status)**: Legacy draft / 구현 전 확장 설계 메모
> **문서 역할(Role)**: canonical source, token metadata dimension, 별도 netflow 모델 후보를 정리합니다.
> 현재 실행 기준은 `dbt/models/staging/ethereum_logs.sql`, `dbt/models/silver/erc20_transfers.sql`,
> `dbt/models/gold/tether_treasury_flow.sql`, `dbt/models/gold/tether_treasury_flow_quality_summary.sql`입니다.

## 3.1 dbt 프로젝트 구성(dbt Project Structure)

```text
dbt/
├── dbt_project.yml
├── models/
│   ├── sources.yml
│   ├── staging/
│   │   └── ethereum_logs.sql
│   └── marts/
│       ├── erc20_transfers.sql
│       ├── tether_treasury_flow.sql
│       └── tether_treasury_netflow.sql
└── macros/
```

`dbt_project.yml`은 모든 dbt project의 필수 설정 파일이다. 모델의 의존관계는 Airflow 코드에 하드코딩하지 않고 dbt의 `ref()` 관계와 manifest가 관리합니다.

## 3.2 Source와 Staging Model

```text
dbt source name
= ethereum_logs

physical relation
= silver.ethereum_logs_canonical

staging model
= ethereum_logs
```

과제의 `ethereum_logs → erc20_transfers` 표기는 dbt source 이름 `ethereum_logs`로 보존합니다.
다만 reorg로 orphan event가 남지 않도록 source relation은 Bronze observation이 아니라 `silver.ethereum_logs_canonical`을
가리킵니다. 예시 `sources.yml`은 아래와 같습니다.

```yaml
sources:
  - name: ethereum
    schema: silver
    tables:
      - name: ethereum_logs
        identifier: ethereum_logs_canonical
```

현재 구현의 `ethereum_logs` 모델 역할:

- hexadecimal string 표준화
- lower-case address 표준화
- `block_date`, `chain_id`, canonical event key 보존
- 필수 필드 null 검증
- current Best Chain에 속하는 event만 전달

Bronze observation은 dbt source로 직접 사용하지 않습니다. reorg 전후 관측 이력은 ingestion audit 목적이고, 분석 모델은 current canonical chain을 기준으로 산출합니다.

## 3.3 ERC-20 Transfer Model

EIP-20은 아래 Transfer event를 정의합니다.

```solidity
event Transfer(address indexed _from, address indexed _to, uint256 _value)
```

`erc20_transfers`는 단순히 topic0이 일치하는 모든 event를 ERC-20으로 단정하지 않습니다. Transfer signature는 decoding의 필요조건이지만, 동일한
signature를 emit하는 비대상 contract까지 배제하려면 token metadata contract가 필요합니다.

### 대상 판정과 decoding 계약

```text
1. topic0 = keccak256("Transfer(address,address,uint256)")
2. topics length = 3
3. data = uint256으로 decode 가능한 32-byte ABI word
4. contract_address가 dim_token_metadata의 enabled ERC-20 token contract와 일치
5. block_timestamp가 metadata 유효기간 `[valid_from, valid_to)`에 포함
6. 위 조건을 통과하고 metadata row가 정확히 하나인 event만 erc20_transfers로 승격
```

```text
from_address
= topics[1]의 마지막 20 bytes

to_address
= topics[2]의 마지막 20 bytes

amount_raw
= data의 uint256 decode 값

token_contract_address
= canonical log의 contract_address
```

EIP-20 Transfer topic signature는 다음 상수로 관리합니다.

```text
0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef
```

`amount_raw`는 token decimals를 적용하기 전 정수값이다. 표시용 `amount_normalized`는 `dim_token_metadata.decimals`를 사용해 계산합니다.
decimals와 token contract address를 SQL에 하드코딩하지 않습니다.

### Token Metadata Contract

```text
dim_token_metadata
- chain_id
- token_contract_address
- symbol
- decimals
- token_standard
- is_enabled
- valid_from
- valid_to
- metadata_source
```

`valid_from`, `valid_to`는 UTC timestamp 경계입니다. metadata join은 다음 조건을 만족해야 합니다.

```sql
ON  log.chain_id = metadata.chain_id
AND log.contract_address = metadata.token_contract_address
AND log.block_timestamp >= metadata.valid_from
AND (
     metadata.valid_to IS NULL
     OR log.block_timestamp < metadata.valid_to
)
AND metadata.is_enabled = TRUE
```

같은 `(chain_id, token_contract_address)`에서 유효기간이 겹치면 하나의 log가 여러 metadata row에 매칭될 수 있습니다.
따라서 metadata dimension은 동일 token의 유효 기간이 겹치지 않아야 하며, 승격 대상 event는 metadata join 결과가 정확히 1건이어야 합니다.

이 dimension은 USDT 대상 token을 명시하고, event signature만으로 token 표준을 단정하는 오류를 막습니다.

### 과제 대상 USDT 식별 계약

`erc20_transfers`는 enabled ERC-20 전체를 보존할 수 있습니다. 그러나 과제의 Treasury 집계는 **Ethereum mainnet USDT만** 대상으로 제한합니다.
따라서 `tether_treasury_flow` 모델에는 아래 selector를 명시합니다.

```text
chain_id
= 1

token_contract_address
= 0xdac17f958d2ee523a2206206994597c13d831ec7

symbol
= USDT

decimals
= 6
```

위 contract address는 Tether의 Ethereum USD₮ integration guide를 기준으로 등록합니다. `dim_token_metadata`에는 아래와 같은 단일 enabled row가 존재해야 합니다.

| chain_id | token_contract_address | symbol | decimals | token_standard | is_enabled | metadata_source |
|---:|---|---|---:|---|---|---|
| 1 | `0xdac17f958d2ee523a2206206994597c13d831ec7` | USDT | 6 | ERC-20 | true | Tether supported protocols + on-chain `decimals()` verification |

`valid_from`은 token deployment date가 아니라 **이 metadata policy가 분석 대상으로 유효한 시작 시점**입니다.
따라서 과제의 earliest backfill start보다 같거나 이전이어야 합니다. seed 또는 metadata loader는 다음을 hard fail로 검증합니다.

```text
- chain_id = 1, lower-case contract address, symbol = USDT 조합이 정확히 1행
- 해당 row가 is_enabled = true
- `eth_call(decimals())` 결과가 metadata.decimals = 6과 일치
- 해당 기간에 유효한 metadata row가 1건을 초과하지 않습니다.
```

이 계약으로 metadata에 다른 enabled token이 추가되어도 `tether_treasury_flow`의 USDT 집계 대상이 넓어지지 않습니다.

### 모델 키와 증분 조건

```text
unique_key
= (chain_id, transaction_hash, log_index)

incremental predicate
= target max block number 또는 max block timestamp 이후
  + reorg 확인을 위한 overlap lookback
```

일반 incremental run은 canonical source의 overlap lookback 범위를 다시 읽고 MERGE합니다. 그러나 source에서 사라진 orphan event는 일반 MERGE만으로 mart target에서 삭제되지 않습니다.

따라서 ingestion layer는 reorg 발생 시 `affected_from_block`, `affected_to_block`, `affected_block_dates`를 dbt run에
전달합니다. `erc20_transfers`와 그 하위 집계 모델은 affected block date 전체를 bounded partition rebuild합니다.

```text
1. target에서 affected_block_dates에 속한 partition 또는 row를 DELETE
2. canonical source에서 같은 affected_block_dates 전체를 다시 SELECT
3. decoded transfer와 Treasury aggregate를 다시 INSERT 또는 MERGE
```

이 방식은 stable 구간의 incremental MERGE를 유지하면서, reorg로 source에서 사라진 event와 그 집계 효과를 target에서 제거합니다.
영향 범위가 운영상 허용된 rebuild 한도를 넘으면 full refresh 또는 별도 backfill run으로 승격합니다.

## 3.4 Tether Treasury Flow Models

대상 Treasury 주소는 과제에서 지정한 아래 주소입니다.

```text
0x5754284f345afc66a98fbb0a0afe71e0f007b949
```

USDT 대상은 `dim_token_metadata`의 `token_contract_address`와 `is_enabled` 설정으로 결정합니다.
Treasury 주소와 token selector는 model variable 또는 dimension으로 관리하며, SQL에 직접 흩어 쓰지 않습니다.

### A. 과제 요구 모델 `tether_treasury_flow` — 방향별 상세 집계

```text
inflow
= to_address = treasury_address

outflow
= from_address = treasury_address
```

```text
grain
= (block_date, treasury_address, token_contract_address, direction)

measures
= amount_raw, amount_normalized, transaction_count
```

한 row는 inflow 또는 outflow 중 하나만 나타냅니다. 따라서 이 테이블에서 netflow를 함께 계산하지 않습니다.

### B. 일별 순유입 집계 `tether_treasury_netflow`

`tether_treasury_flow`를 pivot 또는 conditional aggregation해 아래 grain으로 별도 산출합니다.

```text
grain
= (block_date, treasury_address, token_contract_address)

measures
= inflow_amount_raw
= outflow_amount_raw
= netflow_amount_raw
= inflow_amount_normalized
= outflow_amount_normalized
= netflow_amount_normalized
= inflow_transaction_count
= outflow_transaction_count
```

```text
netflow
= inflow - outflow
```

zero address가 `from` 또는 `to`인 Transfer event는 mint·burn 가능성을 나타낼 수 있습니다.
이를 일반 Treasury inflow·outflow와 구분할지 여부는 `flow_classification_policy_version`으로 기록합니다.

## 3.5 Incremental Model과 Test

### 모델 설정

```text
erc20_transfers
- materialized: incremental
- normal run: overlap lookback + merge
- reorg run: affected_block_dates bounded rebuild
- unique_key: chain_id + transaction_hash + log_index

tether_treasury_flow
- materialized: incremental
- normal run: overlap lookback + merge
- reorg run: affected_block_dates bounded rebuild
- unique_key: block_date + treasury_address + token_contract_address + direction

tether_treasury_netflow
- materialized: incremental
- normal run: overlap lookback + merge
- reorg run: affected_block_dates bounded rebuild
- unique_key: block_date + treasury_address + token_contract_address
```

### 필수 dbt test

| 대상 | 테스트 |
|---|---|
| `ethereum_logs` | not_null, raw natural key unique, accepted hex/status contract |
| `dim_token_metadata` | `(chain_id, token_contract_address)`별 valid period overlap이 없고, USDT Ethereum selector 정확히 1행과 decimals on-chain 검증을 확인함 |
| `erc20_transfers` | unique key, not_null from/to/amount, valid topic0, metadata join completeness, metadata join cardinality = 1 |
| `tether_treasury_flow` | not_null date/direction, accepted direction values, non-negative directional amount, USDT contract selector 일치 |
| `tether_treasury_netflow` | unique grain, inflow - outflow = netflow, non-negative in/out amount |

## 3.6 신규 모델 자동 반영(Automatic Dependency Handling)

Airflow가 각 dbt 모델을 개별 Task로 하드코딩하면 새 모델 추가 시 DAG 수정이 필요합니다.

본 설계는 Airflow가 dbt project 단위로 `dbt build`를 호출하고, 모델 선택과 의존관계는 dbt manifest·`ref()` graph에 위임합니다.

```text
Airflow
→ dbt build

dbt
→ source / staging / mart dependency resolution
```

새 모델이 dbt project에 추가되고 dependency graph에 연결되면 DAG Python 코드를 수정하지 않고 dbt 실행 대상에 포함할 수 있습니다. 실제 선택 범위는 `selector` 또는 tag 정책으로 명시합니다.

## 3.7 구현 검증 체크리스트

아래 체크리스트는 현재 dbt 구현과 historical 확장 설계를 분리해 판정합니다.

- [x] `dbt_project.yml` 생성
  - 근거: `dbt/dbt_project.yml`.
- [ ] source relation이 Silver canonical log를 조회
  - 미완료 사유: 현재 dbt source는 raw Delta `ethereum_logs`를 조회합니다. 별도 Silver canonical log table은 구현하지 않았습니다.
- [x] Transfer topic decoding unit test
  - 근거: `tests/test_log_normalizer.py`, `dbt/tests/erc20_transfer_integrity.sql`.
- [ ] token metadata 유효기간 조인, USDT contract selector, `decimals()` 검증
  - 미완료 사유: token metadata dimension과 on-chain `decimals()` 조회는 구현하지 않았습니다. 현재 USDT는 configured contract와 6 decimals 정책을 사용합니다.
- [ ] 하나의 event가 enabled metadata row 정확히 1건과 매칭됨
  - 미완료 사유: metadata validity table이 없으므로 cardinality 검증 대상이 없습니다.
- [x] raw amount와 normalized amount 검증
  - 근거: `tests/test_log_normalizer.py`, `dbt/tests/ethereum_logs_uint256_contract.sql`, `dbt/tests/erc20_transfer_integrity.sql`.
- [x] Treasury inflow / outflow 표본 대조
  - 근거: `dbt/models/gold/tether_treasury_flow.sql`, `dbt/tests/treasury_flow_integrity.sql`,
    `docs/05_validation_evidence.md`의 DuckDB `tether_treasury_flow=2`.
  - 한계: 별도 `netflow` 모델은 구현하지 않았습니다.
- [x] `dbt build`로 model run과 test를 함께 통과
  - 근거: fixture `dbt build --select tag:ethereum_hourly` 결과 `PASS=43 WARN=0 ERROR=0 SKIP=0 NO-OP=0 TOTAL=43`.
- [ ] reorg fixture에서 affected block date의 `erc20_transfers` 및 Treasury aggregate가 bounded rebuild됨
  - 미완료 사유: canonical reorg replacement fixture가 없습니다.
- [x] 신규 model 추가 시 DAG 코드 수정 없이 `dbt build` 범위에 포함됨
  - 근거: `docs/05_validation_evidence.md`의 `dbt ls --select tag:ethereum_hourly` 결과와 Airflow DAG hash 불변 검증.

## 참고 자료

- Ethereum JSON-RPC: https://ethereum.org/developers/docs/apis/json-rpc/
- Tether Supported Protocols and Integration Guidelines: https://tether.to/en/supported-protocols/
- Ethereum Mainnet USDT Token Reference: https://etherscan.io/token/0xdac17f958d2ee523a2206206994597c13d831ec7
- Geth — Real-time Events: https://geth.ethereum.org/docs/interacting-with-geth/rpc/pubsub
- EIP-20 Token Standard: https://eips.ethereum.org/EIPS/eip-20
- dbt — dbt_project.yml: https://docs.getdbt.com/reference/dbt_project.yml
- dbt — Source Configurations: https://docs.getdbt.com/reference/source-configs
