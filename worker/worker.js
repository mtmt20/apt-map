/* 집콕맵 API (Cloudflare Worker + KV)
 *  POST /reports          {id, name, area, price, kind, note}  호가/실거래 제보 (익명, IP 시간당 20건 제한)
 *  GET  /reports?id=      단지별 제보 목록 (최근 50, 신고 3회 이상은 숨김)
 *  GET  /recent           전체 최근 제보 100건 (숨김 제외)
 *  POST /flag             {id, ts}  제보 신고 (IP당 같은 제보 1회)
 *  POST /favs             {code, ids}  찜 목록 동기화 / GET /favs?code=
 *  POST /alerts           {email, ids}  찜 단지 실거래 알림 등록  / GET /alerts/unsub?email=&t=
 *  GET  /admin/reports?key=   전체 제보(신고 수 포함)  / POST /admin/delete {key, id, ts}
 *  GET  /admin/alerts?key=    알림 등록 목록 (refresh.py 가 읽어 메일 발송)
 *  GET  /health
 * KV 바인딩: APT, 시크릿: ADMIN_KEY
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
const clean = (s, max) => String(s || "").replace(/[<>]/g, "").trim().slice(0, max);
const isEmail = (e) => /^[^\s@]{1,64}@[^\s@]{1,190}\.[a-z]{2,}$/i.test(e);

async function sha(s) {
  const b = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s));
  return [...new Uint8Array(b)].map((x) => x.toString(16).padStart(2, "0")).join("").slice(0, 24);
}
async function readJson(req) { try { return await req.json(); } catch (e) { return null; } }

export default {
  async fetch(req, env) {
    const url = new URL(req.url);
    const h = cors(req.headers.get("Origin"));
    if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: h });
    const path = url.pathname.replace(/\/+$/, "") || "/";
    const ip = req.headers.get("CF-Connecting-IP") || "0";
    const isAdmin = async (key) => !!env.ADMIN_KEY && key === env.ADMIN_KEY;
    try {
      if (path === "/health") return json({ ok: true, t: Date.now() }, 200, h);

      // ---- 제보 ----
      if (path === "/reports" && req.method === "GET") {
        const id = clean(url.searchParams.get("id"), 120);
        if (!id) return json({ error: "id required" }, 400, h);
        const list = ((await env.APT.get("reports:" + id, "json")) || []).filter((r) => (r.flags || 0) < 3 && !r.hidden);
        return json({ id, reports: list }, 200, h);
      }
      if (path === "/reports" && req.method === "POST") {
        const hour = Math.floor(Date.now() / 3600000);
        const rlKey = `rl:${ip}:${hour}`;
        const n = parseInt((await env.APT.get(rlKey)) || "0", 10);
        if (n >= 20) return json({ error: "too many reports, try later" }, 429, h);
        const body = await readJson(req);
        if (!body) return json({ error: "bad json" }, 400, h);
        if (body.hp) return json({ ok: true }, 200, h);                       // honeypot
        const id = clean(body.id, 120), kind = body.kind === "deal" ? "deal" : "ask";
        const area = Math.round(parseFloat(body.area) || 0), price = Math.round(parseFloat(body.price) || 0);
        const note = clean(body.note, 140);
        if (!id || !area || area < 10 || area > 400) return json({ error: "bad area" }, 400, h);
        if (!price || price < 1000 || price > 2000000) return json({ error: "bad price (만원)" }, 400, h);
        const rec = { area, price, kind, note, date: new Date().toISOString().slice(0, 10), ts: Date.now(), flags: 0, iph: await sha(ip) };
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
        const recent = ((await env.APT.get("recent", "json")) || []).filter((r) => (r.flags || 0) < 3 && !r.hidden);
        return json({ recent: recent.map((r) => { const o = Object.assign({}, r); delete o.iph; return o; }) }, 200, h);
      }
      if (path === "/flag" && req.method === "POST") {
        const body = await readJson(req);
        if (!body) return json({ error: "bad json" }, 400, h);
        const id = clean(body.id, 120), ts = parseInt(body.ts, 10);
        if (!id || !ts) return json({ error: "id, ts required" }, 400, h);
        const once = `flag:${await sha(ip)}:${id}:${ts}`;
        if (await env.APT.get(once)) return json({ ok: true, dup: true }, 200, h);
        await env.APT.put(once, "1", { expirationTtl: 60 * 60 * 24 * 30 });
        const bump = async (key) => {
          const list = (await env.APT.get(key, "json")) || [];
          let hit = false;
          list.forEach((r) => { if (r.ts === ts && (!r.id || r.id === id)) { r.flags = (r.flags || 0) + 1; hit = true; } });
          if (hit) await env.APT.put(key, JSON.stringify(list));
        };
        await bump("reports:" + id);
        await bump("recent");
        return json({ ok: true }, 200, h);
      }

      // ---- 찜 ----
      if (path === "/favs" && req.method === "GET") {
        const code = clean(url.searchParams.get("code"), 12).toUpperCase();
        if (!/^[A-Z0-9]{6,12}$/.test(code)) return json({ error: "bad code" }, 400, h);
        return json({ code, ids: (await env.APT.get("favs:" + code, "json")) || [] }, 200, h);
      }
      if (path === "/favs" && req.method === "POST") {
        const body = await readJson(req);
        if (!body) return json({ error: "bad json" }, 400, h);
        const code = clean(body.code, 12).toUpperCase();
        if (!/^[A-Z0-9]{6,12}$/.test(code)) return json({ error: "bad code" }, 400, h);
        const ids = (Array.isArray(body.ids) ? body.ids : []).map((x) => clean(x, 120)).filter(Boolean).slice(0, 200);
        await env.APT.put("favs:" + code, JSON.stringify(ids), { expirationTtl: 60 * 60 * 24 * 365 });
        return json({ ok: true, code, n: ids.length }, 200, h);
      }

      // ---- 실거래 알림 (이메일) ----
      if (path === "/alerts" && req.method === "POST") {
        const body = await readJson(req);
        if (!body) return json({ error: "bad json" }, 400, h);
        const email = clean(body.email, 254).toLowerCase();
        if (!isEmail(email)) return json({ error: "bad email" }, 400, h);
        const ids = (Array.isArray(body.ids) ? body.ids : []).map((x) => clean(x, 120)).filter(Boolean).slice(0, 100);
        if (!ids.length) return json({ error: "ids required" }, 400, h);
        const token = await sha(email + ":" + (env.ADMIN_KEY || "salt"));
        await env.APT.put("alerts:" + email, JSON.stringify({ email, ids, token, ts: Date.now() }), { expirationTtl: 60 * 60 * 24 * 365 });
        const idx = (await env.APT.get("alerts_index", "json")) || [];
        if (!idx.includes(email)) { idx.push(email); await env.APT.put("alerts_index", JSON.stringify(idx.slice(-5000))); }
        return json({ ok: true, n: ids.length }, 200, h);
      }
      if (path === "/alerts/unsub") {
        const email = clean(url.searchParams.get("email"), 254).toLowerCase(), t = clean(url.searchParams.get("t"), 40);
        const rec = await env.APT.get("alerts:" + email, "json");
        if (!rec || rec.token !== t) return new Response("잘못된 링크입니다.", { status: 400, headers: { "Content-Type": "text/plain; charset=utf-8" } });
        await env.APT.delete("alerts:" + email);
        return new Response("알림 수신이 해제되었습니다.", { status: 200, headers: { "Content-Type": "text/plain; charset=utf-8" } });
      }

      // ---- 관리자 ----
      if (path.startsWith("/admin/")) {
        const key = url.searchParams.get("key") || ((await readJson(req.clone())) || {}).key;
        if (!(await isAdmin(key))) return json({ error: "unauthorized" }, 401, h);
        if (path === "/admin/reports") {
          return json({ recent: (await env.APT.get("recent", "json")) || [] }, 200, h);
        }
        if (path === "/admin/delete" && req.method === "POST") {
          const body = await readJson(req);
          const id = clean(body.id, 120), ts = parseInt(body.ts, 10);
          const drop = async (k) => { const list = (await env.APT.get(k, "json")) || []; await env.APT.put(k, JSON.stringify(list.filter((r) => !(r.ts === ts && (!r.id || r.id === id))))); };
          await drop("reports:" + id);
          await drop("recent");
          return json({ ok: true }, 200, h);
        }
        if (path === "/admin/alerts") {
          const idx = (await env.APT.get("alerts_index", "json")) || [];
          const out = [];
          for (const e of idx) { const rec = await env.APT.get("alerts:" + e, "json"); if (rec) out.push(rec); }
          return json({ alerts: out }, 200, h);
        }
      }
      return json({ error: "not found" }, 404, h);
    } catch (e) {
      return json({ error: "server", detail: String(e && e.message) }, 500, h);
    }
  },
};
