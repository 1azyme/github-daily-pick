#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
推送模块：把每天挑好的 3 个项目发到手机上。

可以同时配好几个通道，互相兜底（第一个失败还有第二个）。
配置全部走环境变量：本地放 .env，云端放 GitHub Secrets。

  ntfy           NTFY_TOPIC（可选 NTFY_SERVER / NTFY_TOKEN）  ← 免费、不用注册
  Bark (iPhone)  BARK_KEY（可选 BARK_SERVER）
  PushPlus (微信) PUSHPLUS_TOKEN
  Server酱 (微信) SERVERCHAN_KEY
  飞书机器人       FEISHU_WEBHOOK（可选 FEISHU_SECRET）
  企业微信机器人    WECOM_WEBHOOK
  钉钉机器人       DINGTALK_WEBHOOK（可选 DINGTALK_SECRET）
  Telegram       TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID
  邮件           SMTP_HOST + SMTP_USER + SMTP_PASS + MAIL_TO（可选 SMTP_PORT）
  自定义 webhook  WEBHOOK_URL（POST JSON: {title, text}）
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import smtplib
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from email.message import EmailMessage

UA = "github-daily-pick/1.0"


def _request(url: str, data: bytes | None, headers: dict, timeout: int = 20) -> tuple[bool, str]:
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA, **headers},
                                 method="POST" if data is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", "ignore")
            return 200 <= resp.status < 300, body[:180]
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code} {e.read().decode('utf-8', 'ignore')[:150]}"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def _post_json(url: str, payload: dict) -> tuple[bool, str]:
    return _request(url, json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                    {"Content-Type": "application/json; charset=utf-8"})


def _post_form(url: str, form: dict) -> tuple[bool, str]:
    return _request(url, urllib.parse.urlencode(form).encode("utf-8"),
                    {"Content-Type": "application/x-www-form-urlencoded"})


# ---------------------------------------------------------------- 各通道

def send_ntfy(title: str, title_ascii: str, text: str) -> tuple[bool, str]:
    topic = os.getenv("NTFY_TOPIC", "").strip()
    if not topic:
        return False, "未配置"
    server = os.getenv("NTFY_SERVER", "https://ntfy.sh").rstrip("/")
    # ntfy 的 HTTP 头只能放 ASCII，所以标题用英文短标题，正文里照样有中文
    headers = {
        "Title": title_ascii,
        "Tags": "sparkles",
        "Click": "https://github.com/trending",
    }
    token = os.getenv("NTFY_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return _request(f"{server}/{urllib.parse.quote(topic)}", text.encode("utf-8"), headers)


def send_bark(title: str, title_ascii: str, text: str) -> tuple[bool, str]:
    key = os.getenv("BARK_KEY", "").strip()
    if not key:
        return False, "未配置"
    server = os.getenv("BARK_SERVER", "https://api.day.app").rstrip("/")
    if key.startswith("http"):          # 直接粘贴了 App 里复制的整条地址，顺手拆开
        parsed = urllib.parse.urlparse(key)
        server = f"{parsed.scheme}://{parsed.netloc}"
        key = parsed.path.strip("/").split("/")[0]
    key = key.split("/")[0]
    payload = {
        "device_key": key,
        "title": title,
        "body": text,
        "group": "GitHub每日推荐",
        "url": "https://github.com/trending",
        "level": os.getenv("BARK_LEVEL", "timeSensitive").strip() or "active",
    }
    ok, detail = _post_json(f"{server}/push", payload)
    if not ok and "device token" in detail:
        return False, "Bark key 不对：请在 App 首页重新复制一次（形如 https://api.day.app/xxxxx）"
    return ok, detail


def send_pushplus(title: str, title_ascii: str, text: str) -> tuple[bool, str]:
    token = os.getenv("PUSHPLUS_TOKEN", "").strip()
    if not token:
        return False, "未配置"
    return _post_json("https://www.pushplus.plus/send", {
        "token": token, "title": title, "content": text, "template": "txt",
    })


def send_serverchan(title: str, title_ascii: str, text: str) -> tuple[bool, str]:
    key = os.getenv("SERVERCHAN_KEY", "").strip()
    if not key:
        return False, "未配置"
    return _post_form(f"https://sctapi.ftqq.com/{key}.send",
                      {"title": title, "desp": text})


def send_feishu(title: str, title_ascii: str, text: str) -> tuple[bool, str]:
    url = os.getenv("FEISHU_WEBHOOK", "").strip()
    if not url:
        return False, "未配置"
    payload: dict = {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {"template": "blue",
                       "title": {"tag": "plain_text", "content": title}},
            "elements": [
                {"tag": "div", "text": {"tag": "lark_md", "content": text}},
                {"tag": "hr"},
                {"tag": "note", "elements": [
                    {"tag": "plain_text", "content": "推过的项目不会重复出现"}]},
            ],
        },
    }
    secret = os.getenv("FEISHU_SECRET", "").strip()
    if secret:
        ts = str(int(time.time()))
        sign = base64.b64encode(hmac.new(f"{ts}\n{secret}".encode("utf-8"), b"",
                                         hashlib.sha256).digest()).decode("utf-8")
        payload["timestamp"] = ts
        payload["sign"] = sign
    ok, detail = _post_json(url, payload)
    if ok and '"code"' in detail and '"code":0' not in detail.replace(" ", ""):
        # 卡片发不出去就退回纯文本
        return _post_json(url, {"msg_type": "text", "content": {"text": f"{title}\n{text}"}})
    return ok, detail


