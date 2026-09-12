/* 집콕맵 MVP - 실거래·호가·학군·도로·경매 */
(function () {
  "use strict";
  const $ = (s, el) => (el || document).querySelector(s);
  const $$ = (s, el) => Array.from((el || document).querySelectorAll(s));
  const PY = 3.3058;
  const dark = matchMedia("(prefers-color-scheme: dark)").matches;

  const state = {
    complexes: [], auctions: [], schools: null, meta: null,
    area: "all", sort: null, q: "",
    selected: null, markers: {}, aucMarkers: [], schoolMarkers: [],
    layers: { school: true, road: false, auction: false },
  };

  // ---------- utils ----------
  const fmtPrice = (v) => v == null ? "-" : v >= 10000 ? (v / 10000).toFixed(v >= 100000 ? 0 : 1).replace(/\.0$/, "") + "억" : v.toLocaleString() + "만";
  const fmtChg = (v) => v == null ? "" : `<span class="chg ${v >= 0 ? "up" : "down"}">${v >= 0 ? "+" : ""}${v}%</span>`;
  const bucket = (area) => area < 70 ? "59" : area < 100 ? "84" : "114";
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  function toast(msg) {
    const t = document.createElement("div"); t.className = "toast"; t.textContent = msg; document.body.appendChild(t);
    setTimeout(() => t.remove(), 2200);
  }
  function repArea(c, area) {
    const list = c.by_area || [];
    if (area !== "all") return list.find((a) => bucket(a.area) === area) || null;
    return list.find((a) => bucket(a.area) === "84") || list.slice().sort((a, b) => b.count - a.count)[0] || null;
  }
  function areaMatch(c) { return state.area === "all" || (c.by_area || []).some((a) => bucket(a.area) === state.area); }

  // ---------- map ----------
  // 베이스맵: OpenFreeMap (키 불필요, 벡터). 실패 시 OSM 래스터로 폴백
  const OSM_RASTER = { version: 8, sources: { osm: { type: "raster", tileSize: 256, attribution: "© OpenStreetMap contributors",
    tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"] } }, layers: [{ id: "osm", type: "raster", source: "osm" }] };
  const map = new maplibregl.Map({
    container: "map",
    style: dark ? "https://tiles.openfreemap.org/styles/dark" : "https://tiles.openfreemap.org/styles/positron",
    center: [126.9515, 37.5505], zoom: 14.6, attributionControl: false, maxZoom: 19,
  });
  window.__app = { map, state };
  let mapReady = false;
  map.once("load", () => { mapReady = true; });
  map.once("error", (e) => { if (!map.isStyleLoaded()) { console.warn("basemap fallback", e && e.error); map.setStyle(OSM_RASTER); } });
  setTimeout(() => { if (!map.isStyleLoaded()) { console.warn("basemap timeout -> OSM raster"); map.setStyle(OSM_RASTER); } }, 10000);
  // 스타일이 (다시) 로드될 때마다 오버레이 레이어를 붙인다 (폴백 setStyle 포함)
  map.on("style.load", () => { if (state.schools && !map.getSource("schools")) addLayers(); });
  // 탭 전환/창 크기 변경 후 캔버스 크기 재계산
  document.addEventListener("visibilitychange", () => { if (!document.hidden) setTimeout(() => map.resize(), 50); });
  map.addControl(new maplibregl.AttributionControl({ compact: true }), "top-left");

  const PALETTE = ["#7c3aed", "#0ea5e9", "#f59e0b", "#10b981", "#ec4899", "#f97316", "#14b8a6", "#6366f1"];

  function addLayers() {
    // 학군
    const names = state.schools.features.filter((f) => f.properties.kind === "zone").map((f) => f.properties.name);
    const matchExpr = ["match", ["get", "name"]];
    names.forEach((n, i) => matchExpr.push(n, PALETTE[i % PALETTE.length]));
    matchExpr.push("#94a3b8");
    map.addSource("schools", { type: "geojson", data: state.schools });
    map.addLayer({ id: "school-fill", type: "fill", source: "schools", filter: ["==", ["get", "kind"], "zone"],
      paint: { "fill-color": matchExpr, "fill-opacity": 0.13 } });
    map.addLayer({ id: "school-line", type: "line", source: "schools", filter: ["==", ["get", "kind"], "zone"],
      paint: { "line-color": matchExpr, "line-width": 2, "line-dasharray": [3, 2], "line-opacity": 0.9 } });
    state.schools.features.filter((f) => f.properties.kind === "school").forEach((f, i) => {
      const el = document.createElement("div"); el.className = "mk school";
      el.style.color = PALETTE[names.indexOf(f.properties.name) % PALETTE.length];
      el.innerHTML = `🏫 ${esc(f.properties.name.replace("등학교", ""))}`;
      state.schoolMarkers.push(new maplibregl.Marker({ element: el, anchor: "center" }).setLngLat(f.geometry.coordinates).addTo(map));
    });

    // 도로
    map.addSource("roads", { type: "geojson", data: "data/roads.geojson" });
    const z = (a, b) => ["interpolate", ["linear"], ["zoom"], 13, a, 18, b];
    map.addLayer({ id: "road-walk", type: "line", source: "roads",
      filter: ["all", ["!=", ["get", "class"], "alley"], ["in", ["get", "sidewalk"], ["literal", ["yes", "likely"]]]],
      layout: { "line-cap": "round", "line-join": "round", visibility: "none" },
      paint: { "line-color": "#22c55e", "line-width": ["interpolate", ["linear"], ["zoom"], 13, ["case", ["==", ["get", "class"], "major"], 6, 4], 18, ["case", ["==", ["get", "class"], "major"], 15, 9]], "line-opacity": 0.85 } });
    map.addLayer({ id: "road-alley", type: "line", source: "roads", filter: ["==", ["get", "class"], "alley"],
      layout: { visibility: "none" }, paint: { "line-color": dark ? "#475569" : "#cbd5e1", "line-width": z(1, 3), "line-dasharray": [2, 2] } });
    map.addLayer({ id: "road-minor", type: "line", source: "roads", filter: ["==", ["get", "class"], "minor"],
      layout: { "line-cap": "round", visibility: "none" }, paint: { "line-color": "#94a3b8", "line-width": z(1.5, 5) } });
    map.addLayer({ id: "road-major", type: "line", source: "roads", filter: ["==", ["get", "class"], "major"],
      layout: { "line-cap": "round", "line-join": "round", visibility: "none" },
      paint: { "line-color": "#f97316", "line-width": z(3, 10), "line-opacity": 0.95 } });
    map.on("click", "road-major", (e) => { const p = e.features[0].properties; toast(`${p.name || "이름 없는 큰길"} · ${p.lanes ? p.lanes + "차로 · " : ""}인도 ${p.sidewalk === "yes" ? "있음" : "추정"}`); });
    map.on("click", "school-fill", (e) => { if (!e.originalEvent._mk) toast(`${e.features[0].properties.name} 통학구역 · ${e.features[0].properties.note || ""}`); });
    ["road-major", "school-fill"].forEach((id) => { map.on("mouseenter", id, () => map.getCanvas().style.cursor = "pointer"); map.on("mouseleave", id, () => map.getCanvas().style.cursor = ""); });

    // 경매
    state.auctions.forEach((a) => {
      const el = document.createElement("div"); el.className = "mk auction";
      el.innerHTML = `⚖️ ${fmtPrice(a.min_price)} <small style="color:#fde68a">${a.fail_count}회 유찰</small>`;
      el.addEventListener("click", (ev) => { ev.stopPropagation(); openDetail(a.complex_id, "half"); });
      const m = new maplibregl.Marker({ element: el, anchor: "bottom", offset: [0, -58] }).setLngLat([a.lng, a.lat]);
      state.aucMarkers.push(m);
    });
    applyLayers();
  }

  function applyLayers() {
    const v = (ids, on) => ids.forEach((id) => map.getLayer(id) && map.setLayoutProperty(id, "visibility", on ? "visible" : "none"));
    v(["school-fill", "school-line"], state.layers.school);
    state.schoolMarkers.forEach((m) => m.getElement().style.display = state.layers.school && map.getZoom() >= 14.3 ? "" : "none");
    v(["road-walk", "road-alley", "road-minor", "road-major"], state.layers.road);
    $("#legend").hidden = !state.layers.road;
    state.aucMarkers.forEach((m) => state.layers.auction ? m.addTo(map) : m.remove());
    $$(".lyr[data-layer]").forEach((b) => b.classList.toggle("on", !!state.layers[b.dataset.layer]));
  }

  // ---------- markers ----------
  function renderMarkers() {
    state.complexes.forEach((c) => {
      const rep = repArea(c, state.area);
      let m = state.markers[c.id];
      if (!m) {
        const el = document.createElement("div"); el.className = "mk";
        el.addEventListener("click", (ev) => { ev.stopPropagation(); openDetail(c.id, "half"); });
        m = state.markers[c.id] = new maplibregl.Marker({ element: el, anchor: "bottom", offset: [0, -4] }).setLngLat([c.lng, c.lat]).addTo(map);
      }
      const el = m.getElement();
      const z = map.getZoom();
      const compact = z < 14.8;
      el.style.display = (z < 13.2 && c.trade_count_1y < 20) || (z < 14 && c.trade_count_1y < 10) || (z < 14.8 && c.trade_count_1y < 4) ? "none" : "";
      el.classList.toggle("compact", compact);
      const dim = !areaMatch(c) || (state.q && !matchQ(c));
      el.classList.toggle("dim", dim);
      el.classList.toggle("sel", state.selected === c.id);
      el.innerHTML = !rep ? `<small>${esc(c.name)}</small><b>-</b>`
        : compact ? `<b>${fmtPrice(rep.latest)}</b><small>${rep.area}㎡</small>`
        : `<small>${esc(c.name.length > 9 ? c.name.slice(0, 9) + "…" : c.name)}</small><b>${fmtPrice(rep.latest)}</b><small>${rep.area}㎡ ${fmtChg(c.chg_1y)}</small>`;
    });
  }
  const matchQ = (c) => !state.q || (c.name + c.umd + c.addr).toLowerCase().includes(state.q.toLowerCase());

  // ---------- list ----------
  function visibleComplexes() {
    let list = state.complexes.filter((c) => areaMatch(c) && matchQ(c));
    if (state.sort === "ppy") list.sort((a, b) => (b.ppy || 0) - (a.ppy || 0));
    else if (state.sort === "chg") list.sort((a, b) => (b.chg_1y || 0) - (a.chg_1y || 0));
    else if (state.sort === "school") list = list.filter((c) => c.school.chopuma).sort((a, b) => a.school.elem_dist - b.school.elem_dist);
    else if (state.sort === "gap") list = list.filter((c) => c.jeonse_ratio).sort((a, b) => b.jeonse_ratio - a.jeonse_ratio);
    else list.sort((a, b) => b.trade_count_1y - a.trade_count_1y);
    return list;
  }
  function renderList() {
    const list = visibleComplexes();
    $("#listCount").textContent = `단지 ${list.length}개`;
    $("#list").innerHTML = list.map((c) => {
      const rep = repArea(c, state.area);
      const tags = [
        ...(c.school.chopuma ? [`<span class="tag school">초품아 ${esc(c.school.elem.replace("등학교", ""))}</span>`] : [`<span class="tag">${esc(c.school.elem.replace("등학교", ""))} ${c.school.elem_walk_min}분</span>`]),
        ...c.pros.slice(0, 2).filter((p) => !p.startsWith("초품아")).map((p) => `<span class="tag good">${esc(p)}</span>`),
        ...c.cons.slice(0, 1).map((p) => `<span class="tag bad">${esc(p)}</span>`),
        ...(c.jeonse_ratio ? [`<span class="tag ${c.jeonse_ratio >= 90 ? "bad" : ""}">전세가율 ${c.jeonse_ratio}%</span>`] : []),
        ...(c.sale_type === "혼합" ? [`<span class="tag">분양·임대 혼합</span>`] : []),
      ].join("");
      return `<div class="card ${state.selected === c.id ? "sel" : ""}" data-id="${c.id}">
        <div><h3>${esc(c.name)}</h3><div class="sub">${esc(c.umd)} · ${c.households ? c.households.toLocaleString() + "세대 · " : ""}${c.built}년 · ${esc(c.station.name)} ${c.station.walk_min}분</div></div>
        <div class="price">${rep ? fmtPrice(rep.latest) : "-"}<small>${rep ? "전용 " + rep.area + "㎡ 실거래" : ""} ${fmtChg(c.chg_1y)}</small></div>
        <div class="tags">${tags}</div></div>`;
    }).join("") || `<div class="muted" style="padding:20px 4px">조건에 맞는 단지가 없어요.</div>`;
    $$(".card", $("#list")).forEach((el) => el.addEventListener("click", () => openDetail(el.dataset.id, "full")));
  }

  // ---------- detail ----------
  function chartSVG(trades, areaSel) {
    const pts = trades.filter((t) => !areaSel || bucket(t.area) === areaSel).map((t) => ({ d: new Date(t.date), v: t.price / (t.area / PY), p: t.price }));
    if (pts.length < 2) return `<div class="muted" style="font-size:13px">거래가 적어 추세를 그릴 수 없어요.</div>`;
    const W = 340, H = 150, L = 8, R = 8, T = 12, B = 22;
    const xs = pts.map((p) => p.d.getTime()), vs = pts.map((p) => p.v);
    const x0 = Math.min(...xs), x1 = Math.max(...xs), v0 = Math.min(...vs) * 0.97, v1 = Math.max(...vs) * 1.03;
    const X = (x) => L + (x - x0) / (x1 - x0 || 1) * (W - L - R), Y = (v) => T + (1 - (v - v0) / (v1 - v0 || 1)) * (H - T - B);
    // 월별 중앙값 선
    const byM = {};
    pts.forEach((p) => { const k = p.d.getFullYear() * 12 + p.d.getMonth(); (byM[k] = byM[k] || []).push(p.v); });
    const line = Object.keys(byM).map(Number).sort((a, b) => a - b).map((k) => {
      const arr = byM[k].sort((a, b) => a - b); const med = arr[Math.floor(arr.length / 2)];
      return [X(new Date(Math.floor(k / 12), k % 12, 15).getTime()), Y(med)];
    });
    const path = line.map((p, i) => (i ? "L" : "M") + p[0].toFixed(1) + " " + p[1].toFixed(1)).join(" ");
    const dots = pts.map((p) => `<circle cx="${X(p.d.getTime()).toFixed(1)}" cy="${Y(p.v).toFixed(1)}" r="3" fill="#2563eb" opacity=".45"><title>${p.d.toISOString().slice(0, 10)} ${fmtPrice(p.p)} (평당 ${Math.round(p.v).toLocaleString()}만)</title></circle>`).join("");
    const first = pts[0].d, last = pts[pts.length - 1].d;
    const lab = (d) => `${String(d.getFullYear()).slice(2)}.${d.getMonth() + 1}`;
    return `<svg class="chart" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">
      <path d="${path}" fill="none" stroke="#2563eb" stroke-width="2.5" stroke-linejoin="round"/>${dots}
      <text x="${L}" y="${H - 6}" font-size="11" fill="#94a3b8">${lab(first)}</text>
      <text x="${W - R}" y="${H - 6}" font-size="11" fill="#94a3b8" text-anchor="end">${lab(last)}</text>
      <text x="${W - R}" y="${T}" font-size="11" fill="#94a3b8" text-anchor="end">평당 ${Math.round(v1 / 1.03).toLocaleString()}만</text></svg>`;
  }

  function openDetail(id, sheetState) {
    const c = state.complexes.find((x) => x.id === id); if (!c) return;
    state.selected = id;
    renderMarkers();
    map.flyTo({ center: [c.lng, c.lat], zoom: Math.max(map.getZoom(), 15.2), offset: [0, innerWidth < 900 ? -innerHeight * 0.18 : 0], duration: 700 });
    const areas = c.by_area || [];
    let areaSel = state.area !== "all" && areas.some((a) => bucket(a.area) === state.area) ? state.area : (areas.some((a) => bucket(a.area) === "84") ? "84" : bucket(areas[0].area));
    const aucs = state.auctions.filter((a) => a.complex_id === id);
    const reports = JSON.parse(localStorage.getItem("askReports") || "{}")[id] || [];

    function render() {
      const rep = areas.find((a) => bucket(a.area) === areaSel) || areas[0];
      const ask = c.ask;
      const askLow = ask ? ask.low_ppy * (rep.area / PY) : null, askHigh = ask ? ask.high_ppy * (rep.area / PY) : null;
      const lo = Math.min(rep.latest, askLow || rep.latest) * 0.96, hi = Math.max(rep.latest, askHigh || rep.latest) * 1.04;
      const pos = (v) => ((v - lo) / (hi - lo) * 100).toFixed(1) + "%";
      const age = new Date().getFullYear() - c.built;
      $("#detailView").innerHTML = `
        <div class="d-head"><button class="back" id="backBtn">‹</button>
          <div><h2>${esc(c.name)}</h2><div class="sub">${esc(c.addr)}${c.households ? ` · <b>${c.households.toLocaleString()}세대</b>` : ""} · ${c.built}년 (${age}년차)${c.max_floor ? ` · 최고 ${c.max_floor}층` : ""}${c.dongs ? ` · ${c.dongs}개동` : ""}${c.far ? ` · 용적률 ${c.far}%` : ""}</div></div></div>

        <div class="section">
          <div class="atabs">${areas.map((a) => `<button class="atab ${bucket(a.area) === areaSel ? "on" : ""}" data-a="${bucket(a.area)}">${a.area}㎡ <span class="muted">${a.pyeong}평형</span></button>`).join("")}</div>
          <div class="hero"><div class="big">${fmtPrice(rep.latest)}<small>최근 실거래 · ${rep.latest_date.slice(2).replace(/-/g, ".")}</small></div>
            <div class="meta">평당 <b>${Math.round(rep.latest / (rep.area / PY)).toLocaleString()}만</b>1년 ${fmtChg(c.chg_1y)} · 거래 ${rep.count}건</div></div>
          ${rep.jeonse ? `<div class="jrow"><span>전세 <b>${fmtPrice(rep.jeonse)}</b></span><span>전세가율 <b class="${rep.jeonse_ratio >= 90 ? "up" : ""}">${rep.jeonse_ratio == null ? "-" : rep.jeonse_ratio + "%"}</b></span><span>갭 <b>${fmtPrice(rep.latest - rep.jeonse)}</b></span><span class="muted">최근 6개월 전세 ${rep.jeonse_n}건</span></div>` : ""}
          ${ask ? `<div class="gapbar"><div class="lbl"><span>실거래 <b>${fmtPrice(rep.latest)}</b></span><span>호가 <b>${fmtPrice(Math.round(askLow))} ~ ${fmtPrice(Math.round(askHigh))}</b></span></div>
            <div class="bar"><span class="pin t" style="left:${pos(rep.latest)}"></span><span class="pin a" style="left:${pos(askLow)}"></span><span class="pin a" style="left:${pos(askHigh)}"></span></div>
            <div class="lbl"><span>호가가 실거래보다 <b class="${ask.gap_pct >= 0 ? "up" : "down"}">${ask.gap_pct >= 0 ? "+" : ""}${ask.gap_pct}%</b> 높음</span><span class="muted">${esc(ask.source)}</span></div></div>` : ""}
          ${reports.length ? `<div class="note">내 제보 호가: ${reports.map((r) => fmtPrice(r.price) + " (" + r.date + ")").join(", ")}</div>` : ""}
          <div style="margin-top:12px">${chartSVG(c.trades, areaSel)}</div>
        </div>

        <div class="section"><h4>장단점 요약</h4><div class="plist">
          ${c.pros.map((p) => `<div class="row good"><i>+</i><span>${esc(p)}</span></div>`).join("")}
          ${c.cons.map((p) => `<div class="row bad"><i>−</i><span>${esc(p)}</span></div>`).join("")}
          ${(c.notes || []).map((p) => `<div class="row info"><i>i</i><span>${esc(p)}</span></div>`).join("")}
          ${!c.pros.length && !c.cons.length ? `<div class="muted">특이사항 없음</div>` : ""}</div></div>

        <div class="section"><h4>배정 학군 <span class="r muted">${esc(state.meta.zone_note || "초등 통학구역 기준")}</span></h4>
          <div class="school-hero"><div class="ic">🏫</div><div><b>${esc(c.school.elem)}</b><div class="n">도보 ${c.school.elem_walk_min}분 (${c.school.elem_dist}m) ${c.school.chopuma ? "· <b style='color:#7c3aed'>초품아</b>" : ""}</div>
            ${c.school.elem_stats ? `<div class="n">학생 ${c.school.elem_stats.students.toLocaleString()}명${c.school.elem_stats.chg_pct != null ? ` (전년 ${fmtChg(c.school.elem_stats.chg_pct)})` : ""} · 학급당 ${c.school.elem_stats.class_size}명${c.school.elem_stats.net_move != null ? ` · 순전입 <b class="${c.school.elem_stats.net_move > 0 ? "up" : c.school.elem_stats.net_move < 0 ? "down" : ""}">${c.school.elem_stats.net_move > 0 ? "+" : ""}${c.school.elem_stats.net_move}명</b>` : ""}${c.school.elem_rank ? ` · 전입 선호 ${c.school.elem_rank[0]}위/${c.school.elem_rank[1]}` : ""}</div>` : ""}</div></div>
          ${c.edu ? `<div class="kv" style="margin-top:12px">
            <div><div class="k">1km 내 교과학원</div><div class="v">${c.edu.exam_1km}개<small>${state.meta.area.split(" ").pop()} 상위 ${c.edu.exam_top_pct}%</small></div></div>
            <div><div class="k">1km 내 학원 전체</div><div class="v">${c.edu.aca_1km}개<small>예체능 ${c.edu.art_1km}</small></div></div></div>` : ""}
          <div class="mids">${(c.school.middle_detail && c.school.middle_detail.length ? c.school.middle_detail.map((m) => `<span class="tag">${esc(m.name)} <span class="muted">${m.dist}m${m.public === "사립" ? " · 사립" : ""}${m.coedu && m.coedu !== "남여공학" ? " · " + esc(m.coedu) : ""}${m.stats ? ` · ${m.stats.students}명 · 학급당 ${m.stats.class_size}` : ""}</span></span>`) : c.school.middle.map((m) => `<span class="tag">${esc(m)}</span>`)).join("")}</div>
          <div class="note">${esc(c.school.middle_note)}${c.school.elem_stats ? " · 학생 수·전출입은 학교알리미 " + c.school.elem_stats.year + "년 공시" : ""}</div></div>

        <div class="section"><h4>교통 · 도로 환경</h4><div class="kv">
          <div><div class="k">가까운 역</div><div class="v">${esc(c.station.name)}<small>${esc(c.station.line)} · ${c.station.walk_min}분</small></div></div>
          <div><div class="k">큰길과 거리</div><div class="v">${c.road.major_dist == null ? "-" : c.road.major_dist + "m"}<small>${c.road.roadside ? "대로변" : c.road.major_dist > 150 ? "이면 · 조용" : "인접"}</small></div></div>
          ${c.station.within_600.length > 1 ? `<div style="grid-column:1/-1"><div class="k">600m 내 역</div><div class="v" style="font-size:13.5px">${c.station.within_600.map((s) => esc(s.name) + " " + s.dist + "m").join(" · ")}</div></div>` : ""}
          </div>
          <button class="btn ghost" style="margin-top:10px" id="roadBtn">🛣️ 지도에서 큰길·골목·인도 보기</button></div>

        ${c.life ? `<div class="section"><h4>육아 · 생활 편의 <span class="r muted">단지 반경 기준</span></h4><div class="kv">
          <div><div class="k">어린이집·유치원 (700m)</div><div class="v">${c.life.daycare}곳</div></div>
          <div><div class="k">소아과 (1km)</div><div class="v">${c.life.pediatric}곳</div></div>
          <div><div class="k">병원 (700m) · 약국 (500m)</div><div class="v">${c.life.hospital}<small>· ${c.life.pharmacy}</small></div></div>
          <div><div class="k">대형마트 (1km) · 편의점 (300m)</div><div class="v">${c.life.mart}<small>· ${c.life.convenience}</small></div></div>
          <div><div class="k">공원 (700m)</div><div class="v">${c.life.park}곳</div></div>
          <div><div class="k">도서관 (1km)</div><div class="v">${c.life.library}곳</div></div></div>
          <div class="note">카카오 지도 등록 기준 개수. 소아과는 키워드 검색이라 오차가 있어요.</div></div>` : ""}
        ${aucs.length ? `<div class="section"><h4>경매 물건 <span class="r muted">${esc(aucs[0].court)}</span></h4>
          ${aucs.map((a) => `<div class="auc"><div><b>${esc(a.unit)} · ${a.area}㎡</b><div class="s">${esc(a.case)} · 매각 ${a.sale_date} · ${a.fail_count}회 유찰</div>
            <div class="s">감정가 ${fmtPrice(a.appraisal)} → 최저가 <b>${fmtPrice(a.min_price)}</b>${a.recent_trade ? " · 같은 평형 실거래 " + fmtPrice(a.recent_trade) : ""}</div></div>
            <div class="pct">-${a.discount_pct}%</div></div>`).join("")}
          <div class="note">경매는 권리분석(임차인·선순위 등)이 필수예요. 최저가만 보고 판단하지 마세요.</div></div>` : ""}

        <div class="section"><h4>실거래 내역 <span class="r muted">최근 ${Math.min(12, c.trades.length)}건</span></h4>
          <table class="tbl"><tr><th>계약일</th><th>평형</th><th>층</th><th class="r">가격</th></tr>
          ${c.trades.slice().reverse().slice(0, 12).map((t) => `<tr><td>${t.date.slice(2).replace(/-/g, ".")}</td><td>${Math.floor(t.area)}㎡</td><td>${t.floor}층</td><td class="r"><b>${fmtPrice(t.price)}</b></td></tr>`).join("")}</table></div>

        <div style="margin-top:14px"><button class="btn" id="reportBtn">이 단지 호가 제보하기</button></div>
        <div class="disclaim">${state.meta.mode === "demo" ? "⚠️ 지금은 데모 데이터입니다. 단지 위치·세대수는 대략값, 가격은 시세 흐름을 흉내낸 생성값이며 학군 경계도 예시입니다. 국토교통부 실거래가 API 키를 연결하면 실데이터로 바뀝니다." : "실거래가: 국토교통부 실거래가 공개시스템 (신고 지연 최대 30일). 학군: 학구도안내서비스 기준, 실제 배정은 교육청 공지를 확인하세요."}</div>`;

      $("#backBtn").onclick = closeDetail;
      $$(".atab").forEach((b) => b.onclick = () => { areaSel = b.dataset.a; render(); });
      $("#roadBtn").onclick = () => { state.layers.road = true; applyLayers(); setSheet("peek"); map.flyTo({ center: [c.lng, c.lat], zoom: 16.5 }); };
      $("#reportBtn").onclick = () => {
        const v = prompt(`${c.name} ${rep.area}㎡ 호가를 억 단위로 입력 (예: 16.5)`);
        const n = parseFloat(v); if (!n) return;
        const all = JSON.parse(localStorage.getItem("askReports") || "{}");
        (all[id] = all[id] || []).push({ price: Math.round(n * 10000), area: rep.area, date: new Date().toISOString().slice(0, 10) });
        localStorage.setItem("askReports", JSON.stringify(all)); reports.push(all[id][all[id].length - 1]);
        toast("제보 감사합니다. 검수 후 반영돼요."); render();
      };
    }
    render();
    $("#listView").hidden = true; $("#detailView").hidden = false; $("#sheetBody").scrollTop = 0;
    setSheet(sheetState || "half");
  }
  function closeDetail() {
    state.selected = null; $("#detailView").hidden = true; $("#listView").hidden = false;
    renderMarkers(); renderList(); setSheet("half");
  }

  // ---------- sheet ----------
  const sheet = $("#sheet");
  function setSheet(s) { sheet.dataset.state = s; }
  (function dragInit() {
    const grip = $("#grip"); let y0 = 0, h0 = 0, moved = false;
    grip.addEventListener("pointerdown", (e) => { y0 = e.clientY; h0 = sheet.getBoundingClientRect().height; moved = false; sheet.classList.add("dragging"); grip.setPointerCapture(e.pointerId); });
    grip.addEventListener("pointermove", (e) => { if (!sheet.classList.contains("dragging")) return; const dy = y0 - e.clientY; if (Math.abs(dy) > 4) moved = true; sheet.style.height = Math.max(90, Math.min(innerHeight - 20, h0 + dy)) + "px"; });
    const end = () => {
      if (!sheet.classList.contains("dragging")) return;
      sheet.classList.remove("dragging"); const h = sheet.getBoundingClientRect().height; sheet.style.height = "";
      if (!moved) { setSheet(sheet.dataset.state === "peek" ? "half" : sheet.dataset.state === "half" ? "full" : "peek"); return; }
      const cands = { peek: 156, half: innerHeight * 0.52, full: innerHeight - 20 };
      setSheet(Object.keys(cands).sort((a, b) => Math.abs(cands[a] - h) - Math.abs(cands[b] - h))[0]);
    };
    grip.addEventListener("pointerup", end); grip.addEventListener("pointercancel", end);
  })();

  // ---------- controls ----------
  $$("#areaChips .chip").forEach((b) => b.addEventListener("click", () => {
    if (b.dataset.area) { state.area = b.dataset.area; $$("[data-area]").forEach((x) => x.classList.toggle("on", x === b)); }
    else { state.sort = state.sort === b.dataset.sort ? null : b.dataset.sort; $$("[data-sort]").forEach((x) => x.classList.toggle("on", x.dataset.sort === state.sort)); }
    renderMarkers(); renderList();
  }));
  $("#q").addEventListener("input", (e) => { state.q = e.target.value.trim(); renderMarkers(); renderList(); if (state.q) setSheet("half"); });
  $("#q").addEventListener("keydown", (e) => { if (e.key === "Enter") { const f = visibleComplexes()[0]; if (f) openDetail(f.id, "half"); e.target.blur(); } });
  $$(".lyr[data-layer]").forEach((b) => b.addEventListener("click", () => { state.layers[b.dataset.layer] = !state.layers[b.dataset.layer]; applyLayers(); }));
  $("#locateBtn").addEventListener("click", () => {
    if (!navigator.geolocation) return toast("위치 정보를 지원하지 않는 브라우저예요.");
    navigator.geolocation.getCurrentPosition((p) => {
      const ll = [p.coords.longitude, p.coords.latitude];
      new maplibregl.Marker({ color: "#2563eb" }).setLngLat(ll).addTo(map); map.flyTo({ center: ll, zoom: 15 });
    }, () => toast("위치를 가져오지 못했어요."));
  });
  map.on("click", () => { if (state.selected && innerWidth < 900) setSheet("peek"); });
  let zt = null;
  map.on("zoomend", () => { clearTimeout(zt); zt = setTimeout(() => { renderMarkers(); applyLayers(); }, 60); });

  // ---------- boot ----------
  Promise.all(["complexes", "auctions", "meta"].map((n) => fetch(`data/${n}.json`).then((r) => r.json())).concat(fetch("data/schools.geojson").then((r) => r.json())))
    .then(([complexes, auctions, meta, schools]) => {
      Object.assign(state, { complexes, auctions, meta, schools });
      if (meta.mode === "demo") { $("#modeBadge").hidden = false; $("#modeBadge").textContent = "데모 데이터"; }
      $("#areaLabel").textContent = meta.area;
      $("#gapChip").hidden = !complexes.some((c) => c.jeonse_ratio);
      if (meta.center) map.jumpTo({ center: meta.center, zoom: meta.mode === "real" ? 13.6 : 14.6 });
      // 리스트/마커는 지도 로드와 무관하게 바로, 레이어는 스타일 준비 후
      renderMarkers(); renderList(); setSheet(innerWidth < 900 ? "half" : "full");
      const tryAdd = () => { if (map.getSource("schools")) return; if (map.isStyleLoaded()) addLayers(); else setTimeout(tryAdd, 300); };
      tryAdd();
    })
    .catch((e) => { console.error(e); toast("데이터를 불러오지 못했어요. pipeline/build.py 를 먼저 실행하세요."); });
})();
