# -*- coding: utf-8 -*-
"""계산기 페이지 스크립트 (content_calc.py 에서 참조)"""

CALC_JS = r"""<script>
(function () {
  "use strict";
  var $ = function (s) { return document.querySelector(s); };
  var V = function (id) { var e = $(id); return e ? (parseFloat(e.value) || 0) : 0; };
  var S = function (id) { var e = $(id); return e ? e.value : ""; };
  var C = function (id) { var e = $(id); return e ? e.checked : false; };
  var EOK = function (id) { return V(id) * 1e8; };
  var MAN = function (id) { return V(id) * 1e4; };

  function W(v) {
    v = Math.round(v);
    var neg = v < 0, a = Math.abs(v);
    if (a >= 1e8) {
      var e = Math.floor(a / 1e8), m = Math.round((a % 1e8) / 1e4);
      return (neg ? "-" : "") + e + "억" + (m ? " " + m.toLocaleString() + "만" : "");
    }
    if (a >= 1e4) return (neg ? "-" : "") + Math.round(a / 1e4).toLocaleString() + "만원";
    return (neg ? "-" : "") + a.toLocaleString() + "원";
  }
  function P(v) { return (Math.round(v * 10000) / 100).toFixed(2).replace(/\.?0+$/, "") + "%"; }
  function row(k, v, cls) { return '<div class="row ' + (cls || "") + '"><span>' + k + "</span><b>" + v + "</b></div>"; }
  function tot(k, v) { return '<div class="tot"><span>' + k + "</span><b>" + v + "</b></div>"; }
  function head(k) { return '<div class="head">' + k + "</div>"; }
  function pay(amt, r, n) { return r === 0 ? amt / n : amt * r / (1 - Math.pow(1 + r, -n)); }

  // ---------------- 요율 표 ----------------
  var SALE = [[5e7, 0.006, 25e4], [2e8, 0.005, 80e4], [9e8, 0.004, 0], [12e8, 0.005, 0], [15e8, 0.006, 0], [Infinity, 0.007, 0]];
  var RENT = [[5e7, 0.005, 20e4], [1e8, 0.004, 30e4], [6e8, 0.003, 0], [12e8, 0.004, 0], [15e8, 0.005, 0], [Infinity, 0.006, 0]];
  var CFT2 = [[3e8, 0.005, 0], [6e8, 0.007, 6e5], [12e8, 0.01, 24e5], [25e8, 0.013, 60e5], [50e8, 0.015, 110e5], [94e8, 0.02, 360e5], [Infinity, 0.027, 1018e5]];
  var CFT3 = [[3e8, 0.005, 0], [6e8, 0.007, 6e5], [12e8, 0.01, 24e5], [25e8, 0.02, 1440e4], [50e8, 0.03, 3940e4], [94e8, 0.04, 8940e4], [Infinity, 0.05, 18340e4]];

  function band(tbl, amt) {
    for (var i = 0; i < tbl.length; i++) if (amt < tbl[i][0]) return tbl[i];
    return tbl[tbl.length - 1];
  }
  function brokerage(tbl, amt) {
    var b = band(tbl, amt), f = amt * b[1];
    if (b[2]) f = Math.min(f, b[2]);
    return { fee: f, rate: b[1], cap: b[2] };
  }
  function stamp(p) {
    if (p <= 1e7) return 0;
    if (p <= 3e7) return 2e4;
    if (p <= 5e7) return 4e4;
    if (p <= 1e8) return 7e4;
    if (p <= 1e9) return 15e4;
    return 35e4;
  }
  function acqRate(p, houses, adj, temp) {
    var eff = (temp && houses === 2) ? 1 : houses, rate, heavy = 0;
    if (eff === 1 || (eff === 2 && !adj)) {
      if (p <= 6e8) rate = 0.01;
      else if (p <= 9e8) { var x = p * 2 / 3e8 - 3; rate = (Math.round(x * 1e4) / 1e4) / 100; }
      else rate = 0.03;
    } else if ((eff === 2 && adj) || (eff === 3 && !adj)) { rate = 0.08; heavy = 8; }
    else { rate = 0.12; heavy = 12; }
    return { rate: rate, heavy: heavy };
  }
  function acqAll(p, houses, adj, temp, big) {
    var r = acqRate(p, houses, adj, temp);
    var acq = p * r.rate;
    var edu = r.heavy ? p * 0.004 : acq * 0.1;
    var nong = big ? p * (r.heavy === 12 ? 0.01 : r.heavy === 8 ? 0.006 : 0.002) : 0;
    return { r: r, acq: acq, edu: edu, nong: nong, sum: acq + edu + nong };
  }
  function propTax(base, special) {
    if (special) {
      if (base <= 6e7) return base * 0.0005;
      if (base <= 1.5e8) return 3e4 + (base - 6e7) * 0.001;
      if (base <= 3e8) return 12e4 + (base - 1.5e8) * 0.002;
      return 42e4 + (base - 3e8) * 0.0035;
    }
    if (base <= 6e7) return base * 0.001;
    if (base <= 1.5e8) return 6e4 + (base - 6e7) * 0.0015;
    if (base <= 3e8) return 19.5e4 + (base - 1.5e8) * 0.0025;
    return 57e4 + (base - 3e8) * 0.004;
  }

  // ---------------- 취득세 ----------------
  function calcAcq() {
    var p = EOK("#aqPrice"), houses = +S("#aqHouses"), adj = S("#aqAdj") === "yes",
        big = S("#aqArea") === "over", temp = C("#aqTemp");
    var a = acqAll(p, houses, adj, temp, big), dis = 0;
    if (C("#aqFirst") && p <= 12e8 && (houses === 1 || temp)) dis = Math.min(2e6, a.acq);
    var total = a.sum - dis, h = "";
    h += row("적용 취득세율", P(a.r.rate) + (a.r.heavy ? " <span style='color:#dc2626'>중과</span>" : ""));
    h += row("취득세", W(a.acq));
    h += row("지방교육세", W(a.edu));
    h += row("농어촌특별세", big ? W(a.nong) : "비과세 (85㎡ 이하)");
    if (dis) h += row("생애최초 감면", "− " + W(dis), "ok");
    h += tot("취득 관련 세금", W(total));
    h += row("매매가 대비", P(p > 0 ? total / p : 0));
    h += head("참고: 함께 나가는 돈");
    var bk = brokerage(SALE, p);
    h += row("중개수수료 상한 (부가세 포함)", W(bk.fee * 1.1));
    h += row("인지세 (통상 절반 부담)", W(stamp(p) / 2));
    h += row("법무사 대행 (등기, 시세)", "20~50만원");
    h += row("집값 + 세금 + 중개비", "<span style='font-size:17px'>" + W(p + total + bk.fee * 1.1 + stamp(p) / 2) + "</span>");
    if (temp && houses === 2) h += row("주의", "종전 주택을 기한 내 못 팔면 중과세로 추징", "warn");
    if (a.r.heavy) h += row("주의", "다주택 중과 구간입니다", "warn");
    $("#o-acq").innerHTML = h;
  }

  // ---------------- 중개수수료 ----------------
  function calcFee() {
    var kind = S("#feeKind"), amt = EOK("#feeAmt"), mon = MAN("#feeMonthly");
    var basis = amt, note = "";
    if (kind === "wolse") {
      basis = amt + mon * 100;
      if (basis < 5e7) { basis = amt + mon * 70; note = "5천만원 미만이라 보증금 + 월세×70 으로 재계산"; }
      else note = "보증금 + 월세×100";
    }
    var tbl = kind === "sale" ? SALE : RENT, b = band(tbl, basis);
    var nego = V("#feeNego") / 100;
    var fee = basis * (nego > 0 ? nego : b[1]);
    if (b[2]) fee = Math.min(fee, b[2]);
    var capFee = Math.min(basis * b[1], b[2] || Infinity);
    var vat = fee * (+S("#feeVat") / 100);
    var h = "";
    if (note) h += row("거래금액 산정", note + " = " + W(basis));
    h += row("법정 상한 요율", P(b[1]) + (b[2] ? " (한도 " + W(b[2]) + ")" : ""));
    h += row("상한 적용 시", W(capFee));
    if (nego > 0) h += row("협의 요율 " + P(nego) + " 적용", W(fee), fee < capFee ? "ok" : "warn");
    h += row("부가세", vat > 0 ? W(vat) : "없음");
    h += tot("한쪽이 내는 금액", W(fee + vat));
    if (nego > 0 && capFee > fee) h += row("상한 대비 절약", W((capFee - fee) * 1.1), "ok");
    if (kind === "sale") h += row("매도인 + 매수인 합계", W((fee + vat) * 2));
    h += head("요율 구간표 (" + (kind === "sale" ? "매매·교환" : "임대차") + ")");
    for (var i = 0; i < tbl.length; i++) {
      var lo = i === 0 ? 0 : tbl[i - 1][0];
      var lbl = tbl[i][0] === Infinity ? W(lo) + " 이상" : (lo === 0 ? "0" : W(lo)) + " ~ " + W(tbl[i][0]) + " 미만";
      h += row(lbl + (tbl[i] === b ? " ←" : ""), P(tbl[i][1]) + (tbl[i][2] ? " · 한도 " + W(tbl[i][2]) : ""), tbl[i] === b ? "ok" : "");
    }
    $("#o-fee").innerHTML = h;
  }

  // ---------------- 대출 상환금 ----------------
  function calcLoan() {
    var amt = EOK("#lnAmt"), ar = V("#lnRate") / 100, r = ar / 12;
    var n = Math.round(V("#lnYears") * 12), g = Math.min(Math.round(V("#lnGrace") * 12), n - 1);
    if (g < 0) g = 0;
    var rn = n - g, type = S("#lnType"), gi = amt * r;
    var first, last, ti = gi * g, h = "";
    if (n <= 0 || amt <= 0) { $("#o-loan").innerHTML = row("입력", "대출금과 기간을 넣어주세요"); return; }
    if (type === "bullet") {
      first = last = gi; ti = gi * n;
      h += row("매달 이자만", W(gi));
      h += row("만기에 갚을 원금", W(amt), "warn");
    } else if (type === "eqpay") {
      var m = pay(amt, r, rn);
      ti += m * rn - amt; first = g ? gi : m; last = m;
      if (g) { h += row("거치 기간 (" + (g / 12).toFixed(0) + "년) 월 상환", W(gi)); h += row("거치 종료 후 월 상환", W(m), "warn"); }
      h += row("매달 상환액", W(m));
    } else {
      var pr = amt / rn, bal = amt;
      for (var i = 0; i < rn; i++) { ti += bal * r; bal -= pr; }
      first = g ? gi : pr + amt * r; last = pr + pr * r;
      if (g) h += row("거치 기간 (" + (g / 12).toFixed(0) + "년) 월 상환", W(gi));
      h += row("첫 회차 상환액", W(pr + amt * r));
      h += row("마지막 회차 상환액", W(last));
      h += row("매달 줄어드는 폭", W(pr * r));
    }
    h += tot("첫 달 실제 납입액", W(first));
    h += row("총 이자", W(ti), "warn");
    h += row("총 상환액 (원금 + 이자)", W(amt + ti));
    h += row("이자가 원금의", P(amt > 0 ? ti / amt : 0));
    var inc = MAN("#lnIncome");
    if (inc > 0) {
      var peak = Math.max(first, type === "eqpay" ? last : first);
      h += head("소득 대비 부담");
      h += row("연소득", W(inc));
      h += row("연간 상환액 (최대 시점)", W(peak * 12));
      var burden = peak * 12 / inc;
      h += row("소득 대비 비중", P(burden), burden > 0.4 ? "warn" : burden > 0.3 ? "" : "ok");
      h += row("판단 기준", burden > 0.4 ? "DSR 40%를 넘어 은행 한도 초과 가능" : burden > 0.3 ? "감당 가능하나 여유는 적음" : "비교적 안전한 수준", burden > 0.4 ? "warn" : "");
    }
    $("#o-loan").innerHTML = h;
  }

  // ---------------- DSR 한도 ----------------
  function calcDsr() {
    var inc = MAN("#dsIncome"), other = MAN("#dsOther");
    var realR = V("#dsRate") / 100 / 12, sr = (V("#dsRate") + V("#dsStress")) / 100 / 12;
    var n = Math.round(V("#dsYears") * 12), cap = +S("#dsCap") / 100;
    var price = EOK("#dsPrice"), ltv = V("#dsLtv") / 100;
    if (inc <= 0 || n <= 0) { $("#o-dsr").innerHTML = row("입력", "연소득과 기간을 넣어주세요"); return; }
    var room = inc * cap - other;
    var factor = 12 * pay(1, sr, n);
    var dsrMax = room > 0 ? room / factor : 0;
    var ltvMax = price * ltv;
    var fin = Math.min(dsrMax, ltvMax);
    var monthly = fin > 0 ? pay(fin, realR, n) : 0;
    var a = acqAll(price, 1, false, false, false);
    var bk = brokerage(SALE, price);
    var need = price - fin + a.sum + bk.fee * 1.1 + stamp(price) / 2;
    var h = "";
    h += row("DSR 한도 (" + P(cap) + ")", W(inc * cap) + " / 년");
    if (other > 0) h += row("기존 대출이 쓰는 몫", "− " + W(other));
    h += row("추가로 쓸 수 있는 연 상환액", W(Math.max(0, room)));
    h += row("심사 금리 (스트레스 포함)", P(V("#dsRate") / 100) + " + " + V("#dsStress") + "%p = " + P((V("#dsRate") + V("#dsStress")) / 100));
    h += row("DSR 기준 최대 대출", W(dsrMax));
    h += row("LTV " + P(ltv) + " 기준 최대 대출", W(ltvMax));
    h += tot("실제 가능한 대출", W(fin));
    h += row("한도를 정하는 것", dsrMax < ltvMax ? "소득(DSR)이 한도를 결정" : "집값(LTV)이 한도를 결정");
    h += head("그래서 현금이 얼마 필요한가");
    h += row("집값", W(price));
    h += row("대출", "− " + W(fin));
    h += row("취득세 등", "+ " + W(a.sum));
    h += row("중개수수료 (부가세 포함)", "+ " + W(bk.fee * 1.1));
    h += row("인지세", "+ " + W(stamp(price) / 2));
    h += tot("필요한 자기자금", W(need));
    h += head("갚을 때 부담");
    h += row("실제 금리로 월 상환액", W(monthly));
    h += row("월 소득 대비", P(inc > 0 ? monthly * 12 / inc : 0));
    h += row("총 이자 (" + V("#dsYears") + "년)", W(monthly * n - fin), "warn");
    if (other > 0 && room <= 0) h += row("경고", "기존 대출만으로 이미 DSR 한도를 채웠습니다", "warn");
    $("#o-dsr").innerHTML = h;
  }

  // ---------------- 보유세 ----------------
  function calcHold() {
    var pub = EOK("#hdPub"), houses = +S("#hdHouses"), couple = C("#hdCouple");
    if (pub <= 0) { $("#o-hold").innerHTML = row("입력", "공시가격을 넣어주세요"); return; }
    var share = couple ? 0.5 : 1, per = pub * share;
    var fair = houses === 1 ? (pub <= 3e8 ? 0.43 : pub <= 6e8 ? 0.44 : 0.45) : 0.6;
    var base = per * fair;
    var special = houses === 1 && pub <= 9e8;
    var mul = couple ? 2 : 1;
    var pmain = propTax(base, special);
    var city = base * 0.0014, ptEdu = pmain * 0.2;
    var propSum = (pmain + city + ptEdu) * mul;
    var ded = couple ? 9e8 : (houses === 1 ? 12e8 : 9e8);
    var cft = 0, agri = 0, cftBase = 0, credit = 0, gross = 0, dup = 0;
    if (per > ded) {
      cftBase = (per - ded) * 0.6;
      var tbl = houses >= 3 ? CFT3 : CFT2, b = band(tbl, cftBase);
      gross = cftBase * b[1] - b[2];
      dup = pmain * ((per - ded) / per);
      var net = Math.max(0, gross - dup);
      if (houses === 1 && !couple) {
        var age = V("#hdAge"), hold = V("#hdHold");
        var ac = age >= 70 ? 0.4 : age >= 65 ? 0.3 : age >= 60 ? 0.2 : 0;
        var hc = hold >= 15 ? 0.5 : hold >= 10 ? 0.4 : hold >= 5 ? 0.2 : 0;
        credit = Math.min(0.8, ac + hc);
        net = net * (1 - credit);
      }
      cft = net * mul; agri = cft * 0.2;
    }
    var h = "";
    h += head("재산세");
    h += row("공정시장가액비율", P(fair) + (houses === 1 ? " (1주택 특례)" : ""));
    h += row("과세표준" + (couple ? " (1인 지분)" : ""), W(base));
    h += row("재산세 본세" + (special ? " (1주택 특례세율)" : ""), W(pmain * mul));
    h += row("도시지역분 (과표 0.14%)", W(city * mul));
    h += row("지방교육세 (재산세 20%)", W(ptEdu * mul));
    h += row("재산세 합계", W(propSum));
    h += head("종합부동산세");
    h += row("공제액" + (couple ? " (각 9억 × 2인)" : ""), W(ded * mul));
    if (per <= ded) {
      h += row("종부세", "대상 아님 (공시가격이 공제액 이하)", "ok");
    } else {
      h += row("과세표준" + (couple ? " (1인 지분)" : ""), W(cftBase));
      h += row("산출세액", W(gross * mul));
      h += row("재산세 중복분 공제 (추정)", "− " + W(dup * mul));
      if (credit > 0) h += row("고령자·장기보유 세액공제", "− " + P(credit), "ok");
      h += row("종부세", W(cft));
      h += row("농어촌특별세 (종부세 20%)", W(agri));
    }
    h += tot("연간 보유세 (추정)", W(propSum + cft + agri));
    h += row("공시가격 대비", P(propSum > 0 ? (propSum + cft + agri) / pub : 0));
    h += row("월로 나누면", W((propSum + cft + agri) / 12));
    if (couple && houses === 1 && pub > 18e8) h += row("참고", "1주택 특례(12억 공제 + 세액공제) 신청이 유리할 수 있습니다", "");
    if (!couple && houses === 1 && pub > 12e8) h += row("참고", "부부 공동명의로 바꾸면 공제가 18억으로 늘지만 세액공제는 못 받습니다", "");
    $("#o-hold").innerHTML = h;
  }

  // ---------------- 전월세 환산 ----------------
  function calcConv() {
    var j = EOK("#cvJeonse"), d = EOK("#cvDeposit");
    var legal = Math.min((V("#cvBase") + V("#cvAdd")) / 100, 0.10);
    var real = V("#cvReal") / 100, rate = real > 0 ? real : legal;
    var diff = j - d;
    var h = "";
    h += row("법정 전환율 상한", P(legal) + " (기준금리+" + V("#cvAdd") + "%p 와 10% 중 낮은 값)");
    if (real > 0) h += row("실제 적용 전환율", P(real), real > legal ? "warn" : "ok");
    if (diff <= 0) {
      h += row("입력", "전세 보증금이 전환 후 보증금보다 커야 합니다", "warn");
    } else {
      var m = diff * rate / 12, lm = diff * legal / 12;
      h += head("전세 → 월세");
      h += row("보증금을 " + W(d) + " 로 낮추면", "돌려받는 돈 " + W(diff));
      h += tot("월세", W(m));
      if (real > 0 && Math.abs(m - lm) > 1000) {
        h += row("법정 상한 기준 월세", W(lm));
        h += row("연간 차액", W((m - lm) * 12), m > lm ? "warn" : "ok");
      }
      var lr = V("#cvLoanRate") / 100;
      if (lr > 0) {
        h += head("월세 vs 전세대출 " + P(lr));
        h += row("보증금 차액을 대출로 조달하면 월 이자", W(diff * lr / 12));
        var better = diff * lr / 12 < m;
        h += row("유리한 쪽", better ? "전세 유지 (대출 이자가 더 싸다)" : "월세 전환 (전환율이 대출금리보다 낮다)", "ok");
        h += row("월 차이", W(Math.abs(m - diff * lr / 12)));
      }
    }
    var back = MAN("#cvMonthly");
    if (back > 0 && rate > 0) {
      h += head("월세 → 전세 환산");
      h += row("보증금 " + W(d) + " + 월세 " + W(back), "");
      h += tot("전세로 치면", W(d + back * 12 / rate));
    }
    $("#o-conv").innerHTML = h;
  }

  // ---------------- 갈아타기 ----------------
  function calcMove() {
    var sell = EOK("#mvSell"), left = EOK("#mvLoanLeft"), gain = EOK("#mvGain");
    var buy = EOK("#mvBuy"), nl = EOK("#mvNewLoan"), etc = MAN("#mvEtc"), have = EOK("#mvHave");
    var big = S("#mvArea") === "over";
    var sf = brokerage(SALE, sell).fee * 1.1, bf = brokerage(SALE, buy).fee * 1.1;
    var a = acqAll(buy, 1, false, true, big), st = stamp(buy) / 2;
    var inflow = sell - sf - gain - left + nl + have;
    var outflow = buy + a.sum + bf + etc + st;
    var gapv = inflow - outflow;
    var cost = sf + bf + a.sum + etc + st + gain;
    var h = "";
    h += head("들어오는 돈");
    h += row("지금 집 매도가", W(sell));
    h += row("매도 중개수수료", "− " + W(sf));
    if (gain > 0) h += row("양도소득세", "− " + W(gain));
    h += row("기존 대출 상환", "− " + W(left));
    h += row("새 대출", "+ " + W(nl));
    h += row("보유 현금", "+ " + W(have));
    h += row("합계", W(inflow));
    h += head("나가는 돈");
    h += row("새 집 매수가", W(buy));
    h += row("취득세 등 (" + P(a.r.rate) + ")", W(a.sum));
    h += row("매수 중개수수료", W(bf));
    h += row("인지세", W(st));
    h += row("이사·법무·수리비", W(etc));
    h += row("합계", W(outflow));
    h += tot(gapv >= 0 ? "남는 돈" : "부족한 돈", (gapv < 0 ? "" : "") + W(Math.abs(gapv)));
    if (gapv < 0) h += row("해결 방법", "대출을 " + W(-gapv) + " 더 받거나 예산을 낮춰야 합니다", "warn");
    h += head("갈아타기 순비용");
    h += row("집값 차이", W(buy - sell));
    h += row("세금·중개비·이사비 합계", W(cost), "warn");
    h += row("매수가 대비 거래비용", P(buy > 0 ? cost / buy : 0));
    h += row("총 대출", W(nl) + " (기존 " + W(left) + " 상환 후)");
    h += row("주의", "잔금일이 어긋나면 그 기간 브리지론 이자가 추가됩니다", "");
    $("#o-move").innerHTML = h;
  }

  // ---------------- 공통 ----------------
  var KEY = "jipkok_calc_v1";
  function fields() { return document.querySelectorAll(".f input, .f select"); }
  function save() {
    var o = {};
    Array.prototype.forEach.call(fields(), function (e) { o[e.id] = e.type === "checkbox" ? e.checked : e.value; });
    try { localStorage.setItem(KEY, JSON.stringify(o)); } catch (err) {}
  }
  function load() {
    try {
      var o = JSON.parse(localStorage.getItem(KEY) || "{}");
      Object.keys(o).forEach(function (k) {
        var e = document.getElementById(k);
        if (!e) return;
        if (e.type === "checkbox") e.checked = !!o[k]; else e.value = o[k];
      });
    } catch (err) {}
  }
  function all() {
    [calcAcq, calcFee, calcLoan, calcDsr, calcHold, calcConv, calcMove].forEach(function (f) {
      try { f(); } catch (err) { }
    });
  }
  function tab(k) {
    Array.prototype.forEach.call(document.querySelectorAll("#tabs button"), function (b) {
      b.classList.toggle("on", b.dataset.t === k);
    });
    Array.prototype.forEach.call(document.querySelectorAll(".calc"), function (s) {
      s.classList.toggle("on", s.id === "c-" + k);
    });
  }
  document.getElementById("tabs").addEventListener("click", function (e) {
    var b = e.target.closest("button");
    if (!b) return;
    tab(b.dataset.t);
    history.replaceState(null, "", "#" + b.dataset.t);
  });
  document.addEventListener("input", function (e) {
    if (e.target.closest(".f")) { all(); save(); }
  });
  document.addEventListener("change", function (e) {
    if (e.target.closest(".f")) { all(); save(); }
  });
  function fromHash() {
    var k = (location.hash || "").replace("#", "");
    if (k && document.getElementById("c-" + k)) tab(k);
  }
  window.addEventListener("hashchange", fromHash);
  load();
  // 단지 페이지에서 넘어온 가격(억)을 채운다: calc.html?price=9.5#acq
  try {
    var qp = new URLSearchParams(location.search), pv = parseFloat(qp.get("price"));
    if (pv > 0) {
      ["#aqPrice", "#feeAmt", "#dsPrice", "#mvBuy"].forEach(function (id) {
        var e = $(id); if (e) e.value = pv;
      });
      var nm = qp.get("name");
      if (nm) {
        var n = document.createElement("div");
        n.className = "card";
        n.style.cssText = "margin:10px 0 0";
        n.innerHTML = "<b>" + nm.replace(/[<>&]/g, "") + "</b> 의 실거래가 " + pv + "억을 각 계산기에 채웠습니다. 값을 바꿔서 다시 계산해 보세요.";
        var tb = document.getElementById("tabs");
        tb.parentNode.insertBefore(n, tb);
      }
    }
  } catch (err) {}
  all();
  fromHash();
})();
</script>"""
