/* 집콕맵 API (Cloudflare Worker + KV)
 *  POST /reports        {id, area, price, kind, note}  호가/실거래 제보 (익명, IP 시간당 20건 제한)
 *  GET  /reports?id=    단지별 제보 목록 (최근 50)
 *  GET  /recent         전체 최근 제보 100건
 *  POST /favs           {code, ids}  찜 목록 동기화 (기기 간 공유용 코드)
 *  GET  /favs?code=     찜 목록 조회
 *  GET  /health
 * KV 바인딩: APT
 */
const ALLOW = [/^https:\/\/[a-z0-9-]+\.github\.io$/, /^http:\/\/localhost(:\d+)?$/, /^http:\/\/127\.0\.0\.1(:\d+)?$/];

function cors(origin) {
  const ok = origin && ALLOW.some((re) => re.test(origin));
  return {
    "Access-Control-Allow-Origin": ok ? origin : "https://mtmt88087044-pixel.github.io",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
    "Access-Control-Allow-Headers": "content-type",
    "Access-Control-Max-Age": "86400",
    "Cache-Control": "no-store",
    "Content-Type": "application/json; charset=utf-8",
  };
}
const json = (obj, status, h) => new Response(JSON.stringify(obj), { status: status || 200, headers: h });

function clean(s, max) { return String(s || "").replace(/[<>]/g, "").trim().slice(0, max); }

export default {
  async fetch(req, env) {
    const url = new URL(req.url);
    const h = cors(req.headers.get("Origin"));
    if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: h });
    const path = url.pathname.replace(/\/+$/, "") || "/";
    try {
      if (path === "/health") return json({ ok: true, t: Date.now() }, 200, h);

      if (path === "/reports" && req.method === "GET") {
        const id = clean(url.searchParams.get("id"), 120);
        if (!id) return json({ error: "id required" }, 400, h);
        const list = (await env.APT.get("reports:" + id, "json")) || [];
        return json({ id, reports: list }, 200, h);
      }

      if (path === "/reports" && req.method === "POST") {
        const ip = req.headers.get("CF-Connecting-IP") || "0";
        const hour = Math.floor(Date.now() / 3600000);
        const rlKey = `rl:${ip}:${hour}`;
        const n = parseInt((await env.APT.get(rlKey)) || "0", 10);
        if (n >= 20) return json({ error: "too many reports, try later" }, 429, h);
        let body;
        try { body = await req.json(); } catch (e) { return json({ error: "bad json" }, 400, h); }
        if (body.hp) return json({ ok: true }, 200, h);                       // honeypot
        const id = clean(body.id, 120), kind = body.kind === "deal" ? "deal" : "ask";
        const area = Math.round(parseFloat(body.area) || 0), price = Math.round(parseFloat(body.price) || 0);
        const note = clean(body.note, 140);
        if (!id || !area || area < 10 || area > 400) return json({ error: "bad area" }, 400, h);
        if (!price || price < 1000 || price > 2000000) return json({ error: "bad price (만원)" }, 400, h);
        const rec = { area, price, kind, note, date: new Date().toISOString().slice(0, 10), ts: Date.now() };
        const key = "reports:" + id;
        const list = (await env.APT.get(key, "json")) || [];
        list.unshift(rec);
        await env.APT.put(key, JSON.stringify(list.slice(0, 50)));
        const recent = (await env.APT.get("recent", "json")) || [];
        recent.unshift(Object.assign({ id, name: clean(body.name, 60) }, rec));
        await env.APT.put("recent", JSON.stringify(recent.slice(0, 100)));
        await env.APT.put(rlKey, String(n + 1), { expirationTtl: 3700 });
        return json({ ok: true, count: list.length }, 200, h);
      }

      if (path === "/recent") {
        return json({ recent: (await env.APT.get("recent", "json")) || [] }, 200, h);
      }

      if (path === "/favs" && req.method === "GET") {
        const code = clean(url.searchParams.get("code"), 12).toUpperCase();
        if (!/^[A-Z0-9]{6,12}$/.test(code)) return json({ error: "bad code" }, 400, h);
        return json({ code, ids: (await env.APT.get("favs:" + code, "json")) || [] }, 200, h);
      }
      if (path === "/favs" && req.method === "POST") {
        let body;
        try { body = await req.json(); } catch (e) { return json({ error: "bad json" }, 400, h); }
        const code = clean(body.code, 12).toUpperCase();
        if (!/^[A-Z0-9]{6,12}$/.test(code)) return json({ error: "bad code" }, 400, h);
        const ids = (Array.isArray(body.ids) ? body.ids : []).map((x) => clean(x, 120)).filter(Boolean).slice(0, 200);
        await env.APT.put("favs:" + code, JSON.stringify(ids), { expirationTtl: 60 * 60 * 24 * 365 });
        return json({ ok: true, code, n: ids.length }, 200, h);
      }
      return json({ error: "not found" }, 404, h);
    } catch (e) {
      return json({ error: "server", detail: String(e && e.message) }, 500, h);
    }
  },
};
