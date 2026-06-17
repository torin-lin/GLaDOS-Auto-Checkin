import os
import json
import time
import random
import requests


CHECKIN_URL = "https://glados.cloud/api/user/checkin"
STATUS_URL = "https://glados.cloud/api/user/status"

HEADERS_BASE = {
    "origin": "https://glados.cloud",
    "referer": "https://glados.cloud/console/checkin",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "content-type": "application/json;charset=UTF-8",
}

PAYLOAD = {"token": "glados.cloud"}
TIMEOUT = 10


def push_dingtalk(webhook_url: str, secret: str, title: str, content: str):
    """推送消息到钉钉机器人"""
    if not webhook_url:
        return

   # 使用Markdown格式，钉钉支持部分markdown语法
    data = {
        "msgtype": "markdown",
        "markdown": {
            "title": title,
            "text": f"## {title}\n\n{content.replace('|', ' | ')}"
        },
        "at": {
            "isAtAll": False
        }
    }

    # 如果配置了加签秘钥，进行签名
    if secret:
        timestamp = str(round(time.time() * 1000))
        secret_enc = secret.encode('utf-8')
        string_to_sign = f"{timestamp}\n{secret}"
        string_to_sign_enc = string_to_sign.encode('utf-8')
        
        import hmac
        import hashlib
        import base64
        
        hmac_code = hmac.new(
            secret_enc, 
            string_to_sign_enc, 
            digestmod=hashlib.sha256
        ).digest()
        sign = base64.b64encode(hmac_code).decode('utf-8')
        
        # 拼接完整的webhook地址
        if '?' in webhook_url:
            webhook_url = f"{webhook_url}&timestamp={timestamp}&sign={sign}"
        else:
            webhook_url = f"{webhook_url}?timestamp={timestamp}&sign={sign}"

    try:
        resp = requests.post(webhook_url, json=data, timeout=TIMEOUT)
        if resp.status_code == 200:
            j = safe_json(resp)
            if j.get("errcode") == 0:
                print("✅ 钉钉推送成功")
            else:
                print(f"⚠️ 钉钉推送失败: {j.get('errmsg', '未知错误')}")
        else:
            print(f"⚠️ 钉钉推送失败: HTTP {resp.status_code} | {resp.text}")
    except Exception as e:
        print(f"⚠️ 钉钉推送异常: {e}")


def push_all(webhook_url: str, secret: str, title: str, content: str):
    """推送到钉钉（如果已配置）"""
    if webhook_url:
        push_dingtalk(webhook_url, secret, title, content)
    else:
        print("⚠️ 未配置钉钉推送，请在 Secrets 中配置 DINGTALK_WEBHOOK_URL")


def safe_json(resp):
    try:
        return resp.json()
    except Exception:
        return {}


def main():
    # 从环境变量读取配置
    webhook_url = os.getenv("DINGTALK_WEBHOOK_URL", "")
    secret = os.getenv("DINGTALK_SECRET", "")  # 加签秘钥，可选
    cookies_env = os.getenv("COOKIES", "")
    cookies = [c.strip() for c in cookies_env.split("&") if c.strip()]

    if not cookies:
        push_all(webhook_url, secret, "GLaDOS 签到", "❌ 未检测到 COOKIES")
        return

    session = requests.Session()
    ok = fail = repeat = 0
    lines = []

    for idx, cookie in enumerate(cookies, 1):
        headers = dict(HEADERS_BASE)
        headers["cookie"] = cookie

        email = "unknown"
        points = "-"
        days = "-"

        try:
            r = session.post(
                CHECKIN_URL,
                headers=headers,
                data=json.dumps(PAYLOAD),
                timeout=TIMEOUT,
            )

            j = safe_json(r)
            msg = j.get("message", "")
            msg_lower = msg.lower()

            if "got" in msg_lower:
                ok += 1
                points = j.get("points", "-")
                status = "✅ 成功"
            elif "repeat" in msg_lower or "already" in msg_lower:
                repeat += 1
                status = "🔁 已签到"
            else:
                fail += 1
                status = "❌ 失败"

            # 状态接口（允许失败）
            s = session.get(STATUS_URL, headers=headers, timeout=TIMEOUT)
            sj = safe_json(s).get("data") or {}
            email = sj.get("email", email)
            if sj.get("leftDays") is not None:
                days = f"{int(float(sj['leftDays']))} 天"

        except Exception:
            fail += 1
            status = "❌ 异常"

        lines.append(f"{idx}. {email} | {status} | P:{points} | 剩余:{days}")
        time.sleep(random.uniform(1, 2))

    title = f"GLaDOS 签到完成 ✅{ok} ❌{fail} 🔁{repeat}"
    content = "\n".join(lines)

    print(content)
    
    push_all(webhook_url, secret, title, content)


if __name__ == "__main__":
    main()
    
