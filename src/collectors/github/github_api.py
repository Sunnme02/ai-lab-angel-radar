"""GitHub 采集器:定位某人的 GitHub 账号(主页直链优先,其次搜用户+profile核名)→ 列其 repo。

需 GITHUB_TOKEN(免费 PAT);无 token 时 pipeline 自动跳过。
"""
import base64
import re

from rapidfuzz import fuzz

from ...utils.logging import get_logger
from ...utils.rate_limit import get_json

log = get_logger()
API = "https://api.github.com"


def logins_from_links(github_links):
    """从主页里的 github.com 链接解析用户名(过滤掉常见非用户路径)。"""
    out = []
    bad = {"orgs", "topics", "search", "about", "features", "marketplace", "sponsors"}
    for url in github_links or []:
        m = re.search(r"github\.com/([A-Za-z0-9-]+)", url)
        if m and m.group(1).lower() not in bad:
            out.append(m.group(1))
    return list(dict.fromkeys(out))


class GitHubCollector:
    def __init__(self, token: str = ""):
        self.token = token
        self.enabled = bool(token)
        self.headers = {"Accept": "application/vnd.github+json"}
        if token:
            self.headers["Authorization"] = f"Bearer {token}"

    def _ps(self):
        return 5.0 if self.token else 0.3

    def get_user(self, login):
        try:
            return get_json(f"{API}/users/{login}", key="github", per_sec=self._ps(),
                            headers=self.headers)
        except Exception:  # noqa: BLE001
            return None

    def find_user(self, name, hints=""):
        """搜用户并用 profile 的 name/bio/company 核身份。返回 (login, confidence) 或 (None,0)。

        confidence:profile name 高度匹配 → 0.8;name 匹配 + hint 命中 → 0.75;仅弱匹配 → <0.6。
        """
        try:
            d = get_json(f"{API}/search/users", key="github", per_sec=self._ps(),
                         headers=self.headers, params={"q": name, "per_page": 8})
        except Exception as e:  # noqa: BLE001
            log.debug(f"GitHub 搜用户失败 {name}: {e}")
            return None, 0.0
        best, best_conf = None, 0.0
        for item in d.get("items", [])[:8]:
            u = self.get_user(item["login"])
            if not u:
                continue
            uname = u.get("name") or ""
            blob = " ".join(str(x) for x in [u.get("bio"), u.get("company"), u.get("blog")] if x).lower()
            name_score = fuzz.WRatio(name.lower(), uname.lower()) if uname else 0
            hint_hit = bool(hints) and any(h.strip().lower() in blob
                                           for h in hints.split(",") if len(h.strip()) > 2)
            if name_score >= 88:
                conf = 0.8 + (0.1 if hint_hit else 0)
            elif name_score >= 75 and hint_hit:
                conf = 0.7
            elif name_score >= 70:
                conf = 0.55
            else:
                conf = 0.0
            if conf > best_conf:
                best, best_conf = item["login"], conf
        return best, round(min(best_conf, 0.95), 2)

    def list_user_repos(self, login, keywords=(), limit=5):
        """列某用户的 repo(按 stars 降序),优先含关键词的;否则取 stars 最高。"""
        try:
            repos = get_json(f"{API}/users/{login}/repos", key="github", per_sec=self._ps(),
                             headers=self.headers,
                             params={"sort": "pushed", "per_page": 30, "type": "owner"})
        except Exception:  # noqa: BLE001
            return []
        parsed = [self._parse_repo(r) for r in repos if not r.get("fork")]
        parsed.sort(key=lambda x: x["stars"], reverse=True)
        kws = [k.lower() for k in keywords]

        def relevant(r):
            blob = f"{r['repo_name']} {r.get('description') or ''} {r.get('topics') or ''}".lower()
            return any(k in blob for k in kws)
        rel = [r for r in parsed if relevant(r)]
        chosen = rel[:limit] if rel else parsed[:limit]
        return chosen

    def get_readme(self, owner, repo):
        try:
            d = get_json(f"{API}/repos/{owner}/{repo}/readme", key="github",
                         per_sec=self._ps(), headers=self.headers)
            if d.get("encoding") == "base64" and d.get("content"):
                return base64.b64decode(d["content"]).decode("utf-8", "ignore")[:8000]
        except Exception:  # noqa: BLE001
            pass
        return ""

    def _parse_repo(self, r):
        return {
            "repo_name": r.get("name"), "owner": (r.get("owner") or {}).get("login"),
            "url": r.get("html_url"), "description": r.get("description"),
            "stars": r.get("stargazers_count", 0), "forks": r.get("forks_count", 0),
            "watchers": r.get("watchers_count", 0), "open_issues": r.get("open_issues_count", 0),
            "last_commit_at": r.get("pushed_at"), "created_at_github": r.get("created_at"),
            "topics": ",".join(r.get("topics", []) or []), "language": r.get("language"),
            "homepage": r.get("homepage"),
        }
