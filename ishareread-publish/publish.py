#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
爱分享读书 — 一键发布工具

从飞书多维表格获取未发布文章 → 发布到 Hugo 网站 → 推送 GitHub → 回写飞书 → 发布微信公众号
"""

import os
import sys
import re
import json
import random
import argparse
import subprocess
from pathlib import Path
from datetime import datetime, timezone, timedelta
from urllib.parse import quote

try:
    import urllib.request
    import urllib.error
except ImportError:
    pass

# ===== 常量 =====

SKILL_DIR = Path(__file__).parent
ENV_FILE = SKILL_DIR / ".env"
ENV_EXAMPLE = SKILL_DIR / ".env.example"

REQUIRED_KEYS = [
    "FEISHU_APP_ID",
    "FEISHU_APP_SECRET",
    "FEISHU_APP_TOKEN",
    "FEISHU_TABLE_ID",
    "FEISHU_TOPIC_APP_TOKEN",
    "FEISHU_TOPIC_TABLE_ID",
    "COZE_API_TOKEN",
    "COZE_WORKFLOW_ID",
    "HUGO_SITE_DIR",
    "SITE_BASE_URL",
]

FEISHU_TOKEN_URL = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
FEISHU_RECORDS_URL = "https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records"
COZE_WORKFLOW_URL = "https://api.coze.cn/v1/workflow/stream_run"

CST = timezone(timedelta(hours=8))


# ===== 配置管理 =====


def get_input(prompt, default=""):
    """获取用户输入，支持默认值"""
    if default:
        prompt = f"{prompt} [{default}]: "
    else:
        prompt = f"{prompt}: "
    value = input(prompt).strip()
    return value if value else default


def mask_secret(value):
    """遮蔽敏感信息"""
    if len(value) <= 8:
        return "*" * len(value)
    return value[:4] + "****" + value[-4:]


def is_config_complete(config):
    """检查必填配置是否完整"""
    for key in ["FEISHU_APP_ID", "FEISHU_APP_SECRET", "COZE_API_TOKEN", "HUGO_SITE_DIR", "SITE_BASE_URL"]:
        val = config.get(key, "").strip()
        if not val or val.startswith("your_"):
            return False
    return True


def load_config():
    """加载配置：环境变量 > .env 文件"""
    config = {}

    # 加载 .env 文件
    if ENV_FILE.exists():
        with open(ENV_FILE, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip())

    for key in REQUIRED_KEYS:
        config[key] = os.environ.get(key, "")

    # 设置默认值
    config.setdefault("FEISHU_APP_TOKEN", "XsBnb6AOTafA8usGoIGc2faunUh")
    config.setdefault("FEISHU_TABLE_ID", "tblwHGCK9VwzORYR")
    config.setdefault("FEISHU_TOPIC_APP_TOKEN", "YjN6bWopMaYixSs1ArncqVBLn1c")
    config.setdefault("FEISHU_TOPIC_TABLE_ID", "tblspru4cgIMd5M3")
    config.setdefault("COZE_WORKFLOW_ID", "7475172960854458405")
    config.setdefault("HUGO_SITE_DIR", "/Users/xiejava/xiejavablog/myhugo/ishareread")
    config.setdefault("SITE_BASE_URL", "https://www.ishareread.com")

    return config


def test_feishu_connection(app_id, app_secret):
    """测试飞书连接"""
    try:
        token = get_feishu_token(app_id, app_secret)
        return token is not None
    except Exception:
        return False


def test_hugo_site(site_dir):
    """验证 Hugo 站点目录"""
    path = Path(site_dir)
    if not path.exists():
        return False, "目录不存在"
    if (path / "hugo.toml").exists() or (path / "config").exists():
        return True, "站点有效"
    return False, "未找到 Hugo 配置文件"


def interactive_config():
    """交互式配置初始化向导"""
    print()
    print("🔧 首次使用「爱分享读书发布」技能，开始配置初始化")
    print("=" * 60)
    print("请根据提示输入以下配置信息")
    print("按 Enter 可使用方括号中的默认值")
    print("=" * 60)

    config = {}

    # 飞书配置
    print()
    print("-" * 60)
    print("飞书多维表格配置")
    print("- 在飞书开放平台(https://open.feishu.cn)创建应用获取 App ID 和 App Secret")
    print("- 从多维表格 URL 中获取 App Token 和 Table ID")
    print("-" * 60)
    config["FEISHU_APP_ID"] = get_input("请输入飞书 App ID")
    config["FEISHU_APP_SECRET"] = get_input("请输入飞书 App Secret")
    config["FEISHU_APP_TOKEN"] = get_input("请输入飞书 App Token", "XsBnb6AOTafA8usGoIGc2faunUh")
    config["FEISHU_TABLE_ID"] = get_input("请输入飞书 Table ID", "tblwHGCK9VwzORYR")

    # Coze 配置
    print()
    print("-" * 60)
    print("Coze 微信公众号发布配置")
    print("- 在 Coze 平台(https://www.coze.cn)获取 API Token 和 Workflow ID")
    print("-" * 60)
    config["COZE_API_TOKEN"] = get_input("请输入 Coze API Token")
    config["COZE_WORKFLOW_ID"] = get_input("请输入 Coze Workflow ID", "7475172960854458405")

    # Hugo 配置
    print()
    print("-" * 60)
    print("Hugo 站点配置")
    print("-" * 60)
    config["HUGO_SITE_DIR"] = get_input(
        "请输入 Hugo 站点目录路径", "/Users/xiejava/xiejavablog/myhugo/ishareread"
    )
    config["SITE_BASE_URL"] = get_input("请输入网站域名", "https://www.ishareread.com")

    # 验证
    print()
    print("🔍 正在测试飞书连接...", end=" ")
    if test_feishu_connection(config["FEISHU_APP_ID"], config["FEISHU_APP_SECRET"]):
        print("✅ 连接成功")
    else:
        print("⚠️  连接失败，请检查 App ID 和 App Secret")

    print("🔍 正在验证 Hugo 站点...", end=" ")
    ok, msg = test_hugo_site(config["HUGO_SITE_DIR"])
    print(f"{'✅' if ok else '⚠️ '} {msg}")

    # 摘要
    print()
    print("=" * 60)
    print("配置信息摘要")
    print("=" * 60)
    print(f"  飞书 App ID:     {mask_secret(config['FEISHU_APP_ID'])}")
    print(f"  飞书 App Token:  {config['FEISHU_APP_TOKEN']}")
    print(f"  Coze Workflow:   {config['COZE_WORKFLOW_ID']}")
    print(f"  Hugo 站点:       {config['HUGO_SITE_DIR']}")
    print(f"  网站域名:        {config['SITE_BASE_URL']}")

    print()
    confirm = get_input("配置是否正确？(y/n)", "y").lower()
    if confirm != "y":
        print("🔄 重新配置...")
        return interactive_config()

    # 保存
    try:
        with open(ENV_FILE, "w", encoding="utf-8") as f:
            f.write("# 飞书多维表格配置\n")
            f.write("FEISHU_APP_ID={}\n".format(config["FEISHU_APP_ID"]))
            f.write("FEISHU_APP_SECRET={}\n".format(config["FEISHU_APP_SECRET"]))
            f.write("FEISHU_APP_TOKEN={}\n".format(config["FEISHU_APP_TOKEN"]))
            f.write("FEISHU_TABLE_ID={}\n".format(config["FEISHU_TABLE_ID"]))
            f.write("\n# Coze 微信公众号发布配置\n")
            f.write("COZE_API_TOKEN={}\n".format(config["COZE_API_TOKEN"]))
            f.write("COZE_WORKFLOW_ID={}\n".format(config["COZE_WORKFLOW_ID"]))
            f.write("\n# Hugo 站点路径\n")
            f.write("HUGO_SITE_DIR={}\n".format(config["HUGO_SITE_DIR"]))
            f.write("\n# 网站域名\n")
            f.write("SITE_BASE_URL={}\n".format(config["SITE_BASE_URL"]))
        print(f"✅ 配置已保存到 {ENV_FILE}")
        return config
    except Exception as e:
        print(f"❌ 配置保存失败: {e}")
        return None


def ensure_config():
    """确保配置完整，不完整则进入配置向导"""
    config = load_config()
    if is_config_complete(config):
        return config

    print("⚠️  配置不完整")
    new_config = interactive_config()
    if new_config is None:
        print("❌ 配置失败，退出")
        sys.exit(1)
    return new_config


# ===== 飞书 API =====


def get_feishu_token(app_id=None, app_secret=None):
    """获取飞书 tenant_access_token"""
    config = load_config()
    app_id = app_id or config.get("FEISHU_APP_ID", "")
    app_secret = app_secret or config.get("FEISHU_APP_SECRET", "")

    payload = json.dumps({"app_id": app_id, "app_secret": app_secret}).encode()
    req = urllib.request.Request(
        FEISHU_TOKEN_URL, data=payload, headers={"Content-Type": "application/json"}
    )
    resp = json.loads(urllib.request.urlopen(req).read())
    if resp.get("code") != 0:
        raise RuntimeError(f"获取飞书 token 失败: {resp.get('msg')}")
    return resp["tenant_access_token"]


def feishu_request(path, token, method="GET", data=None):
    """通用飞书 API 请求"""
    url = f"https://open.feishu.cn/open-apis{path}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=payload, headers=headers, method=method)
    resp = json.loads(urllib.request.urlopen(req).read())
    if resp.get("code") != 0:
        raise RuntimeError(f"飞书 API 错误: {resp.get('msg')}")
    return resp["data"]


def fetch_feishu_records(token, config):
    """获取飞书表格所有记录"""
    path = f"/bitable/v1/apps/{config['FEISHU_APP_TOKEN']}/tables/{config['FEISHU_TABLE_ID']}/records?page_size=100"
    data = feishu_request(path, token)
    return data.get("items", [])


def update_feishu_record(token, config, record_id, fields):
    """更新飞书记录"""
    path = f"/bitable/v1/apps/{config['FEISHU_APP_TOKEN']}/tables/{config['FEISHU_TABLE_ID']}/records/batch_update"
    payload = {"records": [{"record_id": record_id, "fields": fields}]}
    feishu_request(path, token, method="POST", data=payload)
    return True


def delete_feishu_records(token, config, record_ids):
    """删除飞书记录"""
    path = f"/bitable/v1/apps/{config['FEISHU_APP_TOKEN']}/tables/{config['FEISHU_TABLE_ID']}/records/batch_delete"
    feishu_request(path, token, method="POST", data={"records": record_ids})
    return True


def sync_topic_status(token, config, article_title, published_url):
    """同步选题库状态：根据文章标题模糊匹配，更新发布状态为已发布并填入发布地址"""
    app_token = config["FEISHU_TOPIC_APP_TOKEN"]
    table_id = config["FEISHU_TOPIC_TABLE_ID"]
    
    if not app_token or not table_id:
        print("  ⚠️  选题库配置未填写，跳过同步")
        return True
    
    try:
        # 获取选题库所有记录
        path = f"/bitable/v1/apps/{app_token}/tables/{table_id}/records?page_size=100"
        data = feishu_request(path, token)
        records = data.get("items", [])
        
        if not records:
            print("  ⚠️  选题库为空，跳过同步")
            return True
        
        # 模糊匹配标题（选题标题包含文章标题 或 文章标题包含选题标题）
        matched_record_id = None
        article_title_lower = article_title.lower()
        
        for record in records:
            fields = record.get("fields", {})
            # 选题标题字段明确为 "选题标题"，飞书返回格式是数组
            topic_title = ""
            if "选题标题" in fields:
                title_arr = fields["选题标题"]
                if isinstance(title_arr, list) and len(title_arr) > 0:
                    topic_title = title_arr[0].get("text", "").lower()
                elif isinstance(title_arr, str):
                    topic_title = title_arr.lower()
            
            if topic_title and (article_title_lower in topic_title or topic_title in article_title_lower):
                matched_record_id = record["record_id"]
                break
        
        if not matched_record_id:
            print("  ⚠️  选题库未找到匹配的选题，跳过同步")
            return True
        
        # 更新状态为已发布，填入发布地址（字段名：状态、文章发布地址）
        update_fields = {
            "状态": "已发布",
            "文章发布地址": published_url
        }
        path = f"/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_update"
        payload = {"records": [{"record_id": matched_record_id, "fields": update_fields}]}
        feishu_request(path, token, method="POST", data=payload)
        
        print("  ✅ 选题库状态已同步为「已发布」")
        return True
        
    except Exception as e:
        print(f"  ⚠️  选题库同步失败: {e}")
        return True


# ===== Hugo 文章操作 =====


def _auto_increment_time(site_dir, date_str):
    """自动处理同日文章排序：查找同一天已有文章的最大时间，在此基础上 +4 小时。

    避免同一天多篇文章都用 00:00:00 导致排序混乱。
    时间分配: 00:00, 04:00, 08:00, 12:00, 16:00, 20:00 (每天最多 6 篇)
    """
    post_dir = site_dir / "content" / "post"
    max_hour = -4  # 起始偏移，第一篇会是 00:00

    if post_dir.exists():
        for d in post_dir.iterdir():
            if d.is_dir() and d.name.startswith(date_str):
                index_md = d / "index.md"
                if index_md.exists():
                    for line in open(index_md, encoding="utf-8"):
                        if line.startswith("date:"):
                            date_val = line.replace("date:", "").strip().strip('"')
                            # 提取小时
                            m = re.search(r"T(\d{2}):", date_val)
                            if m:
                                hour = int(m.group(1))
                                if hour > max_hour:
                                    max_hour = hour
                            break

    new_hour = min(max_hour + 4, 20)  # 每次加 4 小时，最大 20:00
    return f"{date_str}T{new_hour:02d}:00:00+08:00"


def get_existing_tags(site_dir):
    """读取 Hugo 站点已有的标签，返回集合"""
    try:
        # 查找所有已生成文章的 front matter 提取标签
        content_dir = Path(site_dir) / "content" / "post"
        if not content_dir.exists():
            return set()
        
        existing_tags = set()
        # 遍历所有文章目录，提取标签
        for post_dir in content_dir.iterdir():
            if not post_dir.is_dir():
                continue
            index_md = post_dir / "index.md"
            if not index_md.exists():
                continue
            try:
                in_front_matter = False
                found_tags = False
                with open(index_md, encoding="utf-8") as f:
                    for line in f:
                        if line.strip() == "---":
                            if not in_front_matter:
                                in_front_matter = True
                                continue
                            else:
                                break
                        if in_front_matter and line.strip().startswith("tags:"):
                            found_tags = True
                            continue
                        if found_tags and in_front_matter and line.strip().startswith("-"):
                            tag = line.strip().lstrip("- ").strip()
                            if tag:
                                existing_tags.add(tag)
            except Exception:
                continue
        return existing_tags
    except Exception:
        return set()


def extract_tags_from_content(title, content, category, site_dir):
    """从文章标题、内容、分类中自动提取关键词作为标签，优先匹配已有标签，最多4个"""
    existing_tags = get_existing_tags(site_dir)
    candidate_tags = []
    
    # 优先级 1: 分类（肯定第一个）
    if category and category.strip():
        cat = category.strip()
        candidate_tags.append(cat)
    
    # 优先级 2: 书名（从《》中提取），先匹配已有标签
    book_matches = re.findall(r'[《]([^》]+)[》]', content if content else title)
    for book in book_matches:
        book = book.strip()
        if len(book) >= 2:
            # 如果书名在已有标签中，优先放前面
            if book in existing_tags and book not in candidate_tags:
                candidate_tags.insert(1 if len(candidate_tags) == 1 else len(candidate_tags), book)
            elif book not in candidate_tags:
                candidate_tags.append(book)
    
    # 优先级 3: 从标题提取分词，优先匹配已有标签
    title_words = re.findall(r'[\u4e00-\u9fffa-zA-Z0-9]+', title)
    # 先加已有匹配的
    for word in title_words:
        word = word.strip()
        if len(word) >= 3 and word in existing_tags and word not in candidate_tags:
            candidate_tags.append(word)
    # 再加新的关键词
    for word in title_words:
        word = word.strip()
        if len(word) >= 3 and word not in candidate_tags:
            candidate_tags.append(word)
    
    # 如果不够，兜底加默认
    if len(candidate_tags) < 2:
        if "阅读" not in candidate_tags:
            candidate_tags.append("阅读")
        if len(candidate_tags) < 2 and "成长" not in candidate_tags:
            candidate_tags.append("成长")
    
    # 限制最多 4 个标签
    tags = candidate_tags[:4]
    return tags


def create_hugo_article(config, article):
    """创建 Hugo 文章，返回 (文章目录路径, 实际 slug)"""
    site_dir = Path(config["HUGO_SITE_DIR"])
    
    # 飞书表格字段名：文章标题、文章分类、文章摘要、文章内容-markdown、文章配图
    title = ""
    if "title" in article:
        title = article["title"]
    elif "文章标题" in article:
        title_arr = article["文章标题"]
        if isinstance(title_arr, list) and len(title_arr) > 0:
            title = title_arr[0].get("text", "")
    
    description = ""
    if "description" in article:
        description = article["description"]
    elif "文章摘要" in article:
        desc_arr = article["文章摘要"]
        if isinstance(desc_arr, list) and len(desc_arr) > 0:
            description = desc_arr[0].get("text", "")
    
    category = "阅读"
    if "category" in article:
        category = article["category"]
    elif "文章分类" in article:
        cat_arr = article["文章分类"]
        if isinstance(cat_arr, list) and len(cat_arr) > 0:
            category = cat_arr[0].get("text", "阅读")
    
    markdown_content = ""
    if "content_md" in article:
        markdown_content = article["content_md"]
    elif "文章内容-markdown" in article:
        md_arr = article["文章内容-markdown"]
        if isinstance(md_arr, list) and len(md_arr) > 0:
            markdown_content = md_arr[0].get("text", "")
    
    image_url = ""
    if "image_url" in article:
        image_url = article["image_url"]
    elif "文章配图" in article:
        img_arr = article["文章配图"]
        if isinstance(img_arr, list) and len(img_arr) > 0:
            image_url = img_arr[0].get("text", "")
    
    # 自动提取标签：标题 + 书名 + 分类 + 默认兜底，优先匹配已有标签，最多4个
    tags = extract_tags_from_content(title, markdown_content, category, site_dir)
    
    date_str = article.get("date", datetime.now(CST).strftime("%Y-%m-%d"))

    # 自动处理同日文章排序：检查同一天已有文章的最大时间，在此基础上 +4 小时
    iso_date = _auto_increment_time(site_dir, date_str)
    article["iso_date"] = iso_date

    # 生成目录名
    hash_str = format(random.randint(0, 0xFFFFFFFF), "x")
    dir_name = f"{date_str}-{hash_str}"
    article_dir = site_dir / "content" / "post" / dir_name
    article_dir.mkdir(parents=True, exist_ok=True)

    # 下载配图
    if image_url:
        try:
            print(f"  📥 下载配图...")
            req = urllib.request.Request(image_url)
            resp = urllib.request.urlopen(req, timeout=30)
            img_data = resp.read()
            ext = ".jpg"
            content_type = resp.headers.get("Content-Type", "")
            if "png" in content_type:
                ext = ".png"
            with open(article_dir / f"feature{ext}", "wb") as f:
                f.write(img_data)
            # Hugo 使用 feature.jpg 作为封面
            if ext == ".png":
                import shutil

                shutil.copy(article_dir / "feature.png", article_dir / "feature.jpg")
        except Exception as e:
            print(f"  ⚠️  配图下载失败: {e}")

    # 生成 front matter
    tags_yaml = "\n".join(f"    - {t}" for t in tags)
    front_matter = f"""---
