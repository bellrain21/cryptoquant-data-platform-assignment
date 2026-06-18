# 문서 목차(Document Table of Contents)

> 본 디렉터리는 과제 1과 과제 2의 상세 설계 및 구현 근거를 관리합니다.  
> 저장소 최상단 `README.md`는 Repository(저장소) 진입점이며, `docs/README.md`는 전체 문서 지도, 각 과제 하위 디렉터리의 `README.md`는 과제별 진입점 역할을 담당합니다.

## 문서 탐색 구조(Document Navigation)

```text
README.md
└── docs/
    ├── README.md
    ├── 04_ai_usage_and_validation.md
    ├── task_01_bitcoin_velocity/
    │   ├── README.md
    │   ├── 01_metric_definition.md
    │   ├── 02_daily_batch_pipeline.md
    │   └── 03_reorg_quality_limitations.md
    └── task_02_ethereum_log_pipeline/
        ├── README.md
        ├── 01_pipeline_design.md
        ├── 02_delta_lake_ingestion.md
        └── 03_dbt_modeling.md
```

## 과제 1. Bitcoin Network Velocity(비트코인 네트워크 회전율)

| 순서 | 문서 | 범위 | 상태 |
|---:|---|---|---|
| 0 | [README.md](./task_01_bitcoin_velocity/README.md) | 과제 1 전체 목차, 문서 읽는 순서, 설계 범위 | 작성 중 |
| 1 | [01_metric_definition.md](./task_01_bitcoin_velocity/01_metric_definition.md) | 지표 정의, 원천 데이터 필드, 공급량 정책, 계산식, SQL 또는 의사코드, 더미 출력, 결과 테이블 | 작성 중 |
| 2 | [02_daily_batch_pipeline.md](./task_01_bitcoin_velocity/02_daily_batch_pipeline.md) | Daily Batch(일 단위 배치), Airflow, Spark SQL, Delta Lake, 품질 검증, 멱등성, Backfill(과거 구간 재처리) | 예정 |
| 3 | [03_reorg_quality_limitations.md](./task_01_bitcoin_velocity/03_reorg_quality_limitations.md) | Chain Reorganization(Reorg, 체인 재편성), Confirmation Policy(확인 깊이 기반 신뢰도 정책), 재계산 범위, 한계점, 확장 방향 | 예정 |

## 과제 2. Ethereum Log Ingestion(이더리움 로그 수집)

| 순서 | 문서 | 범위 | 상태 |
|---:|---|---|---|
| 0 | [README.md](./task_02_ethereum_log_pipeline/README.md) | 과제 2 전체 목차, 문서 읽는 순서, 구현 범위 | 예정 |
| 1 | [01_pipeline_design.md](./task_02_ethereum_log_pipeline/01_pipeline_design.md) | RPC 수집 범위, Block Range(블록 범위) 계산, Airflow DAG, Retry(재시도), Backfill(과거 구간 재처리) | 예정 |
| 2 | [02_delta_lake_ingestion.md](./task_02_ethereum_log_pipeline/02_delta_lake_ingestion.md) | Delta Lake 스키마, Incremental Append(증분 적재), 논리 키(Logical Key), 멱등성(Idempotency) | 예정 |
| 3 | [03_dbt_modeling.md](./task_02_ethereum_log_pipeline/03_dbt_modeling.md) | ERC-20 Transfer, Tether Treasury Flow, Incremental Model(증분 모델), dbt Test(데이터 검증) | 예정 |

## 공통 문서(Common Documentation)

| 문서 | 범위 | 상태 |
|---|---|---|

## 문서 작성 규칙(Document Convention)

- 원천 사실(Source Fact), 정책 결정(Policy Decision), 구현 가정(Implementation Assumption)을 구분합니다.
- 공개 제품 정의(Product Reference)와 과제 전용 지표 정의(Assignment-specific Metric Definition)를 동일한 값으로 주장하지 않습니다.
- 완료되지 않은 기능과 검증하지 않은 실행 결과는 완료로 표기하지 않습니다.
- 외부 문서에 없는 구현 세부는 사실이 아니라 설계 선택으로 명시합니다.
- 원천 테이블의 실제 스키마가 과제에서 제공되지 않은 경우, 필요한 필드는 명시적 가정으로 기록합니다.
- AI 활용 목적, 대표 프롬프트, 검증 방식과 최종 판단은 저장소 최상단 `README.md`, 공통 AI 문서, 최종 보고서(PDF)에 일관되게 기록합니다.
