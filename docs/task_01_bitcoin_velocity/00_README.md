## 문서 구성
# 과제 1. Bitcoin Velocity 지표 파이프라인 설계

## 목차

1. 과제 이해 및 설계 방향(Task Understanding and Design Direction)

2. Bitcoin Velocity 지표 개요(Bitcoin Velocity Metric Overview)
   - 2.1 Network Velocity 정의
   - 2.2 Transaction Volume 정의
   - 2.3 Circulating Supply 정의
   - 2.4 지표 해석 범위

3. 데이터 범위와 원천 테이블
   - 3.1 On-chain Data 범위
   - 3.2 사용 대상 Delta Lake Table
   - 3.3 Velocity 계산에 필요한 Field 명세
   - 3.4 Field 선택 근거

4. Circulating Supply 산정 정책
   - 4.1 Gross Circulating Supply 정의
   - 4.2 Burned Supply 제외 기준
   - 4.3 Adjusted Circulating Supply 정의
   - 4.4 Dormant UTXO 처리 기준
   - 4.5 Dormant UTXO 재활성화 추적

5. 계산 기간과 수식
   - 5.1 일 단위 계산 기준
   - 5.2 Transaction Volume 계산식
   - 5.3 Gross Circulating Supply 계산식
   - 5.4 Adjusted Circulating Supply 계산식
   - 5.5 Velocity Gross 및 Velocity Adjusted 계산식

6. SQL 또는 의사코드
   - 6.1 Canonical Block 필터링
   - 6.2 Non-Coinbase Transaction 필터링
   - 6.3 Daily Transaction Volume 계산
   - 6.4 Circulating Supply 계산
   - 6.5 Daily Bitcoin Velocity 산출

7. 더미 데이터 기반 출력 예시

8. 결과 테이블 설계
   - 8.1 daily_bitcoin_velocity 테이블
   - 8.2 주요 Column 정의
   - 8.3 calculation_version 관리
   - 8.4 block height range 추적

9. 일 단위 배치 파이프라인 설계
   - 9.1 전체 처리 흐름
   - 9.2 Airflow DAG 구조
   - 9.3 Spark SQL 처리 역할
   - 9.4 Delta Lake 저장 및 갱신 전략
   - 9.5 실패 재시도 및 알림 전략

10. 데이터 품질 검증
    - 10.1 값 범위 검증
    - 10.2 중복 검증
    - 10.3 블록 구간 누락 검증
    - 10.4 전일 대비 이상치 검증

11. 멱등성 및 재계산 전략
    - 11.1 metric_date 기준 재실행
    - 11.2 partition overwrite 전략
    - 11.3 calculation_version별 결과 분리

12. Chain Reorganization 대응 설계
    - 12.1 Reorg가 Velocity에 미치는 영향
    - 12.2 Canonical Block 기준 처리
    - 12.3 Confirmation Depth 적용
    - 12.4 affected block range 재계산
    - 12.5 최근 구간 반복 재계산 전략

13. 한계점
    - 13.1 tx_output 합계 방식의 과대계산 가능성
    - 13.2 Dormant UTXO 기준의 불확실성
    - 13.3 On-chain Metric 해석의 한계

14. 향후 확장 방향
    - 14.1 Change Output Heuristic 적용
    - 14.2 Gross / Adjusted / Dormant 지표 고도화
    - 14.3 Off-chain Metadata 분리
    - 14.4 다중 자산 종합지표계 확장
