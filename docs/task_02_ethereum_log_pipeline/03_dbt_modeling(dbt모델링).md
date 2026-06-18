# 3. dbt 모델링 설계(dbt Modeling Design)

> **문서 상태(Status)**: Draft / 구현 전 설계  
> **문서 역할(Role)**: `ethereum_logs → erc20_transfers → tether_treasury_flow` 변환 체인과 incremental model·test 계약을 정의한다.

## 3.1 dbt 프로젝트 구성(dbt Project Structure)

```text
dbt/
├── dbt_project.yml
├── models/
│   ├── sources.yml
│   ├── staging/
│   │   └── stg_ethereum_logs.sql
│   └── marts/
│       ├── erc20_transfers.sql
│       └── tether_treasury_flow.sql
└── macros/
```

`dbt_project.yml`은 모든 dbt project의 필수 설정 파일이다. 모델의 의존관계는 Airflow 코드에 하드코딩하지 않고 dbt의 `ref()` 관계와 manifest가 관리한다.

## 3.2 Source와 Staging Model

```text
source
= bronze.ethereum_logs

staging model
= stg_ethereum_logs
```

`stg_ethereum_logs`의 역할:

- hexadecimal string 표준화
- lower-case address 표준화
- `block_date`, `chain_id`, logical event key 보존
- 필수 필드 null 검증
- canonical target에 게시 가능한 행만 전달

## 3.3 ERC-20 Transfer Model

EIP-20은 아래 Transfer event를 정의한다.

```solidity
event Transfer(address indexed _from, address indexed _to, uint256 _value)
```

따라서 `erc20_transfers`는 다음 조건을 만족하는 log를 추출한다.

```text
topic0
=
keccak256("Transfer(address,address,uint256)")

from_address
=
topics[1]의 마지막 20 bytes

to_address
=
topics[2]의 마지막 20 bytes

amount_raw
=
data의 uint256 decode 값
```

EIP-20 Transfer topic signature는 다음 상수로 관리한다.

```text
0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef
```

### 모델 키와 증분 조건

```text
unique_key
=
(chain_id, transaction_hash, log_index)

incremental predicate
=
target max block number 또는 max block timestamp 이후
단, overlap lookback을 두고 MERGE하여 경계·retry·reorg를 재검증
```

`amount_raw`는 token decimals를 적용하기 전 정수값이다. 표시용 `amount`는 token metadata의 decimals를 사용해 별도 계산한다. decimals를 하드코딩하지 않는다.

## 3.4 Tether Treasury Flow Model

대상 Treasury 주소는 과제에서 지정한 아래 주소다.

```text
0x5754284f345afc66a98fbb0a0afe71e0f007b949
```

`tether_treasury_flow`는 `erc20_transfers`에서 다음을 수행한다.

```text
inflow
= to_address = treasury_address

outflow
= from_address = treasury_address

netflow
= inflow - outflow
```

USDT만 집계하려면 `token_contract_address`는 구성값 또는 token metadata table에서 지정한다. USDT contract address와 decimals를 SQL에 직접 흩어 쓰지 않고 설정 또는 dimension으로 관리한다.

### 집계 수준

```text
기본
- block_date
- direction(inflow / outflow)
- amount_raw
- amount_normalized
- transaction_count

선택 확장
- hourly
- counterparty address
- mint / burn classification
```

zero address가 `from` 또는 `to`인 Transfer event는 mint·burn 가능성을 나타낼 수 있다. 이를 일반 Treasury inflow·outflow와 구분할지 여부는 별도 policy field로 기록한다.

## 3.5 Incremental Model과 Test

### 모델 설정

```text
erc20_transfers
- materialized: incremental
- incremental_strategy: merge
- unique_key: chain_id + transaction_hash + log_index

tether_treasury_flow
- materialized: incremental
- unique_key: block_date + treasury_address + token_contract_address + direction
```

### 필수 dbt test

| 대상 | 테스트 |
|---|---|
| `stg_ethereum_logs` | not_null, accepted format, unique event key |
| `erc20_transfers` | unique key, not_null from/to/amount, valid topic0 |
| `tether_treasury_flow` | not_null date/direction, accepted values, non-negative inflow/outflow |

## 3.6 신규 모델 자동 반영(Automatic Dependency Handling)

Airflow가 각 dbt 모델을 개별 Task로 하드코딩하면 새 모델 추가 시 DAG 수정이 필요하다.

본 설계는 Airflow가 dbt project 단위로 `dbt build`를 호출하고, 모델 선택과 의존관계는 dbt manifest·`ref()` graph에 위임한다.

```text
Airflow
→ dbt build

dbt
→ source / staging / mart dependency resolution
```

새 모델이 dbt project에 추가되고 dependency graph에 연결되면 DAG Python 코드를 수정하지 않고 dbt 실행 대상에 포함할 수 있다. 실제 선택 범위는 `selector` 또는 tag 정책으로 명시한다.

## 3.7 구현 검증 체크리스트

- [ ] `dbt_project.yml` 생성
- [ ] source relation이 Delta Lake data를 조회
- [ ] Transfer topic decoding unit test
- [ ] raw amount와 normalized amount 검증
- [ ] Treasury inflow / outflow / netflow 표본 대조
- [ ] `dbt run` 후 `dbt test` 통과
- [ ] 신규 model 추가 시 DAG 코드 수정 없이 `dbt build` 범위에 포함됨

## 참고 자료

- EIP-20 Token Standard: https://eips.ethereum.org/EIPS/eip-20
- dbt — dbt_project.yml: https://docs.getdbt.com/reference/dbt_project.yml
- dbt — Source Configurations: https://docs.getdbt.com/reference/source-configs
