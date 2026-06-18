# 3~8. 데이터 계약, 계산 규칙, 결과 테이블(Data Contract, Calculation, and Result Table)

> **문서 상태(Status)**: Draft  
> **문서 역할(Role)**: 원천 테이블과 파생 필드를 구분하고, 정책별 계산식·의사코드·더미 출력·결과 테이블을 정의한다.

# 3. 데이터 범위와 원천 테이블(Data Scope and Raw Tables)

## 3.1 온체인 데이터 범위(On-chain Data Scope)

본 문서는 Bitcoin main chain의 블록, 거래, 입력, 출력, UTXO 데이터를 대상으로 한다. 원천 테이블의 전체 스키마는 과제에서 제공되지 않았으므로, 아래 필드는 설계상 필요한 최소 데이터 계약이다.

## 3.2 원천 테이블과 최소 필드(Minimum Required Fields)

### `block`

| 필드 | 구분 | 용도 |
|---|---|---|
| `block_hash` | 원천 사실 | 블록 식별 및 체인 연결 |
| `previous_block_hash` | 원천 사실 | Best Chain 경로와 Reorg 공통 조상 탐색 |
| `height` | 원천 사실 | 순서·확인 깊이·cutoff 계산 |
| `block_time` | 원천 사실 | UTC 기준 `metric_date` 분류 |
| `observed_at` | 수집 메타데이터 | 체인 스냅샷 관측 시점 추적 |

### `tx`

| 필드 | 구분 | 용도 |
|---|---|---|
| `txid` | 원천 사실 | 거래 식별 |
| `block_hash` | 원천 사실 | 블록 연결 |
| `tx_index` | 원천 사실 | 블록 내 순서 |
| `is_coinbase` | 파생 또는 원천 필드 | 일반 거래량에서 coinbase transaction 제외 |

### `tx_input`

| 필드 | 구분 | 용도 |
|---|---|---|
| `txid` | 원천 사실 | 소비 거래 식별 |
| `input_index` | 원천 사실 | 입력 순서 |
| `prev_txid` | 원천 사실 | 소비된 이전 output 참조 |
| `prev_vout` | 원천 사실 | 소비된 이전 output index 참조 |

### `tx_output`

| 필드 | 구분 | 용도 |
|---|---|---|
| `txid` | 원천 사실 | 거래 연결 |
| `vout` | 원천 사실 | output index |
| `value_sats` | 원천 사실 | 이동량·공급량 계산 |
| `script_pub_key` | 원천 사실 | script classification 입력 |

### `utxo`

`utxo` 테이블이 과거 상태 이력까지 보존하는지, 현재 상태만 보존하는지는 과제에서 명시되지 않았다. 과거 `metric_date`의 공급량을 계산하려면 아래 둘 중 하나가 필요하다.

```text
선택지 A
utxo 테이블이 created/spent lifecycle history를 보존한다.

선택지 B
tx_output과 tx_input에서 silver.utxo_lifecycle을 재구성한다.
```

본 설계는 두 경우 모두를 수용하도록 `silver.utxo_lifecycle`을 파생 계층으로 둔다.

# 4. 파생 필드와 공급량 정책(Derived Fields and Supply Policy)

## 4.1 파생 필드(Derived Fields)

| 필드 | 생성 위치 | 의미 |
|---|---|---|
| `chain_revision_id` | Silver | 관측 시점별 Best Chain 스냅샷 식별자 |
| `is_best_chain` | Silver | 해당 체인 스냅샷에서 Best Chain 소속 여부 |
| `script_class` | Silver | output script 분류 |
| `is_provably_unspendable` | Silver | V1 burn 제외 규칙 적용 대상 |
| `created_height`, `created_block_time` | Silver | UTXO 생성 시점 |
| `spent_height`, `spent_block_time` | Silver | UTXO 소비 시점 |
| `is_coinbase` | Silver | coinbase maturity 적용 |
| `utxo_age_days` | Silver | dormant 정책 적용 |
| `metric_cutoff_block_height` | Silver | 일 종료 시점 공급량 계산 기준 블록 |

## 4.2 Policy-eligible UTXO Supply V1

```text
포함
- Best Chain에 속하는 미소비 UTXO
- 일반 UTXO
- 장기 비활성 상태지만 정책상 제외하지 않은 UTXO

제외
- provably unspendable output
- 기준일 cutoff까지 성숙하지 않은 coinbase output
- Best Chain에서 이탈한 branch의 output
```

## 4.3 Dormancy-adjusted UTXO Supply V1

```text
dormancy_adjusted_utxo_supply_v1
=
policy_eligible_utxo_supply_v1
-
dormant_utxo_supply_v1
```

이 정책은 장기 비활성 UTXO를 분실 코인으로 단정하지 않고, 분모 민감도 분석을 위해 분리한다.

# 5. 계산 기간과 수식(Calculation Window and Formula)

## 5.1 일 단위 산출 기준(Daily Publication Basis)

