#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
每天挑 3 个 GitHub 上好玩的星标项目，然后推到手机。

用法：
    python scripts/main.py                # 正常跑一轮（挑 + 推送 + 记去重）
    python scripts/main.py --dry-run      # 只看今天会推什么，不推送、不记历史
    python scripts/main.py --verbose      # 顺便看看每个候选为什么被选中/被淘汰
    python scripts/main.py --count 5      # 今天想多要几个
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pick as picker      # noqa: E402
import push                # noqa: E402

# Windows 控制台默认是 GBK，直接 print emoji 会报错，这里强制走 UTF-8
for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.json"
HISTORY_PATH = ROOT / "data" / "history.json"
OUTBOX_DIR = ROOT / "data" / "outbox"
WEEKDAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


# ---------------------------------------------------------------- 杂项

def load_dotenv() -> None:
    """把项目根目录的 .env 读进环境变量（已存在的环境变量不覆盖）。"""
    path = ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip().removeprefix("export ").strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def now_local() -> datetime:
    offset = float(os.getenv("TZ_OFFSET", "8") or "8")     # 默认北京时间
    return datetime.now(timezone(timedelta(hours=offset)))


def load_history() -> dict:
    if HISTORY_PATH.exists():
        try:
            return json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print("  ! history.json 解析失败，本次按空历史处理")
    return {"pushed": {}, "recent": []}


def save_history(history: dict, cfg: dict, picked: list[dict], today: str) -> None:
    pushed = history.setdefault("pushed", {})
    for c in picked:
        pushed[c["full_name"]] = today

    cutoff = now_local() - timedelta(days=cfg["repeat_after_days"] + 30)
    for name, day in list(pushed.items()):                 # 老记录清理，文件别无限长大
        try:
            d = datetime.fromisoformat(day)
            d = d.replace(tzinfo=timezone(timedelta(hours=float(os.getenv("TZ_OFFSET", "8")))))
        except ValueError:
            continue
        if d < cutoff:
            pushed.pop(name, None)

    recent = history.setdefault("recent", [])
    recent.append({"date": today, "families": [c["family"] for c in picked]})
    history["recent"] = recent[-6:]
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_PATH.write_text(json.dumps(history, ensure_ascii=False, indent=2),
                            encoding="utf-8")


# ---------------------------------------------------------------- 文案

def updated_text(c: dict) -> str:
    days = picker.days_ago(picker.parse_iso(c.get("pushed_at")))
    if days <= 0:
        return "今天更新"
    if days == 1:
        return "昨天更新"
    if days <= 30:
        return f"{days} 天前更新"
    return f"{days // 30} 个月前更新"


def build_message(picked: list[dict], cfg: dict, when: datetime) -> tuple[str, str, str]:
    """返回 (中文标题, 英文标题, 正文)。"""
    title = f"{cfg['title']} · {when.month}月{when.day}日"
    title_ascii = f"GitHub Daily 3 - {when:%Y-%m-%d}"
    icons = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]

    lines = [f"🎈 {cfg['title']}", f"📅 {when.month}月{when.day}日 {WEEKDAYS[when.weekday()]}", ""]
    for i, c in enumerate(picked):
        meta = " · ".join(x for x in [
            f"⭐ {picker.human_stars(c['stars'])}",
            c["language"],
            c["family"],
            updated_text(c),
        ] if x)
        lines.append(f"{icons[i] if i < len(icons) else '·'} {c['full_name']}")
        lines.append(f"   {meta}")
        if c.get("highlights"):
            lines.append(f"   💡 看点：{'、'.join(c['highlights'][:2])}")
        desc = c["description"]
        if len(desc) > 130:
            cut = desc[:130]
            if " " in cut[100:]:
                cut = cut[:cut.rindex(" ")]
            desc = cut.rstrip(" ,.;:-") + "…"
        lines.append(f"   📝 {desc}")
        lines.append(f"   🔗 {c['url']}")
        lines.append("")
    lines.append("—— 推过的项目不会再出现，每天见 👋")
    body = "\n".join(lines).strip()
    return title, title_ascii, body


# ---------------------------------------------------------------- 主流程

