"""HTTP 工具:限速 + 超时 + 重试。所有 collector 共用。"""
import time

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from .logging import get_logger

log = get_logger()
_last_call = {}


def throttle(key: str, per_sec: float = 5.0):
    """同一 key 的调用按 per_sec 限速。"""
    min_gap = 1.0 / max(per_sec, 0.1)
    now = time.time()
    last = _last_call.get(key, 0)
    wait = min_gap - (now - last)
    if wait > 0:
        time.sleep(wait)
    _last_call[key] = time.time()


@retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=1, min=2, max=30),
       reraise=True)
def get_json(url, key="default", per_sec=5.0, timeout=25, headers=None, params=None):
    """限速 + 重试地取 JSON。失败抛异常(由调用方决定是否吞掉)。"""
    throttle(key, per_sec)
    r = requests.get(url, headers=headers, params=params, timeout=timeout)
    if r.status_code == 429:
        log.warning(f"429 限流 {url[:80]} → 退避重试")
        raise requests.HTTPError("429")
    r.raise_for_status()
    return r.json()


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=20),
       reraise=True)
def get_text(url, key="web", per_sec=3.0, timeout=25, headers=None):
    throttle(key, per_sec)
    h = {"User-Agent": "Mozilla/5.0 ai-lab-angel-radar/0.1"}
    if headers:
        h.update(headers)
    r = requests.get(url, headers=h, timeout=timeout)
    r.raise_for_status()
    return r.text