- `metric_date`: UTC 기준 block header timestamp로 집계한 날짜
- `metric_cutoff_block`: 해당 날짜에 속하는 가장 마지막 Best Chain block
- `as_of_best_chain_tip`: 계산 관측 시점의 Best Chain tip
- `minimum_confirmation_depth`: 내부 게시 정책상 요구하는 최소 확인 깊이

## 5.2 일별 이동량(Daily Gross On-chain Output Volume)

```text
daily_gross_onchain_output_volume_v1_btc(d)
=
SUM(o.value_sats) / 100,000,000
WHERE
  tx.is_coinbase = false
  AND output.is_provably_unspendable = false
  AND block.is_best_chain = true
  AND DATE_UTC(block.block_time) = d
```

## 5.3 후행 365일 이동량(Trailing 365-day Volume)

```text
trailing_365d_gross_onchain_output_volume_v1_btc(d)
=
SUM(daily_gross_onchain_output_volume_v1_btc(t))
for t in [d - 364 days, d]
```

365개 날짜가 모두 존재하고 source completeness를 통과한 경우에만 게시한다.

## 5.4 기본 분모(Policy-eligible UTXO Supply)

```text
policy_eligible_utxo_supply_v1_btc(d)
=
SUM(u.value_sats) / 100,000,000
WHERE
  u.created_height <= cutoff_height(d)
  AND (u.spent_height IS NULL OR u.spent_height > cutoff_height(d))
  AND u.is_provably_unspendable = false
  AND (
       u.is_coinbase = false
       OR cutoff_height(d) - u.created_height >= 100
  )
  AND u.created_block_is_best_chain = true
```

## 5.5 Velocity 변형 지표(Velocity Variants)

```text
assignment_velocity_365d_policy_eligible_utxo_v1(d)
=
trailing_365d_gross_onchain_output_volume_v1_btc(d)
/
policy_eligible_utxo_supply_v1_btc(d)
```

```text
assignment_velocity_365d_dormancy_adjusted_utxo_v1(d)
=
trailing_365d_gross_onchain_output_volume_v1_btc(d)
/
dormancy_adjusted_utxo_supply_v1_btc(d)
```

# 6. SQL 또는 의사코드(SQL or Pseudocode)

## 6.1 Best Chain 스냅샷 생성

```sql
-- Pseudocode
tip = source.get_best_chain_tip(observed_at)

best_chain_blocks = walk_backward(
    start_hash = tip.block_hash,
    previous_hash_column = block.previous_block_hash
)

persist best_chain_blocks with:
  chain_revision_id,
  observed_at,
  block_hash,
  height,
  is_best_chain = true
```

## 6.2 일별 이동량 계산

```sql
WITH best_chain_tx AS (
    SELECT
        DATE(b.block_time) AS metric_date,
        t.txid
    FROM silver.best_chain_block b
    JOIN raw.tx t
      ON t.block_hash = b.block_hash
    WHERE b.chain_revision_id = :chain_revision_id
      AND t.is_coinbase = FALSE
),
daily_volume AS (
    SELECT
        b.metric_date,
        SUM(o.value_sats) / 100000000.0
          AS daily_gross_onchain_output_volume_v1_btc
    FROM best_chain_tx b
    JOIN raw.tx_output o
      ON o.txid = b.txid
    JOIN silver.output_classification c
      ON c.txid = o.txid
     AND c.vout = o.vout
    WHERE c.is_provably_unspendable = FALSE
    GROUP BY b.metric_date
)
SELECT * FROM daily_volume;
```

## 6.3 일별 공급량 계산

```sql
WITH daily_cutoff AS (
    SELECT
        metric_date,
        MAX(height) AS metric_cutoff_block_height
    FROM silver.best_chain_block
    WHERE chain_revision_id = :chain_revision_id
    GROUP BY metric_date
)
SELECT
    d.metric_date,
    SUM(u.value_sats) / 100000000.0
      AS policy_eligible_utxo_supply_v1_btc
FROM daily_cutoff d
JOIN silver.utxo_lifecycle u
  ON u.created_height <= d.metric_cutoff_block_height
 AND (
      u.spent_height IS NULL
      OR u.spent_height > d.metric_cutoff_block_height
 )
WHERE u.is_provably_unspendable = FALSE
  AND (
       u.is_coinbase = FALSE
       OR d.metric_cutoff_block_height - u.created_height >= 100
  )
GROUP BY d.metric_date;
```

## 6.4 365일 Velocity 계산

