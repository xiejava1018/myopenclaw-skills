"""rewriter.py 单测：图片链接解析、路径解析、改写（纯逻辑，无网络）。"""
from pathlib import Path

from rewriter import (
    IMAGE_EXTS,
    ImageRef,
    apply_replacements,
    build_replacement,
    find_image_links,
    resolve_local_path,
)


# ---------------------------------------------------------------------------
# 解析：各形态
# ---------------------------------------------------------------------------
def test_obsidian_plain():
    # ![[x.png]] → obsidian, alt 空, target=x.png
    refs = find_image_links("看这张 ![[x.png]] 图。")
    assert len(refs) == 1
    r = refs[0]
    assert r.kind == "obsidian"
    assert r.target == "x.png"
    assert r.alt == ""
    assert r.title == ""
    assert r.is_url is False
    assert r.raw_text == "![[x.png]]"
    assert md_slice("看这张 ![[x.png]] 图。", r) == "![[x.png]]"


def test_obsidian_with_alt():
    # ![[x.png|说明]] → alt="说明"
    refs = find_image_links("![[cover.png|封面图]]")
    assert refs[0].alt == "封面图"
    assert refs[0].target == "cover.png"


def test_obsidian_numeric_resize_dropped():
    # ![[x.png|500]] → 纯数字 resize 丢弃，alt=""
    refs = find_image_links("![[x.png|500]]")
    assert refs[0].alt == ""
    assert refs[0].target == "x.png"


def test_md_relative_no_title():
    # ![alt](./p/x.png) → kind=md, target="./p/x.png", alt="alt"
    refs = find_image_links("![alt](./p/x.png)")
    r = refs[0]
    assert r.kind == "md"
    assert r.target == "./p/x.png"
    assert r.alt == "alt"
    assert r.title == ""
    assert r.is_url is False


def test_md_with_title():
    # ![alt](p/x.png "标题") → target="p/x.png", title="标题"
    refs = find_image_links('![alt](p/x.png "标题")')
    r = refs[0]
    assert r.target == "p/x.png"
    assert r.alt == "alt"
    assert r.title == "标题"


def test_url_link_is_url():
    # ![alt](http://…) / ![](https://…) → kind=url, is_url=True
    for raw in ("![alt](http://a.com/b.png)", "![](https://cdn/x.jpg)"):
        refs = find_image_links(raw)
        assert len(refs) == 1
        assert refs[0].kind == "url"
        assert refs[0].is_url is True


# ---------------------------------------------------------------------------
# 排除规则
# ---------------------------------------------------------------------------
def test_note_wikilink_excluded():
    # ![[某笔记]] 无图片扩展名 → 视为笔记双链，不返回
    refs = find_image_links("这是一篇 ![[我的笔记]] 笔记。")
    assert refs == []


def test_plain_wikilink_no_bang_excluded():
    # 普通文本里的 [[...]]（无 ! 前缀）不是图片
    refs = find_image_links("见 [[某笔记]] 与 [[x.png]]")
    assert refs == []


def test_md_non_image_link_excluded():
    # md 链接但目标无图片扩展名，不当图片（如指向 .md 文件）
    refs = find_image_links("[text](other.md)")
    assert refs == []


def test_image_exts_constant():
    assert ".avif" in IMAGE_EXTS
    assert ".png" in IMAGE_EXTS


# ---------------------------------------------------------------------------
# 混合多链接
# ---------------------------------------------------------------------------
def test_mixed_multiple_links_in_order():
    md = (
        "首图 ![[a.png]]，中图 ![中](./p/b.jpg \"t\")，"
        "URL ![](https://c.com/c.png)，"
        "笔记 ![[note]] 跳过，尾 ![[d.gif|动图]]"
    )
    refs = find_image_links(md)
    kinds = [r.kind for r in refs]
    targets = [r.target for r in refs]
    assert kinds == ["obsidian", "md", "url", "obsidian"]
    assert targets == ["a.png", "./p/b.jpg", "https://c.com/c.png", "d.gif"]
    assert refs[0].start < refs[1].start < refs[2].start < refs[3].start
    # 每个 raw_text 都能精确切回原文
    for r in refs:
        assert md_slice(md, r) == r.raw_text


def test_offsets_non_overlapping():
    md = "![[a.png]]![[b.png]]"
    refs = find_image_links(md)
    assert len(refs) == 2
    assert refs[0].end <= refs[1].start


