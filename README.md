# CryptoQuant Data Platform Assignment

본 Repository는 CryptoQuant Data Platform Engineer 사전과제 제출용입니다.

본 과제는 Bitcoin Velocity 지표 파이프라인 설계와 Ethereum 로그 수집 파이프라인 구현을 중심으로 구성합니다.  
현재 문서는 과제 1인 Bitcoin Velocity 지표 파이프라인 설계 초안을 우선 작성합니다.

## 문서 구성
# 과제 1. Bitcoin Velocity 지표 파이프라인 설계

## 목차

1. 과제 이해 및 설계 방향
2. Bitcoin Velocity 지표 개요
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

---

## 1. 과제 이해 및 설계 방향

본 과제는 Bitcoin Velocity(비트코인 네트워크 회전율 지표)의 단순 계산값을 산출하는 것보다, 해당 지표를 Daily Metric(일 단위 지표)으로 안정적으로 생산하고 운영할 수 있는 Data Pipeline Design(데이터 파이프라인 설계) 능력을 확인하는 데 목적이 있다.

과제에서 제시된 Network Velocity(네트워크 회전율)는 Transaction Volume(거래 이동량)을 Circulating Supply(유통 공급량)로 나눈 값으로 정의된다.

```text
Network Velocity = Transaction Volume / Circulating Supply
```

즉, Bitcoin(비트코인)이 특정 기간 동안 전체 유통 공급량 대비 얼마나 활발하게 이동했는지를 나타내는 On-chain Metric(온체인 지표)이다. 여기서 Velocity(회전율)는 물리적 의미의 속도가 아니라, 유통 공급량 대비 거래 이동량의 비율을 나타내는 회전율 개념으로 해석한다.

본 설계는 Bitcoin On-chain Raw Data(비트코인 온체인 원천 데이터)가 `block`, `tx`, `tx_input`, `tx_output`, `utxo` 형태의 Delta Lake Table(델타 레이크 테이블)로 존재한다는 전제를 기준으로 한다. 전체 Raw Schema(원천 스키마)를 재정의하지 않고, Velocity(회전율 지표) 산출에 필요한 Field(필드)만 선별하여 계산 기준과 선택 근거를 명확히 작성한다.

설계의 핵심 질문은 Transaction Volume(거래 이동량)을 어떤 기준으로 정의할 것인가, Circulating Supply(유통 공급량)를 어떤 기준으로 산정할 것인가, Daily Batch Pipeline(일 단위 배치 파이프라인)에서 지표를 어떻게 안정적으로 생산할 것인가, Chain Reorganization, Reorg(체인 재편성)가 발생했을 때 이미 산출된 지표를 어떻게 보정할 것인가이다.

특히 Circulating Supply(유통 공급량)는 단일 기준으로 처리하기 어렵다. Burned Supply(소각 공급량)와 Dormant UTXO(장기 비활성 UTXO)는 모두 현재 유통량 해석에 영향을 주지만, 경제적 의미는 다르다. Burned Supply(소각 공급량)는 구조적으로 재유통 가능성이 낮으므로 Circulating Supply(유통 공급량)에서 제외할 수 있다. 반면 Dormant UTXO(장기 비활성 UTXO)는 현재 이동하지 않았을 뿐, 향후 다시 이동할 수 있는 Latent Supply(잠재 공급량)이다.

따라서 본 설계에서는 Circulating Supply(유통 공급량)를 단일 값으로만 산정하지 않고, Gross Circulating Supply(총 유통 공급량), Adjusted Circulating Supply(조정 유통 공급량), Dormant Reactivated Supply(재활성화된 장기 비활성 공급량)로 분리한다. `gross_circulating_supply_btc`는 Burned Supply(소각 공급량)를 제외한 기본 유통 공급량으로 정의한다. `adjusted_circulating_supply_btc`는 Gross Circulating Supply(총 유통 공급량)에서 Dormant UTXO(장기 비활성 UTXO)를 제외한 조정 유통 공급량으로 정의한다. `dormant_reactivated_supply_btc`는 장기 비활성 상태였던 UTXO가 다시 이동한 물량으로 정의한다.

본 설계에서 Velocity(회전율 지표)는 단일 수치가 아니라, 공급량 정의에 따른 해석 차이를 추적할 수 있는 지표 체계로 구성한다. `velocity_gross`는 `transaction_volume_btc`를 `gross_circulating_supply_btc`로 나눈 값으로 산출한다. `velocity_adjusted`는 `transaction_volume_btc`를 `adjusted_circulating_supply_btc`로 나눈 값으로 산출한다. 이를 통해 Burned Supply(소각 공급량), Dormant Supply(장기 비활성 공급량), Dormant Reactivated Supply(재활성화된 장기 비활성 공급량)를 구분할 수 있으며, 단순한 지표 계산을 넘어 지표 해석의 한계와 운영상 추적 가능성을 함께 확보한다.

또한 Bitcoin Network(비트코인 네트워크)에서는 드물지만 Chain Reorganization, Reorg(체인 재편성)가 발생할 수 있다. Reorg(체인 재편성)가 발생하면 기존에 유효하다고 판단했던 Block(블록)이 무효화되고 다른 Block(블록)으로 대체될 수 있으므로, 해당 Block(블록)에 포함된 Transaction(거래)과 Output(거래 출력)을 기준으로 계산한 Transaction Volume(거래 이동량)이 달라질 수 있다. 따라서 본 설계는 Canonical Block(정식 체인에 포함된 블록) 기준 계산, Confirmation Depth(확정 블록 깊이) 적용, Recent Range Recalculation(최근 구간 반복 재계산), Affected Range Overwrite(영향 구간 재작성) 전략을 포함한다.

본 과제의 기본 범위는 On-chain Data(온체인 데이터) 기반 Velocity(회전율 지표) 산출이다. Listing Status(상장 상태), Trading Suspension(거래 일시중지), Deposit and Withdrawal Suspension(입출금 중단), Liquidity Risk(유동성 리스크)와 같은 Off-chain Metadata(오프체인 메타데이터)는 기본 계산에 포함하지 않는다. 다만 Multi-Asset Metric System(다중 자산 지표 체계)으로 확장할 경우에는 이러한 Off-chain Metadata(오프체인 메타데이터)를 별도 레이어로 분리하고, On-chain Metric(온체인 지표)과 조합한 Composite Interpretation Metric(종합 해석 지표)으로 확장할 수 있다.

정리하면 본 설계는 On-chain Raw Table(온체인 원천 테이블)에서 Required Field(필요 필드)를 선별하고, Transaction Volume(거래 이동량)과 Circulating Supply(유통 공급량)의 산정 정책을 정의한 뒤, Gross, Adjusted, Dormant 지표를 분리하여 Daily Batch Pipeline(일 단위 배치 파이프라인)으로 생산하는 구조를 목표로 한다. 또한 Data Quality Check(데이터 품질 검증), Idempotency(멱등성), Reorg(체인 재편성) 대응 전략을 포함하여 Bitcoin Velocity(비트코인 네트워크 회전율 지표)를 운영 가능한 Data Product(운영 지표 산출물)로 생산하는 것을 목표로 한다.
