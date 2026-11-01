"""
api/logging_config.py
----------------------
Structured logging configuration for PrioMed-Rec.

In production: JSON format to logs/priomed-{date}.log + stderr
In development: human-readable format to stderr only

Usage:
    from api.logging_config import get_logger
    
    logger = get_logger(__name__)
    logger.info("patient_analyzed", patient_id="P001", priority="HIGH")
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime
from pathlib import Path


def setup_logging(log_dir: str = "logs", level: str = "INFO") -> None:
    """Configure logging for the application."""
    log_level = getattr(logging, level.upper(), logging.INFO)
    
    # Create logs directory
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    
    # Format
    is_production = os.getenv("ENVIRONMENT", "development").lower() == "production"
    
    if is_production:
        # JSON format for production
        formatter = logging.Formatter(
            '{"timestamp": "%(asctime)s", "level": "%(levelname)s", '
            '"module": "%(name)s", "message": "%(message)s"}',
            datefmt="%Y-%m-%dT%H:%M:%S"
        )
        # File handler
        log_file = Path(log_dir) / f"priomed-{datetime.now().strftime('%Y-%m-%d')}.log"
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        file_handler.setLevel(log_level)
        logging.root.addHandler(file_handler)
    else:
        formatter = logging.Formatter(
            "[%(asctime)s] %(levelname)s %(name)s — %(message)s",
            datefmt="%H:%M:%S"
        )
    
    # Always log to stderr
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(formatter)
    stderr_handler.setLevel(log_level)
    
    logging.root.setLevel(log_level)
    logging.root.addHandler(stderr_handler)


def get_logger(name: str) -> logging.Logger:
    """Get a named logger."""
    return logging.getLogger(name)
