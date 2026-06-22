# 12~14. Chain Reorganization, 한계점, 확장 방향(Reorg, Limitations, and Extensions)

> **문서 상태(Status)**: 설계 문서 정리 완료
> **문서 역할(Role)**: Reorg로 인한 지표 영향·재계산 범위를 정의하고, V1의 한계와 확장 방향을 명시한다.

## 12. Chain Reorganization 대응 설계(Chain Reorganization Handling)

## 12.1 Reorg가 Velocity에 미치는 영향

Reorg는 기존에 선택된 Best Chain 일부가 다른 branch로 교체되는 상황이다. 이 경우 다음 값이 변할 수 있다.

```text
분자 영향
- 교체된 block의 transaction과 output이 달라짐
- affected date의 daily gross output volume이 변경됨
- 해당 날짜를 포함하는 이후 rolling window 결과가 변경됨

분모 영향
- UTXO 생성·소비 lifecycle이 달라짐
- affected date 이후의 day-end UTXO supply가 계속 달라질 수 있음
```

따라서 Reorg 영향은 단지 최근 하루의 분자만 다시 계산하는 문제가 아니다.

## 12.2 Best Chain 기준 처리

이 설계에서 `best_chain`은 특정 `observed_at` 시점에 파이프라인이 선택한 체인 경로다.

```text
best_chain
≠ 영구적으로 변하지 않는 canonical truth

best_chain
= 관측 시점과 chain_revision_id를 가진 체인 스냅샷
```

기존 branch와 해당 revision으로 계산된 metric observation을 즉시 물리 삭제하지 않는다. 다만 현재 소비자용 Gold 결과는 최신 Best Chain 기준 confirmed 결과만 유지하고, 기존 branch와 `superseded_by_reorg` 상태는 audit history에 보존한다.

## 12.3 Reorg 감지(Detection)

저장된 checkpoint와 현재 체인 상태를 비교한다.

```text
stored_block_hash(height)
!=
current_best_chain_block_hash(height)
```

불일치가 발생하면 현재 tip에서 `previous_block_hash`를 역추적해 가장 최근 공통 조상(Common Ancestor)을 찾는다.

## 12.4 영향 범위 재계산(Affected-range Recalculation)

```text
1. common ancestor height 탐색
2. affected_start_date 결정
   = common ancestor 다음 block이 속한 UTC 날짜
3. 기존 branch와 기존 metric observation을 audit history에 `superseded_by_reorg`로 기록
4. 대체 branch를 새로운 `chain_revision_id`로 저장하고 그 revision 기준 lifecycle을 재구성
5. affected_start_date부터 latest confirmed metric date까지
   daily volume 및 day-end supply component 재생성
6. velocity 계산을 위해 affected_start_date - 364일부터
   입력 date spine을 다시 읽음
7. affected_start_date부터 latest confirmed metric date까지
   current Gold metric을 staging 후 MERGE
8. audit log와 chain checkpoint를 갱신
```

후행 365일 분자의 변경은 일반적으로 최대 364일 이후 지표에 직접 영향을 준다. 그러나 분모인 UTXO 공급량은 fork 시점 이후의 날짜 전체에 영향을 줄 수 있으므로, 안전한 기본 복구 범위는 **affected start date부터 최신 confirmed metric date까지**다.

## 12.5 최근 구간 Reconciliation(정합성 재검증)

Reorg 감지와 별도로 최근 N개 블록 또는 최근 N일을 주기적으로 다시 대조한다.

```text
recent_reconciliation_window
= 운영 편의상 설정하는 점검 범위

reorg_recovery_range
= 실제 common ancestor 이후 재계산해야 하는 범위
```

둘은 같은 개념이 아니다. 최근 재검증 창은 감지 효율을 위한 운영 정책이고, 실제 복구 범위는 Reorg가 확인된 체인 상태에서 결정한다.

## 13. 한계점(Limitations)

## 13.1 Gross On-chain Output Volume의 과대계산 가능성

V1 분자는 Change Output과 Self-churn을 제거하지 않는다. 따라서 경제적 실질 이전량보다 크게 관측될 수 있다.

## 13.2 Policy-eligible UTXO Supply의 정책 의존성

이 분모는 프로토콜 표준의 유일한 circulating supply가 아니라, V1 정책상 포함 가능한 UTXO의 합이다. burn 분류, maturity, dormant threshold 변경은 수치를 바꾼다.

## 13.3 Dormant 기준의 불확실성

장기 미사용은 영구 분실을 증명하지 않는다. dormant threshold는 유동성 민감도 분석을 위한 정책이며, 해석 시 버전과 기준을 반드시 함께 표시해야 한다.

## 13.4 Block Header Timestamp의 한계

`metric_date`는 UTC 기준 block header timestamp를 사용한 보고 규칙이다. 이 값은 각 거래가 실제로 발생한 정확한 wall-clock time을 보장하지 않는다.

## 13.5 원천 `utxo` 테이블의 이력 보장 여부

현재 상태만 가진 UTXO 테이블로는 과거 day-end supply를 복원할 수 없다. historical snapshot 또는 `tx_input`·`tx_output` 기반 lifecycle 재구성이 필요하다.

## 13.6 온체인 지표 단독 해석의 한계

Velocity는 가격 방향, 매수·매도, 거래소 흐름, 특정 기관 활동을 직접 확정하지 않는다. 이 해석에는 entity label, exchange flow, 가격·유동성, 외부 이벤트가 추가로 필요하다.

## 14. 향후 확장 방향(Future Extensions)

## 14.1 Change Output Heuristic

주소 재사용, output 구조, 입력 소유 패턴 등을 기반으로 change output을 추정해 V1 gross flow와 분리된 `estimated_economic_transfer_volume` 계열을 추가할 수 있다. 단, 휴리스틱 규칙·오류율·버전은 별도로 관리해야 한다.

## 14.2 Entity Label과 내부 이동 제거

주소 군집화와 entity label을 별도 차원 테이블로 관리하면 거래소·채굴자·기관 내부 이동을 분리한 지표를 만들 수 있다. 이 단계부터는 라벨 출처·신뢰도·유효기간이 필수 메타데이터다.

## 14.3 Versioned Burn Registry

외부 검증을 거친 burn address 또는 script registry를 별도로 도입할 수 있다.

```text
필수 메타데이터
- address_or_script
- classification_source
- confidence
- valid_from
- valid_to
- registry_version
```

## 14.4 오프체인 해석 레이어

상장 상태, 입출금 중단, 유동성, 시장 가격을 기본 온체인 지표와 분리해 결합한다. 기본 지표의 재현성을 유지하면서 해석력을 높이는 방식이다.

## 14.5 다중 자산 지표 템플릿

자산별 UTXO 모델과 account model의 차이를 고려해 공통 운영 원칙만 재사용한다.

```text
공통
- source fact / policy / assumption 분리
- versioning
- quality gate
- backfill
- reorg 또는 chain-state recovery

자산별 별도 정의
- transfer volume
- supply
- account 또는 UTXO lifecycle
- token metadata
```

## 참고 자료(References)

- Bitcoin Developer Documentation — Block Chain: https://developer.bitcoin.org/devguide/block_chain.html
- Bitcoin Developer Documentation — Transactions: https://developer.bitcoin.org/examples/transactions.html