def send_wecom(title: str, title_ascii: str, text: str) -> tuple[bool, str]:
    url = os.getenv("WECOM_WEBHOOK", "").strip()
    if not url:
        return False, "未配置"
    return _post_json(url, {"msgtype": "markdown",
                            "markdown": {"content": f"# {title}\n{text}"}})


def send_dingtalk(title: str, title_ascii: str, text: str) -> tuple[bool, str]:
    url = os.getenv("DINGTALK_WEBHOOK", "").strip()
    if not url:
        return False, "未配置"
    secret = os.getenv("DINGTALK_SECRET", "").strip()
    if secret:
        ts = str(round(time.time() * 1000))
        digest = hmac.new(secret.encode("utf-8"), f"{ts}\n{secret}".encode("utf-8"),
                          hashlib.sha256).digest()
        sep = "&" if "?" in url else "?"
        url = (f"{url}{sep}timestamp={ts}"
               f"&sign={urllib.parse.quote_plus(base64.b64encode(digest).decode('utf-8'))}")
    return _post_json(url, {"msgtype": "markdown",
                            "markdown": {"title": title, "text": f"### {title}\n{text}"}})


def send_telegram(title: str, title_ascii: str, text: str) -> tuple[bool, str]:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat:
        return False, "未配置"
    return _post_json(f"https://api.telegram.org/bot{token}/sendMessage", {
        "chat_id": chat,
        "text": f"{title}\n\n{text}",
        "disable_web_page_preview": True,
    })


def send_mail(title: str, title_ascii: str, text: str) -> tuple[bool, str]:
    host = os.getenv("SMTP_HOST", "").strip()
    user = os.getenv("SMTP_USER", "").strip()
    password = os.getenv("SMTP_PASS", "").strip()
    to_addr = os.getenv("MAIL_TO", "").strip()
    if not (host and user and password and to_addr):
        return False, "未配置"
    port = int(os.getenv("SMTP_PORT", "465") or "465")
    msg = EmailMessage()
    msg["Subject"] = title
    msg["From"] = user
    msg["To"] = to_addr
    msg.set_content(text)
    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=25,
                                  context=ssl.create_default_context()) as s:
                s.login(user, password)
                s.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=25) as s:
                s.starttls(context=ssl.create_default_context())
                s.login(user, password)
                s.send_message(msg)
        return True, "已发送"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def send_webhook(title: str, title_ascii: str, text: str) -> tuple[bool, str]:
    url = os.getenv("WEBHOOK_URL", "").strip()
    if not url:
        return False, "未配置"
    return _post_json(url, {"title": title, "text": text})


CHANNELS = {
    "ntfy": send_ntfy,
    "bark": send_bark,
    "pushplus": send_pushplus,
    "serverchan": send_serverchan,
    "feishu": send_feishu,
    "wecom": send_wecom,
    "dingtalk": send_dingtalk,
    "telegram": send_telegram,
    "mail": send_mail,
    "webhook": send_webhook,
}


def _configured(name: str) -> bool:
    env = os.environ.get
    return {
        "ntfy": bool(env("NTFY_TOPIC", "").strip()),
        "bark": bool(env("BARK_KEY", "").strip()),
        "pushplus": bool(env("PUSHPLUS_TOKEN", "").strip()),
        "serverchan": bool(env("SERVERCHAN_KEY", "").strip()),
        "feishu": bool(env("FEISHU_WEBHOOK", "").strip()),
        "wecom": bool(env("WECOM_WEBHOOK", "").strip()),
        "dingtalk": bool(env("DINGTALK_WEBHOOK", "").strip()),
        "telegram": bool(env("TELEGRAM_BOT_TOKEN", "").strip()
                         and env("TELEGRAM_CHAT_ID", "").strip()),
        "mail": bool(env("SMTP_HOST", "").strip() and env("SMTP_USER", "").strip()
                     and env("SMTP_PASS", "").strip() and env("MAIL_TO", "").strip()),
        "webhook": bool(env("WEBHOOK_URL", "").strip()),
    }[name]


def active_channels() -> list[str]:
    """当前已配置凭据的通道。"""
    return [name for name in CHANNELS if _configured(name)]


def send_all(title: str, title_ascii: str, text: str) -> list[tuple[str, bool, str]]:
    """按配置逐个发送，返回 [(通道, 是否成功, 说明)]。单个通道失败不影响其它通道。"""
    results: list[tuple[str, bool, str]] = []
    for name in active_channels():
        try:
            ok, detail = CHANNELS[name](title, title_ascii, text)
        except Exception as e:
            ok, detail = False, f"{type(e).__name__}: {e}"
        results.append((name, ok, detail))
    return results
