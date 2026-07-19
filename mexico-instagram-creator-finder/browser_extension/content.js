(() => {
  if (globalThis.__mcfContentLoaded) return;
  globalThis.__mcfContentLoaded = true;

  const COLLECTION_VERSION = "0.5.0";
  const text = el => (el?.textContent || "").trim();
  const unique = values => [...new Set(values.filter(Boolean))];
  const absolute = href => { try { return new URL(href, location.origin).href; } catch (_) { return null; } };
  const publicExternalUrl = href => {
    try {
      const url = new URL(href, location.origin);
      if (url.hostname === "l.instagram.com") {
        const target = url.searchParams.get("u");
        return target ? new URL(target).href : null;
      }
      return url.hostname.endsWith("instagram.com") ? null : url.href;
    } catch (_) { return null; }
  };
  const usernameFromUrl = href => {
    try {
      const parts = new URL(href, location.origin).pathname.split("/").filter(Boolean);
      const first = parts[0];
      return first && parts.length === 1 && !["p", "reel", "tv", "explore", "accounts", "stories"].includes(first)
        ? first.toLowerCase() : null;
    } catch (_) { return null; }
  };
  const normalizeUsername = value => {
    const candidate = String(value || "").trim().replace(/^@/, "").toLowerCase();
    return /^[a-z0-9._]{1,30}$/i.test(candidate) ? candidate : null;
  };
  function safety() {
    const body = document.body?.innerText.toLowerCase() || "";
    if (/\/accounts\/login/.test(location.pathname)) return "Instagram 登录状态失效";
    if (/challenge|checkpoint/.test(location.pathname)) return "Instagram Challenge，需要人工处理";
    if (body.includes("please wait a few minutes") || body.includes("try again later") || body.includes("安全验证") || /\b429\b/.test(body)) return "Instagram 限流或安全警告";
    return null;
  }
  function meta(name) { return document.querySelector(`meta[property='${name}'],meta[name='${name}']`)?.content || null; }
  async function waitForPageData(pageType) {
    const selectors = {
      profile: "header",
      hashtag: "a[href*='/p/'],a[href*='/reel/'],a[href*='/tv/']",
      keyword: "a[href*='/p/'],a[href*='/reel/'],a[href*='/tv/']",
      public_list: "main",
      media: "main,article,time,meta[property='og:description']",
    };
    const selector = selectors[pageType];
    for (let attempt = 0; selector && attempt < 20; attempt += 1) {
      if (document.querySelector(selector)) return;
      await new Promise(resolve => setTimeout(resolve, 500));
    }
  }
  function labelledCount(raw, labels) {
    const number = "([\\d.,]+\\s*[KMB万]?)";
    const label = `(?:${labels.join("|")})`;
    return raw.match(new RegExp(`${number}\\s*${label}`, "i"))?.[1]
      || raw.match(new RegExp(`${label}\\s*${number}`, "i"))?.[1]
      || null;
  }
  function isPrivateProfile() {
    const exactPhrases = [
      "this account is private", "esta cuenta es privada", "cette account est privée",
      "此帐户为私密帐户", "此帳號不公開", "这是私密帐号", "這是私人帳號",
    ];
    const areas = [...document.querySelectorAll("main section,main article,header+div")];
    return areas.some(area => exactPhrases.some(phrase => text(area).toLowerCase().includes(phrase)));
  }
  function recommendationCandidates(username) {
    const headings = [...document.querySelectorAll("main h1,main h2,main h3,main span")]
      .filter(el => /similar|suggested|recommended|相似|推荐|推薦|sugerencias|similares/i.test(text(el)));
    const scopes = headings.map(el => el.closest("section") || el.parentElement?.parentElement).filter(Boolean);
    return unique(scopes.flatMap(scope => [...scope.querySelectorAll("a[href]")].map(a => usernameFromUrl(a.href))))
      .filter(value => value && value !== username).slice(0, 20)
      .map(value => ({username: value, profile_url: `https://www.instagram.com/${value}/`}));
  }
  function collectProfile() {
    const username = usernameFromUrl(location.href);
    const header = document.querySelector("header");
    const description = meta("og:description") || "";
    const headerText = text(header);
    const countText = `${description} ${headerText}`;
    const links = unique([...(header?.querySelectorAll("a[href]") || [])].map(a => publicExternalUrl(a.href)));
    const email = (headerText.match(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/i) || [])[0] || null;
    const media = unique([...document.querySelectorAll("main a[href*='/p/'],main a[href*='/reel/'],main a[href*='/tv/']")]
      .map(a => absolute(a.href))).slice(0, 12);
    return {
      source: "instagram_web_extension", collected_at: new Date().toISOString(), page_url: location.href,
      collection_version: COLLECTION_VERSION,
      profile: {
        username,
        full_name: text(header?.querySelector("h1,h2")) || null,
        biography: headerText || null,
        follower_text: labelledCount(countText, ["followers?", "粉丝", "粉絲", "seguidores"]),
        following_text: labelledCount(countText, ["following", "关注", "追蹤中", "seguidos"]),
        post_count_text: labelledCount(countText, ["posts?", "帖子", "貼文", "publicaciones"]),
        external_links: links,
        public_email: email,
        profile_pic_url: header?.querySelector("img")?.src || null,
        is_private: isPrivateProfile(),
        is_verified: !!header?.querySelector("svg[aria-label*='Verified'],svg[aria-label*='认证'],svg[aria-label*='Verificado']"),
        field_sources: {follower_text: "labelled_profile_text", following_text: "labelled_profile_text", post_count_text: "labelled_profile_text", is_private: "profile_empty_state"},
      },
      visible_recommendations: recommendationCandidates(username), recent_media_urls: media,
    };
  }
  function collectList(type) {
    const mediaUrls = unique([...document.querySelectorAll("main a[href*='/p/'],main a[href*='/reel/'],main a[href*='/tv/']")]
      .map(a => absolute(a.href))).slice(0, 20);
    const candidates = type === "hashtag" ? [] : unique([...document.querySelectorAll("main a[href]")]
      .map(a => usernameFromUrl(a.href))).slice(0, 200)
      .map(username => ({username, profile_url: `https://www.instagram.com/${username}/`}));
    return {source_page_url: location.href, source_type: type, candidates, media_urls: mediaUrls};
  }
  function structuredAuthor() {
    for (const node of document.querySelectorAll("script[type='application/ld+json']")) {
      try {
        const data = JSON.parse(node.textContent || "{}");
        const value = data.author?.alternateName || data.author?.name;
        if (typeof value === "string") return value.replace(/^@/, "").toLowerCase();
      } catch (_) { /* ignore invalid page JSON */ }
    }
    return null;
  }
  function metaAuthor() {
    const values = [meta("og:title"), meta("og:description"), document.title].filter(Boolean);
    const patterns = [
      /@([a-z0-9._]{1,30})\b/i,
      /^([a-z0-9._]{1,30})\s+(?:on Instagram|en Instagram)\b/i,
      /(?:Instagram (?:photo|video|reel) by|foto de Instagram de|video de Instagram de)\s+([^(@|·:]+?)\s*\(@([a-z0-9._]{1,30})\)/i,
    ];
    for (const value of values) {
      for (const pattern of patterns) {
        const match = value.match(pattern);
        const username = normalizeUsername(match?.[2] || match?.[1]);
        if (username) return username;
      }
    }
    return null;
  }
  function domAuthor() {
    const scopes = unique([
      document.querySelector("article header"),
      document.querySelector("main article"),
      document.querySelector("main"),
    ]);
    let best = null;
    for (const scope of scopes) {
      for (const link of scope.querySelectorAll("a[href]")) {
        const username = usernameFromUrl(link.href);
        if (!username) continue;
        const rect = link.getBoundingClientRect();
        let score = 0;
        if (link.closest("header")) score += 10;
        if (link.closest("article")) score += 6;
        if (normalizeUsername(text(link)) === username) score += 4;
        if (String(link.getAttribute("aria-label") || "").toLowerCase().includes(username)) score += 3;
        if (rect.top >= 0 && rect.top < 700) score += 2;
        if (link.closest("nav")) score -= 20;
        if (!best || score > best.score) best = {username, score};
      }
      if (best?.score >= 10) break;
    }
    return best?.score >= 0 ? best.username : null;
  }
  function embeddedAuthor(shortcode) {
    const ownerPatterns = [
      /["\\]owner["\\]\s*:\s*\{.{0,2500}?["\\]username["\\]\s*:\s*["\\]([a-z0-9._]{1,30})/i,
      /["\\]author["\\]\s*:\s*\{.{0,1200}?["\\]username["\\]\s*:\s*["\\]([a-z0-9._]{1,30})/i,
      /["\\]alternateName["\\]\s*:\s*["\\]@?([a-z0-9._]{1,30})/i,
    ];
    const scripts = [...document.scripts].filter(node => {
      const value = node.textContent || "";
      return value.length < 3000000 && (!shortcode || value.includes(shortcode));
    });
    for (const node of scripts) {
      const value = node.textContent || "";
      for (const pattern of ownerPatterns) {
        const username = normalizeUsername(value.match(pattern)?.[1]);
        if (username) return username;
      }
    }
    return null;
  }
  function resolveMediaAuthor(shortcode) {
    const methods = [
      ["meta", metaAuthor],
      ["dom", domAuthor],
      ["json_ld", structuredAuthor],
      ["embedded", () => embeddedAuthor(shortcode)],
    ];
    for (const [source, resolver] of methods) {
      const username = normalizeUsername(resolver());
      if (username) return {username, source};
    }
    return {username: null, source: null};
  }
  function mediaDiagnostics() {
    return {
      path_type: location.pathname.split("/").filter(Boolean)[0] || "unknown",
      article_count: document.querySelectorAll("article").length,
      main_profile_links: [...document.querySelectorAll("main a[href]")].filter(link => usernameFromUrl(link.href)).length,
      has_og_title: Boolean(meta("og:title")),
      has_og_description: Boolean(meta("og:description")),
      has_time: Boolean(document.querySelector("time")),
    };
  }
  function collectMedia() {
    const match = location.pathname.match(/\/(?:p|reel|tv)\/([^/]+)/);
    const article = document.querySelector("article");
    const resolvedAuthor = resolveMediaAuthor(match?.[1] || "");
    const author = resolvedAuthor.username;
    const raw = meta("og:description") || text(article);
    const mentionedUsernames = unique([
      ...[...(article?.querySelectorAll("a[href]") || [])].map(link => usernameFromUrl(link.href)),
      ...(raw.match(/@[a-z0-9._]{1,30}/gi) || []).map(value => value.slice(1).toLowerCase()),
    ]).filter(value => value && value !== author).slice(0, 20);
    const likes = raw.match(/([\d.,]+\s*[KMB万]?)\s+(?:likes|Me gusta|赞|讚)/i);
    const comments = raw.match(/([\d.,]+\s*[KMB万]?)\s+(?:comments|comentarios|评论|留言)/i);
    const views = raw.match(/([\d.,]+\s*[KMB万]?)\s+(?:views|reproducciones|播放)/i);
    const parse = value => {
      if (!value) return null;
      const normalized = value.replace(/,/g, ""); const m = normalized.match(/[\d.]+/); if (!m) return null;
      const n = Number(m[0]); return Math.round(n * (/K/i.test(value) ? 1000 : /M/i.test(value) ? 1000000 : /B/i.test(value) ? 1000000000 : /万/.test(value) ? 10000 : 1));
    };
    return {username: author, media_url: location.href, shortcode: match?.[1] || "", media_type: location.pathname.includes("/reel/") ? "reel" : "post", taken_at: document.querySelector("time")?.dateTime || null, caption: raw.slice(0, 3000), like_count: parse(likes?.[1]), comment_count: parse(comments?.[1]), visible_play_count: parse(views?.[1]), is_reel: location.pathname.includes("/reel/"), collected_at: new Date().toISOString(), mentioned_usernames: mentionedUsernames, field_sources: {username: resolvedAuthor.source}};
  }
  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if (message.type !== "COLLECT_TASK_ITEM") return;
    (async () => {
      const safetyError = safety();
      if (safetyError) { sendResponse({ok: false, payload: null, safeStop: true, retryable: false, error: safetyError}); return; }
      try {
        await waitForPageData(message.pageType);
        const payload = message.pageType === "profile" ? collectProfile() : message.pageType === "media" ? collectMedia() : collectList(message.pageType);
        if (message.pageType === "profile" && !payload.profile.username) throw new Error("主页用户名不可用");
        if (message.pageType === "media" && (!payload.username || !payload.shortcode)) {
          sendResponse({ok: false, payload: null, safeStop: false, retryable: false, error: "媒体作者不可用", errorCode: "media_author_unresolved", diagnostics: mediaDiagnostics()});
          return;
        }
        sendResponse({ok: true, payload, safeStop: false, retryable: false, error: null});
      } catch (err) { sendResponse({ok: false, payload: null, safeStop: false, retryable: true, error: err.message, diagnostics: message.pageType === "media" ? mediaDiagnostics() : {}}); }
    })();
    return true;
  });
})();
