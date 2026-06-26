"""图床 key（对象路径）命名：日期桶 / post-slug 桶 + 文件名净化。"""
import os
import re
from datetime import datetime

# 连续空白（含中文全角空格 U+3000，Python3 的 \s 默认覆盖 Unicode 空白）
_WS = re.compile(r"\s+")
# 非 URL 安全字符：保留 字母数字 . _ - 和基本汉字，其余（空格/()?#&+% 等）一律去掉
_UNSAFE = re.compile(r"[^A-Za-z0-9._\-一-鿿]")
# 折叠多余连字符
_MULTI_DASH = re.compile(r"-{2,}")


def sanitize_filename(name: str) -> str:
    """净化文件名/分段：空白→"-"，去掉 URL 不安全字符，折叠多余"-"。

    例：
      "Pasted image 20260626094343.png" → "Pasted-image-20260626094343.png"
      "foo  bar (1).png"                → "foo-bar-1.png"
      "图 1.png"                         → "图-1.png"  （中文保留）
    """
    name = _WS.sub("-", str(name).strip())
    name = _UNSAFE.sub("", name)
    name = _MULTI_DASH.sub("-", name)
    return name.strip("-") or "file"


def make_key(prefix: str, local_path: str, post_slug: str | None = None) -> str:
    """生成图床上的对象 key（文件名与 post_slug 均经净化，URL 永远安全）。

    - 有 post_slug：{prefix}/{post_slug}/{filename}  （migrate 用，一篇文章聚一目录）
    - 无 post_slug：{prefix}/{YYYYMMDD}/{filename}   （upload 用，按日期分桶）
    """
    filename = sanitize_filename(os.path.basename(local_path))
    prefix = (prefix or "").strip("/")
    if post_slug:
        slug = sanitize_filename(post_slug)
        return f"{prefix}/{slug}/{filename}"
    date = datetime.now().strftime("%Y%m%d")
    return f"{prefix}/{date}/{filename}"
