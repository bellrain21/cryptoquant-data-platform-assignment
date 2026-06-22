# 07. Submission Readiness Report

> 상태: 제출 전 점검 보고서
> 기준일: 2026-06-22 KST
> 원칙: 검증된 동작, 설계-only 항목, 제출 제외 개인 자료, generated/local artifact를 분리합니다.

## Repository Inventory Summary

레거시 정리 기준으로 현재 실행 경로에 연결되지 않은 구 패키지와 deprecated DAG shim은
삭제 대상입니다. source/test/fixture/docs/Docker/dbt/Airflow 중 현재 요구사항 증거에
연결된 파일은 유지하고, local/generated artifact는 `.gitignore`와 문서 경계로 제외합니다.

| 분류 | 파일 또는 디렉터리 | 제출 판단 |
|---|---|---|
| Source code | `src/cryptoquant_pipeline/`, `scripts/` | 유지. 삭제된 `src/eth_pipeline/`, `src/cryptoquant_assignment/`는 legacy cleanup report에서 근거 추적 |
| Airflow source | `airflow/dags/ethereum_hourly_logs.py` | 유지. deprecated `ethereum_logs_pipeline.py` shim은 삭제 |
| dbt source | `dbt/dbt_project.yml`, `dbt/macros/`, `dbt/models/`, `dbt/profiles.yml.example` | 유지 |
| Tests and fixtures | `tests/`, `tests/fixtures/` | 유지 |
| Docker/dependency files | `Dockerfile`, `docker-compose.yaml`, `.devcontainer/`, `requirements.txt`, `requirements-runtime.txt`, `pyproject.toml`, `.env.example` | 유지 |
| Core submission docs | `README.md`, `docs/00_documentation_index.md`, `docs/01_system_architecture.md` ~ `docs/07_submission_readiness_report.md`, `docs/09_requirement_traceability_matrix.md`, `docs/10_refactoring_report.md`, `docs/11_documentation_consistency_report.md` | 유지 |
| Task 1 docs | `docs/task_01_bitcoin_velocity/` | 유지. 현재 설계 source of truth |
| Task 2 current docs | `docs/01_system_architecture.md`, `docs/02_data_contracts.md`, `docs/03_execution_guide.md`, `docs/04_failure_retry_backfill_strategy.md`, `docs/05_validation_evidence.md`, `docs/06_code_reading_guide.md` | 유지. 현재 구현 source of truth |
| AI usage transparency | `docs/08_ai_usage_transparency_and_validation.md` | 유지. PDF 제출 요구에 필요한 범위만 포함 |
| Personal learning/reference docs | `docs/14_feynman_concept_map.md`, `docs/02_blockchain_concepts_guide.md` | 제출 범위에서 제거 |
| Exploratory design docs | `docs/task_02_ethereum_log_pipeline/` | 유지하되 Reference / exploratory design — not the current implementation source of truth로 라벨링 |
| Validation evidence | `docs/05_validation_evidence.md`, `docs/10_refactoring_report.md`, `docs/11_documentation_consistency_report.md`, 이 문서의 Validation Results | 유지 |
| Screenshot evidence | `data/imgs/` | 유지. Airflow UI DAG 등록과 run history 보조 증거 |
| Notebook evidence | `src/notebooks/` | 유지. 03번 fixture ETL/idempotency와 04번 accumulated data freshness output 저장 |
| Generated artifacts | `data/delta/`, `data/analytics/`, `dbt/target/` | 제출 source of truth가 아니며, ignore 대상입니다. |
| Caches | `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`, `.mypy_cache/` | ignore 대상입니다. |
| Local environments | `.venv/`, `venv/` | ignore 대상입니다. |
| Local logs/config | `airflow/logs/`, `logs/`, `airflow.cfg`, `dbt/profiles.yml`, `dbt/.user.yml` | ignore 대상입니다. `profiles.yml.example`은 유지합니다. |
| Binaries/extensions | `data/duckdb_extensions/` | ignore 대상입니다. |
| Possible sensitive files | `.env`, `.env.*`, real RPC URLs, local generated config | ignore 대상입니다. `.env.example`만 유지합니다. |

