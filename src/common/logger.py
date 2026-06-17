"""结构化日志。"""

import logging
import sys
from pathlib import Path

from src.common.config import settings


def get_logger(name: str) -> logging.Logger:
    """获取统一格式的 logger。"""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(settings.get("logging.level", "INFO"))

    fmt = settings.get("logging.format", "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
    formatter = logging.Formatter(fmt)

    # 控制台输出
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    logger.addHandler(console)

    # 文件输出
    log_file = settings.get("logging.file")
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger
