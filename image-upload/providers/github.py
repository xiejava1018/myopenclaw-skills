"""GitHub 图床上传 provider。用 Contents API PUT 单文件，requests 在 upload() 内懒导入。"""
import base64

from . import Uploader, UploadResult, join_url


class GithubUploader(Uploader):
    """GitHub 仓库上传器：把图片提交到指定分支，经 raw / 自定义域名访问。"""
    backend_name = "github"

    def upload(self, local_path: str, key: str) -> UploadResult:
        # 懒导入：未装 requests 也不影响其它后端加载
        import requests

        cfg = self.config
        owner, repo, branch, token = cfg.gh_owner, cfg.gh_repo, cfg.gh_branch, cfg.gh_token

        # Contents API：PUT 单文件
        api_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{key}"
        headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github+json"}

        # 二进制读 → base64（GitHub 要求 ASCII 字符串）
        with open(local_path, "rb") as f:
            content_b64 = base64.b64encode(f.read()).decode("ascii")
        body = {"message": f"upload {key}", "content": content_b64, "branch": branch}

        resp = requests.put(api_url, headers=headers, json=body)
        resp.raise_for_status()  # 非 2xx 抛 HTTPError

        # 访问域名：未配置则用 raw.githubusercontent.com 兜底
        domain = cfg.gh_domain or f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}"
        url = join_url(domain, key)

        # 提交 sha（结构缺失时空串兜底）
        sha = resp.json().get("content", {}).get("sha", "")
        return UploadResult(backend="github", key=key, url=url, extra={"commit_sha": sha})
