"""解析与改写 Markdown 图片链接（纯逻辑，无 IO/网络）。

识别三种图片引用形态：
- Obsidian: ``![[x.png]]`` / ``![[x.png|说明]]`` / ``![[x.png|500]]``
- 标准 md: ``![alt](./p/x.png)`` / ``![alt](p/x.png "标题")``
- URL: ``![alt](http://...)`` （已是 URL，main 会跳过不改写）

笔记双链 ``![[某笔记]]``（括号内无图片扩展名）不当作图片，不返回。
"""
import re
from dataclasses import dataclass
from pathlib import Path

# 支持的图片扩展名（小写，匹配时对 target 统一转小写判断）
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp", ".avif"}

# Obsidian 图片嵌入：![[ ... ]]，内部可有 |alt 或 |500
_OBS_RE = re.compile(r"!\[\[([^\[\]]+?)\]\]")
# 标准 md 图片：![alt](target "title")，target 与 title 均可选
# 用普通字符串以兼容 title 段里的双引号
_MD_RE = re.compile(r'!\[([^\]]*)\]\(([^)\s]+)(?:\s+"([^"]*)")?\)')


@dataclass
class ImageRef:
    raw_text: str       # md 里精确匹配到的子串（用于定位/替换）
    is_url: bool        # True = 已是 http(s) URL（main 会跳过）
    alt: str            # alt 文本
    title: str          # title 文本（可能为空）
    start: int          # 在 md_text 中的起始 offset
    end: int            # 结束 offset
    target: str         # 目标：obsidian 文件名 / md 路径串 / URL
    kind: str           # "obsidian" | "md" | "url"


def _is_image_target(name: str) -> bool:
    """按扩展名判断 target 是否为图片文件名/路径。"""
    return Path(name).suffix.lower() in IMAGE_EXTS


def _is_url(s: str) -> bool:
    return s.startswith("http://") or s.startswith("https://")


def find_image_links(md_text: str) -> list[ImageRef]:
    """扫描 md_text，按出现顺序返回所有图片引用。

    排除规则：Obsidian 形态但 target 无图片扩展名（笔记双链）、纯文本 ``[[...]]``
    （无 ``!`` 前缀）均不返回。URL 形态一律返回且 is_url=True。
    """
    # 先收集所有候选匹配及其 span，再按 start 合并排序、去重叠。
    # 两个正则在 ``!`` 处可能各自命中，靠 span 去重保证每个 offset 只取一次。
    spans: list[tuple[int, int, ImageRef]] = []

    for m in _OBS_RE.finditer(md_text):
        inner = m.group(1)
        # 形如 "x.png|说明" 或 "x.png|500" 或 "x.png"
        if "|" in inner:
            target, _, rest = inner.partition("|")
            target = target.strip()
            # 纯数字 resize（如 500）丢弃，不进 alt
            alt = "" if rest.strip().isdigit() else rest.strip()
        else:
            target = inner.strip()
            alt = ""
        if not target or not _is_image_target(target):
            continue  # 笔记双链（无图片扩展名），跳过
        ref = ImageRef(
            raw_text=m.group(0),
            is_url=False,
            alt=alt,
            title="",
            start=m.start(),
            end=m.end(),
            target=target,
            kind="obsidian",
        )
        spans.append((m.start(), m.end(), ref))

    for m in _MD_RE.finditer(md_text):
        alt = m.group(1)
        target = m.group(2)
        title = m.group(3) or ""
        if _is_url(target):
            kind, is_url = "url", True
        elif _is_image_target(target):
            kind, is_url = "md", False
        else:
            continue  # md 链接但非图片扩展名，不当图片
        ref = ImageRef(
            raw_text=m.group(0),
            is_url=is_url,
            alt=alt,
            title=title,
            start=m.start(),
            end=m.end(),
            target=target,
            kind=kind,
        )
        spans.append((m.start(), m.end(), ref))

    # 按 start 升序、end 降序排序；用 occupied 区间去重叠
    spans.sort(key=lambda t: (t[0], -t[1]))
    occupied: list[tuple[int, int]] = []
    refs: list[ImageRef] = []
    for start, end, ref in spans:
        if any(not (end <= s or start >= e) for s, e in occupied):
            continue  # 与已采纳区间重叠，丢弃（避免 ![[ 被错误二次切分）
        occupied.append((start, end))
        refs.append(ref)
    # spans 已按 start 升序构造，refs 即按出现顺序
    return refs


def resolve_local_path(ref, source_dir: Path, vault_roots: list) -> Path | None:
    """把图片引用解析为本地文件 Path，找不到返回 None。

    - ref.is_url：直接返回 None（main 不会对 url ref 调本函数，稳妥起见也兜底）。
    - obsidian（target 为文件名）：依次查 source_dir → assets/ → assets/blog/
      → 每个 vault_root → vault_root/assets → vault_root/assets/blog → rglob 兜底。
    - md（target 为相对路径）：相对 source_dir 解析；存在则返回。
    """
    if ref.is_url:
        return None

    if ref.kind == "obsidian":
        name = ref.target
        # 候选目录优先级：文章同目录、assets、assets/blog，以及各 vault_root 的同序列
        candidates: list[Path] = [
            source_dir / name,
            source_dir / "assets" / name,
            source_dir / "assets" / "blog" / name,
        ]
        for vr in vault_roots:
            vr = Path(vr)
            candidates += [
                vr / name,
                vr / "assets" / name,
                vr / "assets" / "blog" / name,
            ]
        for c in candidates:
            if c.is_file():
                return c
        # rglob 兜底：在全 vault 下按文件名找第一个命中
        for vr in vault_roots:
            vr = Path(vr)
            if vr.is_dir():
                try:
                    for hit in vr.rglob(name):
                        if hit.is_file():
                            return hit
                except (OSError, PermissionError):
                    continue
        return None

    if ref.kind == "md":
        # 相对文章目录解析；target 本身可能是相对路径或绝对路径
        p = (source_dir / ref.target) if not Path(ref.target).is_absolute() else Path(ref.target)
        return p if p.is_file() else None

    return None


def build_replacement(ref, url: str) -> str:
    """构造单个图片引用的改写文本（标准 md 形态）。

    - 有 title：``![{alt}]({url} "{title}")``
    - 无 title：``![{alt}]({url})``（alt 为空则 ``![](...)``）
    """
    if ref.title:
        return f'![{ref.alt}]({url} "{ref.title}")'
    return f"![{ref.alt}]({url})"


def apply_replacements(md_text: str, plan: list) -> str:
    """按 plan（[(ImageRef, url), ...]）改写 md_text。

    从后往前（按 ref.start 降序）替换，避免前面的替换让后面 offset 错位。
    用切片拼接，不用 str.replace（同一 raw_text 多次出现会误伤）。
    """
    if not plan:
        return md_text
    # 按 start 降序处理；同一 plan 内不同 ref 一般不重叠
    ordered = sorted(plan, key=lambda pair: pair[0].start, reverse=True)
    buf = md_text
    for ref, url in ordered:
        repl = build_replacement(ref, url)
        buf = buf[: ref.start] + repl + buf[ref.end:]
    return buf
