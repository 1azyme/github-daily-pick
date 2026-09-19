#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitHub 每日好玩项目 —— 候选抓取 / 过滤 / 打分 / 挑选

数据来源（只用标准库，不需要 pip 装包）：
  1. GitHub Trending 页面（今天的飙升榜）
  2. GitHub Search API（近期新晋高星、随机话题精选）

目标：挑出「高星、活跃、偏应用和好玩、不太像给程序员写作业用」的项目。
"""
from __future__ import annotations

import json
import math
import random
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API = "https://api.github.com"
UA = "github-daily-pick/1.0"
UTC = timezone.utc

# 粗分类：保证同一天 3 个项目不撞类型，也让每天的花样更多
FAMILIES = {
    "游戏": ["game", "games", "gaming", "emulator", "minecraft", "retrogaming",
             "pixel-art", "game-engine", "godot", "unity"],
    "AI": ["ai", "llm", "chatgpt", "agent", "whisper", "stable-diffusion",
           "computer-vision", "ocr", "tts", "text-to-speech", "image-generation",
           "machine-learning", "rag", "chatbot", "gpt"],
    "视觉创意": ["visualization", "data-visualization", "threejs", "webgl", "shader",
                 "generative-art", "creative-coding", "3d", "animation", "svg",
                 "canvas", "ascii-art"],
    "效率工具": ["productivity", "note-taking", "obsidian", "notion", "automation",
                 "rss", "bookmark", "clipboard", "launcher", "todo", "markdown",
                 "calendar"],
    "桌面系统": ["desktop-app", "gui", "windows", "macos", "linux", "electron",
                 "tauri", "themes", "wallpaper", "shell"],
    "手机浏览器": ["android", "ios", "browser-extension", "chrome-extension",
                   "userscript", "pwa", "tampermonkey"],
    "自建家庭": ["self-hosted", "homelab", "docker", "home-automation", "iot",
                 "esp32", "arduino", "raspberry-pi", "smart-home", "nas", "server"],
    "影音图片": ["music", "audio", "video", "ffmpeg", "media", "player", "photography",
                 "image-processing", "fonts", "icons", "design", "emoji", "gif"],
    "网络隐私": ["privacy", "vpn", "proxy", "adblock", "security", "dns",
                 "password-manager"],
    "生活数据": ["maps", "geospatial", "weather", "finance", "stock", "health",
                 "fitness", "travel"],
    "命令行": ["cli", "tui", "terminal", "console", "command-line"],
    "下载实用": ["download", "downloader", "ebook", "translation", "dictionary",
                 "scraper", "converter", "file-manager"],
}


# ---------------------------------------------------------------- 基础工具

def now_utc() -> datetime:
    return datetime.now(UTC)


def parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def days_ago(dt: datetime | None) -> int:
    if not dt:
        return 99999
    return max(0, (now_utc() - dt).days)


def human_stars(n: int) -> str:
    return f"{n / 1000:.1f}k" if n >= 1000 else str(n)


def strip_tags(html: str) -> str:
    return unescape(re.sub(r"<[^>]+>", "", html)).strip()


def http_get(url: str, headers: dict | None = None, timeout: int = 25) -> bytes:
    req = urllib.request.Request(url, headers=headers or {})
    req.add_header("User-Agent", UA)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def gh_api(path_or_url: str, token: str | None = None, quiet: bool = False) -> dict | None:
    """调用 GitHub API。失败不抛异常，返回 None，保证每轮都能跑到底。"""
    url = path_or_url if path_or_url.startswith("http") else API + path_or_url
    headers = {"Accept": "application/vnd.github+json",
               "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    for attempt in range(3):
        try:
            return json.loads(http_get(url, headers, timeout=25))
        except urllib.error.HTTPError as e:
            if e.code in (403, 429):          # 触发限流：等一下再试，别把整轮跑废
                if not quiet:
                    print(f"  ! API 限流 {e.code}，等待重试")
                time.sleep(6 * (attempt + 1))
                continue
            if not quiet:
                print(f"  ! API 错误 {e.code}: {url[:90]}")
            return None
        except Exception as e:
            if not quiet:
                print(f"  ! 请求失败 {type(e).__name__}: {url[:90]}")
            time.sleep(2)
    return None


# ---------------------------------------------------------------- 数据源

def _trending_blocks(period: str) -> list[str]:
    try:
        html = http_get(f"https://github.com/trending?since={period}").decode("utf-8", "ignore")
    except Exception as e:
        print(f"  ! Trending({period}) 抓取失败：{type(e).__name__}")
        return []
    return html.split('<article class="Box-row">')[1:]


def fetch_trending(period: str = "daily") -> list[str]:
    names: list[str] = []
    for block in _trending_blocks(period):
        m = re.search(r'<h2[^>]*>\s*<a[^>]*href="/([^"/]+)/([^"/]+)"', block)
        if m:
            name = f"{m.group(1)}/{m.group(2)}"
            if name not in names:
                names.append(name)
    print(f"  · Trending({period}) 取到 {len(names)} 个")
    return names


def trending_deltas() -> dict[str, str]:
    """顺手抠出「今日新增星数」，用于加分展示。"""
    out: dict[str, str] = {}
    for block in _trending_blocks("daily"):
        m = re.search(r'<h2[^>]*>\s*<a[^>]*href="/([^"/]+)/([^"/]+)"', block)
        if not m:
            continue
        seg = re.search(r"([\d,]+)\s*stars?\s*today", block)
        if seg:
            out[f"{m.group(1)}/{m.group(2)}"] = seg.group(1)
    return out


def search_repos(query: str, token: str | None, per_page: int = 50,
                 sort: str = "stars") -> list[dict]:
    q = urllib.parse.quote(query, safe=":+><=.")
    data = gh_api(f"/search/repositories?q={q}&sort={sort}&order=desc&per_page={per_page}",
                  token=token, quiet=True)
    if not data:
        return []
    return data.get("items", []) or []


def enrich(full_name: str, token: str | None) -> dict | None:
    return gh_api(f"/repos/{full_name}", token=token, quiet=True)


# ---------------------------------------------------------------- 归一化 / 过滤

def normalize(raw: dict, source: str, trend_delta: str | None = None) -> dict:
    topics = set(raw.get("topics") or [])
    desc = (raw.get("description") or "").strip()
    return {
        "full_name": raw["full_name"],
        "owner": raw["full_name"].split("/")[0],
        "name": raw.get("name") or raw["full_name"].split("/")[1],
        "url": raw.get("html_url") or f"https://github.com/{raw['full_name']}",
        "description": desc,
        "stars": int(raw.get("stargazers_count") or 0),
        "forks": int(raw.get("forks_count") or 0),
        "language": raw.get("language") or "",
        "topics": sorted(topics),
        "homepage": (raw.get("homepage") or "").strip(),
        "created_at": raw.get("created_at"),
        "pushed_at": raw.get("pushed_at"),
        "archived": bool(raw.get("archived")),
        "fork": bool(raw.get("fork")),
        "source": source,
        "trend_delta": trend_delta,
        "highlights": [],
        "family": "其他",
    }


def compile_blockers(patterns: list[str]) -> list[re.Pattern]:
    out = []
    for p in patterns:
        p = p.strip().lower()
        if not p:
            continue
        esc = re.escape(p)
        if re.fullmatch(r"[a-z0-9_+-]+", p):     # 纯英文短词加词边界，避免误伤
            out.append(re.compile(rf"\b{esc}\b"))
        else:
            out.append(re.compile(esc))
    return out


def blocked_reason(c: dict, blockers: list[re.Pattern], exclude_topics: set[str]) -> str | None:
    if c["archived"]:
        return "已归档"
    if c["fork"]:
        return "fork 项目"
    if not c["description"]:
        return "没有简介"
    hit_topics = exclude_topics & set(c["topics"])
    if hit_topics:
        return f"排除话题 {sorted(hit_topics)}"
    haystack = " ".join([c["name"], c["description"], " ".join(c["topics"])]).lower()
    for pat in blockers:
        if pat.search(haystack):
            return f"屏蔽词 {pat.pattern}"
    return None


def prefilter(c: dict, cfg: dict) -> str | None:
    if c["stars"] < cfg["min_stars"]:
        return f"星数不足（{c['stars']}）"
    if c["stars"] > cfg["max_stars"]:
        return f"星数过高（{c['stars']}）"
    return None


def family_of(topics: set[str]) -> str:
    best, best_hits = "其他", 0
    for fam, keys in FAMILIES.items():
        hits = len(topics & set(keys))
        if hits > best_hits:
            best, best_hits = fam, hits
    return best


# ---------------------------------------------------------------- 打分

def score(c: dict, cfg: dict, recent_families: set[str]) -> tuple[float, list[str]]:
    reasons: list[str] = []
    stars = max(c["stars"], 1)
    s = 2.4 * math.log10(stars)               # 高星基础分：4k≈8.7，40k≈11.2
    reasons.append(f"星数基础分 {s:.1f}")

    topics = set(c["topics"])
    boosts = sorted(
        ((cfg["boost_topics"][t][0], cfg["boost_topics"][t][1], t)
         for t in topics if t in cfg["boost_topics"]),
        reverse=True,
    )
    hit = min(sum(w for w, _, _ in boosts[:3]), 5.0)   # 封顶，防止刷话题霸榜
    if hit:
        s += hit
        reasons.append(f"话题加分 +{hit:.1f}（{', '.join(t for _, _, t in boosts[:3])}）")
    c["highlights"] = []
    seen_keys: set[str] = set()
    for _, label, _ in boosts:
        key = label[:3].lower().replace(" ", "")     # 避免「3D 特效 / 3D 相关」这种重复
        if key in seen_keys:
            continue
        seen_keys.add(key)
        c["highlights"].append(label)
        if len(c["highlights"]) >= 2:
            break

    penalty = min(sum(cfg["penalty_topics"][t] for t in topics if t in cfg["penalty_topics"]), 6.0)
    if penalty:
        s -= penalty
        reasons.append(f"话题扣分 -{penalty:.1f}")

    # 描述里带「给工程师用的」味道，也压一点分
    haystack = f"{c['name']} {c['description']}".lower()
    kw_hit = [k for k in cfg.get("penalty_keywords", {}) if k in haystack]
    if kw_hit:
        kw_penalty = min(sum(cfg["penalty_keywords"][k] for k in kw_hit), 3.0)
        s -= kw_penalty
        reasons.append(f"关键词扣分 -{kw_penalty:.1f}（{', '.join(kw_hit)}）")

    if c["homepage"]:
        s += 1.2
        reasons.append("有官网 / 在线体验 +1.2")

    created_days = days_ago(parse_iso(c["created_at"]))
    if created_days <= 365:
        s += 1.0
        reasons.append("一年内新项目 +1.0")
    elif created_days <= 730:
        s += 0.4
        reasons.append("两年内新项目 +0.4")

    pushed_days = days_ago(parse_iso(c["pushed_at"]))
    if pushed_days <= 14:
        s += 1.0
        reasons.append("最近两周还在更新 +1.0")
    elif pushed_days <= 60:
        s += 0.5
        reasons.append("最近两个月还在更新 +0.5")

    if c.get("trend_delta"):
        s += 1.4
        reasons.append(f"Trending 今日 +{c['trend_delta']} 星 +1.4")
    elif c["source"].startswith("trending"):
        s += 0.8
        reasons.append("登上 Trending 榜 +0.8")

    if c["stars"] > 90000:                     # 太家喻户晓的压一压，给新东西让位
        s -= 1.2
        reasons.append("超大众项目 -1.2")

    fam = family_of(topics)
    c["family"] = fam
    if fam in recent_families:
        s -= 1.5
        reasons.append(f"最近几天推过「{fam}」-1.5")

    jitter = random.uniform(0, 1.3)            # 随机项：保证每天推的不一样
    s += jitter
    reasons.append(f"随机项 +{jitter:.1f}")
    return s, reasons


# ---------------------------------------------------------------- 挑选

def pick(candidates: list[dict], cfg: dict, history: dict) -> list[dict]:
    count = cfg["count"]
    pushed: dict = history.get("pushed", {})
    recent_families: set[str] = set()
    for rec in history.get("recent", [])[-2:]:
        recent_families.update(rec.get("families", []))

    pool: list[dict] = []
    for c in candidates:
        last = pushed.get(c["full_name"])
        if last:
            prev = parse_iso(last if "T" in last else last + "T00:00:00+00:00")
            if days_ago(prev) < cfg["repeat_after_days"]:
                continue                        # 推过的不再推
        c["score"], c["reasons"] = score(c, cfg, recent_families)
        pool.append(c)

    pool.sort(key=lambda x: x["score"], reverse=True)
    if not pool:
        return []

    chosen: list[dict] = []
    used_owners: set[str] = set()
    used_families: set[str] = set()
    used_labels: set[str] = set()
    for c in pool:                              # 第一轮：类型、看点、作者都不重复
        if len(chosen) >= count:
            break
        if c["owner"] in used_owners or c["family"] in used_families:
            continue
        if used_labels & set(c.get("highlights", [])):
            continue
        chosen.append(c)
        used_owners.add(c["owner"])
        used_families.add(c["family"])
        used_labels.update(c.get("highlights", []))
    for c in pool:                              # 第二轮：只保证不撞作者和看点
        if len(chosen) >= count:
            break
        if c in chosen or c["owner"] in used_owners:
            continue
        if used_labels & set(c.get("highlights", [])):
            continue
        chosen.append(c)
        used_owners.add(c["owner"])
        used_labels.update(c.get("highlights", []))
    for c in pool:                              # 第三轮：还不够就放宽到底
        if len(chosen) >= count:
            break
        if c in chosen:
            continue
        chosen.append(c)
    return chosen[:count]


# ---------------------------------------------------------------- 主流程

def gather(cfg: dict, token: str | None, topic_rounds: int) -> list[dict]:
    candidates: dict[str, dict] = {}
    deltas = trending_deltas()

    # 1) Trending 榜单（不需要 API 配额）
    for period in ("daily", "weekly"):
        for name in fetch_trending(period):
            candidates.setdefault(name, {"full_name": name, "_sources": []})
            candidates[name]["_sources"].append(period)

    # 2) 补全 Trending 项目的详情（只补前若干个，省配额）
    todo = list(candidates.keys())
    if not token:
        todo = todo[:6]
    else:
        todo = todo[: cfg["trending_enrich_limit"]]
    for name in todo:
        raw = enrich(name, token)
        if raw:
            candidates[name]["_raw"] = raw

    enriched: list[dict] = []
    for name, v in candidates.items():
        if "_raw" in v:
            enriched.append(normalize(v["_raw"], "trending", deltas.get(name)))
    print(f"  · Trending 补全 {len(enriched)} 个")

    # 3) Search：近期新晋高星（新鲜感的来源）
    since = (now_utc() - timedelta(days=cfg["new_repo_days"])).strftime("%Y-%m-%d")
    for raw in search_repos(f"created:>{since} stars:>{cfg['new_repo_min_stars']}",
                            token, per_page=cfg["search_per_page"]):
        enriched.append(normalize(raw, "new"))
    print(f"  · 加上近期新晋高星后共 {len(enriched)} 个")

    # 4) Search：随机抽几个有趣话题
    topics = list(cfg["topics"])
    random.shuffle(topics)
    for t in topics[:max(1, topic_rounds)]:
        items = search_repos(f"topic:{t} stars:>{cfg['min_stars']}", token, per_page=40)
        if items:
            # 每个话题里随机取一部分，别老是那几个超级明星项目
            for raw in random.sample(items, min(len(items), 12)):
                enriched.append(normalize(raw, f"topic:{t}"))
        if not token:
            time.sleep(2)
    print(f"  · 话题精选后共 {len(enriched)} 个候选")
    return enriched


def dedupe(cands: list[dict]) -> list[dict]:
    out: dict[str, dict] = {}
    for c in cands:
        key = c["full_name"]
        if key not in out:
            out[key] = c
            continue
        prev = out[key]
        sources = sorted({prev["source"], c["source"]})
        if c["stars"] > prev["stars"]:
            out[key] = c
        out[key]["source"] = "+".join(sources)
        out[key]["trend_delta"] = c.get("trend_delta") or prev.get("trend_delta")
    return list(out.values())


def run(cfg: dict, token: str | None, history: dict, verbose: bool = False) -> list[dict]:
    topic_rounds = 8 if token else 3
    raw = gather(cfg, token, topic_rounds)
    cands = dedupe(raw)

    blockers = compile_blockers(cfg["block_patterns"])
    exclude_topics = set(cfg.get("exclude_topics", []))
    exclude_owners = set(cfg.get("exclude_owners", []))

    kept: list[dict] = []
    dropped: dict[str, int] = {}
    for c in cands:
        why = blocked_reason(c, blockers, exclude_topics)
        if not why and c["owner"] in exclude_owners:
            why = "作者被排除"
        if not why:
            why = prefilter(c, cfg)
        if not why and days_ago(parse_iso(c["pushed_at"])) > cfg["max_stale_days"]:
            why = "太久没更新"
        if why:
            dropped[why] = dropped.get(why, 0) + 1
            if verbose:
                print(f"    x {c['full_name']}: {why}")
            continue
        kept.append(c)

    top = sorted(dropped.items(), key=lambda kv: -kv[1])[:6]
    print(f"  · 过滤后剩 {len(kept)} 个候选；淘汰原因 Top：{dict(top)}")

    picked = pick(kept, cfg, history)
    for c in picked:
        c["family"] = family_of(set(c["topics"]))
    return picked
