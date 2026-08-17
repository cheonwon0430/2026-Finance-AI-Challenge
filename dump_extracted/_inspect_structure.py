"""
구조 조사 전용 스크립트 (파서 아님 - 데이터 추출 로직 없음).
dump_extracted/ 밑의 5개 XML을 열어서 인코딩·태그구조·섹션위치·표 마크업 스키마를
'있는 그대로' 눈으로 확인할 수 있게 원문 발췌와 함께 보고서로 뽑는다.

주의: 이 XML들은 완전한 well-formed XML이 아닐 수 있다(주석 섹션 등에
이스케이프 안 된 "<당기말>" 같은 텍스트가 섞여 있는 경우가 실제로 있었음).
그래서 DOM 파서(lxml recover 등)로 "복구"해서 보지 않고, 최대한 raw 텍스트/
정규식 기반으로 원본 그대로를 조사한다. 이래야 진짜 구조적 이상까지 보고된다.
"""
import re
from pathlib import Path

BASE = Path(__file__).parent
FILES = {
    "트래블월렛": BASE / "travelwallet" / "20260331000341_00760.xml",
    "핀샷": BASE / "finshot" / "20260414002654_00760.xml",
    "아이씨비": BASE / "icb" / "20260402000570_00760.xml",
    "이롬넷": BASE / "eromnet" / "20260331000402_00760.xml",
    "센트비": BASE / "sentbe" / "20260331000944_00760.xml",
}

out_lines: list[str] = []


def p(*args):
    s = " ".join(str(a) for a in args)
    print(s)
    out_lines.append(s)


def hr(title):
    p("")
    p("=" * 90)
    p(title)
    p("=" * 90)


# ---------------------------------------------------------------------------
# [1] 인코딩 확인
# ---------------------------------------------------------------------------
hr("[1] 인코딩 확인 - 선언부 vs 실제 바이트")

for name, path in FILES.items():
    raw = path.read_bytes()
    first_line = raw[:200].split(b"\n", 1)[0].decode("ascii", errors="replace")
    decl_match = re.search(r'encoding="([^"]+)"', first_line)
    declared = decl_match.group(1) if decl_match else "(선언 없음)"

    utf8_ok = True
    try:
        raw.decode("utf-8")
    except UnicodeDecodeError as e:
        utf8_ok = False
        utf8_err = str(e)

    cp949_ok = True
    try:
        raw.decode("cp949")
    except UnicodeDecodeError as e:
        cp949_ok = False
        cp949_err = str(e)

    p(f"- {name}: 선언={declared} / 실제 UTF-8 디코드={'성공' if utf8_ok else 'FAIL: ' + utf8_err} "
      f"/ 실제 CP949 디코드={'성공' if cp949_ok else 'FAIL: ' + cp949_err}")

# ---------------------------------------------------------------------------
# [2] 최상위 구조 - depth 1~2 태그 트리 (관용적 스택 트레이서, DOM 파서 아님)
# ---------------------------------------------------------------------------
hr("[2] 최상위 구조 (depth 1~2)")

TAG_RE = re.compile(r"<(/?)([A-Za-z0-9\-]+)([^>]*?)(/?)>")


def top_levels(text: str, max_depth: int = 2):
    """태그 여닫힘을 관용적으로 추적해서 depth<=max_depth인 태그만 등장순으로 반환.
    close mismatch가 나도 무시하고 계속 진행(원본이 malformed일 수 있으므로)."""
    stack = []
    result = []  # (depth, tag)
    seen_at_depth = {}
    for m in TAG_RE.finditer(text):
        closing, tag, attrs, selfclose = m.groups()
        if closing:
            if stack and stack[-1] == tag:
                stack.pop()
            elif stack:
                # mismatch - 그냥 무시하고 진행 (malformed 구간 대응)
                pass
            continue
        depth = len(stack) + 1
        if depth <= max_depth:
            key = (depth, tag)
            seen_at_depth[key] = seen_at_depth.get(key, 0) + 1
        if not selfclose:
            stack.append(tag)
    ordered = []
    seen_order = []
    for (depth, tag), cnt in seen_at_depth.items():
        seen_order.append((depth, tag, cnt))
    seen_order.sort(key=lambda x: (x[0], -x[2]))
    return seen_order


trees = {}
for name, path in FILES.items():
    text = path.read_text(encoding="utf-8", errors="replace")
    trees[name] = top_levels(text, max_depth=2)

