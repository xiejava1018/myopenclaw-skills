#!/usr/bin/env python3
"""image-upload: 上传图片到图床（七牛/GitHub）+ 改写博客文章图片链接。

子命令：
  upload <file...>   上传图片，返回 URL（原语）
  migrate <post.md>  扫描文章图片引用，上传 + 原地改写为图床 URL
  init               从 PicGo data.json 一次性导入七牛配置到 .env
  list               查看 manifest（本地文件↔图床 URL 账本）
"""
import argparse
import json
import sys
from pathlib import Path

from config import load_config, Config
from keys import make_key
from manifest import Manifest, sha256_of_file
from rewriter import find_image_links, resolve_local_path, apply_replacements
from providers import get_uploader, supported_backends

SKILL_DIR = Path(__file__).resolve().parent
MANIFEST_PATH = SKILL_DIR / "manifest.json"
PICGO_PATH = Path.home() / "Library/Application Support/picgo/data.json"


def _resolve_backend(args, cfg: Config) -> str:
    backend = args.backend or cfg.default_backend
    if backend not in supported_backends():
        print(f"[error] 不支持的后端: {backend}，支持: {supported_backends()}", file=sys.stderr)
        sys.exit(2)
    missing = cfg.validate(backend)
    if missing:
        print(f"[error] 后端 {backend} 缺失配置: {', '.join(missing)}（请在 .env 填写）", file=sys.stderr)
        sys.exit(2)
    return backend


def cmd_upload(args, cfg: Config) -> int:
    backend = _resolve_backend(args, cfg)
    uploader = get_uploader(backend, cfg)
    prefix = cfg.prefix_for(backend)
    man = Manifest(MANIFEST_PATH)
    results = []
    for f in args.files:
        p = Path(f).expanduser()
        if not p.is_absolute():
            p = Path.cwd() / p
        p = p.resolve()
        if not p.exists():
            print(f"[skip] 文件不存在: {f}", file=sys.stderr)
            results.append({"file": f, "url": None, "status": "missing", "backend": backend})
            continue
        h = sha256_of_file(p)
        entry = man.get(h, backend)
        if entry:
            url, status = entry["url"], "manifest-hit"
        else:
            key = make_key(prefix, str(p))
            res = uploader.upload(str(p), key)
            man.put(h, backend, str(p), res.key, res.url)
            man.save()
            url, status = res.url, "uploaded"
        results.append({"file": str(p), "url": url, "status": status, "backend": backend})

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        for r in results:
            print(f"{r['file']} -> {r['url'] or '-'}  [{r['status']}]")
    return 0


def cmd_migrate(args, cfg: Config) -> int:
    backend = _resolve_backend(args, cfg)
    post = Path(args.post).expanduser().resolve()
    if not post.exists():
        print(f"[error] 文章不存在: {post}", file=sys.stderr)
        return 1
    source_dir = post.parent
    vault_roots = [source_dir]
    if args.vault_root:
        vr = Path(args.vault_root).expanduser().resolve()
        vault_roots += [vr, vr / "assets", vr / "assets/blog"]

    prefix = cfg.prefix_for(backend)
    post_slug = post.stem
    man = Manifest(MANIFEST_PATH)
    uploader = None if args.dry_run else get_uploader(backend, cfg)

    md = post.read_text(encoding="utf-8")
    refs = find_image_links(md)
    plan = []  # [(ImageRef, url)]
    counts = {"uploaded": 0, "manifest_hit": 0, "url_skip": 0, "missing": 0}

    for ref in refs:
        if ref.is_url:
            counts["url_skip"] += 1
            continue
        p = resolve_local_path(ref, source_dir, vault_roots)
        if p is None:
            counts["missing"] += 1
            print(f"[warn] 找不到本地图: {ref.raw_text}", file=sys.stderr)
            continue
        h = sha256_of_file(p)
        entry = man.get(h, backend)
        if entry:
            plan.append((ref, entry["url"]))
            counts["manifest_hit"] += 1
            continue
        key = make_key(prefix, str(p), post_slug)
        if args.dry_run:
            print(f"[dry-run] 将上传 {p.name} -> {backend}:{key}")
            counts["uploaded"] += 1
            continue
        res = uploader.upload(str(p), key)
        man.put(h, backend, str(p), res.key, res.url)
        man.save()
        plan.append((ref, res.url))
        counts["uploaded"] += 1

    if args.dry_run:
        print(f"[dry-run] 计划上传 {counts['uploaded']}，manifest命中 {counts['manifest_hit']}，"
              f"已是URL跳过 {counts['url_skip']}，缺失 {counts['missing']}（未改写文件）")
        return 0

    if plan:
        new_md = apply_replacements(md, plan)
        if new_md != md:
            post.write_text(new_md, encoding="utf-8")
    print(f"[done] 改写 {len(plan)} 处，上传 {counts['uploaded']}，"
          f"manifest命中 {counts['manifest_hit']}，已是URL跳过 {counts['url_skip']}，缺失 {counts['missing']}")
    return 0


