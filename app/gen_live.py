#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_live.py — 「这男人有点东西」每日 live.json 服务端生成器
运行环境：GitHub Actions (ubuntu-latest)，无需本机开机。

数据来源（全部免费、无需密钥）：
  - 新闻类 6 模块（财经/热点/汽车/腕表/奢侈品/拍卖）：vvhan 免费热榜接口，按关键词过滤。
  - 创作类 8 模块（金句/电商/二创/主推/标题/情绪金句/吃喝玩乐/策略）：GitHub Models 免费模型额度生成。

降级策略：任一模块抓取/生成失败，保留上一天 live.json 中该模块的对应内容（不轮播、不覆盖为空白）。
仅在完全无历史 live.json 且全部失败时，才写入一份极简合法骨架。
"""
import os
import re
import json
import datetime
import urllib.request
import urllib.error
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
LIVE = os.path.join(BASE, "live.json")

# 北京时间
def now_cst():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))

DATE = now_cst().strftime("%Y.%m.%d")

# ---------------------------------------------------------------------------
# 网络
# ---------------------------------------------------------------------------
def http_get(url, timeout=15, headers=None):
    try:
        req = urllib.request.Request(url, headers=headers or {"User-Agent": "Mozilla/5.0"})
        return urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "replace")
    except Exception as e:
        print("  [warn] GET FAIL", url, "->", e)
        return None

# ---------------------------------------------------------------------------
# GitHub Models 免费模型（零积分）
# ---------------------------------------------------------------------------
MODEL_CANDIDATES = [
    os.environ.get("GH_MODEL") or "gpt-4o-mini",
    "gpt-4o-mini",
    "meta/llama-3.1-8b-instruct",
    "mistralai/mistral-7b-instruct-v0.3",
]

def llm(system, user, max_tokens=3000):
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("  [warn] 无 GITHUB_TOKEN，跳过 LLM")
        return None
    url = "https://models.inference.ai.azure.com/v1/chat/completions"
    last_err = None
    for model in MODEL_CANDIDATES:
        if not model:
            continue
        body = json.dumps({
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.85,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        }).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        })
        try:
            raw = urllib.request.urlopen(req, timeout=120).read().decode("utf-8", "replace")
            data = json.loads(raw)
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            last_err = e
            print(f"  [warn] LLM {model} FAIL ->", e)
    return None

def extract_json(text):
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        m = re.search(r"\{.*\}", text, re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                return None
    return None

# ---------------------------------------------------------------------------
# 热榜抓取 + 关键词过滤
# ---------------------------------------------------------------------------
VVHAN = {
    "weibo": "https://api.vvhan.com/api/hotlist/wbHot",
    "baidu": "https://api.vvhan.com/api/hotlist/baidu",
    "zhihu": "https://api.vvhan.com/api/hotlist/zhihu",
}

def parse_vvhan(text):
    """解析 vvhan 热榜返回，返回 [(title, hot, src)]。"""
    out = []
    if not text:
        return out
    try:
        j = json.loads(text)
    except Exception:
        return out
    rows = j.get("data") if isinstance(j, dict) else None
    if not isinstance(rows, list):
        return out
    for r in rows:
        if not isinstance(r, dict):
            continue
        t = r.get("title") or r.get("name") or r.get("word")
        if not t:
            continue
        hot = r.get("hot") or r.get("num") or r.get("weight") or 0
        try:
            hot = int(hot)
        except Exception:
            hot = 0
        out.append((str(t).strip(), hot))
    return out

def fetch_pool():
    pool = []
    for src, url in VVHAN.items():
        rows = parse_vvhan(http_get(url))
        for t, hot in rows:
            pool.append({"t": t, "hot": hot, "src": src})
    # 去重（按标题）
    seen = {}
    for it in pool:
        k = it["t"]
        if k not in seen or it["hot"] > seen[k]["hot"]:
            seen[k] = it
    return list(seen.values())

KW = {
    "finance": ["股", "涨", "跌", "央行", "美联储", "人民币", "A股", "美股", "黄金", "比特币",
                "经济", "GDP", "通胀", "财报", "利率", "债券", "基金", "上市", "退市", "汇率", "降息", "加息"],
    "auto": ["汽车", "新能源", "比亚迪", "小米汽车", "特斯拉", "理想", "蔚来", "小鹏", "华为", "上汽",
             "广汽", "宝马", "奔驰", "奥迪", "车型", "续航", "智驾", "销量", "申报", "召回"],
    "watch": ["腕表", "手表", "劳力士", "百达翡丽", "欧米茄", "卡地亚", "浪琴", "积家", "江诗丹顿",
              "理查德", "钟表", "腕表展"],
    "luxury": ["奢侈品", "爱马仕", "LV", "路易威登", "香奈儿", "Gucci", "古驰", "迪奥", "Prada",
               "LVMH", "开云", "华伦天奴", "葆蝶家", "奢侈"],
    "auction": ["拍卖", "佳士得", "苏富比", "保利", "嘉德", "西泠", "匡时", "瀚海", "成交", "春拍",
                "秋拍", "藏品", "拍品", "艺术家", "亿元"],
}

def match(pool, kws, topn):
    res = []
    for it in pool:
        if any(k in it["t"] for k in kws):
            res.append(it)
    res.sort(key=lambda x: x["hot"], reverse=True)
    return [f"{i+1:02d} · {it['t']}" for i, it in enumerate(res[:topn])]

def build_news(prev):
    pool = fetch_pool()
    print(f"  [info] 热榜池抓取 {len(pool)} 条")
    if not pool:
        print("  [warn] 热榜池为空，新闻类模块沿用昨日")
        return prev

    trending = sorted(pool, key=lambda x: x["hot"], reverse=True)[:10]
    trending = [f"{i+1:02d} · {it['t']}" for i, it in enumerate(trending)]

    out = {
        "trending": trending,
        "finance": match(pool, KW["finance"], 10),
        "auto": match(pool, KW["auto"], 8),
        "watch": match(pool, KW["watch"], 8),
        "luxury": match(pool, KW["luxury"], 8),
        "auction": match(pool, KW["auction"], 4),
    }
    # 空模块补一句诚实占位（非轮播，仅当当日无命中）
    for k in ("finance", "auto", "watch", "luxury", "auction"):
        if not out[k]:
            out[k] = [f"01 · 今日实时热榜中暂未捕捉到「{k}」领域显著动态，明日再探。"]
    return out

# ---------------------------------------------------------------------------
# 创作类（GitHub Models 免费生成）
# ---------------------------------------------------------------------------
CREATIVE_SYSTEM = (
    "你是东方美学文创 App「这男人有点东西」的内容主编，风格：留白美术馆式的"
    "高级、清爽、克制，带文人意境与生活态度。请严格按用户给出的 JSON Schema 输出，"
    "不要任何多余解释，只输出合法 JSON。"
)

CREATIVE_USER = '''今天是 {date}。今日真实热点参考（用于让内容沾点当下气息，但不要硬塞新闻进金句）：
{trending}

请生成以下 8 个创作模块，严格按 JSON 输出：
{{
  "quotes": [ {{"text":"美学金句(古句或雅句)","source":"— 作者《书名》 或 录自…","analysis":"一句赏析"}} ]  // 恰好3条，金句只讲器物/审美/心境，绝不掺新闻
  "ecom": [ {{"platform":"淘宝/京东/抖音/小红书/拼多多 之一","desc":"一行电商趋势描述"}} ]  // 恰好5条，每平台一条
  "ideas": [ {{"title":"二创方向名","cats":"适用品类清单(用/分隔，如 香/沉香/手串/文房)","note":"一句钩子"}} ]  // 恰好4条
  "feature": {{"kicker":"小标签","catName":"主推品类名","topic":"一个社交图文选题","angle":"切入角度","platform":"平台建议"}}
  "tags": ["手串爆款标题(含标点,不超20字,非两字钩子非材质名)", ...]  // 10~15条
  "emojiquotes": ["情绪金句(短句,带情绪张力:小丧/洒脱/自洽/清醒)", ...]  // 恰好6条
  "dailyplay": [ {{"scene":"场景名","text":"60~110字可直接配图的社媒文案"}} ]  // 恰好8条,覆盖:喝酒微醺/深夜宵夜/干饭吃货/闲逛放风/居家百态/打工人发疯/生活翻车/互动提问
  "strategy": ["转化钩子+发布时机+内容节奏 的一段长文"]  // 恰好1条
}}'''

def build_creative(prev, trending_text):
    raw = llm(CREATIVE_SYSTEM, CREATIVE_USER.format(date=DATE, trending=trending_text))
    data = extract_json(raw)
    if not data:
        print("  [warn] 创作类生成失败，沿用昨日创作模块")
        return {k: prev.get(k) for k in
                ("quotes", "ecom", "ideas", "feature", "tags", "emojiquotes", "dailyplay", "strategy")}
    # 数量兜底
    data["quotes"] = (data.get("quotes") or [])[:3] or prev.get("quotes", [])
    data["ecom"] = (data.get("ecom") or [])[:5] or prev.get("ecom", [])
    data["ideas"] = (data.get("ideas") or [])[:4] or prev.get("ideas", [])
    data["tags"] = (data.get("tags") or [])[:15] or prev.get("tags", [])
    data["emojiquotes"] = (data.get("emojiquotes") or [])[:6] or prev.get("emojiquotes", [])
    data["dailyplay"] = (data.get("dailyplay") or [])[:8] or prev.get("dailyplay", [])
    data["strategy"] = (data.get("strategy") or [])[:1] or prev.get("strategy", [])
    if not data.get("feature"):
        data["feature"] = prev.get("feature", {})
    return data

# ---------------------------------------------------------------------------
# 线香每日营销方案：按日期轮取品种池一款，GitHub Models 免费生成
# ---------------------------------------------------------------------------
def load_incense_pool():
    p = os.path.join(BASE, "incense.json")
    try:
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return [x for x in data if isinstance(x, dict) and x.get("name")]
    except Exception as e:
        print("  [warn] 读 incense.json 失败 ->", e)
    return None

INCENSE_SYSTEM = (
    "你是东方美学文创 App「这男人有点东西」的线香内容主编。风格：留白美术馆式的高级、清爽、克制，"
    "带文人意境与生活态度。今天只针对一款指定线香，产出一份可直接用于社媒分发的营销方案。"
    "严格按用户给出的 JSON Schema 输出，不要任何多余解释，只输出合法 JSON。"
)
INCENSE_USER = '''今天要做的线香是：{name}（{note}）
请为它产出一份「每日线香营销方案」，严格按 JSON 输出：
{{
  "name": "线香品种名(与给定一致)",
  "position": "一句话定位(20字内,点出气质与人群)",
  "keywords": ["风味/气质关键词1","关键词2","关键词3"],
  "scenes": ["适用场景1","适用场景2","适用场景3","适用场景4"],
  "hooks": ["可直接发的社媒文案钩子1(带标点,不超24字)","钩子2","钩子3"],
  "pitch": "一段转化话术(60~110字,讲清为什么买这盒)",
  "timing": "最佳发布时机与平台建议(一句话)"
}}'''

def build_incense(prev, pool):
    if not pool:
        return prev.get("incense") or {}
    base = datetime.date(2026, 8, 10)
    idx = (now_cst().date() - base).days % len(pool)
    item = pool[idx]
    name = item.get("name", "")
    note = item.get("note", "")
    raw = llm(INCENSE_SYSTEM, INCENSE_USER.format(name=name, note=note))
    data = extract_json(raw)
    if not data or not data.get("name"):
        print("  [warn] 线香生成失败，沿用昨日")
        return prev.get("incense") or {"name": name}
    data["name"] = name
    return data

# ---------------------------------------------------------------------------
# 拍卖模块：优先从热榜拍卖命中，不足则用真实风格占位（不轮播）
# ---------------------------------------------------------------------------
def build_auction(prev, auction_news):
    # auction_news 已是字符串列表（来自热榜过滤），直接用
    return auction_news if auction_news and len(auction_news) >= 1 else prev.get("auction", [])

# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def load_prev():
    try:
        with open(LIVE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def skeleton():
    return {
        "date": DATE,
        "updated": "每日 AI 生成 · 已更新",
        "quotes": [{"text": "器以载道，物以传情。", "source": "— 录自 文震亨《长物志》", "analysis": "器物之美，在于承载心境。"}],
        "auction": [{"lot": "今日拍卖资讯", "meta": "实时热榜未捕捉到拍卖动态", "note": "明日再探。"}],
        "finance": ["01 · 今日实时财经热榜暂未捕捉到显著动态。"],
        "trending": ["01 · 今日实时热榜加载中。"],
        "auto": ["01 · 今日汽车领域实时热榜暂未捕捉到显著动态。"],
        "watch": ["01 · 今日腕表领域实时热榜暂未捕捉到显著动态。"],
        "luxury": ["01 · 今日奢侈品领域实时热榜暂未捕捉到显著动态。"],
        "ecom": [{"platform": "淘宝", "desc": "东方美学器物持续走热。"},
                 {"platform": "京东", "desc": "文房清供品类稳健。"},
                 {"platform": "抖音", "desc": "手串盘玩内容曝光走高。"},
                 {"platform": "小红书", "desc": "线香/香薰种草活跃。"},
                 {"platform": "拼多多", "desc": "平价文创礼盒走量。"}],
        "ideas": [{"title": "器物里的慢生活", "cats": "香/沉香/文房/茶空间器物", "note": "用一件器物讲一段安静时光。"}],
        "feature": {"kicker": "今日主推", "catName": "线香", "topic": "一炉香里的时间", "angle": "以香入静", "platform": "小红书+视频号"},
        "tags": ["新手盘串必看！3个坑别踩。", "百元手串，盘出千元质感？", "我的第一串金刚，封神了！"],
        "emojiquotes": ["生活不易，微醺解千愁。", "不必合群，自洽就好。", "清醒是种温柔的残忍。"],
        "dailyplay": [{"scene": "喝酒微醺场", "text": "生活不易，微醺解千愁。今晚小酌一杯，敬自己。"}],
        "strategy": ["转化钩子：以『定心之物』切入；发布时机：早8晚9；内容节奏：日更+周主题。"],
        "incense": {"name": "老山檀香", "position": "温润奶香，安神定气。", "keywords": ["奶香", "温润", "宁神"], "scenes": ["独处", "书房", "睡前", "茶席"], "hooks": ["一炉老山檀，把浮躁按下去。", "男生书房该有的味道，温润不冲。", "睡前点它，比数羊管用。"], "pitch": "老山檀香气味醇厚带奶韵，安神助眠，书房茶席皆宜。", "timing": "晚9-11点 · 小红书/视频号 助眠场景最佳。"},
    }

def main():
    mock = "--mock" in sys.argv
    prev = load_prev()

    print(f"== gen_live {DATE} (mock={mock}) ==")

    if mock:
        # 自测：用内嵌数据验证组装逻辑，不触网不调模型
        news = {
            "trending": [f"{i+1:02d} · 自测热点{i+1}" for i in range(10)],
            "finance": [f"{i+1:02d} · 自测财经{i+1}" for i in range(10)],
            "auto": [f"{i+1:02d} · 自测汽车{i+1}" for i in range(8)],
            "watch": [f"{i+1:02d} · 自测腕表{i+1}" for i in range(8)],
            "luxury": [f"{i+1:02d} · 自测奢侈品{i+1}" for i in range(8)],
            "auction": [f"{i+1:02d} · 自测拍卖{i+1}" for i in range(4)],
        }
        creative = extract_json('''{
          "quotes":[{"text":"疏影横斜水清浅","source":"— 林逋《山园小梅》","analysis":"孤高之境，意在言外。"},
                    {"text":"室无兰不雅","source":"— 文震亨《长物志》","analysis":"一物之陈，见主人心境。"},
                    {"text":"聊乘化以归尽","source":"— 陶渊明《归去来兮辞》","analysis":"顺其自然，是为自洽。"}],
          "ecom":[{"platform":"淘宝","desc":"东方美学器物持续走热。"},
                  {"platform":"京东","desc":"文房清供品类稳健。"},
                  {"platform":"抖音","desc":"手串盘玩内容曝光走高。"},
                  {"platform":"小红书","desc":"线香/香薰种草活跃。"},
                  {"platform":"拼多多","desc":"平价文创礼盒走量。"}],
          "ideas":[{"title":"器物里的慢生活","cats":"香/沉香/文房/茶空间器物","note":"用一件器物讲一段安静时光。"},
                   {"title":"盘串即修行","cats":"手串/金刚/星月/沉香","note":"把焦虑盘进包浆里。"},
                   {"title":"一方闲章","cats":"文房/雕刻件/印章","note":"给自己盖个章。"},
                   {"title":"香事四季","cats":"线香/焚香器具/香","note":"顺时令而焚。"}],
          "feature":{"kicker":"今日主推","catName":"线香","topic":"一炉香里的时间","angle":"以香入静","platform":"小红书+视频号"},
          "tags":["新手盘串必看！3个坑别踩。","百元手串，盘出千元质感？","我的第一串金刚，封神了！","手串搭配指南｜谁戴谁高级","送男友手串，他天天戴出门。","盘串三年，心态稳了。","小叶紫檀，越戴越亮？","星月菩提，这样盘不花。","沉香手串，闻着入睡。","手串不是装饰，是念想。","周末盘串，充电两不误。","老玩家才知道的盘玩顺序。","手串配色，高级感拉满。","男生戴串，低调有品。"],
          "emojiquotes":["生活不易，微醺解千愁。","不必合群，自洽就好。","清醒是种温柔的残忍。","洒脱不是不在乎，是看得开。","今天也想发疯，但忍住了。","孤独是成年人的奢侈品。"],
          "dailyplay":[{"scene":"喝酒微醺场","text":"生活不易，微醺解千愁。今晚小酌一杯，敬自己。"},
                       {"scene":"深夜宵夜场","text":"深夜的大排档，是成年人的避难所。"},
                       {"scene":"干饭吃货场","text":"吃是人生第一要义，减肥明天再说。"},
                       {"scene":"闲逛放风场","text":"无目的瞎溜达，才是真放松。"},
                       {"scene":"居家百态场","text":"不用社交的沙发，是全世界最舒服的地方。"},
                       {"scene":"打工人发疯场","text":"精神状态良好，但想发疯。"},
                       {"scene":"生活翻车场","text":"今天做饭翻车了，但笑得很开心。"},
                       {"scene":"互动提问场","text":"你今晚微醺还是宵夜？评论区交出来。"}],
          "strategy":["转化钩子：以『定心之物』切入，承接当下避险与自洽情绪；发布时机：早8通勤、晚9睡前双高峰；内容节奏：日更金句+周主题深更，电商节点前置种草。"]
        }''')
        incense = {"name":"老山檀香","position":"温润奶香，安神定气。","keywords":["奶香","温润","宁神"],"scenes":["独处","书房","睡前","茶席"],"hooks":["一炉老山檀，把浮躁按下去。","男生书房该有的味道，温润不冲。","睡前点它，比数羊管用。"],"pitch":"老山檀香气味醇厚带奶韵，安神助眠，书房茶席皆宜。","timing":"晚9-11点 · 小红书/视频号 助眠场景最佳。"}
    else:
        news = build_news(prev)
        trending_text = "\n".join(news.get("trending", []))
        creative = build_creative(prev, trending_text)
        incense = build_incense(prev, load_incense_pool())

    auction = build_auction(prev, news.get("auction", []))

    result = {
        "date": DATE,
        "updated": "每日 AI 生成 · 已更新",
        "quotes": creative.get("quotes") or prev.get("quotes", []),
        "auction": auction or prev.get("auction", []),
        "finance": news.get("finance") or prev.get("finance", []),
        "trending": news.get("trending") or prev.get("trending", []),
        "auto": news.get("auto") or prev.get("auto", []),
        "watch": news.get("watch") or prev.get("watch", []),
        "luxury": news.get("luxury") or prev.get("luxury", []),
        "ecom": creative.get("ecom") or prev.get("ecom", []),
        "ideas": creative.get("ideas") or prev.get("ideas", []),
        "feature": creative.get("feature") or prev.get("feature", {}),
        "tags": creative.get("tags") or prev.get("tags", []),
        "emojiquotes": creative.get("emojiquotes") or prev.get("emojiquotes", []),
        "dailyplay": creative.get("dailyplay") or prev.get("dailyplay", []),
        "strategy": creative.get("strategy") or prev.get("strategy", []),
        "incense": incense or prev.get("incense", {}),
    }

    # 校验：必需模块均非空
    for k in ("quotes", "auction", "finance", "trending", "auto", "watch", "luxury",
              "ecom", "ideas", "feature", "tags", "emojiquotes", "dailyplay", "strategy", "incense"):
        if not result.get(k):
            print(f"  [warn] 模块 {k} 为空，回退骨架")
            result[k] = skeleton()[k]

    with open(LIVE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print("  [ok] 写入", LIVE)
    print("  模块数量:", {k: (len(v) if isinstance(v, list) else "obj") for k, v in result.items() if k not in ("date", "updated")})

if __name__ == "__main__":
    main()
