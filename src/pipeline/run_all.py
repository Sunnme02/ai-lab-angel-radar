"""跑全部 seed labs：python -m src.pipeline.run_all [--config configs/settings.yaml]"""
import argparse

from ..config import Config
from ..utils.logging import get_logger
from .core import Context, finalize, process_lab

log = get_logger()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=None)
    ap.add_argument("--limit-labs", type=int, default=None, help="只跑前 N 个 lab(调试)")
    ap.add_argument("--seeds", nargs="+", default=None,
                    help="seed 文件路径(可多个,合并;默认手写+csrankings)")
    ap.add_argument("--no-github", action="store_true",
                    help="跳过 GitHub 采集(只跑学术层,快很多;工程信号可二次补)")
    a = ap.parse_args()

    cfg = Config(a.config)
    ctx = Context(cfg)
    if a.no_github:
        ctx.gh.enabled = False
        log.info("--no-github:本轮跳过 GitHub 采集(学术层先行)")
    seeds = cfg.load_seeds_merged(a.seeds)

    labs = []
    for school in seeds["schools"]:
        for lab in school["labs"]:
            labs.append((school["name"], lab))
    if a.limit_labs:
        labs = labs[:a.limit_labs]

    log.info(f"开始采集 {len(labs)} 个 seed lab")
    for school, lab in labs:
        try:
            process_lab(ctx, school, lab)
        except Exception as e:  # noqa: BLE001 单 lab 失败不阻塞整体
            log.error(f"lab 失败 {school}/{lab['pi_name']}: {e}")

    log.info("评分 + 图谱 + 导出…")
    summary = finalize(ctx)
    log.info(f"完成。导出: {summary}")


if __name__ == "__main__":
    main()
