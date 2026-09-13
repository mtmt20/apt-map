# -*- coding: utf-8 -*-
"""부동산 계산기 + 자금마련 가이드 페이지 본문 (generate_content.py 에서 import)

세율/요율 기준일은 RATE_ASOF 로 표시하고, 자주 바뀌는 값은 화면에서 직접 고칠 수 있게 입력으로 뺀다.
"""

RATE_ASOF = "2026-09"

CALC_CSS = """<style>
.tabs{display:flex;flex-wrap:wrap;gap:6px;margin:14px 0 4px;position:sticky;top:0;background:var(--bg);padding:8px 0;z-index:5}
.tabs button{font-size:13.5px;font-weight:700;padding:8px 12px;border-radius:999px;border:1px solid var(--line);background:var(--bg);color:var(--muted);cursor:pointer}
.tabs button.on{background:var(--brand);border-color:var(--brand);color:#fff}
.calc{display:none}.calc.on{display:block}
.f{display:grid;grid-template-columns:1fr 1fr;gap:10px 12px;margin:4px 0 12px}
.f label{display:flex;flex-direction:column;gap:4px;font-size:12.5px;font-weight:700;color:var(--muted)}
.f label.wide{grid-column:1/-1}
.f input,.f select{font:inherit;font-size:15px;font-weight:700;color:var(--fg);padding:10px 11px;border:1px solid var(--line);border-radius:11px;background:var(--bg);width:100%}
.f input[type=checkbox]{width:auto;transform:scale(1.25);margin-right:7px}
.f label.chk{flex-direction:row;align-items:center;font-size:13.5px;color:var(--fg);padding-top:6px}
.out{background:var(--bg);border-radius:14px;padding:13px 15px;margin-top:4px}
.out .tot{font-size:15px;font-weight:800;display:flex;justify-content:space-between;align-items:baseline;padding:9px 0 4px;border-top:2px solid var(--line);margin-top:6px}
.out .tot b{font-size:26px;letter-spacing:-1px;color:var(--brand)}
.out .row{display:flex;justify-content:space-between;gap:10px;font-size:14px;padding:5px 0;border-bottom:1px solid var(--line)}
.out .row span:first-child{color:var(--muted);font-weight:600}
.out .row b{font-weight:800;white-space:nowrap}
.out .row.warn b{color:var(--bad)}.out .row.ok b{color:var(--good)}
.out .head{font-size:12px;font-weight:800;color:var(--muted);margin:12px 0 2px;letter-spacing:.3px}
.hint{font-size:12px;color:var(--muted);margin-top:9px;line-height:1.65}
@media(max-width:520px){.f{grid-template-columns:1fr}}
</style>"""


def _f(rows):
    return '<div class="f">' + "".join(rows) + "</div>"


def num(id_, label, val, step="0.1", unit="", wide=False):
    u = ' <span style="font-weight:600;color:var(--brand)">' + unit + '</span>' if unit else ""
    return '<label class="{w}"><span>{l}{u}</span><input id="{i}" type="number" step="{s}" value="{v}"></label>'.format(
        w="wide" if wide else "", l=label, u=u, i=id_, s=step, v=val)


def sel(id_, label, opts, wide=False):
    return '<label class="{w}"><span>{l}</span><select id="{i}">{o}</select></label>'.format(
        w="wide" if wide else "", l=label, i=id_,
        o="".join('<option value="{}"{}>{}</option>'.format(v, " selected" if d else "", t) for v, t, d in opts))


def chk(id_, label, on=False, wide=False):
    return '<label class="chk {w}"><input id="{i}" type="checkbox"{c}> {l}</label>'.format(
        w="wide" if wide else "", i=id_, c=" checked" if on else "", l=label)


TABS = [("acq", "취득세"), ("fee", "중개수수료"), ("loan", "대출 상환금"),
        ("dsr", "내 대출한도"), ("hold", "보유세"), ("conv", "전세↔월세"), ("move", "갈아타기")]

