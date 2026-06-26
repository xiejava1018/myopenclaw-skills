"""图床 key（对象路径）命名：日期桶 / post-slug 桶。"""
import os
from datetime import datetime


def make_key(prefix: str, local_path: str, post_slug: str | None = None) -> str:
    """生成图床上的对象 key。

    - 有 post_slug：{prefix}/{post_slug}/{filename}  （migrate 用，一篇文章聚一目录）
    - 无 post_slug：{prefix}/{YYYYMMDD}/{filename}   （upload 用，按日期分桶）
    """
    filename = os.path.basename(local_path)
    prefix = (prefix or "").strip("/")
    if post_slug:
        return f"{prefix}/{post_slug}/{filename}"
    date = datetime.now().strftime("%Y%m%d")
    return f"{prefix}/{date}/{filename}"