def test_push() -> int:
    """只发一条测试消息，确认推送通道配置正确。"""
    channels = push.active_channels()
    print(f"已启用的推送通道：{channels or '无'}")
    if not channels:
        print("还没配置任何通道。复制 .env.example 为 .env，填一个通道再试。")
        return 2
    body = ("🔔 这是一条测试消息。\n\n"
            "看到它，说明 GitHub 每日 3 选已经能推到你手机上了。\n"
            "以后每天这个时间会收到 3 个挑好的高星项目。")
    results = push.send_all("测试推送", "Test", body)
    failed = 0
    for name, ok, detail in results:
        print(f"  {name}: {'✅ 成功' if ok else '❌ 失败'}  {detail[:150]}")
        failed += 0 if ok else 1
    return 0 if failed < len(results) else 2


def set_bark(value: str) -> int:
    """把 Bark 地址写进 .env，省得手动编辑文件。"""
    value = value.strip()
    env_path = ROOT / ".env"
    if not value:
        print("用法：python scripts/main.py --set-bark https://api.day.app/你的key")
        return 2
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()
    else:
        lines = [
            "# 由 --set-bark 生成；也可以自己往里加别的通道（见 .env.example）",
        ]
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("BARK_KEY="):
            lines[i] = f"BARK_KEY={value}"
            break
    else:
        lines.append(f"BARK_KEY={value}")
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    shown = value if value.startswith("http") else f"https://api.day.app/{value}"
    print(f"✅ 已写入 {env_path}")
    print(f"   BARK_KEY = {shown}")
    print("   下一步：python scripts/main.py --test-push")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="GitHub 每日 3 选")
    parser.add_argument("--dry-run", action="store_true", help="只打印，不推送也不记历史")
    parser.add_argument("--verbose", action="store_true", help="打印候选筛选与打分细节")
    parser.add_argument("--ignore-history", action="store_true", help="忽略去重记录（测试用）")
    parser.add_argument("--count", type=int, default=0, help="今天想要几个项目")
    parser.add_argument("--json", action="store_true", help="额外输出一份 JSON")
    parser.add_argument("--test-push", action="store_true",
                        help="只发一条测试消息，验证推送通道配好了没")
    parser.add_argument("--set-bark", metavar="地址或key", default=None,
                        help="把 Bark 的 key 写进 .env（直接粘贴 App 里复制的整条地址也行）")
    args = parser.parse_args(argv)

    if args.set_bark is not None:
        return set_bark(args.set_bark)

    load_dotenv()

    if args.test_push:
        return test_push()

    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if args.count:
        cfg["count"] = args.count
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN") or ""
    channels = push.active_channels()
    when = now_local()
    today = when.strftime("%Y-%m-%d")

    print(f"[{today}] 开始挑项目（API 令牌：{'有' if token else '无'}；推送通道：{channels or '无（只写本地文件）'}）")
    history = {"pushed": {}, "recent": []} if args.ignore_history else load_history()

    picked = picker.run(cfg, token, history, verbose=args.verbose)
    if not picked:
        print("!! 今天没挑到合适的项目（可能是网络或 API 限流），换个时间再跑一次试试")
        return 1

    if args.verbose:
        print("\n--- 打分明细 ---")
        for c in picked:
            print(f"\n{c['full_name']}  总分 {c['score']:.1f}")
            for r in c["reasons"]:
                print(f"    · {r}")
        print()

    title, title_ascii, body = build_message(picked, cfg, when)
    print("\n" + "=" * 46 + "\n" + body + "\n" + "=" * 46 + "\n")

    OUTBOX_DIR.mkdir(parents=True, exist_ok=True)
    (OUTBOX_DIR / f"{today}.md").write_text(f"# {title}\n\n{body}\n", encoding="utf-8")
    (OUTBOX_DIR / "latest.md").write_text(f"# {title}\n\n{body}\n", encoding="utf-8")
    if args.json:
        print(json.dumps(picked, ensure_ascii=False, indent=2))

    if args.dry_run:
        print("(dry-run：没有推送，也没有更新去重记录)")
        return 0

    results = push.send_all(title, title_ascii, body)
    if not results:
        print("提示：没有配置任何推送通道，内容已写到 data/outbox/。"
              "想让手机收到提醒，看 README 的「手机推送」一节。")
    for name, ok, detail in results:
        print(f"  推送 {name}: {'成功' if ok else '失败'} {detail[:120]}")

    delivered = any(ok for _, ok, _ in results) or not results
    if delivered:
        save_history(history, cfg, picked, today)
        print("已更新去重记录 data/history.json")
        return 0
    print("!! 所有推送通道都失败了，本次不写入去重记录，下次可以重推")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
