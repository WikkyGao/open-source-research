#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
三平台开源仓库检索（GitHub / CNB / Gitee），分层降级，输出统一结构 JSON。

设计原则：
1. API 优先：GitHub 优先复用已登录的 gh CLI；CNB、Gitee 有 token 时走官方 API。
2. 网页兜底：无 token 或 API 失败时，不静默失败，而是输出 fallback_queries，
   交由上层 Agent 用 WebSearch / WebFetch 完成检索。
3. 结果归一化：三平台字段名不同，统一为同一套 key，方便后续生成对照报告。

用法：
    python3 search_oss.py --query "开源ERP 库存 凭证" --limit 10
    python3 search_oss.py -q "flutter offline erp" --platforms github,cnb --lang dart --min-stars 200 --out /tmp/oss.json
    python3 search_oss.py -q "crm" --keywords "商机,赢单,跟进" --out /tmp/oss.json

环境变量 / token 文件（可选，配了就自动升级为 API 通道）：
    GITHUB_TOKEN / GH_TOKEN   GitHub PAT（gh CLI 已登录时可省略）
    CNB_TOKEN                 CNB 访问令牌（cnb.cool → 设置 → 访问令牌，需 repo-basic-info:r）
    GITEE_TOKEN               Gitee 私人令牌（Gitee → 设置 → 私人令牌）

脚本会自动读取以下 token 文件（按优先级，已存在于环境变量的不会被覆盖）：
    ~/.workbuddy/oss-tokens.env
    ~/.config/open-source-research/tokens.env
    --token-file 指定的文件（最高优先级）
