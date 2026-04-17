#!/usr/bin/env python3
"""爱分享读书 — 文章写作工作流脚本

提供飞书多维表格、飞书云盘、Coze 工作流的 API 调用封装。
供 AI 智能体在执行「选题→写稿→入库」流程时调用。

首次使用会自动引导配置 API Key 等参数，配置保存在脚本同目录的 .env 文件中。

用法:
    python3 article_workflow.py init              # 初始化/重新配置
    python3 article_workflow.py check-config      # 检查配置状态
    python3 article_workflow.py get-token
    python3 article_workflow.py get-topic <keyword> [--status 待写] [--detail]
    python3 article_workflow.py get-articles [--category X] [--keyword X] [--full]
    python3 article_workflow.py upload-file <local_path> <file_name> [--folder-token TOKEN]
    python3 article_workflow.py update-topic-status <record_id> <status>
    python3 article_workflow.py call-coze --title X --digest X --type X --content-file X --image-prompt X
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

# ── 路径常量 ──────────────────────────────────────────────
SKILL_DIR = Path(__file__).parent
ENV_FILE = SKILL_DIR / ".env"
ENV_EXAMPLE = SKILL_DIR / ".env.example"

# 必填配置项
REQUIRED_KEYS = [
    "FEISHU_APP_ID",
    "FEISHU_APP_SECRET",
]

# 可选配置项（有默认值）
DEFAULTS = {
    "TOPIC_APP_TOKEN": "YjN6bWopMaYixSs1ArncqVBLn1c",
    "TOPIC_TABLE_ID": "tblspru4cgIMd5M3",
    "ARTICLE_APP_TOKEN": "XsBnb6AOTafA8usGoIGc2faunUh",
    "ARTICLE_TABLE_ID": "tblwHGCK9VwzORYR",
    "UPLOAD_FOLDER_TOKEN": "YPMwfcqfilMkxgd2MsTcOAumn6g",
    "COZE_API_TOKEN": "",
    "COZE_WORKFLOW_ID": "7629233812262879273",
}

# ── 配置管理 ──────────────────────────────────────────────

def mask_secret(value):
    """遮蔽敏感信息"""
    if not value or len(value) <= 8:
        return "*" * max(len(value), 4)
    return value[:4] + "****" + value[-4:]


def get_input(prompt, default=""):
    """获取用户输入，支持默认值"""
    if default:
        prompt = f"{prompt} [{default}]: "
    else:
        prompt = f"{prompt}: "
    value = input(prompt).strip()
    return value if value else default


def load_config():
    """加载配置：环境变量 > .env 文件 > 默认值"""
    config = {}

    # 加载 .env 文件
    if ENV_FILE.exists():
        with open(ENV_FILE, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip())

    # 读取必填项
    for key in REQUIRED_KEYS:
        config[key] = os.environ.get(key, "")

    # 读取可选项（带默认值）
    for key, default in DEFAULTS.items():
        config[key] = os.environ.get(key, default)

    return config


def is_config_valid(config):
    """检查必填配置是否完整"""
    for key in REQUIRED_KEYS:
        val = config.get(key, "").strip()
        if not val or val.startswith("your_"):
            return False
    return True


def save_config(config):
    """保存配置到 .env 文件"""
    lines = [
        "# 爱分享读书 — 文章写作工作流配置",
        "# 由 article_workflow.py init 自动生成",
        "",
        "# ── 飞书开放平台 ──",
        "# 获取地址: https://open.feishu.cn → 创建应用 → 凭证与基础信息",
        f"FEISHU_APP_ID={config.get('FEISHU_APP_ID', '')}",
        f"FEISHU_APP_SECRET={config.get('FEISHU_APP_SECRET', '')}",
        "",
        "# ── 飞书多维表格 ──",
        "# 选题库（通常不需要修改）",
        f"TOPIC_APP_TOKEN={config.get('TOPIC_APP_TOKEN', DEFAULTS['TOPIC_APP_TOKEN'])}",
        f"TOPIC_TABLE_ID={config.get('TOPIC_TABLE_ID', DEFAULTS['TOPIC_TABLE_ID'])}",
        "",
        "# 文案库（通常不需要修改）",
        f"ARTICLE_APP_TOKEN={config.get('ARTICLE_APP_TOKEN', DEFAULTS['ARTICLE_APP_TOKEN'])}",
        f"ARTICLE_TABLE_ID={config.get('ARTICLE_TABLE_ID', DEFAULTS['ARTICLE_TABLE_ID'])}",
        "",
        "# ── 飞书云盘 ──",
        "# 投稿文件夹 Token（从文件夹 URL 获取）",
        f"UPLOAD_FOLDER_TOKEN={config.get('UPLOAD_FOLDER_TOKEN', DEFAULTS['UPLOAD_FOLDER_TOKEN'])}",
        "",
        "# ── Coze 工作流 ──",
        "# 获取地址: https://www.coze.cn → 工作流 → API",
        f"COZE_API_TOKEN={config.get('COZE_API_TOKEN', '')}",
        f"COZE_WORKFLOW_ID={config.get('COZE_WORKFLOW_ID', DEFAULTS['COZE_WORKFLOW_ID'])}",
    ]
    with open(ENV_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def interactive_config():
    """交互式配置初始化向导"""
    config = load_config()

    print()
    print("🔧 首次使用「爱分享读书·文章写作」技能，开始配置初始化")
    print("=" * 60)
    print("请根据提示输入以下配置信息")
    print("按 Enter 可使用方括号中的默认值")
    print("=" * 60)

    # ── 飞书配置 ──
    print()
    print("─" * 60)
    print("1. 飞书开放平台配置（必填）")
    print("   获取地址: https://open.feishu.cn → 创建应用 → 凭证与基础信息")
    print("   需要开通权限: bitable:record, drive:file, 云文档相关权限")
    print("─" * 60)
    config["FEISHU_APP_ID"] = get_input("请输入飞书 App ID", config.get("FEISHU_APP_ID", ""))
    config["FEISHU_APP_SECRET"] = get_input("请输入飞书 App Secret", config.get("FEISHU_APP_SECRET", ""))

    # ── 多维表格配置 ──
    print()
    print("─" * 60)
    print("2. 飞书多维表格配置（通常无需修改）")
    print("─" * 60)
    config["TOPIC_APP_TOKEN"] = get_input("选题库 App Token", config.get("TOPIC_APP_TOKEN", DEFAULTS["TOPIC_APP_TOKEN"]))
    config["TOPIC_TABLE_ID"] = get_input("选题库 Table ID", config.get("TOPIC_TABLE_ID", DEFAULTS["TOPIC_TABLE_ID"]))
    config["ARTICLE_APP_TOKEN"] = get_input("文案库 App Token", config.get("ARTICLE_APP_TOKEN", DEFAULTS["ARTICLE_APP_TOKEN"]))
    config["ARTICLE_TABLE_ID"] = get_input("文案库 Table ID", config.get("ARTICLE_TABLE_ID", DEFAULTS["ARTICLE_TABLE_ID"]))

    # ── 飞书云盘 ──
    print()
    print("─" * 60)
    print("3. 飞书云盘投稿文件夹（通常无需修改）")
    print("─" * 60)
    config["UPLOAD_FOLDER_TOKEN"] = get_input("投稿文件夹 Token", config.get("UPLOAD_FOLDER_TOKEN", DEFAULTS["UPLOAD_FOLDER_TOKEN"]))

    # ── Coze 配置 ──
    print()
    print("─" * 60)
    print("4. Coze 工作流配置（写入文案库需要）")
    print("   获取地址: https://www.coze.cn → 工作流 → API 发布")
    print("   如暂不使用可跳过（按 Enter）")
    print("─" * 60)
    config["COZE_API_TOKEN"] = get_input("请输入 Coze API Token", config.get("COZE_API_TOKEN", ""))
    config["COZE_WORKFLOW_ID"] = get_input("请输入 Coze Workflow ID", config.get("COZE_WORKFLOW_ID", DEFAULTS["COZE_WORKFLOW_ID"]))

    # ── 验证 & 保存 ──
    print()
    if not config.get("FEISHU_APP_ID") or not config.get("FEISHU_APP_SECRET"):
        print("❌ 飞书 App ID 和 App Secret 为必填项！")
        print("   请重新运行: python3 article_workflow.py init")
        sys.exit(1)

    save_config(config)
    print("✅ 配置已保存到:", ENV_FILE)
    print()

    # 测试连接
    print("正在测试飞书连接...")
    try:
        token = _get_tenant_token(config)
        if token:
            print("✅ 飞书连接成功!")
        else:
            print("❌ 飞书连接失败，请检查 App ID 和 App Secret")
    except Exception as e:
        print(f"❌ 飞书连接失败: {e}")


def check_config():
    """检查配置状态"""
    config = load_config()
    print("配置文件:", ENV_FILE)
    print(f"文件存在: {'是' if ENV_FILE.exists() else '否'}")
    print()
    print("配置状态:")
    print(f"  FEISHU_APP_ID      = {mask_secret(config.get('FEISHU_APP_ID', ''))}")
    print(f"  FEISHU_APP_SECRET  = {mask_secret(config.get('FEISHU_APP_SECRET', ''))}")
    print(f"  TOPIC_APP_TOKEN    = {config.get('TOPIC_APP_TOKEN', '(未设置)')}")
    print(f"  TOPIC_TABLE_ID     = {config.get('TOPIC_TABLE_ID', '(未设置)')}")
    print(f"  ARTICLE_APP_TOKEN  = {config.get('ARTICLE_APP_TOKEN', '(未设置)')}")
    print(f"  ARTICLE_TABLE_ID   = {config.get('ARTICLE_TABLE_ID', '(未设置)')}")
    print(f"  UPLOAD_FOLDER_TOKEN= {config.get('UPLOAD_FOLDER_TOKEN', '(未设置)')}")
    print(f"  COZE_API_TOKEN     = {mask_secret(config.get('COZE_API_TOKEN', ''))}")
    print(f"  COZE_WORKFLOW_ID   = {config.get('COZE_WORKFLOW_ID', '(未设置)')}")
    print()
    if is_config_valid(config):
        print("✅ 必填配置完整")
    else:
        print("❌ 必填配置不完整，请运行: python3 article_workflow.py init")


# ── 通用 HTTP 辅助 ────────────────────────────────────────

def _curl_get(url, token):
    cmd = ["curl", "-s", url, "-H", f"Authorization: Bearer {token}"]
    return json.loads(subprocess.check_output(cmd))


def _curl_put(url, token, body_dict):
    payload = json.dumps(body_dict, ensure_ascii=False)
    tmp = "/tmp/_feishu_put.json"
    with open(tmp, "w") as f:
        f.write(payload)
    cmd = ["curl", "-s", "-X", "PUT", url,
           "-H", f"Authorization: Bearer {token}",
           "-H", "Content-Type: application/json",
           "-d", f"@{tmp}"]
    result = json.loads(subprocess.check_output(cmd))
    os.remove(tmp)
    return result


# ── 飞书认证 ──────────────────────────────────────────────

def _get_tenant_token(config=None):
    """获取飞书 tenant_access_token"""
    if config is None:
        config = load_config()
    payload = json.dumps({"app_id": config["FEISHU_APP_ID"], "app_secret": config["FEISHU_APP_SECRET"]})
    tmp = "/tmp/_feishu_auth.json"
    with open(tmp, "w") as f:
        f.write(payload)
    cmd = ["curl", "-s", "-X", "POST",
           "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
           "-H", "Content-Type: application/json",
           "-d", f"@{tmp}"]
    result = json.loads(subprocess.check_output(cmd))
    os.remove(tmp)
    if result.get("code") != 0:
        print(f"ERROR: 飞书认证失败 - {result}", file=sys.stderr)
        return None
    return result["tenant_access_token"]


def get_tenant_token():
    """获取飞书 token（带配置检查）"""
    config = load_config()
    if not is_config_valid(config):
        print("❌ 配置不完整，请先运行初始化:")
        print(f"   python3 {sys.argv[0]} init")
        sys.exit(1)
    token = _get_tenant_token(config)
    if not token:
        sys.exit(1)
    return token


# ── 选题库 ────────────────────────────────────────────────

def _fetch_all_topics(token, config):
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{config['TOPIC_APP_TOKEN']}/tables/{config['TOPIC_TABLE_ID']}/records?page_size=100"
    result = _curl_get(url, token)
    if result.get("code") != 0:
        print(f"ERROR: {result}", file=sys.stderr)
        sys.exit(1)
    return result["data"]["items"]


def get_topics(token, config, keyword=None, status=None):
    items = _fetch_all_topics(token, config)
    if keyword:
        items = [i for i in items if keyword in str(i["fields"])]
    if status:
        items = [i for i in items if status in str(i["fields"].get("状态", ""))]
    for item in items:
        f = item["fields"]
        print(json.dumps({
            "record_id": item["record_id"],
            "选题标题": f.get("选题标题", ""),
            "主题分类": f.get("主题分类", ""),
            "状态": f.get("状态", ""),
            "推荐书籍": f.get("推荐书籍", ""),
            "热点结合": f.get("热点结合", ""),
            "备注": f.get("备注", ""),
            "文章发布地址": f.get("文章发布地址", ""),
        }, ensure_ascii=False))


def get_topic_detail(token, config, keyword):
    items = _fetch_all_topics(token, config)
    for item in items:
        if keyword in str(item["fields"]):
            print(json.dumps({"record_id": item["record_id"], "fields": item["fields"]}, ensure_ascii=False))
            return
    print(json.dumps({"error": f"未找到包含 '{keyword}' 的选题"}, ensure_ascii=False))


def update_topic_status(token, config, record_id, status):
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{config['TOPIC_APP_TOKEN']}/tables/{config['TOPIC_TABLE_ID']}/records/{record_id}"
    result = _curl_put(url, token, {"fields": {"状态": status}})
    if result.get("code") == 0:
        print(f"OK: 选题状态已更新为「{status}」")
    else:
        print(f"ERROR: {result}", file=sys.stderr)


# ── 文案库 ────────────────────────────────────────────────

def _fetch_all_articles(token, config):
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{config['ARTICLE_APP_TOKEN']}/tables/{config['ARTICLE_TABLE_ID']}/records?page_size=100"
    result = _curl_get(url, token)
    if result.get("code") != 0:
        print(f"ERROR: {result}", file=sys.stderr)
        sys.exit(1)
    return result["data"]["items"]


def get_articles(token, config, category=None, keyword=None):
    items = _fetch_all_articles(token, config)
    if category:
        items = [i for i in items if category in str(i["fields"].get("文章分类", ""))]
    if keyword:
        items = [i for i in items if keyword in str(i["fields"])]
    for item in items:
        f = item["fields"]
        print(json.dumps({
            "record_id": item["record_id"],
            "文章标题": f.get("文章标题", ""),
            "文章分类": f.get("文章分类", ""),
            "文章摘要": f.get("文章摘要", ""),
            "文章内容-markdown": str(f.get("文章内容-markdown", ""))[:200],
        }, ensure_ascii=False))


def get_article_full_content(token, config, keyword):
    items = _fetch_all_articles(token, config)
    for item in items:
        fields = item["fields"]
        if keyword in str(fields.get("文章标题", "")):
            print(json.dumps({
                "record_id": item["record_id"],
                "文章标题": fields.get("文章标题", ""),
                "文章内容-markdown": fields.get("文章内容-markdown", ""),
            }, ensure_ascii=False))
            return
    print(json.dumps({"error": f"未找到包含 '{keyword}' 的文章"}, ensure_ascii=False))


# ── 飞书云盘上传 ──────────────────────────────────────────

def upload_file(token, config, local_path, file_name, folder_token):
    file_size = os.path.getsize(local_path)
    cmd = ["curl", "-s", "-X", "POST",
           "https://open.feishu.cn/open-apis/drive/v1/files/upload_all",
           "-H", f"Authorization: Bearer {token}",
           "-F", f"file_name={file_name}",
           "-F", "parent_type=explorer",
           "-F", f"parent_node={folder_token}",
           "-F", f"size={file_size}",
           "-F", f"file=@{local_path}"]
    result = json.loads(subprocess.check_output(cmd))
    if result.get("code") == 0:
        print(f"OK: 文件已上传, file_token={result['data']['file_token']}")
    else:
        print(f"ERROR: {result}", file=sys.stderr)


# ── Coze 工作流 ──────────────────────────────────────────

def call_coze_workflow(config, title, digest, article_type, content_file, image_prompt):
    if not config.get("COZE_API_TOKEN"):
        print("ERROR: COZE_API_TOKEN 未配置，请运行: python3 article_workflow.py init", file=sys.stderr)
        sys.exit(1)

    with open(content_file, "r") as f:
        article_content = f.read()

    payload = json.dumps({
        "workflow_id": config.get("COZE_WORKFLOW_ID", DEFAULTS["COZE_WORKFLOW_ID"]),
        "parameters": {
            "article_content": article_content,
            "article_digest": digest,
            "article_imageprompt": image_prompt,
            "article_title": title,
            "article_type": article_type,
        },
    }, ensure_ascii=False)

    tmp = "/tmp/_coze_payload.json"
    with open(tmp, "w") as f:
        f.write(payload)

    cmd = ["curl", "-s", "-X", "POST",
           "https://api.coze.cn/v1/workflow/stream_run",
           "-H", f"Authorization: Bearer {config['COZE_API_TOKEN']}",
           "-H", "Content-Type: application/json",
           "-d", f"@{tmp}"]
    output = subprocess.check_output(cmd, timeout=120).decode()
    os.remove(tmp)

    for line in output.split("\n"):
        if line.startswith("data: "):
            try:
                d = json.loads(line[6:])
                if d.get("node_is_finish"):
                    print(f"OK: Coze 工作流节点「{d.get('node_title', '')}」完成")
            except json.JSONDecodeError:
                pass
    print("OK: Coze 工作流执行完成")


# ── CLI 入口 ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="爱分享读书 — 文章写作工作流")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("init", help="初始化/重新配置 API Key 等参数")
    sub.add_parser("check-config", help="检查配置状态")
    sub.add_parser("get-token", help="获取飞书 tenant_access_token")

    p_topic = sub.add_parser("get-topic", help="获取选题（按关键词过滤）")
    p_topic.add_argument("keyword")
    p_topic.add_argument("--status", default=None)
    p_topic.add_argument("--detail", action="store_true", help="输出完整字段")

    p_articles = sub.add_parser("get-articles", help="获取文案库文章")
    p_articles.add_argument("--category", default=None)
    p_articles.add_argument("--keyword", default=None)
    p_articles.add_argument("--full", action="store_true", help="输出完整 Markdown 内容")

    p_upload = sub.add_parser("upload-file", help="上传文件到飞书云盘")
    p_upload.add_argument("local_path")
    p_upload.add_argument("file_name")
    p_upload.add_argument("--folder-token", default=None)

    p_update = sub.add_parser("update-topic-status", help="更新选题状态")
    p_update.add_argument("record_id")
    p_update.add_argument("status")

    p_coze = sub.add_parser("call-coze", help="调用 Coze 工作流写入文案库")
    p_coze.add_argument("--title", required=True)
    p_coze.add_argument("--digest", required=True)
    p_coze.add_argument("--type", required=True)
    p_coze.add_argument("--content-file", required=True)
    p_coze.add_argument("--image-prompt", required=True)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    # ── 配置管理命令 ──
    if args.command == "init":
        interactive_config()
        return
    elif args.command == "check-config":
        check_config()
        return

    # ── 需要认证的命令 ──
    config = load_config()
    if not is_config_valid(config):
        print("❌ 配置不完整，请先运行初始化:")
        print(f"   python3 {sys.argv[0]} init")
        sys.exit(1)

    if args.command == "get-token":
        token = get_tenant_token()
        print(token)

    elif args.command == "get-topic":
        token = get_tenant_token()
        if args.detail:
            get_topic_detail(token, config, args.keyword)
        else:
            get_topics(token, config, keyword=args.keyword, status=args.status)

    elif args.command == "get-articles":
        token = get_tenant_token()
        if args.full:
            get_article_full_content(token, config, args.keyword or "")
        else:
            get_articles(token, config, category=args.category, keyword=args.keyword)

    elif args.command == "upload-file":
        token = get_tenant_token()
        folder_token = args.folder_token or config.get("UPLOAD_FOLDER_TOKEN", DEFAULTS["UPLOAD_FOLDER_TOKEN"])
        upload_file(token, config, args.local_path, args.file_name, folder_token)

    elif args.command == "update-topic-status":
        token = get_tenant_token()
        update_topic_status(token, config, args.record_id, args.status)

    elif args.command == "call-coze":
        call_coze_workflow(config, args.title, args.digest, args.type, args.content_file, args.image_prompt)


if __name__ == "__main__":
    main()
