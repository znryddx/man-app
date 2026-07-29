(function () {
  "use strict";

  // 30 天内容池：按今天日期取模，每天打开显示不同一天的内容（零日常积分、无需重新部署）
  const POOL = window.APP_DAYS && window.APP_DAYS.length ? window.APP_DAYS : [window.APP_DATA];
  const START = new Date(2026, 6, 29); // 2026-07-29 为第 0 天
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const dayIdx = ((Math.floor((today - START) / 86400000)) % POOL.length + POOL.length) % POOL.length;
  let D = POOL[dayIdx];
  D.__dayIndex = dayIdx + 1; // 1..30，便于状态栏显示

  const TITLES = {
    overview: "今日总览",
    quotes: "美学金句",
    auction: "拍卖行资讯",
    finance: "财经新闻",
    trending: "热点新闻",
    ecom: "文创 · 线香趋势",
    ideas: "爆款二创灵感",
    feature: "主推品类 · 选题",
    headlines: "吸睛标题库",
    copy: "情绪种草文案",
    tags: "爆款话题标签",
    strategy: "全案营销策略"
  };

  const NAV = [
    { id: "overview", label: "今日总览" },
    { group: "灵感来源", items: [{ id: "quotes", label: "美学金句" }] },
    {
      group: "内容生产",
      items: [
        { id: "auction", label: "拍卖行资讯" },
        { id: "finance", label: "财经新闻" },
        { id: "trending", label: "热点新闻" },
        { id: "ecom", label: "文创线香趋势" },
        { id: "ideas", label: "爆款二创灵感" },
        { id: "feature", label: "主推品类选题" }
      ]
    },
    {
      group: "传播物料",
      items: [
        { id: "headlines", label: "吸睛标题库" },
        { id: "copy", label: "情绪种草文案" },
        { id: "tags", label: "爆款话题标签" },
        { id: "strategy", label: "全案营销策略" }
      ]
    }
  ];

  function el(tag, props, children) {
    const n = document.createElement(tag);
    if (props) {
      for (const k in props) {
        if (k === "class") n.className = props[k];
        else if (k === "html") n.innerHTML = props[k];
        else if (k === "text") n.textContent = props[k];
        else n.setAttribute(k, props[k]);
      }
    }
    if (children) {
      (Array.isArray(children) ? children : [children]).forEach((c) => {
        if (c == null) return;
        n.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
      });
    }
    return n;
  }

  function secHead(title, en) {
    return el("div", { class: "sec-head" }, [
      el("div", { class: "sec-title", text: title }),
      el("div", { class: "sec-en", text: en })
    ]);
  }

  function section(id, title, en, body) {
    return el("section", { class: "section", id: id }, [secHead(title, en), body]);
  }

  /* ---------- Overview ---------- */
  function buildOverview() {
    const q = D.quotes[0];
    const hero = el("div", { class: "hero" }, [
      el("div", { class: "hero-kicker", text: "DAILY QUOTE" }),
      el("div", { class: "hero-quote", text: q.text }),
      el("div", { class: "hero-source", text: q.source }),
      el("div", { class: "hero-analysis", text: q.analysis })
    ]);

    const hl = (tag, title, meta, note, id) =>
      el("div", Object.assign({ class: "hl-card" }, id ? { id: id } : {}), [
        el("div", { class: "hl-tag", text: tag }),
        el("div", { class: "hl-title", text: title }),
        meta ? el("div", { class: "hl-meta", text: meta }) : null,
        el("div", { class: "hl-note", text: note })
      ]);

    const grid = el("div", { class: "hl-grid" }, [
      hl("拍卖高光", D.auction[0].lot, D.auction[0].meta, D.auction[0].note),
      hl("财经速览", D.finance[0].replace(/^\d+ · /, ""), "", D.finance[1].replace(/^\d+ · /, ""), "ov-finance"),
      hl("热点 TOP3", D.trending[0].replace(/^\d+ · /, ""), "", D.trending[5].replace(/^\d+ · /, ""), "ov-trending"),
      hl("主推品类", D.feature.catName, "", D.feature.topic)
    ]);

    return el("section", { class: "section", id: "overview" }, [
      secHead("今日总览", "TODAY AT A GLANCE"),
      hero,
      el("div", { style: "height:20px" }),
      grid
    ]);
  }

  /* ---------- Quotes ---------- */
  function buildQuotes() {
    const card = el("div", { class: "card" });
    D.quotes.forEach((q, i) => {
      if (i > 0) card.appendChild(el("div", { style: "height:1px;background:var(--hair);margin:18px 0" }));
      card.appendChild(el("div", { class: "hero-quote", style: "font-size:16px;margin:0", text: q.text }));
      card.appendChild(el("div", { class: "hero-source", style: "margin:6px 0", text: q.source }));
      card.appendChild(el("div", { class: "hero-analysis", style: "margin:0", text: q.analysis }));
    });
    return section("quotes", "美学金句 · 三则", "DAILY QUOTES", card);
  }

  /* ---------- Auction ---------- */
  function buildAuction() {
    const row = el("div", { class: "row-2" });
    D.auction.forEach((a) => {
      row.appendChild(
        el("div", { class: "acard" }, [
          el("div", { class: "lot", text: a.lot }),
          el("div", { class: "meta", text: a.meta }),
          el("div", { class: "note", text: a.note })
        ])
      );
    });
    return section("auction", "拍卖行资讯", "AUCTION WIRE", row);
  }

  /* ---------- 实时数据（财经/热点 打开时拉真实热榜，失败退回池） ---------- */
  const TRENDING_SOURCES = [
    { name: "微博", url: "https://api.vvhan.com/api/hotlist/wbHot" },
    { name: "百度", url: "https://api.vvhan.com/api/hotlist/baiduRD" },
    { name: "知乎", url: "https://api.vvhan.com/api/hotlist/zhihuHot" }
  ];
  const FINANCE_SOURCES = [
    { name: "财经热点", url: "https://api.vvhan.com/api/hotlist/cjrl" },
    { name: "财联社", url: "https://api.vvhan.com/api/hotlist/roll" }
  ];

  function normalizeHot(j) {
    let arr = null;
    if (Array.isArray(j)) arr = j;
    else if (j && Array.isArray(j.data)) arr = j.data;
    else if (j && j.data && Array.isArray(j.data.list)) arr = j.data.list;
    else if (j && j.data && Array.isArray(j.data.data)) arr = j.data.data;
    else if (j && Array.isArray(j.result)) arr = j.result;
    if (!arr) return [];
    return arr
      .map((x) => (x ? String(x.title || x.name || x.word || x.hotword || "").trim() : ""))
      .filter(Boolean)
      .slice(0, 12);
  }

  function fetchHot(sources, cb) {
    const all = [];
    const labels = [];
    const jobs = sources.map((s) =>
      (async () => {
        try {
          const ctrl = new AbortController();
          const to = setTimeout(() => ctrl.abort(), 6000);
          const r = await fetch(s.url, { signal: ctrl.signal, mode: "cors" });
          clearTimeout(to);
          if (!r.ok) return;
          const j = await r.json();
          const items = normalizeHot(j);
          if (items.length) { all.push(...items); labels.push(s.name); }
        } catch (e) {}
      })()
    );
    Promise.all(jobs).then(() => {
      const seen = new Set();
      const uniq = all.filter((t) => {
        const k = t.slice(0, 16);
        if (seen.has(k)) return false;
        seen.add(k);
        return true;
      });
      if (uniq.length) cb(uniq.slice(0, 10), labels.join("/"));
    });
  }

  function buildLiveSection(id, title, en, poolItems, sources) {
    const liveOn = !!(window.__LIVE && window.__LIVE.quotes);
    const badge = el("div", { class: "live-badge" + (liveOn ? " live" : ""), text: liveOn ? "每日生成 · AI" : "示例内容" });
    const wrap = el("div", { class: "cols-2" });
    poolItems.forEach((t) => wrap.appendChild(el("div", { class: "news-line", text: t })));
    const body = el("div", null, [badge, wrap]);
    const sec = section(id, title, en, body);
    if (!liveOn) {
      fetchHot(sources, (items, label) => {
        wrap.innerHTML = "";
        items.forEach((t) => wrap.appendChild(el("div", { class: "news-line", text: t })));
        badge.textContent = "实时 · " + label;
        badge.classList.add("live");
        onLiveReady(id, items);
      });
    }
    return sec;
  }

  function onLiveReady(id, items) {
    if (id === "finance" && items[0]) {
      const m = document.getElementById("ov-finance");
      if (m) m.querySelector(".hl-title").textContent = items[0];
    }
    if (id === "trending" && items[0] && items[5]) {
      const t = document.getElementById("ov-trending");
      if (t) {
        t.querySelector(".hl-title").textContent = items[0];
        t.querySelector(".hl-note").textContent = items[5];
      }
    }
  }

  /* ---------- Ecom ---------- */
  function buildEcom() {
    const card = el("div", { class: "card" });
    D.ecom.forEach((e) => {
      card.appendChild(
        el("div", { class: "ecom-row" }, [
          el("div", { class: "ecom-plat", text: e.platform }),
          el("div", { class: "ecom-desc", text: e.desc })
        ])
      );
    });
    return section("ecom", "文创 · 线香电商趋势", "E-COM TRENDS", card);
  }

  /* ---------- Ideas ---------- */
  function buildIdeas() {
    const row = el("div", { class: "row-2" });
    D.ideas.forEach((it) => {
      row.appendChild(
        el("div", { class: "acard" }, [
          el("div", { class: "lot", text: it.title }),
          el("div", { class: "meta", text: it.cats }),
          el("div", { class: "note", text: it.note })
        ])
      );
    });
    return section("ideas", "爆款二创灵感", "CREATIVE ANGLES", row);
  }

  /* ---------- Feature ---------- */
  function buildFeature() {
    const f = D.feature;
    const card = el("div", { class: "card feature" }, [
      el("div", { class: "kicker", text: f.kicker }),
      el("div", { class: "cat", text: f.catName }),
      el("div", { class: "topic", text: f.topic }),
      el("div", { class: "meta-line", text: f.angle }),
      el("div", { class: "meta-line", text: f.platform })
    ]);
    return section("feature", "主推品类 · 今日选题", "FEATURE & TOPIC", card);
  }

  /* ---------- Headlines ---------- */
  function buildHeadlines() {
    const list = el("div", { class: "hl-list" });
    D.headlines.forEach((h, i) => {
      list.appendChild(
        el("div", { class: "hl-item" }, [
          el("div", { class: "hl-idx", text: String(i + 1).padStart(2, "0") }),
          el("div", { class: "hl-text", text: h })
        ])
      );
    });
    return section("headlines", "吸睛标题库", "HEADLINE BANK", el("div", { class: "card" }, [list]));
  }

  /* ---------- Copy ---------- */
  function buildCopy() {
    const card = el("div", { class: "card" }, [
      el("div", { class: "kicker", text: D.copy.kicker }),
      el("div", { class: "copy-p", text: D.copy.paragraph })
    ]);
    return section("copy", "情绪种草文案", "EMOTIONAL COPY", card);
  }

  /* ---------- Tags ---------- */
  function buildTags() {
    const wrap = el("div", { class: "tag-wrap" });
    D.tags.forEach((t) => wrap.appendChild(el("div", { class: "tag", text: t })));
    return section("tags", "爆款话题标签", "HASHTAGS", el("div", { class: "card" }, [wrap]));
  }

  /* ---------- Strategy ---------- */
  function buildStrategy() {
    const card = el("div", { class: "card" });
    D.strategy.forEach((s) => card.appendChild(el("div", { class: "strat-line", text: s })));
    return section("strategy", "全案营销策略", "GROWTH PLAYBOOK", card);
  }

  /* ---------- Mount ---------- */
  function render() {
    if (window.__LIVE && window.__LIVE.quotes && window.__LIVE.quotes.length) D = window.__LIVE;
    const nav = document.getElementById("nav");
    const content = document.getElementById("content");
    const statusbar = document.getElementById("statusbar");

    NAV.forEach((item) => {
      if (item.group) {
        nav.appendChild(el("div", { class: "nav-group-label", text: item.group }));
        item.items.forEach((sub) => nav.appendChild(makeNav(sub.id, sub.label)));
      } else {
        nav.appendChild(makeNav(item.id, item.label));
      }
    });

    content.appendChild(buildOverview());
    content.appendChild(buildQuotes());
    content.appendChild(buildAuction());
    content.appendChild(buildLiveSection("finance", "财经新闻", "MARKETS", D.finance, FINANCE_SOURCES));
    content.appendChild(buildLiveSection("trending", "热点新闻", "TRENDING", D.trending, TRENDING_SOURCES));
    content.appendChild(buildEcom());
    content.appendChild(buildIdeas());
    content.appendChild(buildFeature());
    content.appendChild(buildHeadlines());
    content.appendChild(buildCopy());
    content.appendChild(buildTags());
    content.appendChild(buildStrategy());

    document.getElementById("topsub").textContent = "今日 " + D.date + " · " + D.updated;
    statusbar.textContent = "今日 " + D.date + " · " + D.updated;
    setActive("overview");
  }

  function makeNav(id, label) {
    const n = el("div", { class: "nav-item", "data-target": id }, [
      el("span", { class: "dot" }),
      el("span", { text: label })
    ]);
    n.addEventListener("click", () => {
      const target = document.getElementById(id);
      if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
      setActive(id);
    });
    return n;
  }

  function setActive(id) {
    document.querySelectorAll(".nav-item").forEach((n) => {
      n.classList.toggle("active", n.getAttribute("data-target") === id);
    });
    const t = TITLES[id] || "今日总览";
    document.getElementById("pageTitle").textContent = t;
  }

  /* ---------- Toast ---------- */
  let toastTimer;
  function toast(msg) {
    const t = document.getElementById("toast");
    t.textContent = msg;
    t.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => t.classList.remove("show"), 2200);
  }

  window.addEventListener("scroll", () => {
    // highlight nav based on visible section
    const secs = Array.from(document.querySelectorAll(".section"));
    let cur = secs[0] && secs[0].id;
    for (const s of secs) {
      const r = s.getBoundingClientRect();
      if (r.top <= 120) cur = s.id;
    }
    if (cur) setActive(cur);
  }, { passive: true });

  // ---------- 安装到桌面（PWA） ----------
  let deferredInstall = null;
  window.addEventListener("beforeinstallprompt", (e) => {
    e.preventDefault();
    deferredInstall = e;
    const b = document.getElementById("installBtn");
    const h = document.getElementById("installHint");
    if (b) b.hidden = false;        // 支持 PWA 一键安装则显示醒目按钮
    if (h) h.style.display = "none"; // 同时隐藏兜底提示
  });
  function doInstall() {
    if (deferredInstall) {
      deferredInstall.prompt();
      deferredInstall.userChoice.then((r) => {
        if (r.outcome === "accepted") toast("已安装到桌面 ✓");
        deferredInstall = null;
        const b = document.getElementById("installBtn");
        if (b) b.hidden = true;
      }).catch(() => {});
      return;
    }
    // 浏览器不支持一键安装 / 未触发安装事件：弹出带二维码的指引浮层
    openInstallHelp();
  }
  function openInstallHelp() {
    const ov = document.getElementById("installHelp");
    const qr = document.getElementById("ihQr");
    if (qr && !qr.getAttribute("src")) qr.setAttribute("src", "./icons/app-qr.png");
    if (ov) ov.hidden = false;
  }
  window.addEventListener("appinstalled", () => {
    const b = document.getElementById("installBtn"); if (b) b.hidden = true;
    const h = document.getElementById("installHint"); if (h) h.style.display = "none";
    toast("已安装到桌面 ✓");
  });

  document.addEventListener("DOMContentLoaded", () => {
    loadLiveThenRender();
    const gb = document.getElementById("genBtn");
    if (gb) gb.addEventListener("click", () => toast("已为你生成今日内容（演示）"));
    const ib = document.getElementById("installBtn");
    const ih = document.getElementById("installHintBtn");
    if (ib) ib.addEventListener("click", doInstall);
    if (ih) ih.addEventListener("click", doInstall);
    const ihc = document.getElementById("installHelpClose");
    if (ihc) ihc.addEventListener("click", () => { const ov = document.getElementById("installHelp"); if (ov) ov.hidden = true; });

    if ("serviceWorker" in navigator) {
      navigator.serviceWorker.register("./sw.js").catch(() => {});
    }

    // 打开页面即弹出安装指引（同一次访问只弹一次），免去用户自己找菜单
    try {
      if (!sessionStorage.getItem("installHelpShown")) {
        sessionStorage.setItem("installHelpShown", "1");
        setTimeout(openInstallHelp, 1200);
      }
    } catch (_) {}
  });

  // 打开时优先拉取「当日 AI 生成包」live.json；拿到就用，拿不到（1.5s 超时）退回 120 天池
  function loadLiveThenRender() {
    let done = false;
    const finish = () => {
      if (done) return;
      done = true;
      render();
    };
    const to = setTimeout(finish, 1500);
    fetch("./live.json", { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((j) => {
        if (j && j.quotes && Array.isArray(j.quotes) && j.finance && j.trending) {
          window.__LIVE = j;
        }
      })
      .catch(() => {})
      .finally(finish);
  }
})();
