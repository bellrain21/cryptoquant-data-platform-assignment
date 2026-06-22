# 13. 실행 증거 스냅샷 해석 기준

> 기준일: 2026-06-23 KST
> 목적: 서로 다른 시점의 실행 기록과 누적 수치를 같은 시점의 결과로 해석하지 않도록 기준을 정리합니다.

## 증거 우선순위

1. Airflow task log: 특정 logical interval의 task state와 dbt 실행 결과를 확인합니다.
2. Delta metadata 및 natural key 점검: raw table의 schema, 누적 row 수, 중복 여부를 확인합니다.
3. 동일 입력의 dbt build 결과: 해당 fixture 또는 지정 window의 모델과 test 통과 여부를 확인합니다.
4. Notebook output: 지정된 로컬 산출물에 대한 보조 검증 결과입니다.
5. Airflow UI screenshot: DAG 등록과 실행 이력을 보여주는 시각적 보조 증거입니다.

## 누적 수치 규칙

- 문서와 Notebook에 기록된 row count는 각 기록이 생성된 시점의 값입니다.
- 재실행 또는 추가 scheduled run 뒤에는 누적 row count가 달라질 수 있습니다.
- 기준 시각이 다른 수치는 현재 총량으로 비교하지 않고 historical evidence로만 사용합니다.
- 수치를 새로 기록할 때는 관측 시점, artifact 경로, logical interval 또는 실행 명령을 함께 남깁니다.

## 현재 경계

| 항목 | 상태 | 해석 |
|---|---|---|
| 실행 증거의 관측 시점과 우선순위 | VERIFIED | 이 문서에서 해석 기준을 고정합니다 |
| 저장된 DuckDB view의 환경별 경로 이식성 | PARTIALLY VERIFIED | 현재 환경에서 dbt build로 재생성한 결과가 있어야 검증 완료로 올릴 수 있습니다 |
| Notebook 04가 감지한 UTC hourly gap의 해소 | NOT VERIFIED | 재수집, task log, Delta 결과, dbt build 결과가 함께 확인되기 전까지 열린 항목으로 둡니다 |

DuckDB는 Delta raw를 기반으로 생성한 로컬 분석 산출물입니다. raw landing 증거는 Delta metadata와 직접 점검 결과를 우선하고, DuckDB view는 재생성 가능한 보조 산출물로 해석합니다.