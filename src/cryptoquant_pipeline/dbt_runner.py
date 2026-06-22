"""dbt subprocess runner for the hourly Ethereum pipeline."""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from cryptoquant_pipeline.config import PipelineSettings
from cryptoquant_pipeline.exceptions import DbtBuildError

LOGGER = logging.getLogger(__name__)

DBT_BUILD_TIMEOUT_SECONDS = 900
DBT_LOG_TAIL_LINES = 80


def run_dbt_build(
    settings: PipelineSettings,
    window_start_utc: datetime,
    window_end_utc: datetime,
) -> Mapping[str, Any]:
    """Airflow window vars로 dbt `tag:ethereum_hourly` graph를 실행함.

    불변: DAG는 개별 dbt 모델명을 알지 않음. selector와 ref graph가 실행 순서를 정함.
    실패: SQL/schema test 오류는 DbtBuildError로 전파해 Airflow task를 실패 처리함.
    """
    vars_payload = {
        "window_start": _utc_isoformat(window_start_utc),
        "window_end": _utc_isoformat(window_end_utc),
    }

    command = [
        settings.dbt_bin,
        "build",
        "--project-dir",
        str(settings.dbt_project_dir),
        "--profiles-dir",
        str(settings.dbt_profiles_dir),
        "--select",
        "tag:ethereum_hourly",
        "--vars",
        json.dumps(vars_payload),
    ]

    env = os.environ.copy()
    env["DELTA_LOGS_PATH"] = str(settings.delta_logs_path)
    env["DUCKDB_PATH"] = str(settings.duckdb_path)

    LOGGER.info(
        "Running dbt build: project_dir=%s profiles_dir=%s "
        "selector=tag:ethereum_hourly delta_logs_path=%s duckdb_path=%s "
        "window_start=%s window_end=%s",
        settings.dbt_project_dir,
        settings.dbt_profiles_dir,
        settings.delta_logs_path,
        settings.duckdb_path,
        vars_payload["window_start"],
        vars_payload["window_end"],
    )

    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            env=env,
            timeout=DBT_BUILD_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        stdout_tail = _safe_log_tail(exc.stdout, env)
        stderr_tail = _safe_log_tail(exc.stderr, env)

        LOGGER.error(
            "dbt build timed out after %s seconds.\nstdout_tail:\n%s\nstderr_tail:\n%s",
            DBT_BUILD_TIMEOUT_SECONDS,
            stdout_tail,
            stderr_tail,
        )

        raise DbtBuildError(
            f"dbt build timed out after {DBT_BUILD_TIMEOUT_SECONDS} seconds."
        ) from exc

    except OSError as exc:
        LOGGER.error(
            "dbt build process could not start: dbt_bin=%s error=%s",
            settings.dbt_bin,
            exc,
        )
        raise DbtBuildError(f"dbt build process could not start: {exc}") from exc

    if result.returncode != 0:
        stdout_tail = _safe_log_tail(result.stdout, env)
        stderr_tail = _safe_log_tail(result.stderr, env)

        LOGGER.error(
            "dbt build failed: returncode=%s\nstdout_tail:\n%s\nstderr_tail:\n%s",
            result.returncode,
            stdout_tail,
            stderr_tail,
        )

        raise DbtBuildError(f"dbt build failed with exit code {result.returncode}.")

    return {
        "returncode": result.returncode,
        "vars": vars_payload,
    }


def _utc_isoformat(value: datetime) -> str:
    """dbt var에 넣을 재현 가능한 UTC ISO-8601 문자열 생성함."""
    if value.tzinfo is None:
        raise ValueError("Datetime value must include timezone information.")

    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _safe_log_tail(
    output: str | bytes | None,
    env: Mapping[str, str],
) -> str:
    """dbt 로그 끝부분만 남기고 알려진 secret 값은 마스킹함."""
    if output is None:
        return ""

    text = output.decode("utf-8", errors="replace") if isinstance(output, bytes) else output
    tail = "\n".join(text.splitlines()[-DBT_LOG_TAIL_LINES:])

    secret_values = [
        value
        for key, value in env.items()
        if value
        and any(
            token in key.lower()
            for token in (
                "api_key",
                "apikey",
                "token",
                "password",
                "secret",
                "rpc_url",
            )
        )
    ]

    for secret in secret_values:
        tail = tail.replace(secret, "***")

    return re.sub(
        r"([?&](?:api[_-]?key|token|password|secret)=)[^&\s]+",
        r"\1***",
        tail,
        flags=re.IGNORECASE,
    )