"""

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

UA = "Mozilla/5.0 (open-source-research)"
TIMEOUT = 30  # Gitee 走代理时响应较慢，不要用太小的超时

# 技能根目录（scripts/ 的上一级）
SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 自动加载的 token 文件路径，按优先级从高到低
# 1) 技能目录内的 .env —— 主位置，随技能走，已被 .gitignore 忽略
# 2) 用户级全局文件 —— 技能被分发到别处时的兜底
# 3) XDG 配置目录
DEFAULT_TOKEN_FILES = [
    os.path.join(SKILL_ROOT, ".env"),
    os.path.expanduser("~/.workbuddy/oss-tokens.env"),
    os.path.expanduser("~/.config/open-source-research/tokens.env"),
]

# 占位符未替换的标记：命中则视为未配置，避免把模板占位符当成真 token
PLACEHOLDER_MARKS = ("{{", "<你的", "<your", "xxxx", "TODO")


# ---------------------------------------------------------------- HTTP 基础

def http_json(url, headers=None, timeout=TIMEOUT):
    """GET 一个 JSON 接口，返回 (status_code, data_or_None, error_msg)。"""
    hdrs = {"User-Agent": UA, "Accept": "application/json"}
    hdrs.update(headers or {})
    req = urllib.request.Request(url, headers=hdrs, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
            status = resp.getcode()
    except urllib.error.HTTPError as e:
        return e.code, None, "HTTP %s %s" % (e.code, e.reason)
    except Exception as e:  # 超时 / 连接失败 / DNS
        return 0, None, "%s: %s" % (type(e).__name__, e)
    try:
        return status, json.loads(raw), None
    except Exception:
        return status, None, "响应不是合法 JSON，前 200 字符：%s" % raw[:200]


def load_token_files(extra=None):
    """从 token 文件加载凭证到环境变量。已存在的环境变量优先，不会被覆盖。

    文件格式：每行 KEY=value，支持 export 前缀、引号包裹、# 注释。
    """
    loaded = []
    for path in ([extra] if extra else []) + DEFAULT_TOKEN_FILES:
        if not path or not os.path.isfile(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                for lineno, line in enumerate(f, 1):
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k = k.strip()
                    if k.startswith("export "):
                        k = k[len("export "):].strip()
                    v = v.strip().strip('"').strip("'")
                    if not k or not v:
                        continue
                    if any(m in v for m in PLACEHOLDER_MARKS):
                        continue  # 占位符未替换，视为未配置
                    if os.environ.get(k):
                        continue  # 环境变量优先
                    os.environ[k] = v
                    loaded.append((k, path))
        except Exception as e:
            print("读取 token 文件失败 %s：%s" % (path, e), file=sys.stderr)
    return loaded


def gh_cli(path):
    """用已登录的 gh CLI 调 API，成功返回 dict，失败返回 None。"""
    try:
        p = subprocess.run(
            ["gh", "api", path],
            capture_output=True, text=True, timeout=TIMEOUT,
        )
    except Exception:
        return None
    if p.returncode != 0:
        return None
    try:
        return json.loads(p.stdout)
    except Exception:
        return None


def pick(d, *keys, default=None):
    """按候选 key 依次取值，适配不同平台字段命名。"""
    for k in keys:
        if isinstance(d, dict) and d.get(k) not in (None, ""):
            return d[k]
    return default


def norm_repo(raw, platform):
    """归一化为统一结构。"""
    if platform == "github":
        return {
            "platform": "github",
            "full_name": pick(raw, "full_name"),
            "url": pick(raw, "html_url"),
            "description": (pick(raw, "description") or "")[:400],
            "stars": pick(raw, "stargazers_count", default=0),
            "forks": pick(raw, "forks_count", default=0),
            "language": pick(raw, "language", default=""),
            "license": (pick(raw, "license") or {}).get("spdx_id") if isinstance(pick(raw, "license"), dict) else pick(raw, "license"),
            "updated_at": pick(raw, "pushed_at", "updated_at", default=""),
            "topics": pick(raw, "topics", default=[]),
            "archived": bool(pick(raw, "archived", default=False)),
            "open_issues": pick(raw, "open_issues_count", default=0),
        }
    if platform == "cnb":
        slug = pick(raw, "path", "full_name", "name", default="")
        return {
            "platform": "cnb",
            "full_name": slug,
            "url": pick(raw, "web_url") or ("https://cnb.cool/%s" % slug if slug else ""),
            "description": (pick(raw, "description") or "")[:400],
            "stars": pick(raw, "star_count", "stars", default=0),
            "forks": pick(raw, "fork_count", default=0),
            "language": pick(raw, "language", default="") or "",
            "license": pick(raw, "license", default=""),
            "updated_at": pick(raw, "last_updated_at", "updated_at", default=""),
            "topics": pick(raw, "topics", default=[]) or [],
            "archived": False,
            "open_issues": pick(raw, "open_issue_count", default=0),
        }
    # gitee
    return {
        "platform": "gitee",
        "full_name": pick(raw, "full_name", "path_with_namespace", default=""),
        "url": pick(raw, "html_url", "url", default=""),
        "description": (pick(raw, "description", "human_name") or "")[:400],
        "stars": pick(raw, "stargazers_count", "star_count", "stars_count", default=0),
        "forks": pick(raw, "forks_count", "forks", default=0),
        "language": pick(raw, "language", default="") or "",
        "license": pick(raw, "license", default="") or "",
        "updated_at": pick(raw, "pushed_at", "updated_at", "last_push_at", default=""),
        "topics": pick(raw, "topics", default=[]) or [],
        "archived": bool(pick(raw, "archived", default=False)),
        "open_issues": pick(raw, "open_issues_count", default=0),
    }


# ---------------------------------------------------------------- 各平台检索

def search_github(query, limit, lang, min_stars, keywords):
    """GitHub：优先 gh CLI（已登录，配额高），失败退回匿名 API。"""
    q_parts = [query]
    if keywords:
        q_parts.extend(keywords[:3])
    if lang:
        q_parts.append("language:%s" % lang)
    if min_stars:
        q_parts.append("stars:>%d" % min_stars)
    q = " ".join(q_parts)
    path = "search/repositories?q=%s&sort=stars&order=desc&per_page=%d" % (
        urllib.parse.quote(q), min(limit, 100))

    data = gh_cli(path)
    channel = "gh-cli"
    err = None
    if data is None:
        data, err = None, "gh CLI 不可用或未登录"
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        headers = {"Authorization": "Bearer %s" % token} if token else {}
        status, data2, err2 = http_json("https://api.github.com/" + path, headers)
        if data2 is not None:
            data, channel, err = data2, "api.github.com", None
        else:
            err = "gh CLI 与匿名 API 均失败（%s；%s）" % (err, err2)

    if data is None:
        return {"status": "failed", "channel": channel, "count": 0, "results": [],
                "note": err or "未知错误",
                "fallback_queries": ["site:github.com " + query]}

    items = data.get("items", []) if isinstance(data, dict) else []
    return {"status": "ok", "channel": channel, "count": len(items),
            "results": [norm_repo(r, "github") for r in items[:limit]],
            "note": "", "fallback_queries": []}


def search_cnb(query, limit, lang, min_stars, keywords):
    """CNB：需要访问令牌，无令牌直接降级。"""
    token = os.environ.get("CNB_TOKEN")
    if not token:
        return {
            "status": "needs_token", "channel": "none", "count": 0, "results": [],
            "note": "未设置 CNB_TOKEN，CNB 开放 API 全部要求 Bearer 认证（401）。"
                    "到 cnb.cool → 设置 → 访问令牌 创建令牌（需 repo-basic-info:r 权限）后导出环境变量即可自动启用。",
            "fallback_queries": ["site:cnb.cool " + query, "cnb.cool 开源 " + query],
        }
    qs = urllib.parse.urlencode({
        "key": query, "order_by": "stars", "desc": "true", "topN": min(limit, 100),
    })
    url = "https://api.cnb.cool/search/public-repos?" + qs
    status, data, err = http_json(url, {
        "Authorization": "Bearer %s" % token,
        "Accept": "application/vnd.cnb.api+json",
    })
    if data is None:
        return {"status": "failed", "channel": "api.cnb.cool", "count": 0, "results": [],
                "note": "CNB API 调用失败：%s" % err,
                "fallback_queries": ["site:cnb.cool " + query]}
    items = data if isinstance(data, list) else (data.get("data") or [])
    out = [norm_repo(r, "cnb") for r in items]
    if min_stars:
        out = [r for r in out if (r["stars"] or 0) >= min_stars]
    if lang:
        out = [r for r in out if lang.lower() in (r["language"] or "").lower()]
    return {"status": "ok", "channel": "api.cnb.cool", "count": len(out),
            "results": out[:limit], "note": "", "fallback_queries": []}


def search_gitee(query, limit, lang, min_stars, keywords):
    """Gitee：匿名调用返回空数组，必须带 access_token 才有结果。"""
    token = os.environ.get("GITEE_TOKEN")
    params = {"q": query, "sort": "stars_count", "order": "desc", "per_page": min(limit, 100)}
    if lang:
        params["language"] = lang
    if token:
        params["access_token"] = token
    url = "https://gitee.com/api/v5/search/repositories?" + urllib.parse.urlencode(params)

    status, data, err = http_json(url, {})
    if data is None:
        return {"status": "failed", "channel": "gitee-api", "count": 0, "results": [],
                "note": "Gitee API 调用失败：%s" % err,
                "fallback_queries": ["site:gitee.com " + query, "gitee 开源 " + query]}

    items = data if isinstance(data, list) else []
    if not items and not token:
        return {
            "status": "needs_token", "channel": "gitee-api", "count": 0, "results": [],
            "note": "Gitee API 可达但未登录时仓库搜索返回空数组。设置 GITEE_TOKEN（Gitee → 设置 → 私人令牌）后重试。",
            "fallback_queries": ["site:gitee.com " + query, "gitee 开源 " + query,
                                 "码云 开源项目 " + query],
        }

    out = [norm_repo(r, "gitee") for r in items]
    if min_stars:
        out = [r for r in out if (r["stars"] or 0) >= min_stars]
    return {"status": "ok", "channel": "gitee-api", "count": len(out),
            "results": out[:limit], "note": "", "fallback_queries": []}


SEARCHERS = {"github": search_github, "cnb": search_cnb, "gitee": search_gitee}


# ---------------------------------------------------------------- 入口

def main():
    ap = argparse.ArgumentParser(description="三平台开源仓库检索（GitHub / CNB / Gitee）")
    ap.add_argument("-q", "--query", required=True, help="检索主关键词，建议用英文或中英混合")
    ap.add_argument("--keywords", default="", help="补充关键词，逗号分隔，最多取 3 个")
    ap.add_argument("--platforms", default="github,cnb,gitee", help="检索平台，逗号分隔")
    ap.add_argument("--limit", type=int, default=10, help="每平台返回条数，默认 10")
    ap.add_argument("--lang", default="", help="语言过滤，如 python / java / dart / go")
    ap.add_argument("--min-stars", type=int, default=0, help="最低 star 数过滤")
    ap.add_argument("--out", default="", help="结果 JSON 输出路径，省略则打到标准输出")
    ap.add_argument("--token-file", default="", help="额外指定 token 文件，优先级最高")
    args = ap.parse_args()

    loaded = load_token_files(args.token_file)
    for k, p in loaded:
        print("[凭证] 已从 %s 加载 %s" % (p, k), file=sys.stderr)

    keywords = [k.strip() for k in args.keywords.split(",") if k.strip()]
    platforms = [p.strip() for p in args.platforms.split(",") if p.strip() in SEARCHERS]

    payload = {
        "query": args.query,
        "keywords": keywords,
        "filters": {"lang": args.lang, "min_stars": args.min_stars, "limit": args.limit},
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "platforms": {},
        "results": [],
        "pending_web_fallback": [],
    }

    for p in platforms:
        t0 = time.time()
        res = SEARCHERS[p](args.query, args.limit, args.lang, args.min_stars, keywords)
        res["elapsed_sec"] = round(time.time() - t0, 1)
        payload["platforms"][p] = res
        payload["results"].extend(res["results"])
        if res["status"] in ("needs_token", "failed") and res["fallback_queries"]:
            payload["pending_web_fallback"].append({
                "platform": p, "reason": res["status"], "queries": res["fallback_queries"],
            })
        # 控制台进度（走 stderr，不污染 stdout 的 JSON）
        print("[%s] %s：%s 条（%.1fs）%s" % (
            p, res["status"], res["count"], res["elapsed_sec"],
            ("— " + res["note"]) if res["note"] else ""), file=sys.stderr)

    payload["results"].sort(key=lambda r: (r.get("stars") or 0), reverse=True)

    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
        print("已写入 %s" % args.out, file=sys.stderr)
    else:
        print(text)

    if payload["pending_web_fallback"]:
        print("\n⚠️ 以下平台需要网页兜底检索（把 queries 交给 WebSearch/WebFetch）：", file=sys.stderr)
        for item in payload["pending_web_fallback"]:
            print("  - %s(%s)：%s" % (item["platform"], item["reason"], " | ".join(item["queries"])),
                  file=sys.stderr)


if __name__ == "__main__":
    main()