```sql
WITH date_spine AS (
    SELECT metric_date
    FROM dim.calendar
    WHERE metric_date BETWEEN :start_date AND :end_date
),
daily_base AS (
    SELECT
        d.metric_date,
        v.daily_gross_onchain_output_volume_v1_btc,
        s.policy_eligible_utxo_supply_v1_btc
    FROM date_spine d
    LEFT JOIN silver.daily_gross_onchain_output_volume v
      ON d.metric_date = v.metric_date
    LEFT JOIN silver.daily_policy_eligible_utxo_supply s
      ON d.metric_date = s.metric_date
),
validated_base AS (
    SELECT *
    FROM daily_base
    WHERE daily_gross_onchain_output_volume_v1_btc IS NOT NULL
      AND policy_eligible_utxo_supply_v1_btc IS NOT NULL
),
rolling_metric AS (
    SELECT
        metric_date,
        SUM(daily_gross_onchain_output_volume_v1_btc)
          OVER (
            ORDER BY metric_date
            ROWS BETWEEN 364 PRECEDING AND CURRENT ROW
          ) AS trailing_365d_gross_onchain_output_volume_v1_btc,
        policy_eligible_utxo_supply_v1_btc,
        COUNT(*) OVER (
            ORDER BY metric_date
            ROWS BETWEEN 364 PRECEDING AND CURRENT ROW
        ) AS rolling_coverage_days
    FROM validated_base
)
SELECT
    metric_date,
    trailing_365d_gross_onchain_output_volume_v1_btc,
    policy_eligible_utxo_supply_v1_btc,
    trailing_365d_gross_onchain_output_volume_v1_btc
      / policy_eligible_utxo_supply_v1_btc AS velocity
FROM rolling_metric
WHERE rolling_coverage_days = 365
  AND policy_eligible_utxo_supply_v1_btc > 0;
```

`COALESCE(volume, 0)`를 source completeness 검증 전에 사용하지 않는다. 실제 0 이동량과 원천 데이터 누락을 구분해야 하기 때문이다.

# 7. 더미 데이터 기반 출력 예시(Dummy Output)

> 아래는 계산 설명을 위한 3일 축소 예시다. 실제 지표는 365일 window를 사용한다.

| metric_date | daily gross output volume | 3-day rolling volume | policy-eligible UTXO supply | illustrative velocity |
|---|---:|---:|---:|---:|
| 2026-06-01 | 2.0 BTC | 2.0 BTC | 19,000,000 BTC | 0.0000001053 |
| 2026-06-02 | 3.5 BTC | 5.5 BTC | 19,000,100 BTC | 0.0000002895 |
| 2026-06-03 | 1.5 BTC | 7.0 BTC | 19,000,200 BTC | 0.0000003684 |

# 8. 결과 테이블 설계(Result Table Design)

## 8.1 `gold.daily_bitcoin_velocity`

| 컬럼 | 설명 |
|---|---|
| `metric_date` | UTC 기준 지표일 |
| `metric_variant` | `policy_eligible_utxo_v1` 또는 `dormancy_adjusted_utxo_v1` |
| `volume_window_days` | 기본값 365 |
| `trailing_365d_gross_onchain_output_volume_v1_btc` | 후행 365일 분자 |
| `policy_eligible_utxo_supply_v1_btc` | 기본 분모 |
| `dormant_utxo_supply_v1_btc` | 장기 비활성 공급량 |
| `dormancy_adjusted_utxo_supply_v1_btc` | 보조 분모 |
| `dormant_utxo_spent_volume_v1_btc` | 보조 흐름 |
| `denominator_supply_btc` | 해당 variant에서 실제 사용한 분모 |
| `velocity` | 산출 결과 |
| `metric_definition_version` | 공식·윈도우·variant 정의 버전 |
| `volume_definition_version` | 분자 산정 규칙 버전 |
| `supply_policy_version` | 분모·dormancy 정책 버전 |
| `pipeline_code_version` | 변환 코드 버전 |
| `metric_cutoff_block_height`, `metric_cutoff_block_hash` | 기준일 종료 checkpoint |
| `as_of_best_chain_tip_height`, `as_of_best_chain_tip_hash` | 관측 시점 Best Chain tip |
| `minimum_confirmation_depth` | 게시 정책 확인 깊이 |
| `chain_confidence_status` | `pending_confirmation`, `confirmed_by_policy`, `superseded_by_reorg` |
| `chain_revision_id` | Best Chain 스냅샷 식별자 |
| `calculated_at` | 계산 시점 |

## 8.2 논리 키(Logical Key)와 갱신

이 설계는 Delta Lake의 데이터베이스 강제 Primary Key에 의존하지 않는다.

```text
published logical key
=
(metric_date, metric_variant, metric_definition_version)
```

중복 방지는 다음 조합으로 처리한다.

1. staging 단계의 논리 키 중복 검사  
2. 품질 검증 통과 후 Delta `MERGE`  
3. 게시 테이블의 사후 중복 검사  
4. Reorg 이전 값은 audit history 또는 변경 로그에 보존  

`chain_revision_id`는 논리 키가 아니라 결과가 어떤 체인 스냅샷에서 계산됐는지 추적하는 메타데이터다.

## 참고 자료(References)

- Bitcoin Developer Documentation — Block Chain: https://developer.bitcoin.org/devguide/block_chain.html
- Bitcoin Developer Documentation — Transactions: https://developer.bitcoin.org/examples/transactions.html
- Delta Lake — MERGE: https://docs.delta.io/delta-update/