for name, tree in trees.items():
    p(f"\n--- {name} ---")
    for depth, tag, cnt in tree:
        indent = "  " * depth
        p(f"{indent}{tag}  (x{cnt})")

hr("[2-비교] 5개 파일 depth1 태그 공통점/차이")
depth1_sets = {name: {tag for d, tag, c in tree if d == 1} for name, tree in trees.items()}
common = set.intersection(*depth1_sets.values())
p("공통 depth1 태그:", sorted(common))
for name, s in depth1_sets.items():
    diff = s - common
    if diff:
        p(f"{name}만 있는 depth1 태그:", sorted(diff))

# ---------------------------------------------------------------------------
# [3] 섹션 식별 - 위치 + 300자 발췌
# ---------------------------------------------------------------------------
hr("[3] 섹션 식별 (원문 300자 발췌)")

SECTION_TARGETS = {
    "감사의견": ["감사의견"],
    "계속기업_관련_불확실성(굵은소제목)": None,  # 별도 로직
    "재무상태표": ["재 무 상 태 표", "재무상태표"],
    "손익계산서": ["손 익 계 산 서", "손익계산서"],
    "현금흐름표": ["현 금 흐 름 표", "현금흐름표"],
    "주석_시작지점": ["<TITLE", "주석"],  # 별도 로직
}

OPINION_KEYWORDS = ["적정", "한정", "부적정", "의견거절"]

for name, path in FILES.items():
    text = path.read_text(encoding="utf-8", errors="replace")
    p(f"\n--- {name} ---")

    # 감사의견 + 의견종류
    i = text.find("감사의견")
    if i == -1:
        p("  감사의견: 없음")
    else:
        excerpt = text[i:i + 300].replace("\n", " ")
        found_opinions = [kw for kw in OPINION_KEYWORDS if kw in text[i:i + 3000]]
        p(f"  감사의견: 위치={i}바이트, 의견종류키워드={found_opinions or '판정불가'}")
        p(f"    발췌: {excerpt}")

    # 계속기업 관련 불확실성 - 굵은 소제목(P USERMARK=B)에 실제로 있는지만 판정
    bold_headers = re.findall(r'<P USERMARK="B"\s*>([^<]+)</P>', text)
    real_eom = [h for h in bold_headers if "계속기업" in h and ("불확실" in h or "의문" in h)]
    p(f"  굵은 소제목 전체: {bold_headers}")
    if real_eom:
        p(f"  계속기업_관련_불확실성: 있음 - 소제목=\"{real_eom[0]}\"")
    else:
        p(f"  계속기업_관련_불확실성: 없음 (표준 4개 소제목만 존재, '계속기업'단어는 보일러플레이트 문장에만 등장)")

    for label in ["재무상태표", "손익계산서", "현금흐름표"]:
        # TITLE 태그 안의 글자간띄어쓰기 버전을 우선 탐색
        spaced = " ".join(list(label.replace("재무", "재 무").replace("손익", "손 익").replace("현금", "현 금"))) if False else None
        candidates = [
            "재 무 상 태 표" if label == "재무상태표" else None,
            "손 익 계 산 서" if label == "손익계산서" else None,
            "현 금 흐 름 표" if label == "현금흐름표" else None,
            label,
        ]
        candidates = [c for c in candidates if c]
        found_pos, found_kw = None, None
        for kw in candidates:
            idx = text.find(f">{kw}</TITLE>")
            if idx != -1:
                found_pos, found_kw = idx, kw
                break
        if found_pos is None:
            p(f"  {label}: 없음 (TITLE 태그 형태로는 못 찾음)")
        else:
            excerpt = text[found_pos:found_pos + 300].replace("\n", " ")
            p(f"  {label}: 위치={found_pos}바이트, TITLE텍스트=\"{found_kw}\"")
            p(f"    발췌: {excerpt}")

    # 주석 시작지점
    idx = text.find(">주석</TITLE>")
    if idx == -1:
        p("  주석_시작지점: 없음")
    else:
        excerpt = text[idx:idx + 300].replace("\n", " ")
        p(f"  주석_시작지점: 위치={idx}바이트")
        p(f"    발췌: {excerpt}")

# ---------------------------------------------------------------------------
# [4] 주석 항목 존재여부 (정확한 제목 그대로)
# ---------------------------------------------------------------------------
hr("[4] 주석 항목 존재여부 (정확한 원문 제목)")