Tracked generated artifact는 `git ls-files` 기준으로 관측하지 못했습니다. 비추적 local artifact는 삭제하지 않았고, 제출 범위에서 제외되도록 `.gitignore`를 보강했습니다.

## Task 1 Architecture and Policy Explainability

### Metric Purpose

Task 1 지표는 Bitcoin 공급량 대비 온체인 output movement가 얼마나 크게 관측되는지 보는 assignment-scoped activity indicator다. 가격 방향, exchange spot trading volume, 실제 경제 주체 간 순가치 이전, CryptoQuant production metric 재현을 주장하지 않습니다.

### Formula

```text
assignment_velocity_365d_policy_eligible_utxo_v1(d)
=
trailing_365d_gross_onchain_output_volume_v1_btc(d)
/
policy_eligible_utxo_supply_v1_btc(d)
```

분자:

- canonical Bitcoin chain의 regular transaction에서 생성된 `tx_output.value_sats` 합계.
- UTC date 기준 trailing 365-day window.
- Coinbase transaction은 일반 transfer activity가 아니므로 제외.
- Provably unspendable output은 protocol/script 수준에서 기술적으로 식별 가능한 경우 제외.

분모:

- day-end cutoff block 기준 policy-eligible UTXO supply.
- 미소비 output, coinbase maturity 100-block 조건, canonical chain membership, unspendable exclusion 정책을 적용.
- Dormant UTXO는 자동으로 lost coins가 아니므로 기본 분모에서 제외하지 않습니다.

이 정의는 universal truth가 아니라 V1 policy choice입니다. 과제에 production source tables, proprietary estimation method, entity label contract가 제공되지 않았기 때문에 재현 가능한 투명 정책을 우선합니다.

### Data Source Roles

| Source table | 역할 |
|---|---|
| `block` | chain linkage, height, UTC date, confirmation/reorg checkpoint |
| `tx` | block 안의 transaction, coinbase 여부, tx identity |
| `tx_input` | 이전 output 소비 참조입니다. UTXO lifecycle 재구성에 필요합니다. |
| `tx_output` | 새 spendable right 생성. gross output volume과 UTXO 생성 근거 |
| `utxo` | day-end supply 계산 또는 lifecycle 검증 보조입니다. 현재 snapshot만으로 과거 supply를 단독 복원하지 않습니다. |

관계:

```text
block -> tx -> tx_input references previous tx_output
              -> tx_output creates new spendable rights
unspent tx_outputs -> UTXOs
```

### Policy Decisions and Rationale

| 정책 | 결정 | 이유 |
|---|---|---|
| Coinbase treatment | 일반 transaction volume에서 제외 | 신규 발행/채굴 보상은 regular BTC transfer activity와 다름 |
| Change output limitation | V1은 change output을 제거하지 않습니다. | 주소 군집화와 change heuristic이 제공되지 않아 투명한 gross output 기준을 선택했습니다. |
| Dormant UTXO treatment | long-dormant UTXO를 lost coins로 단정하지 않습니다. | 장기 미사용은 관측 상태이지 소유권 상실 사실이 아닙니다. |
| Unspendable/burn treatment | protocol/script 수준에서 식별 가능한 provably unspendable output만 제외 | 외부 burn label은 별도 registry와 provenance가 필요합니다 |
| Coinbase maturity | cutoff height에서 100-block maturity 조건 적용 | 미성숙 coinbase output은 소비 가능 UTXO로 보지 않음 |
| Canonical chain / confirmation | Best Chain snapshot과 successor-block policy를 적용 | reorg로 바뀔 수 있는 값을 즉시 확정값처럼 게시하지 않기 위함 |

### Failure Rules

Hard fail:

- 365-day window의 source date가 누락됩니다.
- `block -> tx -> tx_output` 관계가 깨짐.
- UTXO lifecycle에서 생성/소비 관계가 모순됩니다.
- denominator가 0 또는 null입니다.
- reorg checkpoint 불일치가 감지되었으나 영향 범위를 재계산하지 못했습니다.