CALC_BODY = """
<h1>부동산 계산기</h1>
<p class="sub">취득세·중개수수료·대출 상환금·보유세·전월세 환산·갈아타기 비용을 한 페이지에서. 입력값은 브라우저에만 저장되고 서버로 보내지 않습니다.</p>
<div class="tabs" id="tabs">""" + "".join(
    '<button data-t="{}"{}>{}</button>'.format(k, ' class="on"' if i == 0 else "", t) for i, (k, t) in enumerate(TABS)) + """</div>

<section class="calc on" id="c-acq">
<h2>취득세 계산</h2>
<div class="card">""" + _f([
    num("aqPrice", "매매가", "9", "0.1", "억"),
    sel("aqHouses", "취득 후 보유 주택 수", [("1", "1주택", True), ("2", "2주택", False), ("3", "3주택", False), ("4", "4주택 이상", False)]),
    sel("aqArea", "전용면적", [("under", "85㎡ 이하 (농특세 비과세)", True), ("over", "85㎡ 초과", False)]),
    sel("aqAdj", "소재지", [("no", "비조정대상지역", True), ("yes", "조정대상지역", False)]),
    chk("aqFirst", "생애최초 주택 구입 (12억 이하 · 최대 200만원 감면)", False, True),
    chk("aqTemp", "일시적 2주택 (종전 주택을 기한 내 처분 → 1주택 세율)", False, True),
]) + """<div class="out" id="o-acq"></div>
<div class="hint">6억 초과 9억 이하 구간은 <b>세율(%) = 매매가(억) × 2 ÷ 3 − 3</b> 으로 매매가에 따라 1~3% 사이에서 연속으로 올라갑니다. 지방교육세는 취득세의 10%(중과 시 0.4% 고정)이고, 농어촌특별세는 전용 85㎡ 초과일 때만 붙습니다. 분양권·입주권, 상속·증여 취득, 오피스텔, 조합원 승계는 세율 체계가 달라 이 계산기로는 맞지 않습니다.</div>
</div></section>

<section class="calc" id="c-fee">
<h2>중개수수료 계산</h2>
<div class="card">""" + _f([
    sel("feeKind", "거래 종류", [("sale", "매매·교환", True), ("jeonse", "전세", False), ("wolse", "월세", False)]),
    num("feeAmt", "매매가 / 보증금", "9", "0.1", "억"),
    num("feeMonthly", "월세 (월세 거래만)", "0", "1", "만원"),
    sel("feeVat", "중개사 과세 유형", [("10", "일반과세자 (부가세 10%)", True), ("0", "간이과세자 (부가세 없음)", False)]),
    num("feeNego", "협의 요율 (0이면 상한 적용)", "0", "0.01", "%", True),
]) + """<div class="out" id="o-fee"></div>
<div class="hint">서울특별시 주택 중개보수 요율(2021년 10월 개정) 기준입니다. 표에 적힌 요율은 <b>상한</b>이라 실제로는 깎을 수 있고, 특히 9억 이상 구간은 협의 여지가 큽니다. 월세는 거래금액을 <b>보증금 + 월세×100</b>으로 잡되 그 값이 5천만원 미만이면 <b>보증금 + 월세×70</b>으로 다시 계산합니다. 오피스텔·상가는 요율 체계가 다릅니다.</div>
</div></section>

<section class="calc" id="c-loan">
<h2>대출 월 상환금</h2>
<div class="card">""" + _f([
    num("lnAmt", "대출금", "4", "0.1", "억"),
    num("lnRate", "연 금리", "4.2", "0.01", "%"),
    num("lnYears", "대출 기간", "30", "1", "년"),
    num("lnGrace", "거치 기간 (이자만)", "0", "1", "년"),
    sel("lnType", "상환 방식", [("eqpay", "원리금균등 (매달 같은 금액)", True), ("eqprin", "원금균등 (갈수록 줄어듦)", False), ("bullet", "만기일시 (이자만, 만기에 원금)", False)], True),
    num("lnIncome", "세전 연소득 (부담률 계산용, 선택)", "0", "100", "만원", True),
]) + """<div class="out" id="o-loan"></div>
<div class="hint">원리금균등은 매달 내는 돈이 같아 계획이 쉽고, 원금균등은 초반 부담이 크지만 총이자가 적습니다. 거치 기간에는 원금이 전혀 줄지 않으니 거치가 끝나는 달의 상환액을 반드시 확인하세요. 중도상환수수료(보통 1.2~1.4%, 3년 경과 시 면제)와 인지세·근저당 설정비는 포함되지 않았습니다.</div>
</div></section>

<section class="calc" id="c-dsr">
<h2>내 소득으로 얼마까지 빌릴 수 있나</h2>
<div class="card">""" + _f([
    num("dsIncome", "세전 연소득 (부부 합산 가능)", "6000", "100", "만원"),
    num("dsOther", "기존 대출 연간 원리금 상환액", "0", "10", "만원"),
    num("dsRate", "예상 금리", "4.2", "0.01", "%"),
    num("dsStress", "스트레스 금리 가산", "1.5", "0.1", "%p"),
    num("dsYears", "대출 기간", "30", "1", "년"),
    sel("dsCap", "금융권", [("40", "1금융권 은행 (DSR 40%)", True), ("50", "보험사·상호금융 (DSR 50%)", False)]),
    num("dsPrice", "사려는 집 가격", "9", "0.1", "억"),
    num("dsLtv", "적용 LTV", "70", "1", "%"),
]) + """<div class="out" id="o-dsr"></div>
<div class="hint">DSR은 <b>연간 갚는 모든 대출 원리금 ÷ 연소득</b>입니다. 한도 심사에는 실제 금리가 아니라 여기에 스트레스 금리를 더한 값으로 원리금을 계산하므로 체감 한도가 줄어듭니다. 신용대출·마이너스통장·카드론·학자금도 전부 합산되니 기존 대출 칸에 빠짐없이 넣으세요. LTV는 지역·주택가격·무주택 여부에 따라 달라지고 생애최초는 더 높게 적용될 수 있습니다. 실제 한도는 은행 심사 결과가 기준입니다.</div>
</div></section>

<section class="calc" id="c-hold">
<h2>보유세 (재산세 + 종합부동산세)</h2>
<div class="card">""" + _f([
    num("hdPub", "공시가격", "7", "0.1", "억"),
    sel("hdHouses", "보유 주택 수", [("1", "1세대 1주택", True), ("2", "2주택", False), ("3", "3주택 이상", False)]),
    chk("hdCouple", "부부 공동명의 (지분 각 50%)", False, True),
    num("hdAge", "만 나이 (1주택 단독명의 세액공제)", "0", "1", "세"),
    num("hdHold", "보유 기간", "0", "1", "년"),
]) + """<div class="out" id="o-hold"></div>
<div class="hint"><b>여기 넣는 값은 실거래가가 아니라 공시가격입니다.</b> 공시가격은 보통 실거래가의 60~70% 수준이고, <a href="https://www.realtyprice.kr" target="_blank" rel="noopener">부동산공시가격 알리미</a>에서 주소로 조회할 수 있습니다. 그래서 다른 탭과 달리 단지 실거래가가 자동으로 채워지지 않습니다.<br>재산세 과세표준은 공시가격에 공정시장가액비율(1주택 43~45%, 그 외 60%)을 곱해 구하고, 여기에 도시지역분(과표의 0.14%)과 지방교육세(재산세의 20%)가 더해집니다. 종부세는 1세대 1주택 12억, 그 외 9억을 공제한 뒤 60%를 곱해 계산하며 부부 공동명의는 각자 9억씩 공제받습니다. 고령자·장기보유 세액공제는 1주택 단독명의일 때만, 합쳐서 최대 80%까지 적용했습니다. 세부담상한(전년 대비 105~130%)과 지자체 탄력세율은 반영하지 않은 추정치입니다.</div>
</div></section>

<section class="calc" id="c-conv">
<h2>전세 ↔ 월세 환산</h2>
<div class="card">""" + _f([
    num("cvJeonse", "전세 보증금", "5", "0.1", "억"),
    num("cvDeposit", "월세로 돌릴 때 남길 보증금", "1", "0.1", "억"),
    num("cvBase", "한국은행 기준금리", "2.5", "0.05", "%"),
    num("cvAdd", "법정 가산", "2", "0.1", "%p"),
    num("cvMonthly", "역산할 월세", "100", "1", "만원"),
    num("cvReal", "실제 제시받은 전환율 (0이면 법정)", "0", "0.1", "%"),
    num("cvLoanRate", "전세대출 금리 (월세와 비교용)", "3.8", "0.01", "%", True),
]) + """<div class="out" id="o-conv"></div>
<div class="hint">주택임대차보호법상 법정 전환율은 <b>기준금리 + 2%p</b> 와 <b>연 10%</b> 중 낮은 값이고, 이 상한은 <b>기존 계약을 월세로 바꿀 때</b>만 강제됩니다. 새로 맺는 계약이나 집주인이 바뀐 경우에는 시장 전환율(서울 아파트는 대체로 4~6%)로 협의합니다. 전환율이 높을수록 세입자에게 불리하니, 실제 제시받은 월세를 <b>실제 전환율</b> 칸으로 역산해 비교해 보세요. 기준금리는 <a href="https://www.bok.or.kr" target="_blank" rel="noopener">한국은행</a>에서 확인해 넣으세요.</div>
</div></section>

<section class="calc" id="c-move">
<h2>아파트 갈아타기 비용</h2>
<div class="card">""" + _f([
    num("mvSell", "지금 집 매도가", "7", "0.1", "억"),
    num("mvLoanLeft", "지금 집 대출 잔액", "2", "0.1", "억"),
    num("mvGain", "양도소득세 (비과세면 0)", "0", "0.1", "억"),
    num("mvBuy", "새 집 매수가", "11", "0.1", "억"),
    num("mvNewLoan", "새로 받을 대출", "4", "0.1", "억"),
    sel("mvArea", "새 집 전용면적", [("under", "85㎡ 이하", True), ("over", "85㎡ 초과", False)]),
    num("mvEtc", "이사·법무·수리비", "500", "10", "만원"),
    num("mvHave", "지금 가진 현금", "1", "0.1", "억"),
]) + """<div class="out" id="o-move"></div>
<div class="hint">갈아타기는 세금과 중개비가 <b>양쪽 모두</b> 들어갑니다. 매도 중개비 + 매수 중개비 + 취득세 + 이사·법무비를 합치면 보통 매수가의 4~6%가 되고, 이 돈은 대출이 안 나오는 순수 현금입니다. 새 집 잔금일과 지금 집 잔금일이 어긋나면 그 기간만큼 브리지론 이자를 따로 잡아야 합니다. 일시적 2주택 비과세는 종전 주택을 정해진 기간 안에 팔아야 유지되니 잔금 일정을 먼저 맞추세요.</div>
</div></section>

<div class="note" style="margin-top:20px">세율과 요율은 """ + RATE_ASOF + """ 기준입니다. 세법은 자주 바뀌고 지자체 탄력세율·감면 특례·개인 사정에 따라 실제 금액은 달라집니다. 이 계산기는 어림잡기용이며 세무 자문이나 투자 권유가 아닙니다. 계약 전에는 <a href="https://www.wetax.go.kr" target="_blank" rel="noopener">위택스</a>와 <a href="https://www.hometax.go.kr" target="_blank" rel="noopener">홈택스</a>, 세무사, 금융기관에서 확인하세요.</div>
<div class="card" style="margin-top:16px"><p style="margin:0">집 살 돈을 어떻게 마련할지, 부모님께 빌릴 때 증여세는 어떻게 되는지, 은행과 보험사 대출은 뭐가 다른지는 <a href="fund.html"><b>자금 마련 가이드</b></a>에 정리했습니다.</p></div>
"""
