"""Ethereum hourly log ingestion package for the CryptoQuant assignment."""

from cryptoquant_pipeline.chunking import MAX_BLOCKS_PER_LOG_REQUEST
from cryptoquant_pipeline.pipeline import run_interval

__all__ = ["MAX_BLOCKS_PER_LOG_REQUEST", "run_interval"]