Review alert:

- daily gross output volume 급증.
- dormant UTXO spent volume 급증.
- denominator supply의 비정상 변화.
- exchange/wallet reorganization 가능성이 있는 큰 movement.

Hard fail은 publish하면 잘못된 metric이 되는 구조적/논리적 무결성 실패입니다. Review alert는 실제 chain 또는 market event일 수 있으므로 publish 중단보다 조사 플래그가 맞습니다.

### Recovery Design

- Rerun은 logical key와 metric contract version 기준으로 idempotent해야 합니다.
- Backfill은 scheduled run과 같은 transformation logic을 사용해야 합니다.
- Reorg 감지 시 stored block hash와 current best chain block hash를 비교합니다.
- Common ancestor를 찾고 affected start date부터 최신 confirmed metric date까지 daily component와 velocity를 재계산합니다.
- 기존 published value는 조용히 삭제하지 않고 audit history에서 superseded 상태로 보존합니다.

### Task 1 Validity Scan

2026-06-22 KST에 `docs/task_01_bitcoin_velocity/` 하위 문서를 정적 스캔하여 과제 1 필수 요구사항 누락 여부를 별도로 확인했습니다.

| 검증 축 | 결과 |
|---|---|
| Velocity formula | PASS |
| Raw tables | PASS |
| Volume policy | PASS |
| Supply policy | PASS |
| SQL pseudocode | PASS |
| Dummy data | PASS |
| Daily batch | PASS |
| Reorg | PASS |

이 결과는 설계 문서와 의사 SQL의 정합성을 의미합니다. 실제 Bitcoin source DB, Spark job, Delta table을 실행한 결과로 표현하지 않습니다.

### How to Explain This in an Interview

30-second explanation:

> 이 과제의 Velocity는 CryptoQuant production metric을 복제한 값이 아니라, Bitcoin raw table만으로 방어 가능하게 정의한 gross on-chain output velocity입니다. 분자는 최근 365일 regular transaction output 합계이고, 분모는 day-end policy-eligible UTXO supply입니다. Change output과 내부 지갑 이동이 섞일 수 있으므로 경제적 거래량이나 가격 예측 지표라고 말하지 않습니다.

1-minute explanation:

> 저는 source fact, policy choice, assumption을 분리했습니다. `block`, `tx`, `tx_input`, `tx_output`에서 UTXO lifecycle을 재구성하고, day-end cutoff에서 미소비이고 성숙한 coinbase 조건을 만족하며 provably unspendable이 아닌 UTXO만 분모로 봅니다. 분자는 non-coinbase transaction의 output value 합계라 change output을 제거하지 않습니다. 그래서 이 값은 온체인 활동성 지표이지 경제적 transfer volume이 아닙니다. Reorg가 발생하면 common ancestor 이후 날짜와 rolling window 영향 범위를 재계산하고 이전 값은 audit history에 superseded로 남기는 설계입니다.

Likely reviewer questions:

| 질문 | 답변 |
|---|---|
| CryptoQuant Velocity와 같은 값인가? | 아닙니다. 공개 설명은 context only이고, production estimation method가 없어서 assignment-scoped V1 metric으로 정의했습니다. |
| 왜 change output을 제거하지 않았나? | change heuristic과 entity label이 없으면 제거 규칙이 불투명해집니다. V1은 gross output으로 명시하고 한계를 문서화했습니다. |
| Dormant UTXO를 lost coins로 봤나? | 아닙니다. dormant는 장기 미사용 상태이며, lost coin은 사실 판정이 아니라 별도 sensitivity analysis로만 다룹니다. |
| Reorg는 어떻게 처리하나? | stored checkpoint와 current chain hash를 비교하고 common ancestor 이후 affected dates를 같은 transformation logic으로 재계산합니다. 이전 published value는 audit에 남긴다. |
| 이 지표로 가격을 예측하나? | 아닙니다. 가격 방향이나 거래소 내부 거래량을 직접 측정하지 않습니다. |

## Task 2 Implementation and Integrity Review

