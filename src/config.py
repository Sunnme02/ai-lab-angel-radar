"""配置:读取 .env + settings.yaml + labs_seed.yaml,管理 API key。"""
import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent


class Config:
    def __init__(self, settings_path: str = None):
        load_dotenv(ROOT / ".env")
        settings_path = settings_path or (ROOT / "configs" / "settings.yaml")
        with open(settings_path, encoding="utf-8") as f:
            self.settings = yaml.safe_load(f)

        # API keys（均可为空：第一版 LLM 非必须，无 GitHub token 则跳过 GitHub 采集）
        self.openalex_email = os.getenv("OPENALEX_EMAIL", "")
        self.s2_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY", "")
        self.github_token = os.getenv("GITHUB_TOKEN", "")
        self.openai_key = os.getenv("OPENAI_API_KEY", "")
        self.anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")

    # 便捷取值
    @property
    def year_from(self):
        return self.settings.get("year_from", 2023)

    @property
    def year_to(self):
        return self.settings.get("year_to", 2026)

    @property
    def keywords(self):
        return self.settings.get("keywords", [])

    @property
    def db_path(self):
        return str(ROOT / self.settings["database"]["path"])

    @property
    def exports_dir(self):
        d = ROOT / self.settings["paths"]["exports"]
        d.mkdir(parents=True, exist_ok=True)
        return str(d)

    @property
    def openalex_cache_dir(self):
        return str(ROOT / self.settings["paths"].get("openalex_cache", "data/raw/openalex_cache"))

    @property
    def max_papers_per_lab(self):
        return self.settings.get("max_papers_per_lab", 60)

    @property
    def max_repos_per_author(self):
        return self.settings.get("max_repos_per_author", 5)

    @property
    def max_students_per_lab(self):
        return self.settings.get("max_student_candidates_per_lab", 20)

    @property
    def http(self):
        return self.settings.get("http", {"timeout": 25, "retries": 4, "rate_limit_per_sec": 5})

    def load_seeds(self):
        with open(ROOT / self.settings["paths"]["seeds"], encoding="utf-8") as f:
            return yaml.safe_load(f)

    def load_seeds_merged(self, paths=None):
        """合并多个 seed(默认:手写 seeds + 可选 seeds_extra)。手写优先。"""
        from .pipeline.seed_merge import merge_seeds
        if paths is None:
            paths = [self.settings["paths"]["seeds"]]
            extra = self.settings["paths"].get("seeds_extra")
            if extra and (ROOT / extra).exists():
                paths.append(extra)
        loaded = []
        for p in paths:
            fp = p if os.path.isabs(p) else (ROOT / p)
            if os.path.exists(fp):
                with open(fp, encoding="utf-8") as f:
                    loaded.append(yaml.safe_load(f))
        return merge_seeds(*loaded)

    @property
    def has_github(self):
        return bool(self.github_token)
