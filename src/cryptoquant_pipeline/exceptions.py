"""Typed exception hierarchy for retry and data-contract decisions."""

from __future__ import annotations

from dataclasses import dataclass


class PipelineError(Exception):
    """패키지 내부에서 의도적으로 발생시키는 최상위 예외."""


class ConfigError(PipelineError, ValueError):
    """환경 변수 또는 실행 설정이 데이터 계약과 맞지 않을 때 발생."""


class BlockRangeError(PipelineError):
    """UTC interval을 안전한 block range로 바꿀 수 없을 때 발생."""


class RetryableIntervalNotFinalized(PipelineError):
    """finalized head가 Airflow interval end까지 도달하지 않아 retry가 필요함."""


class LogCollectionError(PipelineError):
    """eth_getLogs 수집 구간이 단일 블록까지 분할된 뒤에도 실패함."""

    def __init__(self, message: str, *, failed_range: tuple[int, int] | None = None) -> None:
        super().__init__(message)
        self.failed_range = failed_range


class NormalizationError(PipelineError):
    """RPC raw log를 raw Delta schema row로 변환할 수 없음."""


class DeltaWriteError(PipelineError):
    """Delta table schema, dependency, write 과정에서 발생한 실패."""


class DataQualityError(PipelineError):
    """수집·적재·분석 결과가 품질 계약을 만족하지 못할 때 발생."""


class DbtBuildError(PipelineError):
    """dbt build subprocess가 실패함."""


@dataclass(frozen=True)
class RpcErrorDetail:
    """Provider 오류를 retry 정책과 함께 보존하는 값 객체."""

    method: str
    message: str
    retryable: bool
    code: int | None = None
    http_status: int | None = None


class RpcError(PipelineError):
    """JSON-RPC 오류 base class. 메시지에 endpoint나 key를 포함하지 않음."""

    def __init__(self, detail: RpcErrorDetail) -> None:
        super().__init__(detail.message)
        self.detail = detail


class RetryableRpcError(RpcError):
    """HTTP 429, 5xx, timeout 등 재시도 가치가 있는 RPC 실패."""


class NonRetryableRpcError(RpcError):
    """인증 오류, 잘못된 요청, payload shape 오류 같은 deterministic 실패."""


class RpcRateLimitError(RetryableRpcError):
    """Provider rate limit 또는 throttle 실패."""


class RpcTimeoutError(RetryableRpcError):
    """HTTP timeout 또는 provider timeout 실패."""


class RpcRangeTooLargeError(RetryableRpcError):
    """Provider가 block range 제한으로 요청을 거부함."""


class RpcTooManyResultsError(RetryableRpcError):
    """Provider가 응답 크기 또는 결과 수 제한으로 요청을 거부함."""