| 점검 항목 | 현재 확인 결과 | 제출 상태 |
|---|---|---|
| Raw log unique key chain identity | raw row에 `chain_id`와 `block_hash`는 저장됩니다. Delta dedup key는 `chain_id + transaction_hash + log_index`이며 `block_hash`는 포함하지 않습니다. | retry dedup은 구현했습니다. reorg replacement key는 구현되지 않았습니다. |
| Duplicate ingestion | batch 내부 중복과 기존 Delta key 중복 skip 구현 | fixture-tested |
| Retry duplication | 같은 raw batch 재실행 시 row count 불변 테스트 있습니다. | fixture-tested |
| Reorg replacement | finality buffer는 있습니다. block-hash checkpoint/canonical stale row replacement는 없습니다. | design-only/future hardening |
| Stale canonical rows | 별도 canonical table이 없어 stale canonical row 제거 구현이 없습니다. | 구현되지 않았습니다. |
| Partial subrange failure | 단일 block 실패 시 `LogFetchError`, raw quality gate에서 failed subrange 실패 처리 | fixture-tested/code-inspected |
| `eth_chainId` validation | `pipeline.run_interval`에서 RPC endpoint chain id와 `ETH_CHAIN_ID` 일치 여부 확인 | implemented/tested by mock, real basic RPC verified |
| Collection scope | `CollectionScope.default_transfer_topic_all_addresses`가 `address_filter=None`, Transfer `topic0`만 허용하고 `ETH_LOG_ADDRESS_FILTER` drift를 설정 단계에서 차단 | implemented/fixture-tested. Airflow scheduled-run evidence는 있습니다. provider qualification manifest는 구현되지 않았습니다. |
| Airflow UI run history | `data/imgs/` screenshot에서 DAG 등록, `@hourly`, success 47, failed 14, failed task instance 13건을 확인 | VERIFIED as run-history evidence. UI screenshot 단독 row-level correctness는 아닙니다. |
| Airflow external RPC scheduled runs | `airflow/logs/`에서 successful scheduled 반환값 33건 확인. latest direct inspection 기준 `data/delta/ethereum_logs_v2` row count `6848937`, `erc20_transfers=6079379` | VERIFIED in local Docker Airflow. production SLA는 별도 |
| Accumulated local raw Delta | `src/notebooks/04_*`가 최신 v2 pair를 선택해 schema current, row count `6848937`, duplicate key `0`을 확인 | PARTIALLY VERIFIED. 2026-06-22 12:00 UTC hourly gap과 DuckDB staging view 절대경로 문제가 남아 있습니다. |
| Block hash checkpoints | raw row `block_hash` 보존 외 checkpoint reconciliation 없습니다. | P1 gap |
| DAG concurrency | `max_active_runs=1` 있습니다. task pool/concurrency/Delta writer lock은 없습니다. | 부분 통제 |
| `uint256` handling | raw hex 보존, Python exact decimal text 생성, dbt `DECIMAL(38,0)` 파생은 38자리 이하만 채움 | 제한 명시. float conversion 없습니다. |
| `uint256` boundary tests | DECIMAL38 범위 안/밖 상태값과 raw decimal text 계약을 fixture/dbt test로 검증 | fixture-tested |
| Address labels | USDT contract와 Tether Treasury-labelled address는 dbt env var로 설정. label provenance/version registry 없습니다. | external assumption |
| Claimed reorg behavior | current docs must state finality/idempotency only. legacy docs are exploratory | 문서 라벨 보강 |

Task 2의 현재 source of truth는 `src/cryptoquant_pipeline/`, `airflow/dags/ethereum_hourly_logs.py`, `dbt/models/`, `docs/01_system_architecture.md`, `docs/02_data_contracts.md`, `docs/03_execution_guide.md`, `docs/04_failure_retry_backfill_strategy.md`다. 삭제된 `src/eth_pipeline/`와 `src/cryptoquant_assignment/`는 이전 구현이며 현재 실행 경로가 아닙니다.

## Security and Operational Risk Assessment