# ---------------------------------------------------------------------------
# build_replacement
# ---------------------------------------------------------------------------
def test_build_replacement_with_title():
    ref = ImageRef("![](x.png)", True, "alt", "标题", 0, 9, "x.png", "md")
    assert build_replacement(ref, "http://u/x.png") == '![alt](http://u/x.png "标题")'


def test_build_replacement_no_title_empty_alt():
    ref = ImageRef("![](x.png)", False, "", "", 0, 9, "x.png", "obsidian")
    assert build_replacement(ref, "http://u/x.png") == "![](http://u/x.png)"


# ---------------------------------------------------------------------------
# apply_replacements
# ---------------------------------------------------------------------------
def test_apply_replacements_multiple_keeps_offsets():
    md = "前 ![[a.png]] 中 ![b](b.jpg) 后"
    refs = {r.target: r for r in find_image_links(md) if r.kind in ("obsidian", "md")}
    plan = [
        (refs["a.png"], "http://u/a.png"),
        (refs["b.jpg"], "http://u/b.jpg"),
    ]
    out = apply_replacements(md, plan)
    assert out == "前 ![](http://u/a.png) 中 ![b](http://u/b.jpg) 后"


def test_apply_replacements_duplicate_raw_text_not_misapplied():
    # 同一 raw_text 出现两次，只改 plan 里指定的那个 offset
    md = "![[a.png]] 重复 ![[a.png]]"
    refs = find_image_links(md)
    assert len(refs) == 2
    # 只改第二个
    plan = [(refs[1], "http://u/a.png")]
    out = apply_replacements(md, plan)
    assert out == "![[a.png]] 重复 ![](http://u/a.png)"


def test_apply_replacements_preserves_title():
    md = '![b](b.jpg "t")'
    ref = find_image_links(md)[0]
    out = apply_replacements(md, [(ref, "http://u/b.jpg")])
    assert out == '![b](http://u/b.jpg "t")'


def test_apply_replacements_empty_plan_unchanged():
    md = "![[a.png]]"
    assert apply_replacements(md, []) == md


# ---------------------------------------------------------------------------
# resolve_local_path
# ---------------------------------------------------------------------------
def test_resolve_obsidian_in_assets_blog(tmp_path):
    # Arrange: assets/blog/x.png 存在
    (tmp_path / "assets" / "blog").mkdir(parents=True)
    f = tmp_path / "assets" / "blog" / "x.png"
    f.write_text("img")
    ref = ImageRef("![[x.png]]", False, "", "", 0, 9, "x.png", "obsidian")
    # Act
    p = resolve_local_path(ref, tmp_path, [tmp_path])
    # Assert
    assert p == f


def test_resolve_obsidian_in_source_dir(tmp_path):
    f = tmp_path / "cover.jpg"
    f.write_text("img")
    ref = ImageRef("![[cover.jpg]]", False, "", "", 0, 13, "cover.jpg", "obsidian")
    assert resolve_local_path(ref, tmp_path, []) == f


def test_resolve_obsidian_rglob_fallback(tmp_path):
    # 候选目录都没有，靠 rglob 在 vault 深处命中
    deep = tmp_path / "notes" / "sub"
    deep.mkdir(parents=True)
    f = deep / "deep.png"
    f.write_text("img")
    ref = ImageRef("![[deep.png]]", False, "", "", 0, 13, "deep.png", "obsidian")
    assert resolve_local_path(ref, tmp_path, [tmp_path]) == f


def test_resolve_md_relative(tmp_path):
    f = tmp_path / "p" / "x.png"
    f.parent.mkdir(parents=True)
    f.write_text("img")
    ref = ImageRef("![](p/x.png)", False, "", "", 0, 12, "p/x.png", "md")
    assert resolve_local_path(ref, tmp_path, []) == f


def test_resolve_url_returns_none(tmp_path):
    ref = ImageRef("![](http://a/b.png)", True, "", "", 0, 18, "http://a/b.png", "url")
    assert resolve_local_path(ref, tmp_path, []) is None


def test_resolve_missing_returns_none(tmp_path):
    ref = ImageRef("![[nope.png]]", False, "", "", 0, 12, "nope.png", "obsidian")
    assert resolve_local_path(ref, tmp_path, []) is None


# ---------------------------------------------------------------------------
# 辅助
# ---------------------------------------------------------------------------
def md_slice(md: str, ref: ImageRef) -> str:
    """按 start/end 切片，验证 raw_text 与 offset 一致。"""
    return md[ref.start: ref.end]
