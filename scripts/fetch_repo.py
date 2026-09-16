#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
拉取一个开源仓库并抽出「够用于对标分析」的骨架信息，避免把整个仓库读进上下文。

输出内容：目录树、README 正文、依赖清单、技术栈推断、业务关键词命中文件、最近提交。

两条获取通道（自动降级）：
  A. git clone --depth 1  —— 正常网络环境最快，能拿到提交信息
  B. 归档包下载（tarball/zip）—— 在受限网络（公司代理、沙箱拦截 git 协议）下可用

用法：
    python3 fetch_repo.py https://github.com/foo/bar --out /tmp/bar.json
    python3 fetch_repo.py cnb.cool/foo/bar --grep "凭证,库存,课消" --tree-depth 3
    python3 fetch_repo.py gitee.com/foo/bar --method archive --keep

说明：
- 默认分析完删除本地副本，用 --keep 保留。
- 失败不抛异常，JSON 里给出 status=failed 与原因，由上层改用 WebFetch 抓仓库页面。
"""

import argparse
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime

UA = "Mozilla/5.0 (open-source-research)"
TIMEOUT = 60

NOISE_DIRS = {
    ".git", "node_modules", "vendor", "build", "dist", "out", "target",
    ".gradle", ".idea", ".vscode", "__pycache__", "Pods", ".dart_tool",
    ".next", ".nuxt", "coverage", "bin", "obj", ".terraform", ".venv", "venv",
}

MANIFESTS = [
    "package.json", "pom.xml", "build.gradle", "build.gradle.kts", "go.mod",
    "Cargo.toml", "pyproject.toml", "requirements.txt", "pubspec.yaml",
    "composer.json", "Gemfile", "Podfile", "CMakeLists.txt", "Makefile",
    "docker-compose.yml", "docker-compose.yaml", "Dockerfile", ".cnb.yml",
    "application.yml", "application.yaml", "appsettings.json",
]

README_NAMES = ["README.md", "readme.md", "README.MD", "README.rst", "README.txt",
                "README.zh-CN.md", "README_CN.md", "README-zh.md", "docs/README.md"]

STACK_RULES = [
    ("pubspec.yaml", "Flutter/Dart"), ("package.json", "Node.js/前端"),
    ("pom.xml", "Java/Maven"), ("build.gradle", "Java/Gradle"),
    ("go.mod", "Go"), ("Cargo.toml", "Rust"), ("pyproject.toml", "Python"),
    ("requirements.txt", "Python"), ("composer.json", "PHP"),
    ("Gemfile", "Ruby"), ("CMakeLists.txt", "C/C++"),
]
STACK_DIR_RULES = [("android/", "Android"), ("ios/", "iOS"), ("cmd/", "Go")]

CANDIDATE_BRANCHES = ["main", "master", "develop", "dev"]


def run(cmd, cwd=None, timeout=180):
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        return 124, "", "命令超时（>%ds）" % timeout
    except Exception as e:
        return 1, "", "%s: %s" % (type(e).__name__, e)


def parse_slug(url):
    """从 URL 或 slug 解析 (platform, owner/repo, web_url)。"""
    u = re.sub(r"^https?://", "", url.strip().rstrip("/"))
    u = re.sub(r"\.git$", "", u)
    parts = [p for p in u.split("/") if p]
    # 坑（2026-09-10 修复）：直接传 "owner/repo" 这种裸 slug 会走到下面按 host 判断的分支，
    # 结果被判成 unknown。裸两段式 slug 默认按 GitHub 处理。
    if len(parts) == 2 and "." not in parts[0]:
        return "github", "/".join(parts), "https://github.com/%s" % "/".join(parts)
    if len(parts) < 2:
        return "unknown", "", ""
    host, slug = parts[0].lower(), "/".join(parts[1:3])
    if "github" in host:
        return "github", slug, "https://github.com/%s" % slug
    if "cnb.cool" in host:
        return "cnb", slug, "https://cnb.cool/%s" % slug
    if "gitee" in host:
        return "gitee", slug, "https://gitee.com/%s" % slug
    return "unknown", slug, "https://%s/%s" % (host, slug)


def http_get(url, timeout=TIMEOUT):
    """返回 (bytes_or_None, err_msg)。urllib 会自动读取 http_proxy/https_proxy 环境变量。"""
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read(), None
    except Exception as e:
        return None, "%s: %s" % (type(e).__name__, e)


def archive_urls(platform, slug):
    """按平台生成候选归档地址（按分支逐个尝试）。"""
    name = slug.split("/")[-1]
    urls = []
    for br in CANDIDATE_BRANCHES:
        if platform == "github":
            urls.append((br, "https://codeload.github.com/%s/tar.gz/refs/heads/%s" % (slug, br)))
        elif platform == "cnb":
            urls.append((br, "https://cnb.cool/%s/-/archive/%s/%s.tar.gz" % (slug, br, name)))
        elif platform == "gitee":
            urls.append((br, "https://gitee.com/%s/repository/archive/%s.zip" % (slug, br)))
    return urls


def _safe_extract_tar(tf, dest):
    os.makedirs(dest, exist_ok=True)
    for m in tf.getmembers():
        target = os.path.realpath(os.path.join(dest, m.name))
        if not target.startswith(os.path.realpath(dest) + os.sep):
            continue  # 防 zip-slip
        tf.extract(m, dest)


def _safe_extract_zip(zf, dest):
    os.makedirs(dest, exist_ok=True)
    for m in zf.namelist():
        target = os.path.realpath(os.path.join(dest, m))
        if not target.startswith(os.path.realpath(dest) + os.sep):
            continue
        zf.extract(m, dest)


def download_archive(platform, slug, dest):
    """尝试下载并解压归档包，成功返回 (branch, err_None)。"""
    errors = []
    for br, url in archive_urls(platform, slug):
        raw, err = http_get(url)
        if not raw or len(raw) < 100:
            errors.append("%s → %s" % (br, err or "内容为空"))
            continue
        try:
            if url.endswith(".zip"):
                with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                    _safe_extract_zip(zf, dest)
            else:
                with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as tf:
                    _safe_extract_tar(tf, dest)
        except Exception as e:
            errors.append("%s → 解压失败 %s" % (br, e))
            shutil.rmtree(dest, ignore_errors=True)
            continue
        return br, None
    return "", "归档下载全部失败： " + " | ".join(errors[:4])


def unwrap_single_root(dest):
    """归档包通常多一层 xxx-main/ 目录，摊平掉。"""
    entries = [e for e in os.listdir(dest) if not e.startswith(".")]
    if len(entries) == 1 and os.path.isdir(os.path.join(dest, entries[0])):
        root = os.path.join(dest, entries[0])
        tmp = dest + "__unwrap"
        os.rename(root, tmp)
        for e in os.listdir(tmp):
            shutil.move(os.path.join(tmp, e), os.path.join(dest, e))
        shutil.rmtree(tmp, ignore_errors=True)


def build_tree(root, max_depth, max_files=800):
    lines, count = [], 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in NOISE_DIRS and not d.startswith("."))
        rel = os.path.relpath(dirpath, root)
        depth = 0 if rel == "." else rel.count(os.sep) + 1
        if depth > max_depth:
            dirnames[:] = []
            continue
        indent = "  " * depth
        if rel != ".":
            lines.append("%s%s/" % (indent, os.path.basename(dirpath)))
        for fn in sorted(filenames):
            if fn.startswith("."):
                continue
            lines.append("%s  %s" % (indent, fn))
            count += 1
            if count >= max_files:
                lines.append("... （文件数超过 %d，已截断）" % max_files)
                return "\n".join(lines)
    return "\n".join(lines)


def _find_upto(root, filename, max_depth=3):
    """在 max_depth 层内查找文件是否存在（清单文件常藏在子目录里）。"""
    base = root.rstrip(os.sep)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in NOISE_DIRS and not d.startswith(".")]
        rel = os.path.relpath(dirpath, base)
        depth = 0 if rel == "." else rel.count(os.sep) + 1
        if depth > max_depth:
            dirnames[:] = []
            continue
        if filename in filenames:
            return os.path.join(dirpath, filename)
    return ""


def detect_stack(root, tree_text):
    stack = []
    for fname, tag in STACK_RULES:
        if os.path.exists(os.path.join(root, fname)) or _find_upto(root, fname) or ("/" + fname) in tree_text:
            stack.append(tag)
    for d, tag in STACK_DIR_RULES:
        if os.path.isdir(os.path.join(root, d)):
            stack.append(tag)
    return sorted(set(stack))


def read_head(path, limit):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read(limit)
    except Exception:
        return ""


def grep_keywords(root, keywords, max_hits=15):
    """搜业务关键词命中的文件路径，用于定位业务模块代码位置。"""
    hits = {}
    text_ext = re.compile(
        r"\.(md|dart|ts|tsx|js|jsx|py|java|go|rs|kt|php|rb|vue|sql|yaml|yml|json)$", re.I)
    for kw in keywords:
        found = []
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in NOISE_DIRS and not d.startswith(".")]
            for fn in filenames:
                if not text_ext.search(fn):
                    continue
                fp = os.path.join(dirpath, fn)
                try:
                    if os.path.getsize(fp) > 2_000_000:
                        continue
                    with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                        if kw in f.read():
                            found.append(os.path.relpath(fp, root))
                except Exception:
                    continue
                if len(found) >= max_hits:
                    break
            if len(found) >= max_hits:
                break
        hits[kw] = found
    return hits


def main():
    ap = argparse.ArgumentParser(description="拉取开源仓库并抽取骨架信息")
    ap.add_argument("repo", help="仓库 URL 或 slug（github.com/a/b、cnb.cool/a/b、gitee.com/a/b）")
    ap.add_argument("--dest", default="", help="本地落地目录，默认 /tmp/open-source-research/<slug>")
    ap.add_argument("--out", default="", help="结果 JSON 输出路径，省略则打到标准输出")
    ap.add_argument("--depth", type=int, default=1, help="git clone 深度，默认 1")
    ap.add_argument("--method", choices=["auto", "git", "archive"], default="auto",
                    help="获取方式：auto=先 git 后归档；git=只用 git；archive=只下载归档包")
    ap.add_argument("--tree-depth", type=int, default=2, help="目录树层级，默认 2")
    ap.add_argument("--readme-limit", type=int, default=8000, help="README 读取字符上限")
    ap.add_argument("--grep", default="", help="业务关键词，逗号分隔，用于定位业务模块文件")
    ap.add_argument("--keep", action="store_true", help="保留本地副本（默认分析完删除）")
    args = ap.parse_args()

    platform, slug, web_url = parse_slug(args.repo)
    if platform == "unknown":
        print("无法识别平台：%s" % args.repo, file=sys.stderr)
        sys.exit(2)

    dest = args.dest or os.path.join("/tmp", "open-source-research", slug.replace("/", "__"))
    result = {
        "platform": platform, "slug": slug, "url": web_url,
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
        "status": "ok", "error": "", "method": "", "branch": "",
    }

    shutil.rmtree(dest, ignore_errors=True)
    os.makedirs(os.path.dirname(dest), exist_ok=True)

    # ---- 通道 A：git clone
    if args.method in ("auto", "git"):
        code, out, err = run(["git", "clone", "--depth", str(args.depth),
                              "%s.git" % web_url, dest])
        if code == 0:
            result["method"] = "git-clone"
            c2, o2, _ = run(["git", "log", "-1", "--format=%H|%ci|%s"], cwd=dest)
            if c2 == 0 and o2.strip():
                h, date, subj = (o2.strip().split("|", 2) + ["", ""])[:3]
                result["last_commit"] = {"sha": h[:12], "date": date, "subject": subj}
            c3, o3, _ = run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=dest)
            result["branch"] = o3.strip() if c3 == 0 else ""
        else:
            git_err = (err or out).strip()[:300]
            if args.method == "git":
                result.update(status="failed", method="git-clone",
                              error="git clone 失败：%s" % git_err)
                print(json.dumps(result, ensure_ascii=False, indent=2))
                sys.exit(0)
            shutil.rmtree(dest, ignore_errors=True)

    # ---- 通道 B：归档包
    if not result["method"]:
        os.makedirs(dest, exist_ok=True)
        br, err = download_archive(platform, slug, dest)
        if err:
            result.update(status="failed", method="archive", error=err)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            sys.exit(0)
        result["method"] = "archive"
        result["branch"] = br
        unwrap_single_root(dest)

    tree = build_tree(dest, args.tree_depth)
    result["tree"] = tree
    result["tech_stack"] = detect_stack(dest, tree)

    # README
    readme_path, readme_text = "", ""
    for name in README_NAMES:
        p = os.path.join(dest, name)
        if os.path.isfile(p):
            readme_path, readme_text = name, read_head(p, args.readme_limit)
            break
    if not readme_text:
        for dirpath, dirnames, filenames in os.walk(dest):
            dirnames[:] = [d for d in dirnames if d not in NOISE_DIRS]
            for fn in filenames:
                if fn.lower().startswith("readme") and fn.lower().endswith((".md", ".rst", ".txt")):
                    p = os.path.join(dirpath, fn)
                    readme_path = os.path.relpath(p, dest)
                    readme_text = read_head(p, args.readme_limit)
                    break
            if readme_text:
                break
    result["readme_file"] = readme_path
    result["readme"] = readme_text

    manifests = {}
    for m in MANIFESTS:
        p = os.path.join(dest, m)
        if not os.path.isfile(p):
            p = _find_upto(dest, m, max_depth=2)
        if p and os.path.isfile(p):
            manifests[os.path.relpath(p, dest)] = read_head(p, 3000)
    result["manifests"] = manifests

    if args.grep:
        kws = [k.strip() for k in args.grep.split(",") if k.strip()]
        result["keyword_hits"] = grep_keywords(dest, kws)

    result["file_count_estimate"] = sum(
        1 for dp, dn, fns in os.walk(dest)
        if not any(nd in dp for nd in NOISE_DIRS) for _ in fns)

    if args.keep:
        result["local_path"] = dest
    else:
        shutil.rmtree(dest, ignore_errors=True)
        result["local_path"] = "(已清理)"

    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
        print("已写入 %s（%s）" % (args.out, result["method"]), file=sys.stderr)
    else:
        print(text)


if __name__ == "__main__":
    main()