This repository is designed as a reproducible local assignment demo. Default credentials, host port bindings, writable mounts, single-provider trust, and dependency pinning are treated as development conveniences rather than production security controls.

Production hardening would require secret management, strong Airflow authentication, network isolation, TLS, immutable deployment artifacts, dependency locking, provider redundancy, chain checkpointing, audit retention, and monitoring.

### Threat Model

| Threat actor/failure | 설명 |
|---|---|
| External attacker | Local Airflow UI, exposed port, default credentials, weak auth를 악용할 수 있습니다. |
| Local developer/operator mistake | `.env`, RPC URL, generated logs/data를 Git에 추가하거나 잘못된 backfill을 실행할 수 있습니다. |
| Malicious or faulty RPC provider | rate limit, partial response, malformed payload, wrong chain endpoint, stale data를 반환할 수 있습니다. |
| Normal chain/data failure | Ethereum reorg, retry duplication, partial ingestion, Delta writer conflict, uint256 precision loss가 발생할 수 있습니다. |

### Protected Assets

- RPC credentials and provider URLs.
- Airflow administration surface.
- Source data integrity and replay auditability.
- Delta/DuckDB output integrity.
- Assignment/repository credibility.

### Risk Table

| Scenario | Impact | Current control | Gap | Recommended mitigation | Implementation status |
|---|---|---|---|---|---|
| Real `.env` or RPC key committed | Credential exposure | `.env`, `.env.*` ignored; `.env.example` placeholder only | Generated logs/shell history는 별도 통제 없습니다. | secret scanning, pre-commit checks, rotate exposed keys | P0 documented |
| Airflow default credentials | Unauthorized local UI access | `.env.example` labels `airflow/airflow`; local demo only | Strong auth 없습니다. | strong password, SSO/RBAC, network isolation | P2 |
| Airflow web UI host port `8080` | Local network exposure | Docker compose explicit port mapping | TLS/network restriction 없습니다. | bind to localhost only, TLS/reverse proxy, firewall | P2 |
| Empty Fernet key | Airflow connection/variable encryption 약화 | Demo config only | production secret encryption 없습니다. | set strong Fernet key via secret manager | P2 |
| Default Postgres credentials | Metadata DB compromise in local network | Docker local volume | hardened DB auth 없습니다. | strong password, network isolation | P2 |
| Writable host mounts | DAG/source tampering affects runtime | Local dev convenience | immutable deploy 없습니다. | read-only mounts, image-baked DAGs, signed artifacts | P2 |
| Single RPC provider trust | Wrong/stale/partial data accepted | bounded retry, malformed payload handling | provider redundancy/chain checkpoint 없습니다. | multi-provider cross-check, `eth_chainId`, block hash checkpoints | P1 |
| Rate limit or partial responses | Missing logs or failed DAG | adaptive split, failed subrange hard failure | real provider behavior unverified | provider-specific integration tests, alerting | P1 |
| Ethereum reorg | stale raw/canonical rows | finality buffer, `block_hash` stored | canonical replacement 구현되지 않았습니다. | checkpoint reconciliation, reorg lookback rebuild | P1 |
| Retry/manual backfill duplication | duplicate analytics rows | Delta dedup key, dbt unique_key | concurrent writer conflict not fully controlled | transactional merge/delete-insert by affected range, lock/pool | P1 |
| Delta concurrent writer conflict | failed or partial writes | `max_active_runs=1` | task/pool level lock 없습니다. | Airflow pool, file lock, single writer policy | P1 |
| Partial ingestion treated as success | downstream false success | failed subrange exception, raw quality gate | real provider partial semantics unverified | response completeness checks, run manifest | P1 |
| Large `uint256` precision loss | wrong transfer amount | raw hex preserved, no float conversion | full decimal conversion not implemented | Python exact int/UDF, boundary tests | P1 |
| Address label drift | wrong entity flow | env-configured address | provenance/version/expiry가 없습니다. | label registry with source, valid_from/to, confidence | P1 |
| Docker image tag drift | non-reproducible runtime | some package pins | base image/postgres tag not digest-pinned | digest pinning, SBOM, vulnerability scan | P2 |
| Dependency drift/supply chain | changed behavior or vulnerable package | version pins in requirements | no lockfile/hash validation | lockfile, hash checking, vulnerability scan | P2 |

