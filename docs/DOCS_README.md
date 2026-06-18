# 문서 목차(Document Table of Contents)

> 이 디렉터리는 CryptoQuant 데이터 플랫폼 사전 과제의 상세 설계와 구현 근거를 관리합니다.  
> 저장소 최상단 `README.md`는 저장소 진입점이고, 이 문서는 전체 문서 지도이며, 각 과제 하위 디렉터리의 `TASK_XX_README.md`는 과제별 진입점입니다.

## 문서 탐색 구조(Document Navigation)

```text
docs/
├── DOCS_README.md
├── ai_usage_and_validation.md
├── task_01_bitcoin_velocity/
│   ├── TASK_01_README.md
│   ├── 01_understanding_and_design_direction.md
│   ├── 02_metric_definition.md
│   ├── 03_data_contract_and_calculation.md
│   ├── 04_daily_batch_pipeline.md
│   └── 05_quality_reorg_limitations.md
└── task_02_ethereum_log_pipeline/
    ├── TASK_02_README.md
    ├── 01_pipeline_design.md
    ├── 02_delta_lake_ingestion.md
    └── 03_dbt_modeling.md
```

## 과제 1. Bitcoin Velocity(비트코인 회전율) 지표 파이프라인 설계

| 순서 | 문서 | 범위 | 상태 |
|---:|---|---|---|
| 0 | [TASK_01_README.md](./task_01_bitcoin_velocity/TASK_01_README.md) | 전체 목차, 문서 읽는 순서, 지표 계약 요약 | 설계 문서 정리 완료 |
| 1 | [01_understanding_and_design_direction.md](./task_01_bitcoin_velocity/01_understanding_and_design_direction.md) | 과제 목적, 범위, 제품 참조와 과제 지표 분리, 설계 원칙 | 설계 문서 정리 완료 |
| 2 | [02_metric_definition.md](./task_01_bitcoin_velocity/02_metric_definition.md) | Velocity, 이동량, 공급량, 장기 비활성 UTXO, 해석 범위 | 설계 문서 정리 완료 |
| 3 | [03_data_contract_and_calculation.md](./task_01_bitcoin_velocity/03_data_contract_and_calculation.md) | 원천 필드, 파생 필드, 계산식, SQL 또는 의사코드, 더미 출력, 결과 테이블 | 설계 문서 정리 완료 |
| 4 | [04_daily_batch_pipeline.md](./task_01_bitcoin_velocity/04_daily_batch_pipeline.md) | Airflow, Spark SQL, Delta Lake, 품질 검증, 멱등성, Backfill(과거 구간 재처리) | 설계 문서 정리 완료 |
| 5 | [05_quality_reorg_limitations.md](./task_01_bitcoin_velocity/05_quality_reorg_limitations.md) | Reorg(체인 재편성), 재계산, 한계점, 확장 방향 | 설계 문서 정리 완료 |

## 과제 2. Ethereum Log Ingestion(이더리움 로그 수집) 파이프라인 구현

| 순서 | 문서 | 범위 | 상태 |
|---:|---|---|---|
| 0 | [TASK_02_README.md](./task_02_ethereum_log_pipeline/TASK_02_README.md) | 전체 목차, 구현 범위, 산출물 계약 | 설계 문서 정리 완료 / 구현 증거 대기 |
| 1 | [01_pipeline_design.md](./task_02_ethereum_log_pipeline/01_pipeline_design.md) | RPC 수집 범위, Block Range(블록 범위) 계산, Airflow DAG, Retry(재시도), Backfill, Reorg state | 설계 문서 정리 완료 / 구현 증거 대기 |
| 2 | [02_delta_lake_ingestion.md](./task_02_ethereum_log_pipeline/02_delta_lake_ingestion.md) | observation/canonical 스키마, 증분 적재, 키, 멱등성, 품질 규칙 | 설계 문서 정리 완료 / 구현 증거 대기 |
| 3 | [03_dbt_modeling.md](./task_02_ethereum_log_pipeline/03_dbt_modeling.md) | ERC-20 Transfer, `tether_treasury_flow`, netflow, Incremental Model, dbt Test | 설계 문서 정리 완료 / 구현 증거 대기 |

## 공통 문서(Common Documentation)

| 문서 | 범위 | 상태 |
|---|---|---|
| [ai_usage_and_validation.md](./ai_usage_and_validation.md) | AI 활용 원칙, 검증 기준, 주요 설계 판단 | 설계 문서 정리 완료 |

## 문서 작성 규칙(Document Convention)

- 원천 사실(Source Fact), 정책 결정(Policy Decision), 구현 가정(Implementation Assumption)을 구분합니다.
- 공개 제품 정의(Product Reference)와 과제 전용 정의(Assignment-specific Definition)를 동일한 계산값으로 주장하지 않습니다.
- 완료되지 않은 기능과 실행하지 않은 테스트는 완료로 표기하지 않습니다.
- 외부 문서에 없는 세부 구현은 사실이 아니라 설계 선택으로 명시합니다.
- 링크 대상 파일은 이 문서 구조에 실제 존재하는 파일만 사용합니다.
- 주요 기술·도메인 용어는 첫 등장에만 `English(한글)`로 병기하고 이후에는 한국어 또는 코드 식별자를 일관되게 사용합니다.
