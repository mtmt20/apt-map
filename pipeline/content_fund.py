# -*- coding: utf-8 -*-
"""자금 마련 가이드 페이지 본문 (부모님 차용·증여, 금융권 비교)"""

from content_calc import _f, num, sel, chk

FUND_BODY = """
<h1>집 살 돈 마련하기</h1>
<p class="sub">정책대출부터 부모님 도움, 은행과 보험사 대출의 차이까지. 싼 돈 먼저 쓰는 순서로 정리했습니다.</p>

<div class="card">
<p>자금은 <b>이자가 싼 순서</b>로 쌓는 게 원칙입니다. ① 내 현금 → ② 정책대출 → ③ 1금융권 주택담보대출 → ④ 부모님 증여·차용 → ⑤ 보험사·상호금융 → ⑥ 신용대출. 순서를 거꾸로 하면 같은 집을 사면서 30년 동안 수천만원을 더 냅니다. 특히 ②번 정책대출은 조건이 맞는데도 모르고 지나치는 사람이 많습니다.</p>
</div>

<h2>1. 먼저 정책대출 조건을 본다</h2>
<div class="card">
<p>정책대출은 금리가 시중은행보다 1~2%p 낮고 고정금리인 경우가 많습니다. 자녀가 있으면 소득·한도 요건이 크게 완화되니 반드시 먼저 확인하세요.</p>
<table>
<tr><th>상품</th><th>주요 요건</th><th>특징</th></tr>
<tr><td><b>신생아 특례 디딤돌</b></td><td>대출 신청일 기준 2년 내 출산·입양 무주택 가구</td><td>소득·주택가격·한도 요건이 가장 느슨하고 금리도 가장 낮은 편. 자녀를 더 낳으면 금리 추가 인하</td></tr>
<tr><td><b>디딤돌 대출</b></td><td>무주택 세대주, 부부합산 소득 기준 있음 (신혼·다자녀는 완화)</td><td>2자녀 이상이면 소득 기준과 한도가 함께 완화됩니다</td></tr>
<tr><td><b>보금자리론</b></td><td>소득 기준 있음, 주택가격 상한 있음</td><td>최장 50년 고정금리. 금리 변동 걱정이 없는 게 최대 장점</td></tr>
<tr><td><b>버팀목 전세자금</b></td><td>무주택 세대주, 보증금 상한 있음</td><td>전세로 버티며 자금을 모으는 구간에서 유리. 다자녀 우대금리</td></tr>
</table>
<p class="note">소득·주택가격·한도 기준은 해마다, 때로는 몇 달 만에 바뀝니다. <a href="https://nhuf.molit.go.kr" target="_blank" rel="noopener">주택도시기금</a>과 <a href="https://hf.go.kr" target="_blank" rel="noopener">한국주택금융공사</a>에서 오늘 기준 조건을 직접 확인하세요. 자녀가 셋이면 거의 모든 상품에서 다자녀 우대를 받습니다.</p>
</div>

<h2>2. 은행 · 보험사 · 상호금융 · 저축은행은 뭐가 다른가</h2>
<div class="card">
<p>1금융권에서 한도가 안 나올 때 그다음 선택지가 <b>보험사</b>입니다. 저축은행과 함께 "2금융권"으로 불리지만 조건은 전혀 다릅니다.</p>
<table>
<tr><th>항목</th><th>1금융권 은행</th><th>보험사</th><th>상호금융</th><th>저축은행·캐피탈</th></tr>
<tr><td>DSR 한도</td><td>40%</td><td><b>50%</b></td><td>50%</td><td>50%</td></tr>
<tr><td>금리</td><td>가장 낮음</td><td>은행 + 0.3~1.0%p</td><td>지역별 편차 큼</td><td>훨씬 높음</td></tr>
<tr><td>한도</td><td>보수적</td><td>은행보다 더 나옴</td><td>담보 위주 심사</td><td>가장 크지만 위험</td></tr>
<tr><td>신용점수 영향</td><td>거의 없음</td><td>소폭 하락</td><td>소폭 하락</td><td>크게 하락</td></tr>
<tr><td>정책대출 취급</td><td>○</td><td>일부</td><td>일부</td><td>×</td></tr>
<tr><td>만기</td><td>최장 40~50년</td><td>40년 이상 가능</td><td>상품별</td><td>짧음</td></tr>
</table>
</div>
<div class="card">
<h3 style="margin:0 0 8px">보험사 대출의 장점</h3>
<ul class="plist">
<li class="good"><i>+</i><span><b>DSR이 50%라 한도가 더 나옵니다.</b> 은행에서 "소득 때문에 4억밖에 안 됩니다"라는 말을 들었다면 같은 소득으로 보험사에서 5억이 나올 수 있습니다. 한도가 부족해 집을 놓치는 상황에서는 이 차이가 결정적입니다.</span></li>
<li class="good"><i>+</i><span>금리가 은행과 크게 벌어지지 않습니다. 저축은행처럼 두 자릿수로 뛰지 않고 대체로 은행 + 0.3~1.0%p 수준입니다.</span></li>
<li class="good"><i>+</i><span>은행이 부결한 물건(다세대, 근린생활시설 혼용, 노후 주택)도 취급하는 경우가 있고, 만기와 거치 조건을 유연하게 잡아줍니다.</span></li>
<li class="good"><i>+</i><span>신용점수 하락 폭이 카드론·저축은행보다 훨씬 작습니다.</span></li>
</ul>
<h3 style="margin:14px 0 8px">보험사 대출의 단점</h3>
<ul class="plist">
<li class="bad"><i>−</i><span>같은 조건이면 금리가 은행보다 높습니다. 4억을 30년 빌릴 때 0.5%p 차이는 총이자로 약 3천만원입니다.</span></li>
<li class="bad"><i>−</i><span>중도상환수수료가 은행보다 높거나 면제 시점이 늦은 상품이 있습니다. 3년 안에 갈아탈 계획이면 꼭 확인하세요.</span></li>
<li class="bad"><i>−</i><span>디딤돌·보금자리론 같은 정책대출을 못 받는 경우가 많습니다. 정책대출 자격이 되면 보험사로 갈 이유가 거의 없습니다.</span></li>
<li class="bad"><i>−</i><span>제2금융권 이용 이력이 신용평가에 남습니다. 이후 다른 대출 심사에서 불리해질 수 있습니다.</span></li>
</ul>
<p class="note">정리하면 <b>순서는 정책대출 → 1금융권 → 보험사</b>이고, 보험사는 "금리를 조금 더 내는 대신 한도를 늘리는 카드"입니다. 저축은행·캐피탈은 금리와 신용점수 타격이 커서 주택 구입 자금으로는 마지막 수단입니다. 어느 쪽이든 <a href="calc.html#dsr">내 대출한도 계산기</a>에서 DSR 40%와 50%를 바꿔 넣어보면 차이가 바로 보입니다.</p>
</div>

<h2>3. 부모님께 도움을 받을 때 (증여와 차용)</h2>
<div class="card">
<p>부모님 돈을 받는 방법은 <b>증여</b>(그냥 주는 것)와 <b>차용</b>(빌리고 갚는 것) 두 가지이고, 세금이 완전히 다릅니다. 실무에서는 공제 한도까지는 증여로, 그 위는 차용으로 섞는 경우가 많습니다.</p>
<h3 style="margin:12px 0 6px">증여 — 공제 한도까지는 세금 없음</h3>
<ul class="plist">
<li class="info"><i>1</i><span><b>직계존속 → 성년 자녀: 10년간 5,000만원</b>까지 증여세가 없습니다. 미성년 자녀는 2,000만원입니다. 10년 합산이라 과거에 받은 게 있으면 함께 계산됩니다.</span></li>
<li class="info"><i>2</i><span><b>혼인·출산 증여재산공제로 1억원이 추가</b>됩니다. 혼인신고 전후 2년 이내, 또는 자녀 출생·입양일로부터 2년 이내에 받으면 적용되고 혼인과 출산을 합쳐 1억원이 한도입니다.</span></li>
<li class="info"><i>3</i><span>따라서 조건이 맞으면 <b>한 사람당 1억 5,000만원</b>, 부부가 각자 자기 부모님께 받으면 <b>합쳐 3억원</b>까지 증여세 없이 받을 수 있습니다.</span></li>
<li class="info"><i>4</i><span>공제 한도를 넘으면 초과분에 10~50% 세율이 붙습니다. 기한 내에 신고하면 세액의 3%를 깎아주니, 세금이 0원이라도 신고해두면 자금 출처를 증명하기 쉬워집니다.</span></li>
</ul>
<h3 style="margin:16px 0 6px">차용 — 2억 1,700만원까지는 무이자도 가능</h3>
<ul class="plist">
<li class="info"><i>1</i><span>세법이 정한 <b>적정 이자율은 연 4.6%</b>입니다. 이보다 싸게 빌리면 그 차액만큼을 증여받은 것으로 봅니다.</span></li>
<li class="info"><i>2</i><span>단, <b>이자 차액이 연 1,000만원 미만이면 증여로 보지 않습니다.</b> 4.6%로 계산해 1,000만원이 되는 금액이 약 2억 1,700만원이라, 그 아래로는 <b>무이자로 빌려도 증여세가 없습니다.</b></span></li>
<li class="info"><i>3</i><span>2억 1,700만원을 넘으면 초과분에 대한 이자 차액 전체가 증여로 계산됩니다. 한도를 조금 넘길 상황이면 일부는 증여 공제로 처리하고 차용액을 한도 아래로 맞추는 편이 낫습니다.</span></li>
<li class="bad"><i>!</i><span><b>가장 중요한 건 "진짜 빌린 것"으로 보이게 하는 것입니다.</b> 차용증만 써두고 한 번도 갚지 않으면 사실상 증여로 보아 나중에 세금과 가산세를 함께 추징당합니다.</span></li>
</ul>
<h3 style="margin:16px 0 6px">차용증에 꼭 들어가야 하는 것</h3>
<ul class="plist">
<li class="good"><i>☐</i><span>빌린 사람·빌려준 사람 인적사항, 금액, 빌린 날짜</span></li>
<li class="good"><i>☐</i><span><b>만기와 상환 방법</b> (매달 얼마씩, 또는 언제 일시 상환). "형편 되는대로"는 안 됩니다</span></li>
<li class="good"><i>☐</i><span>이자율과 이자 지급일 (무이자로 할 경우에도 무이자임을 명시)</span></li>
<li class="good"><i>☐</i><span><b>작성일을 증명할 장치</b>: 공증, 또는 우체국 내용증명 발송, 최소한 스캔 후 자신에게 이메일 발송</span></li>
<li class="good"><i>☐</i><span><b>실제 계좌 이체 기록</b>: 원금과 이자를 약정대로 계좌로 이체하고 기록을 남깁니다. 현금 전달은 증명이 안 됩니다</span></li>
<li class="good"><i>☐</i><span>이자를 받는 부모님은 <b>이자소득세 27.5%</b>를 원천징수해 신고해야 합니다 (무이자라면 해당 없음)</span></li>
</ul>
</div>

<h2>부모님 자금 계산기</h2>
<div class="card">""" + _f([
    num("fdGift", "증여받을 금액", "0", "100", "만원"),
    sel("fdRel", "증여자", [("adult", "부모 → 성년 자녀 (5,000만원 공제)", True), ("minor", "부모 → 미성년 자녀 (2,000만원 공제)", False)]),
    chk("fdWed", "혼인 또는 출산 2년 이내 (1억원 추가 공제)", False, True),
    num("fdPrev", "지난 10년간 이미 증여받은 금액", "0", "100", "만원", True),
    num("fdLoan", "부모님께 빌릴 금액", "20000", "100", "만원"),
    num("fdRate", "실제 지급할 이자율", "0", "0.1", "%"),
]) + """<div class="out" id="o-fund"></div>
<div class="hint">증여세는 <b>10년간 합산</b>해 계산하므로 예전에 받은 돈이 있으면 반드시 넣으세요. 차용 한도는 적정이자율 4.6%와 연 1,000만원 기준으로 계산했습니다. 세율과 공제액은 바뀔 수 있고 개인 사정에 따라 결과가 달라지니, 실제 신고 전에는 세무사나 <a href="https://www.hometax.go.kr" target="_blank" rel="noopener">홈택스</a>에서 확인하세요.</div>
</div>

<h2>4. 자금조달계획서를 미리 생각해둔다</h2>
<div class="card">
<p>일정 요건에 해당하는 주택을 사면 계약 후 30일 안에 <b>주택취득자금 조달 및 입주계획서</b>를 내야 합니다. 규제지역이면 금액과 무관하게, 비규제지역도 일정 금액 이상이면 대상입니다. 여기에 돈의 출처를 항목별로 적고 증빙을 첨부합니다.</p>
<ul class="plist">
<li class="info"><i>·</i><span>예금·주식 등 자기자금, 금융기관 대출, <b>임대보증금</b>, <b>증여·상속</b>, <b>그 밖의 차입금</b>으로 나눠 적습니다</span></li>
<li class="info"><i>·</i><span>부모님께 빌린 돈은 "그 밖의 차입금"에 적고 <b>차용증</b>을, 증여받은 돈은 "증여"에 적고 <b>증여세 신고서</b>를 첨부합니다</span></li>
<li class="bad"><i>!</i><span>계획서에 적은 내용과 실제 통장 흐름이 다르면 국세청 자금출처 조사로 이어집니다. <b>계약서에 서명하기 전에</b> 돈의 경로를 정해두세요. 계약 후에 차용증을 소급 작성하는 것이 가장 흔한 실수입니다</span></li>
</ul>
</div>

<h2>5. 자주 하는 실수</h2>
<div class="card"><ul class="plist">
<li class="bad"><i>1</i><span><b>취득세와 중개비를 빼고 예산을 잡는다.</b> 9억 집이면 세금·중개비·이사비로 4천만원 안팎이 더 듭니다. 이 돈은 대출이 안 나옵니다. <a href="calc.html#acq">취득세 계산기</a>로 먼저 확인하세요</span></li>
<li class="bad"><i>2</i><span><b>한도를 꽉 채워 빌린다.</b> DSR 한도까지 빌리면 금리가 1%p 오르거나 소득이 줄 때 버틸 여유가 없습니다. 월 상환액이 월 소득의 30%를 넘으면 한 번 더 생각해 보세요</span></li>
<li class="bad"><i>3</i><span><b>거치 기간을 길게 잡는다.</b> 거치 중에는 원금이 전혀 줄지 않고, 거치가 끝나는 달 상환액이 크게 뜁니다. 그 금액을 지금 감당할 수 있는지로 판단하세요</span></li>
<li class="bad"><i>4</i><span><b>부모님께 받은 돈을 그냥 쓴다.</b> 차용증도 이체 기록도 없으면 몇 년 뒤 증여세와 가산세를 함께 냅니다</span></li>
<li class="bad"><i>5</i><span><b>갈아타기에서 잔금일을 안 맞춘다.</b> 매도 잔금이 늦게 들어오면 그 기간 브리지론 이자를 따로 물고, 종전 주택 처분 기한을 놓치면 취득세 중과와 양도세 비과세를 동시에 잃습니다</span></li>
</ul></div>

<div class="note" style="margin-top:20px">이 페이지는 공개된 세법·금융 규정을 정리한 일반 정보이며 세무 자문이나 투자 권유가 아닙니다. 공제 한도, 적정이자율, DSR·LTV 비율, 정책대출 요건은 모두 바뀔 수 있습니다. 금액이 큰 결정 전에는 세무사와 금융기관에서 오늘 기준 조건을 확인하세요.</div>
<div class="card" style="margin-top:16px"><p style="margin:0">금액을 넣어 직접 계산해 보려면 <a href="calc.html"><b>부동산 계산기</b></a>로 가세요. 취득세, 중개수수료, 대출 상환금, 내 소득 기준 대출한도, 보유세, 전월세 환산, 갈아타기 비용을 모두 계산할 수 있습니다.</p></div>
"""