### Minimum P0 Submission Controls

- No real secrets in repository: 현재 스캔 범위에서 실제 key는 확인되지 않았고 `.env.example` placeholder만 있습니다.
- Local/demo credentials clearly labeled: README와 이 문서에 default credential risk를 명시.
- Generated logs/data excluded: `.gitignore`에서 data, dbt target/logs, Airflow logs, caches 제외.
- Validation status honesty: fixture/static/real RPC/Airflow runtime 범위를 분리.
- Unresolved reorg limitation documented: finality/idempotency와 canonical replacement 구현되지 않은 항목을 분리.
- No false production-ready claims: local assignment demo로만 표현.

### P1 Code/Design Hardening

- Multi-provider chain identity cross-check and alerting.
- Block-hash checkpoints and common-ancestor reconciliation.
- Reorg lookback rebuild policy and fixture.
- Partial-ingestion publish guard with run manifest.
- DAG task pool/concurrency control around Delta/DuckDB writers.
- `uint256` boundary tests and exact decimal conversion path.
- Label provenance registry for externally sourced entity labels.

### P2 Production Hardening

- Secret manager for RPC URLs, Airflow credentials, Fernet key.
- SSO/RBAC/TLS for Airflow.
- Network isolation and restricted host port exposure.
- Immutable image deployment and read-only runtime mounts.
- Image digest pinning and SBOM/vulnerability scan.
- Dependency lockfile with hash validation.
- Multi-provider cross validation.
- Monitoring, alerting, and audit retention.

## Validation Results

이번 제출 점검 세션에서 실행한 명령입니다. 상태 라벨은 `VERIFIED`, `PARTIALLY VERIFIED`, `NOT VERIFIED`, `BLOCKED`만 사용합니다.

