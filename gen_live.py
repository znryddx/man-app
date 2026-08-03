#!/usr/bin/env python3
# 云端每日生成 live.json —— 由 GitHub Actions 调用，服务器上无本地依赖
# 通过 OpenAI 兼容接口调用 LLM 生成「这男人有点东西」当日内容，写入 live.json
import os, json, datetime, ssl, urllib.request, urllib.error
ssl._create_default_https_context = ssl._create_unverified_context

APP_DIR = os.path.dirname(os.path.abspath(__file__))
API_KEY = os.environ.get("LLM_API_KEY")
BASE_URL = os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
MODEL = os.environ.get("LLM_MODEL", "gpt-4o-mini")

if not API_KEY:
    raise SystemExit("缺少 LLM_API_KEY 环境变量")

today = datetime.date.today()
date_str = today.strftime("%Y.%m.%d")
mmdd = today.strftime("%m-%d")

SYSTEM = (
    "你是资深东方美学 / 文人意境风格的内容营销专家，服务于文创器物品牌"
    "「这男人有点东西」（面向男性，品类含线香、沉香、手串、屏风、柜子、家具、"
    "文房、漆器、螺钿、百宝嵌、手把件、茶空间器物等）。文案雅致、不浮夸、"
    "符合文人审美，避免堆砌与硬广。"
)

USER = f"""请生成「今天」（{date_str}）的每日内容包，严格按下面的 JSON 结构输出，只输出合法 JSON，不要任何解释或 markdown 代码块。

字段与要求：
- date: "{date_str}"
- updated: "每日 AI 生成 · {mmdd} 实时联网更新"
- quotes: 长度3的数组，每项 {{text(一句东方美学/文人意境金句), source(出处如「— 明·文震亨《长物志》」), analysis(一句营销启发)}}
- auction: 长度4的数组，每项 {{lot(拍品名), meta(拍卖行+场次+成交/估价), note(一句市场解读)}}
- finance: 长度10的数组，每条形如 "01 · 当日真实财经要点"（尽量用贴近今日的真实宏观/市场热点）
- trending: 长度10的数组，每条形如 "01 · 热点事件 · 平台"（平台取 微博/抖音/小红书/百度/知乎/哔哩哔哩 之一）
- ecom: 长度5的数组，固定覆盖平台 淘宝/抖音/小红书/京东/拼多多，每项 {{platform, desc(该平台品类趋势一句话)}}
- ideas: 长度4的数组，每项 {{title(二创选题名), cats(适用品类, 形如「适用 · 手串 / 文玩」), note(执行要点)}}
- feature: 对象 {{kicker:"今日主推品类", catName(主推品类名), topic(社交图文选题), angle(切入角度), platform(平台建议)}}
- headlines: 长度3的数组，吸睛标题文案
- copy: 对象 {{kicker:"情绪种草 · 150–200 字", paragraph(150–200字情绪种草文案，第一人称男性视角)}}
- tags: 长度15的数组，话题标签（带#）
- strategy: 长度1的数组，全案营销策略一句

finance 与 trending 请用尽量真实、贴近 {date_str} 的当日热点；拍卖案例用近期真实或合理的品类。保持整体文人克制基调。"""

def call_llm():
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": USER},
        ],
        "temperature": 0.85,
        "response_format": {"type": "json_object"},
    }
    req = urllib.request.Request(
        BASE_URL + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=150) as r:
        resp = json.loads(r.read())
    return resp["choices"][0]["message"]["content"]

def main():
    raw = call_llm()
    try:
        obj = json.loads(raw)
    except Exception:
        # 容错：去掉可能包裹的 ```json ``` 标记
        s = raw.strip()
        if s.startswith("```"):
            s = s.split("```", 2)[1]
            if s.startswith("json"):
                s = s[4:]
        obj = json.loads(s)
    obj["date"] = date_str
    obj["updated"] = f"每日 AI 生成 · {mmdd} 实时联网更新"
    out = os.path.join(APP_DIR, "live.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    print("live.json generated ->", date_str)

if __name__ == "__main__":
    main()
