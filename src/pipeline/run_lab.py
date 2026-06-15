"""跑单个 PI：
    python -m src.pipeline.run_lab --pi "Xipeng Qiu" --school "Fudan University" --keywords "LLM,PEFT,LoRA"
"""
import argparse

from ..config import Config
from ..utils.logging import get_logger
from .core import Context, finalize, process_lab

log = get_logger()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pi", required=True)
    ap.add_argument("--school", required=True)
    ap.add_argument("--pi-cn", default=None)
    ap.add_argument("--homepage", default=None)
    ap.add_argument("--keywords", default="", help="逗号分隔")
    ap.add_argument("--config", default=None)
    a = ap.parse_args()

    cfg = Config(a.config)
    ctx = Context(cfg)
    lab_seed = {
        "pi_name": a.pi, "pi_name_cn": a.pi_cn, "homepage_url": a.homepage,
        "keywords": [k.strip() for k in a.keywords.split(",") if k.strip()],
    }
    process_lab(ctx, a.school, lab_seed)
    summary = finalize(ctx)
    log.info(f"完成。导出: {summary}")


if __name__ == "__main__":
    main()