FUND_JS = r"""<script>
(function () {
  "use strict";
  var $ = function (s) { return document.querySelector(s); };
  var V = function (id) { var e = $(id); return e ? (parseFloat(e.value) || 0) : 0; };
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
  function row(k, v, cls) { return '<div class="row ' + (cls || "") + '"><span>' + k + "</span><b>" + v + "</b></div>"; }
  function tot(k, v) { return '<div class="tot"><span>' + k + "</span><b>" + v + "</b></div>"; }
  function head(k) { return '<div class="head">' + k + "</div>"; }

  var LEGAL = 0.046;                 // 상속세및증여세법 적정이자율
  var FREE = 1e7 / LEGAL;            // 이자 차액 1,000만원 미만 -> 약 2억 1,739만원
  var GIFT = [[1e8, 0.1, 0], [5e8, 0.2, 1e7], [10e8, 0.3, 6e7], [30e8, 0.4, 1.6e8], [Infinity, 0.5, 4.6e8]];

  function giftTax(base) {
    if (base <= 0) return 0;
    for (var i = 0; i < GIFT.length; i++) if (base <= GIFT[i][0]) return base * GIFT[i][1] - GIFT[i][2];
    return base * 0.5 - 4.6e8;
  }

  function run() {
    var gift = MAN("#fdGift"), prev = MAN("#fdPrev"), loan = MAN("#fdLoan"), rate = V("#fdRate") / 100;
    var base = $("#fdRel").value === "minor" ? 2e7 : 5e7;
    var extra = $("#fdWed").checked ? 1e8 : 0;
    var ded = base + extra;
    var h = "";
    h += head("증여");
    h += row("기본 공제 (10년)", W(base) + ($("#fdRel").value === "minor" ? " · 미성년" : " · 성년"));
    if (extra) h += row("혼인·출산 추가 공제", W(extra), "ok");
    h += row("공제 한도 합계", W(ded));
    var used = Math.min(prev, ded);
    if (prev > 0) h += row("이미 쓴 공제", "− " + W(used));
    var left = Math.max(0, ded - prev);
    h += row("남은 공제 여력", W(left), left > 0 ? "ok" : "warn");
    if (gift > 0) {
      var taxBase = Math.max(0, gift + prev - ded);
      var g = giftTax(taxBase);
      var credit = g * 0.03;
      h += row("증여 과세표준", W(taxBase));
      if (taxBase <= 0) {
        h += row("증여세", "0원 (공제 범위 내)", "ok");
      } else {
        h += row("산출세액", W(g));
        h += row("기한 내 신고 세액공제 3%", "− " + W(credit), "ok");
        h += row("낼 증여세", W(g - credit), "warn");
        h += row("실제로 손에 남는 돈", W(gift - (g - credit)));
      }
    } else {
      h += row("증여세", "증여 금액을 넣으면 계산됩니다");
    }
    h += head("차용 (빌리기)");
    h += row("무이자로 빌릴 수 있는 한도", W(FREE));
    h += row("근거", "연 4.6% 이자가 1,000만원 미만이면 증여로 보지 않음");
    if (loan > 0) {
      h += row("빌릴 금액", W(loan));
      var legalInt = loan * LEGAL, paidInt = loan * rate;
      var gap = legalInt - paidInt;
      h += row("법정 기준 연 이자 (4.6%)", W(legalInt));
      h += row("실제 지급할 연 이자 (" + (rate * 100).toFixed(2).replace(/\.?0+$/, "") + "%)", W(paidInt));
      h += row("이자 차액 (증여로 보는 금액)", W(Math.max(0, gap)));
      if (gap < 1e7) {
        h += row("판정", "차액이 연 1,000만원 미만 → 증여세 없음", "ok");
      } else {
        var remain = Math.max(0, left - gift);
        var taxable = Math.max(0, gap - remain);
        h += row("판정", "차액이 연 1,000만원 이상 → 증여로 과세", "warn");
        h += row("이자를 얼마로 올려야 안전한가", ((Math.max(0, legalInt - 1e7 + 1) / loan) * 100).toFixed(2) + "% 이상");
        h += row("또는 차용액을 줄이면", W(FREE) + " 이하로");
        if (taxable <= 0) h += row("올해 낼 증여세", "0원 (남은 증여공제 " + W(remain) + " 로 흡수)", "ok");
        else h += row("연간 추정 증여세", W(giftTax(taxable) * 0.97), "warn");
        h += row("주의", "매년 반복되면 공제가 소진되어 이후에는 세금이 붙습니다", "warn");
      }
      if (paidInt > 0) {
        h += row("부모님 이자소득세 (27.5% 원천징수)", W(paidInt * 0.275));
        h += row("매달 보낼 이자", W(paidInt / 12));
      }
    }
    if (gift > 0 || loan > 0) {
      h += tot("부모님께 받는 총액", W(gift + loan));
      h += row("이 중 갚아야 할 돈", W(loan));
    }
    $("#o-fund").innerHTML = h;
  }
  document.addEventListener("input", function (e) { if (e.target.closest(".f")) run(); });
  document.addEventListener("change", function (e) { if (e.target.closest(".f")) run(); });
  run();
})();
</script>"""