def cmd_init(args, cfg: Config) -> int:
    if not PICGO_PATH.exists():
        print(f"[error] 未找到 PicGo 配置: {PICGO_PATH}", file=sys.stderr)
        print("        请手动 cp .env.example .env 并填写七牛配置。", file=sys.stderr)
        return 1
    data = json.loads(PICGO_PATH.read_text(encoding="utf-8"))
    q = (data.get("picBed") or {}).get("qiniu")
    if not q:
        print("[error] PicGo 配置里没有七牛段 (picBed.qiniu)", file=sys.stderr)
        return 1

    new_vals = {
        "DEFAULT_BACKEND": "qiniu",
        "QINIU_ACCESS_KEY": q.get("accessKey", ""),
        "QINIU_SECRET_KEY": q.get("secretKey", ""),
        "QINIU_BUCKET": q.get("bucket", ""),
        "QINIU_DOMAIN": q.get("url", ""),
        "QINIU_AREA": q.get("area", "z0"),
        "QINIU_PATH": q.get("path", "") or "blog",
    }
    env_file = SKILL_DIR / ".env"
    keep = {}
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if s and "=" in s and not s.startswith("#"):
                k, _, v = s.partition("=")
                keep[k.strip()] = v
    keep.update(new_vals)

    blocks = [
        "DEFAULT_BACKEND=" + keep["DEFAULT_BACKEND"], "",
        "# 七牛（从 PicGo 导入）",
        "QINIU_ACCESS_KEY=" + keep["QINIU_ACCESS_KEY"],
        "QINIU_SECRET_KEY=" + keep["QINIU_SECRET_KEY"],
        "QINIU_BUCKET=" + keep["QINIU_BUCKET"],
        "QINIU_DOMAIN=" + keep["QINIU_DOMAIN"],
        "QINIU_AREA=" + keep["QINIU_AREA"],
        "QINIU_PATH=" + keep["QINIU_PATH"], "",
        "# GitHub（按需填写）",
        "GH_TOKEN=" + keep.get("GH_TOKEN", ""),
        "GH_OWNER=" + keep.get("GH_OWNER", ""),
        "GH_REPO=" + keep.get("GH_REPO", ""),
        "GH_BRANCH=" + keep.get("GH_BRANCH", "main"),
        "GH_PATH=" + keep.get("GH_PATH", "blog"),
        "GH_DOMAIN=" + keep.get("GH_DOMAIN", ""),
    ]
    env_file.write_text("\n".join(blocks) + "\n", encoding="utf-8")
    try:
        env_file.chmod(0o600)
    except OSError:
        pass
    print(f"[done] 已从 PicGo 导入七牛配置到 {env_file}")
    print(f"       bucket={new_vals['QINIU_BUCKET']}, domain={new_vals['QINIU_DOMAIN']}, area={new_vals['QINIU_AREA']}")
    print("       PicGo 此后可卸载，skill 已自包含。")
    return 0


def cmd_list(args, cfg: Config) -> int:
    man = Manifest(MANIFEST_PATH)
    data = man.data
    if not data:
        print("(manifest 为空)")
        return 0
    for h, entry in data.items():
        print(f"{h[:12]}  {entry.get('local', '?')}")
        for b in ("qiniu", "github"):
            if b in entry:
                print(f"           {b}: {entry[b].get('url')}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="image-upload", description="图床上传 + 博客图片链接改写")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_up = sub.add_parser("upload", help="上传图片，返回 URL")
    p_up.add_argument("files", nargs="+")
    p_up.add_argument("--backend", choices=supported_backends())
    p_up.add_argument("--json", action="store_true", help="结构化 JSON 输出")
    p_up.set_defaults(func=cmd_upload)

    p_mig = sub.add_parser("migrate", help="扫描文章图片引用，上传 + 改写")
    p_mig.add_argument("post")
    p_mig.add_argument("--backend", choices=supported_backends())
    p_mig.add_argument("--dry-run", action="store_true", help="只打印计划，不传不改")
    p_mig.add_argument("--vault-root", default=None, help="vault 根目录（解析 ![[...]] 时优先搜索 assets/assets/blog）")
    p_mig.set_defaults(func=cmd_migrate)

    p_init = sub.add_parser("init", help="从 PicGo data.json 导入七牛配置到 .env")
    p_init.set_defaults(func=cmd_init)

    p_list = sub.add_parser("list", help="查看 manifest")
    p_list.set_defaults(func=cmd_list)

    args = ap.parse_args(argv)
    cfg = load_config()
    return args.func(args, cfg)


if __name__ == "__main__":
    sys.exit(main())
