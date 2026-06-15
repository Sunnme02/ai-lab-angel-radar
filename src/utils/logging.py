"""统一日志(loguru)。"""
import sys

from loguru import logger

_configured = False


def get_logger():
    global _configured
    if not _configured:
        logger.remove()
        logger.add(sys.stderr, level="INFO",
                   format="<green>{time:HH:mm:ss}</green> | <level>{level: <7}</level> | "
                          "<cyan>{name}</cyan> - {message}")
        _configured = True
    return logger