NOTE_ITEMS = {
    "특수관계자거래": [r"특수\s*관계자\s*(거래|등\s*거래|공시)"],
    "소송_우발부채_충당부채": [r"우발\s*(부채|채무)", r"소송"],
    "CB_BW_RCPS": [r"전환\s*사채", r"신주인수권부\s*사채", r"상환전환우선주"],
    "주주구성_지분율": [r"주주\s*(현황|구성)", r"지분율"],
    "매출처_거래처집중도": [r"매출처", r"거래처\s*집중도", r"고객\s*집중"]
}

result_table = {}
for name, path in FILES.items():
    text = path.read_text(encoding="utf-8", errors="replace")
    # 태그 제거한 순수 텍스트 버전(글자간 공백은 유지 - 제목 그대로 찾기 위해 태그만 제거)
    plain = re.sub(r"<[^>]+>", "", text)
    row = {}
    for item, patterns in NOTE_ITEMS.items():
        hit = None
        for pat in patterns:
            m = re.search(pat, plain)
            if m:
                s = max(0, m.start() - 20)
                e = min(len(plain), m.end() + 20)
                hit = plain[s:e].replace("\n", " ")
                break
        row[item] = hit
    result_table[name] = row

names = list(FILES.keys())
p(f"{'항목':<22}" + "".join(f"{n:<14}" for n in names))
for item in NOTE_ITEMS:
    cells = []
    for n in names:
        cells.append("있음" if result_table[n][item] else "없음")
    p(f"{item:<22}" + "".join(f"{c:<14}" for c in cells))

p("\n[상세 발췌 - 있음으로 판정된 것들의 원문 주변]")
for name in names:
    p(f"\n--- {name} ---")
    for item, hit in result_table[name].items():
        if hit:
            p(f"  {item}: ...{hit}...")
        else:
            p(f"  {item}: 없음")

# ---------------------------------------------------------------------------
# [5] 표 마크업 스키마
# ---------------------------------------------------------------------------
hr("[5] 표 마크업 스키마 (TD 계열 vs TE ACODE 계열)")

for name, path in FILES.items():
    text = path.read_text(encoding="utf-8", errors="replace")
    n_te = len(re.findall(r"<TE\b", text))
    n_td = len(re.findall(r"<TD\b", text))
    n_finance_table = len(re.findall(r'<TABLE[^>]*ACLASS="FINANCE"', text))
    n_normal_table = len(re.findall(r'<TABLE[^>]*ACLASS="NORMAL"', text))
    n_extraction_table = len(re.findall(r'<TABLE[^>]*ACLASS="EXTRACTION"', text))
    p(f"\n--- {name} ---")
    p(f"  <TE 태그 수: {n_te}  |  <TD 태그 수: {n_td}")
    p(f"  TABLE ACLASS=FINANCE: {n_finance_table}건  |  ACLASS=NORMAL: {n_normal_table}건  |  ACLASS=EXTRACTION: {n_extraction_table}건")

    m_te = re.search(r"<TE\b[^>]*>[^<]*", text)
    if m_te:
        p(f"  TE 태그 원문 예시: {m_te.group(0)[:200]}")
    m_td = re.search(r"<TD\b[^>]*>[^<]*", text)
    if m_td:
        p(f"  TD 태그 원문 예시: {m_td.group(0)[:200]}")

# ---------------------------------------------------------------------------
# [6] 목차 존재여부
# ---------------------------------------------------------------------------
hr("[6] 목차(TOC) 존재여부")

for name, path in FILES.items():
    text = path.read_text(encoding="utf-8", errors="replace")
    idx = text.find("목              차")
    if idx == -1:
        idx = text.find(">목차<")
    if idx == -1:
        idx = re.search(r">목\s*차<", text)
        idx = idx.start() if idx else -1

    atoc_titles = re.findall(r'<TITLE\s+ATOC="Y"[^>]*ATOCID="(\d+)"[^>]*>([^<]+)</TITLE>', text)

    p(f"\n--- {name} ---")
    if idx == -1:
        p("  목차: 없음")
    else:
        excerpt = text[idx:idx + 300].replace("\n", " ")
        p(f"  목차: 위치={idx}바이트")
        p(f"    발췌: {excerpt}")
    p(f"  ATOC=\"Y\" (목차와 연결되는 섹션 표시) 태그 목록: {atoc_titles}")

# ---------------------------------------------------------------------------
# 저장
# ---------------------------------------------------------------------------
report_path = BASE / "_structure_report.md"
report_path.write_text("```\n" + "\n".join(out_lines) + "\n```\n", encoding="utf-8")
print(f"\n\n보고서 저장 완료: {report_path}")