| Command | Status | Direct result/cause |
|---|---|---|
| `python -m pytest -q` | BLOCKED | 호스트 Python 3.13 환경에서 `No module named pytest`가 발생했습니다. 의존성 미설치로 차단됐으며, 코드 실패로 판정하지 않습니다. |
| `python -m compileall src tests airflow/dags scripts` | PARTIALLY VERIFIED | `src`, `tests`, `airflow/dags`, `scripts` 문법 compile 통과 |
| `$env:PYTHONPATH='src'; python -c "...PipelineConfig...EthereumIngestionSettings..."` | PARTIALLY VERIFIED | 핵심 설정 객체 import와 기본 env parse는 통과했습니다. Airflow/dbt/Delta optional dependency import는 검증하지 않았습니다. |
| `docker compose -f docker-compose.yaml -f .devcontainer/docker-compose.devcontainer.yaml config --quiet` | VERIFIED | exit 0 |
| `dbt parse --project-dir dbt --profiles-dir dbt --no-partial-parse` | BLOCKED | 호스트 환경에 `dbt` executable이 없습니다. |
| `ruff check .` | BLOCKED | 호스트 환경에 `ruff` executable이 없습니다. |
| `docker compose -f docker-compose.yaml -f .devcontainer/docker-compose.devcontainer.yaml images workspace-dev` | VERIFIED | 기존 `workspace-dev` image 존재 확인 |
| `docker compose -f docker-compose.yaml -f .devcontainer/docker-compose.devcontainer.yaml run --rm --no-deps workspace-dev python --version` | VERIFIED | `Python 3.12.3` |
| `docker compose -f docker-compose.yaml -f .devcontainer/docker-compose.devcontainer.yaml run --rm --no-deps workspace-dev airflow version` | VERIFIED | `2.10.5` |
| `docker compose -f docker-compose.yaml -f .devcontainer/docker-compose.devcontainer.yaml run --rm --no-deps workspace-dev /opt/airflow/python/bin/python -c "...DagBag..."` | VERIFIED | `import_errors={}`, `dag_ids=['ethereum_hourly_logs']` |
| `docker compose -f docker-compose.yaml -f .devcontainer/docker-compose.devcontainer.yaml run --rm --no-deps workspace-dev python -m pytest -q` | VERIFIED | `49 passed` |
| `docker compose -f docker-compose.yaml -f .devcontainer/docker-compose.devcontainer.yaml run --rm --no-deps workspace-dev ruff check .` | VERIFIED | `All checks passed!` |
| `docker compose -f docker-compose.yaml -f .devcontainer/docker-compose.devcontainer.yaml run --rm --no-deps workspace-dev python scripts/create_dbt_validation_fixture.py --root /workspace/data/tmp/dbt_validation/final_refactor` | VERIFIED | `{'inserted': 2, 'rows': 2}` |
| `docker compose -f docker-compose.yaml -f .devcontainer/docker-compose.devcontainer.yaml run --rm --no-deps -e DELTA_LOGS_PATH=/workspace/data/tmp/dbt_validation/final_refactor/ethereum_logs -e DUCKDB_PATH=/workspace/data/tmp/dbt_validation/final_refactor/ethereum_analytics.duckdb -e DUCKDB_EXTENSION_DIR=/workspace/data/duckdb_extensions workspace-dev dbt build --project-dir dbt --profiles-dir dbt --select tag:ethereum_hourly --vars '{"window_start": "2024-01-01T00:00:00Z", "window_end": "2024-01-01T01:00:00Z"}' --no-partial-parse` | VERIFIED | `PASS=43 WARN=0 ERROR=0 SKIP=0 NO-OP=0 TOTAL=43` |
| `docker compose -f docker-compose.yaml -f .devcontainer/docker-compose.devcontainer.yaml run --rm --no-deps -e DELTA_LOGS_PATH=/workspace/data/tmp/dbt_validation/final_refactor/ethereum_logs -e DUCKDB_PATH=/workspace/data/tmp/dbt_validation/final_refactor/ethereum_analytics.duckdb -e DUCKDB_EXTENSION_DIR=/workspace/data/duckdb_extensions workspace-dev dbt ls --project-dir dbt --profiles-dir dbt --select tag:ethereum_hourly --output name --no-partial-parse` | VERIFIED | `Found 4 models, 39 data tests, 1 source, 486 macros`; `tether_treasury_flow_quality_summary` 포함 |
| `docker compose -f docker-compose.yaml -f .devcontainer/docker-compose.devcontainer.yaml run --rm --no-deps workspace-dev python -c "...relation counts..."` | VERIFIED | `{'ethereum_logs': 2, 'erc20_transfers': 2, 'tether_treasury_flow': 1, 'tether_treasury_flow_quality_summary': 1}` |
| `nbclient` execution of `src/notebooks/03_fixture_etl_replay_idempotency_validation.ipynb` | VERIFIED | `second_inserted_row_count=0`, `duplicate_natural_key_count=0`, saved error output이 없습니다. |
| custom code-cell execution of `src/notebooks/04_accumulated_pipeline_data_freshness_validation.ipynb` | PARTIALLY VERIFIED | `latest_v2_local` 선택, raw `6848937`, duplicate key `0`, schema current. 12:00 UTC hourly gap과 DuckDB staging view 절대경로 문제 확인 |
| `scripts/inspect_outputs.py` with canonical paths | PARTIALLY VERIFIED | `delta_row_count=1`, `delta_duplicate_natural_key_count=0`, `erc20_transfers_row_count=1`, `tether_treasury_flow_row_count=1`. schema freshness는 별도 불일치 |
| `data/imgs/` screenshot manual review | PARTIALLY VERIFIED | Airflow UI 기준 DAG 등록, `@hourly`, success 47, failed 14, failed task instance 13건 확인 |
| Airflow task log parse | VERIFIED | successful scheduled run 반환값 33건, first `scheduled__2026-06-20T21:00:00+00:00`, latest parsed run `scheduled__2026-06-22T08:00:00+00:00`, `row_count_after=6082932`, `dbt.returncode=0` |
| Delta/DuckDB direct inspection in `workspace-dev` | VERIFIED | latest recheck 기준 `data/delta/ethereum_logs_v2` row count `6848937`, `data/analytics/ethereum_analytics_v2.duckdb`의 `erc20_transfers=6079379`, `tether_treasury_flow=2`, `quality_summary=1` |
| `git diff --check` | VERIFIED | exit 0. 줄끝 변환 경고만 출력됨 |
| Markdown local link check | VERIFIED | `markdown local links ok` |
| secret-like value scan | VERIFIED | tracked file에서 secret-like token match가 없습니다. `.env`는 Git 추적 대상이 아니며 `.env.example`만 추적됩니다. |