title: "{title}"
date: {iso_date}
draft: false
description: "{description}"
categories:
    - {category}
tags:
{tags_yaml}
image: "feature.jpg"
---"""

    # markdown 内容：去掉第一行 H1 标题
    lines = markdown_content.split("\n")
    if lines and lines[0].startswith("# "):
        content = "\n".join(lines[1:]).strip()
    else:
        content = markdown_content.strip()

    # 写入文件
    with open(article_dir / "index.md", "w", encoding="utf-8") as f:
        f.write(front_matter + "\n" + content + "\n")

    print(f"  ✅ 文章创建: content/post/{dir_name}/")
    return str(article_dir)


def build_hugo(config):
    """构建 Hugo 站点，返回是否成功"""
    site_dir = config["HUGO_SITE_DIR"]
    try:
        result = subprocess.run(
            ["hugo", "--minify"],
            cwd=site_dir,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            print(f"  ❌ Hugo 构建失败: {result.stderr}")
            return False
        print("  ✅ Hugo 构建成功")
        return True
    except FileNotFoundError:
        print("  ❌ Hugo 未安装")
        return False


def get_published_url(config, title):
    """从 public/p/ 目录匹配已生成文章的实际 slug，返回完整 URL"""
    site_dir = Path(config["HUGO_SITE_DIR"])
    base_url = config["SITE_BASE_URL"].rstrip("/")
    public_p = site_dir / "public" / "p"

    if not public_p.exists():
        return None

    # Hugo slug 规则：去掉几乎所有标点符号（中英文），只保留字母数字和中文
    def normalize_for_match(t):
        s = t.lower()
        # 去掉所有非字母数字非中文的字符
        s = re.sub(r'[^\w\u4e00-\u9fff]', '', s, flags=re.UNICODE)
        return s

    target_text = normalize_for_match(title)

    # 先收集所有 public/p/ 下的目录，按修改时间排序（最新的在前）
    slug_dirs = sorted(
        [d for d in public_p.iterdir() if d.is_dir() and (d / "index.html").exists()],
        key=lambda d: d.stat().st_mtime,
        reverse=True,
    )

    for slug_dir in slug_dirs:
        dir_text = normalize_for_match(slug_dir.name)
        if dir_text == target_text:
            return f"{base_url}/p/{slug_dir.name}/"

    # 未精确匹配，尝试包含匹配
    for slug_dir in slug_dirs:
        dir_text = normalize_for_match(slug_dir.name)
        if dir_text in target_text or target_text in dir_text:
            return f"{base_url}/p/{slug_dir.name}/"

    return None


# ===== Git 操作 =====


def git_pull_latest(config):
    """发布前先拉取最新代码，避免冲突"""
    site_dir = config["HUGO_SITE_DIR"]
    try:
        result = subprocess.run(
            ["git", "pull", "origin", "main"],
            cwd=site_dir,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            print("  ✅ Git pull 成功，代码已是最新")
            return True
        else:
            print(f"  ⚠️  Git pull 失败: {result.stderr}")
            return False
    except Exception as e:
        print(f"  ⚠️  Git pull 异常: {e}")
        return False


def git_commit_and_push(config, title):
    """提交文章到 Git 并推送到 GitHub"""
    site_dir = config["HUGO_SITE_DIR"]

    try:
        # 发布前先拉取最新代码
        print("  🔄 拉取最新代码...")
        git_pull_latest(config)
        
        # git add
        subprocess.run(["git", "add", "content/", "public/", "static/"], cwd=site_dir, capture_output=True)

        # 检查是否有变更
        result = subprocess.run(
            ["git", "diff", "--cached", "--quiet"], cwd=site_dir, capture_output=True
        )
        if result.returncode == 0:
            print("  ⚠️  没有检测到变更")
            return True

        # git commit
        commit_msg = f"feat: 发布文章《{title}》"
        result = subprocess.run(
            ["git", "commit", "-m", commit_msg],
            cwd=site_dir,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"  ❌ Git commit 失败: {result.stderr}")
            return False
        print(f"  ✅ Git commit: {commit_msg}")

        # git push
        result = subprocess.run(
            ["git", "push", "origin", "main"],
            cwd=site_dir,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"  ❌ Git push 失败: {result.stderr}")
            return False
        print("  ✅ Git push 成功")
        return True

    except Exception as e:
        print(f"  ❌ Git 操作失败: {e}")
        return False


# ===== 微信公众号发布 =====


def publish_to_wechat(config, article, publish_url):
    """通过 Coze 工作流发布到微信公众号"""
    token = config["COZE_API_TOKEN"]
    workflow_id = config["COZE_WORKFLOW_ID"]

    title = article["title"]
    html_content = article.get("content_html", "")
    image_url = article.get("image_url", "")
    digest = article.get("description", "")[:120]

    payload = json.dumps(
        {
            "workflow_id": workflow_id,
            "parameters": {
                "title": title,
                "content": html_content,
                "imageurl": image_url,
                "digest": digest,
                "source_url": publish_url or "",
            },
        },
        ensure_ascii=False,
    ).encode()

    req = urllib.request.Request(
        COZE_WORKFLOW_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )

    resp = urllib.request.urlopen(req, timeout=120)
    full_output = ""
    while True:
        chunk = resp.read(4096)
        if not chunk:
            break
        full_output += chunk.decode("utf-8")

    # 检查是否包含成功标志
    if "node_is_finish" in full_output:
        print("  ✅ 微信公众号发布成功")
        return True
    else:
        print(f"  ⚠️  微信公众号发布响应: {full_output[:200]}")
        return False


# ===== 主流程 =====


def parse_feishu_article(record):
    """从飞书记录解析文章数据"""
    fields = record.get("fields", {})
    title = fields.get("文章标题", "")

    # 解析日期
    date_ts = fields.get("日期", 0)
    if isinstance(date_ts, (int, float)) and date_ts > 0:
        dt = datetime.fromtimestamp(date_ts / 1000, tz=CST)
        date_str = dt.strftime("%Y-%m-%d")
        iso_date = dt.strftime("%Y-%m-%dT%H:%M:%S+08:00")
    else:
        date_str = datetime.now(CST).strftime("%Y-%m-%d")
        iso_date = datetime.now(CST).strftime("%Y-%m-%dT%H:%M:%S+08:00")

    # 解析描述（从 markdown 内容中提取引用行）
    content_md = fields.get("文章内容-markdown", "")
    description = ""
    for line in content_md.split("\n"):
        if line.startswith(">") and not line.startswith(">>"):
            description = line.lstrip("> ").strip()
            break

    return {
        "record_id": record.get("record_id", ""),
        "title": title,
        "description": description,
        "content_md": content_md,
        "content_html": fields.get("文章内容-html", ""),
        "category": fields.get("文章分类", "阅读"),
        "tags": ["阅读", "成长"],
        "image_url": fields.get("文章配图", ""),
        "publish_url": fields.get("文章发布地址", ""),
        "date": date_str,
        "iso_date": iso_date,
    }


def list_unpublished(articles):
    """列出未发布文章"""
    unpublished = [a for a in articles if not a["publish_url"]]
    if not unpublished:
        print("🎉 所有文章均已发布！")
        return []

    print(f"\n📋 未发布文章 ({len(unpublished)} 篇)：")
    print("-" * 60)
    for i, article in enumerate(unpublished, 1):
        print(f"  {i}. {article['title']}")
        print(f"     分类: {article['category']}  日期: {article['date']}")
    print()
    return unpublished


def select_articles(unpublished, title_filter=None):
    """选择要发布的文章"""
    if title_filter:
        matched = [a for a in unpublished if title_filter in a["title"]]
        if not matched:
            print(f"❌ 未找到匹配「{title_filter}」的未发布文章")
            return []
        return matched

    if len(unpublished) == 1:
        print(f"📝 即将发布: {unpublished[0]['title']}")
        return unpublished

    print("请选择要发布的文章（输入编号，多个用逗号分隔，0=全部）：")
    choice = input("> ").strip()

    if choice == "0":
        return unpublished

    try:
        indices = [int(x.strip()) - 1 for x in choice.split(",")]
        return [unpublished[i] for i in indices if 0 <= i < len(unpublished)]
    except (ValueError, IndexError):
        print("❌ 无效选择")
        return []


def publish_article(config, article, hugo_only=False, wechat_only=False):
    """发布单篇文章的完整流程"""
    title = article["title"]
    print(f"\n{'='*60}")
    print(f"📝 发布: {title}")
    print(f"{'='*60}")

    publish_url = article.get("publish_url", "")

    # Step 0: 发布前先拉取最新代码（避免多代理发布冲突）
    if not wechat_only:
        print("\n[Step 0/6] 拉取 GitHub 最新代码...")
        if not git_pull_latest(config):
            print("  ⚠️  拉取失败，继续发布可能产生冲突")

    # Step 1: 发布到 Hugo 网站
    if not wechat_only:
        print("\n[Step 1/6] 创建 Hugo 文章...")
        article_dir = create_hugo_article(config, article)

        print("\n[Step 2/6] 构建 Hugo 站点...")
        if not build_hugo(config):
            return False

        # 获取发布 URL
        print("\n[Step 3/6] 提交到 Git 并推送...")
        publish_url = get_published_url(config, title)
        if not publish_url:
            print("  ⚠️  无法获取发布 URL，使用估算 URL")
            base_url = config["SITE_BASE_URL"].rstrip("/")
            publish_url = f"{base_url}/p/?"

        if not git_commit_and_push(config, title):
            return False

        # Step 4: 回写飞书表格
        print("\n[Step 4/6] 回写文案库...")
        try:
            token = get_feishu_token()
            update_feishu_record(token, config, article["record_id"], {"文章发布地址": publish_url})
            print(f"  ✅ 发布地址: {publish_url}")
        except Exception as e:
            print(f"  ⚠️  文案库回写失败: {e}")

        # Step 4.5: 同步选题库状态
        print("\n[Step 5/6] 同步选题库状态...")
        try:
            token = get_feishu_token()
            sync_topic_status(token, config, article["title"], publish_url)
        except Exception as e:
            print(f"  ⚠️  选题库同步失败: {e}")

        if hugo_only:
            print("\n✅ Hugo 网站发布完成（跳过微信公众号发布）")
            return True

    # Step 6: 发布微信公众号
    if not hugo_only:
        print("\n[Step 6/6] 发布到微信公众号...")
        try:
            publish_to_wechat(config, article, publish_url)
        except Exception as e:
            print(f"  ❌ 微信公众号发布失败: {e}")
            return False

    print(f"\n🎉 《{title}》发布完成！")
    if publish_url:
        print(f"   📎 {publish_url}")
    return True


def main():
    parser = argparse.ArgumentParser(description="爱分享读书 — 一键发布工具")
    parser.add_argument("--title", "-t", help="指定要发布的文章标题（支持模糊匹配）")
    parser.add_argument("--list", "-l", action="store_true", help="仅列出未发布文章")
    parser.add_argument("--hugo-only", action="store_true", help="仅发布到 Hugo 网站（不发微信公众号）")
    parser.add_argument("--wechat-only", action="store_true", help="仅发布到微信公众号（网站已发布）")
    args = parser.parse_args()

    # 加载配置
    config = ensure_config()

    # 获取飞书数据
    print("📡 正在从飞书多维表格获取文章数据...")
    try:
        token = get_feishu_token()
        records = fetch_feishu_records(token, config)
    except Exception as e:
        print(f"❌ 飞书 API 调用失败: {e}")
        sys.exit(1)

    # 解析文章
    articles = [parse_feishu_article(r) for r in records]
    print(f"📊 共获取 {len(articles)} 篇文章")

    # 列出未发布
    unpublished = list_unpublished(articles)
    if not unpublished or args.list:
        return

    # 选择文章
    selected = select_articles(unpublished, args.title)
    if not selected:
        return

    # 确认发布
    if not args.title:
        print(f"\n即将发布 {len(selected)} 篇文章，确认？(y/n) [y]: ", end="")
        confirm = input().strip().lower()
        if confirm and confirm != "y":
            print("已取消")
            return

    # 逐篇发布
    success_count = 0
    for article in selected:
        if publish_article(config, article, hugo_only=args.hugo_only, wechat_only=args.wechat_only):
            success_count += 1

    print(f"\n{'='*60}")
    print(f"📊 发布完成: {success_count}/{len(selected)} 篇成功")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
