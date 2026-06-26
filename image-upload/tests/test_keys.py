"""keys.py 单测：key 命名 + 文件名净化。"""
from datetime import datetime
from keys import make_key, sanitize_filename


# ---------- sanitize_filename ----------
def test_sanitize_replaces_spaces_with_dash():
    assert sanitize_filename("Pasted image 20260626094343.png") == "Pasted-image-20260626094343.png"


def test_sanitize_collapses_multiple_spaces():
    assert sanitize_filename("foo  bar.png") == "foo-bar.png"


def test_sanitize_removes_parens():
    assert sanitize_filename("foo (1).png") == "foo-1.png"


def test_sanitize_keeps_chinese():
    # 中文保留，空格变 -
    assert sanitize_filename("图 1.png") == "图-1.png"
    assert sanitize_filename("架构 图 v2.png") == "架构-图-v2.png"


def test_sanitize_strips_unsafe_url_chars():
    assert sanitize_filename("a?b#c&d+e%.png") == "abcde.png"


def test_sanitize_empty_fallback():
    assert sanitize_filename("") == "file"
    assert sanitize_filename("   ") == "file"
    assert sanitize_filename("()") == "file"


def test_sanitize_keeps_extension_and_case():
    assert sanitize_filename("Scheme_Writer-arch.PNG") == "Scheme_Writer-arch.PNG"


# ---------- make_key ----------
def test_make_key_with_post_slug():
    key = make_key("blog", "/abs/path/Foo Bar.png", post_slug="my-post")
    assert key == "blog/my-post/Foo-Bar.png"


def test_make_key_post_slug_also_sanitized():
    key = make_key("images", "/x/Pasted image 1.png", post_slug="2026 我 的文章")
    assert key == "images/2026-我-的文章/Pasted-image-1.png"


def test_make_key_date_bucket_when_no_slug():
    key = make_key("blog", "/abs/path/foo.png")
    date = datetime.now().strftime("%Y%m%d")
    assert key == f"blog/{date}/foo.png"


def test_make_key_strips_prefix_slashes():
    key = make_key("/blog/", "/abs/path/foo.png", post_slug="p")
    assert key == "blog/p/foo.png"


def test_make_key_real_obsidian_paste_name():
    # 回归：Obsidian 粘贴命名不应再产生带空格的 URL
    key = make_key("images", "/vault/Pasted image 20260626094343.png")
    assert " " not in key
    assert key.endswith("/Pasted-image-20260626094343.png")