NOT VERIFIED:

- production-grade provider SLA, alerting, secret rotation, full-history backfill.
- 2026-06-22 12:00 UTC hourly gap 원인 확인 및 필요 시 backfill.
- DuckDB `main.ethereum_logs` staging view의 `/opt/airflow/...` 절대경로 이식성 보강.
- Docker image build 재실행.
- Reorg replacement fixture.
- Full `uint256` decimal boundary behavior.

## Remaining Submission Risks

| Impact | Risk | Current handling |
|---|---|---|
| High | Real Ethereum RPC/mainnet ingestion은 로컬 Docker에서 검증됐지만 production SLA는 검증하지 않았습니다. | Airflow log, Delta/DuckDB evidence로 검증 범위를 명시하고 production hardening은 별도 처리 |
| High | Reorg canonical replacement not implemented | finality buffer only로 문서화 |
| Medium | Multi-provider chain identity/cross-check 구현되지 않았습니다. | 단일 provider `eth_chainId` 일치 확인만 구현 |
| Medium | Full `uint256` DECIMAL(38,0) conversion not implemented in DuckDB/dbt | raw hex and exact decimal text preserved; fixed-precision numeric limitation documented |
| Medium | Tether Treasury label provenance/version missing | externally sourced label assumption으로 문서화 |
| Medium | Airflow UI/default credentials are local demo settings | production security control이 아니라는 점을 문서화했습니다. |
| Medium | dbt/DuckDB local generated artifacts can be stale | `.gitignore` exclusion and validation evidence separation |

## Sequential Implementation Plan to Deadline

마감 시한은 2026-06-22 월요일 23:59 KST로 둡니다. 아래 순서는 새 기능 확장보다 제출 리스크를 낮추는 순서입니다.

| 순서 | 목표 시점 | 작업 | 완료 기준 |
|---:|---|---|---|
| 1 | 2026-06-19 | 중간 커밋 생성 | README, readiness report, ignore, 구현 scaffold, fixture tests가 하나의 checkpoint로 커밋됨 |
| 2 | 2026-06-20 | Docker 재빌드 검증 | `workspace-dev build`, `pytest`, `ruff`, `dbt parse/build` 결과를 `docs/05_validation_evidence.md`에 갱신 |
| 3 | 2026-06-20 | `eth_chainId` validation 추가 | RPC endpoint chain id mismatch를 ingestion 전 실패 처리하고 mock test 추가 |
| 4 | 2026-06-21 | `uint256` boundary test 추가 | 큰 `uint256`은 raw hex 보존, numeric null 또는 exact conversion 정책이 테스트로 고정됨 |
| 5 | 2026-06-21 | label provenance 문서/config 보강 | Tether Treasury-labelled address가 외부 라벨 가정이며 source/version/validity가 기록됨 |
| 6 | 2026-06-21 | collection scope 교정 | raw 수집 기본 scope가 `transfer_topic_all_addresses`로 코드/README/test에 일치 |
| 7 | 2026-06-22 | reorg 한계 최종 정리 | 구현된 finality/idempotency와 구현되지 않은 canonical replacement가 README/report에 일치합니다. |
| 8 | 2026-06-22 | 최종 제출 검증 | 실제 실행한 명령과 Airflow log/Delta/DuckDB evidence만 VERIFIED로 갱신하고, production에서 검증하지 않은 항목은 숨기지 않습니다. |
