"""Run the notebook-equivalent Ethereum RPC smoke validation without printing secrets."""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

from cryptoquant_pipeline.block_range import (
    block_timestamp_from_payload,
    resolve_interval_block_range,
)
from cryptoquant_pipeline.chunking import iter_block_chunks
from cryptoquant_pipeline.config import TETHER_TREASURY_ADDRESS, PipelineSettings
from cryptoquant_pipeline.delta_writer import (
    count_duplicate_natural_keys,
    count_rows,
    write_ethereum_logs_insert_only,
)
from cryptoquant_pipeline.log_collector import collect_raw_logs
from cryptoquant_pipeline.log_normalizer import (
    decode_uint256_decimal,
    is_erc20_transfer_topic,
    normalize_logs,
    topic_to_address,
)
from cryptoquant_pipeline.rpc_client import EthereumJsonRpcClient


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", help="UTC ISO start. Default: last complete hour minus 24h.")
    parser.add_argument("--end", help="UTC ISO end. Default: start + 1h.")
    parser.add_argument("--delta-root", type=Path, default=Path("data/tmp/rpc_smoke_validation"))
    args = parser.parse_args()

    _load_env()
    settings = PipelineSettings.from_env()
    interval_start, interval_end = _interval(args.start, args.end)

    with EthereumJsonRpcClient(
        settings.provider,
        timeout_seconds=settings.rpc_timeout_seconds,
        max_retries=settings.rpc_max_retries,
        requests_per_second=settings.rpc_requests_per_second,
    ) as client:
        chain_id = client.eth_chain_id()
        finalized = client.eth_get_finalized_block()
        resolved = resolve_interval_block_range(
            client,
            interval_start_utc=interval_start,
            interval_end_utc=interval_end,
        )
        chunks = iter_block_chunks(resolved.from_block, resolved.to_block)
        raw_logs = collect_raw_logs(
            client,
            from_block=resolved.from_block,
            to_block=resolved.to_block,
            collection_scope=settings.collection_scope,
        )
        block_numbers = sorted({int(log["blockNumber"], 16) for log in raw_logs})
        block_timestamps = {
            number: block_timestamp_from_payload(client.eth_get_block_by_number(number))
            for number in block_numbers
        }

    transfer_logs = [
        log
        for log in raw_logs
        if log.get("topics") and is_erc20_transfer_topic(str(log["topics"][0]))
    ]
    sample = _decode_transfer_sample(transfer_logs[0]) if transfer_logs else None
    treasury_sample_count = _count_treasury_samples(transfer_logs)

    normalized = normalize_logs(
        raw_logs,
        block_timestamps_utc=block_timestamps,
        chain_id=settings.chain_id,
        interval_start_utc=interval_start,
        interval_end_utc=interval_end,
    )

    root = args.delta_root.resolve()
    if "rpc_smoke_validation" not in root.parts:
        raise SystemExit("Refusing to remove a path outside rpc_smoke_validation.")
    shutil.rmtree(root, ignore_errors=True)
    first = write_ethereum_logs_insert_only(normalized.rows, table_path=root / "ethereum_logs")
    first_count = count_rows(root / "ethereum_logs")
    second = write_ethereum_logs_insert_only(normalized.rows, table_path=root / "ethereum_logs")
    second_count = count_rows(root / "ethereum_logs")

    print(
        {
            "env": {
                "ETH_RPC_URL_configured": True,
                "auth_mode": settings.provider.auth_mode,
                "chain_id_expected": settings.chain_id,
                "collection_scope_id": settings.collection_scope.scope_id,
                "collection_scope_fingerprint": settings.collection_scope.fingerprint,
            },
            "rpc": {
                "eth_chainId": chain_id,
                "chain_id_ok": chain_id == settings.chain_id,
                "finalized_block_number": int(str(finalized["number"]), 16),
                "finalized_block_timestamp_utc": block_timestamp_from_payload(
                    finalized
                ).isoformat(),
            },
            "range": {
                "interval_start_utc": interval_start.isoformat(),
                "interval_end_utc": interval_end.isoformat(),
                "from_block": resolved.from_block,
                "to_block": resolved.to_block,
                "chunk_count": len(chunks),
                "max_chunk_size": max(chunk.block_count for chunk in chunks),
            },
            "logs": {
                "raw_log_count": len(raw_logs),
                "unique_event_key_count": len(
                    {
                        (settings.chain_id, log.get("transactionHash"), log.get("logIndex"))
                        for log in raw_logs
                    }
                ),
                "transfer_log_count": len(transfer_logs),
                "decoded_transfer_sample": sample,
                "treasury_sample_count": treasury_sample_count,
            },
            "delta_idempotency": {
                "first_inserted_row_count": first.inserted_row_count,
                "first_row_count": first_count,
                "second_inserted_row_count": second.inserted_row_count,
                "second_row_count": second_count,
                "row_count_stable": first_count == second_count,
                "duplicate_natural_key_count": count_duplicate_natural_keys(
                    root / "ethereum_logs"
                ),
            },
        }
    )


def _load_env() -> None:
    root = Path.cwd()
    load_dotenv(root / ".env", override=False)
    if not os.environ.get("ETH_RPC_URL"):
        load_dotenv(root / "src" / ".env", override=True)


def _interval(start: str | None, end: str | None) -> tuple[datetime, datetime]:
    if start:
        interval_start = _parse_utc(start)
    else:
        current_hour = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
        interval_start = current_hour - timedelta(hours=24)
    interval_end = _parse_utc(end) if end else interval_start + timedelta(hours=1)
    return interval_start, interval_end


def _parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("interval datetime must be timezone-aware UTC.")
    return parsed.astimezone(UTC)


def _decode_transfer_sample(log: object) -> dict[str, str | None]:
    if not isinstance(log, dict):
        return {}
    topics = log.get("topics", [])
    if not isinstance(topics, list):
        return {}
    return {
        "from_address": topic_to_address(topics[1]) if len(topics) > 1 else None,
        "to_address": topic_to_address(topics[2]) if len(topics) > 2 else None,
        "raw_amount": str(decode_uint256_decimal(str(log["data"]))) if log.get("data") else None,
    }


def _count_treasury_samples(logs: list[object]) -> int:
    treasury = TETHER_TREASURY_ADDRESS.lower()
    count = 0
    for log in logs:
        if not isinstance(log, dict):
            continue
        topics = log.get("topics", [])
        if not isinstance(topics, list) or len(topics) <= 2:
            continue
        addresses = {topic_to_address(topics[1]), topic_to_address(topics[2])}
        if treasury in addresses:
            count += 1
    return count


if __name__ == "__main__":
    main()
    # deltalake/pyarrow native teardown can abort after successful output in this
    # one-shot smoke script. Exceptions still propagate before this point.
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)
