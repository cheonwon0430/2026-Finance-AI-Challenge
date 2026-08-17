"""
5개 회사를 모아서 두 종류의 실측 통계를 낸다.

(A) zip 내부(document.xml) 항목 존재여부 매트릭스
    - 표지: 감사의견, 계속기업 불확실성, 감사인명, 감사보고서일
    - 본문: 재무상태표, 손익계산서, 현금흐름표
    - 주석: 특수관계자거래, 소송·우발부채, CB·BW·RCPS, 주주구성·지분율, 매출처집중도
    ※ 키워드 매칭이라 휴리스틱임 - 존재/부재의 "1차 스크리닝"이지 100% 확정은 아님.
      False 나온 항목은 원문 열어서 실제로 없는지 눈으로 한 번 더 봐야 함.

(B) API 응답 필드의 실측 카운트
    - bizr_no / jurir_no 실값 채워진 비율 (n/5)
    - est_dt 공란 비율
    - acc_mt 12월 아닌 회사
    - F002(연결감사대상) 제출 회사 수
    - [기재정정] 건수
    - zip 내부 파일 개수 분포
"""
import io
import json
import zipfile
import urllib.request
from pathlib import Path

from corp_lookup import fetch_company_overview, fetch_disclosure_list

DART_KEY = "053284b30c287dbfd3324294b588649e2729bdca"
BASE_DIR = Path(__file__).parent

COMPANIES = {
    "트래블월렛": {"corp_code": "01726910", "rcept_no": "20260331000341"},
    "핀샷": {"corp_code": "01836952", "rcept_no": "20260414002654"},
    "아이씨비": {"corp_code": "01355572", "rcept_no": "20260402000570"},
    "이롬넷": {"corp_code": "01730658", "rcept_no": "20260331000402"},
    "센트비": {"corp_code": "01685996", "rcept_no": "20260331000944"},
}

PRESENCE_CHECKS = {
    "표지_감사의견": ["감사의견"],
    "표지_계속기업불확실성": ["계속기업", "불확실성"],
    "표지_감사인명": ["회계법인"],
    "표지_감사보고서일": ["감사보고서일"],
    "본문_재무상태표": ["재 무 상 태 표"],
    "본문_손익계산서": ["손 익 계 산 서"],
    "본문_현금흐름표": ["현 금 흐 름 표"],
    "주석_특수관계자거래": ["특수관계자"],
    "주석_소송우발부채": ["우발"],
    "주석_CB_BW_RCPS": ["전환사채", "신주인수권부사채", "상환전환우선주"],
    "주석_주주구성지분율": ["지분율"],
    "주석_매출처집중도": ["매출처", "집중도"],
}


def get_doc_xml(name: str, rcept_no: str) -> tuple[str, int]:
    """document.xml 텍스트와 zip 내부 파일 개수를 반환. 로컬에 이미 있으면 재사용."""
    doc_dir = BASE_DIR / f"{name}_doc"
    doc_dir.mkdir(exist_ok=True)
    xml_path = doc_dir / f"{rcept_no}_00760.xml"
    zip_path = doc_dir / f"{rcept_no}.zip"

    if not zip_path.exists():
        url = f"https://opendart.fss.or.kr/api/document.xml?crtfc_key={DART_KEY}&rcept_no={rcept_no}"
        data = urllib.request.urlopen(url).read()
        zip_path.write_bytes(data)

    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        n_files = len(names)
        if not xml_path.exists():
            zf.extractall(doc_dir)

    return xml_path.read_text(encoding="utf-8"), n_files


def main() -> None:
    presence_matrix = {}
    zip_file_counts = {}

    for name, meta in COMPANIES.items():
        text, n_files = get_doc_xml(name, meta["rcept_no"])
        zip_file_counts[name] = n_files
        presence_matrix[name] = {item: any(kw in text for kw in kws) for item, kws in PRESENCE_CHECKS.items()}

    print("=" * 70)
    print("(A) zip 내부 항목 존재여부 매트릭스 (휴리스틱 - False는 원문으로 재확인 필요)")
    print("=" * 70)
    header = f"{'항목':<24}" + "".join(f"{n:<12}" for n in COMPANIES)
    print(header)
    for item in PRESENCE_CHECKS:
        row = f"{item:<24}" + "".join(f"{'O' if presence_matrix[n][item] else 'X':<12}" for n in COMPANIES)
        print(row)

    print()
    print("=" * 70)
    print("(B) API 응답 필드 실측 카운트")
    print("=" * 70)

    overviews = {}
    f001_lists = {}
    f002_lists = {}
    for name, meta in COMPANIES.items():
        overviews[name] = fetch_company_overview(meta["corp_code"], DART_KEY)
        f001_lists[name] = fetch_disclosure_list(meta["corp_code"], DART_KEY, pblntf_detail_ty="F001", bgn_de="20180101")
        f002_lists[name] = fetch_disclosure_list(meta["corp_code"], DART_KEY, pblntf_detail_ty="F002", bgn_de="20180101")

    n = len(COMPANIES)
    bizr_filled = sum(1 for ov in overviews.values() if ov.get("bizr_no"))
    jurir_filled = sum(1 for ov in overviews.values() if ov.get("jurir_no"))
    est_dt_blank = [name for name, ov in overviews.items() if not ov.get("est_dt")]
    acc_mt_not_dec = [(name, ov.get("acc_mt")) for name, ov in overviews.items() if ov.get("acc_mt") != "12"]
    f002_companies = [name for name, d in f002_lists.items() if d.get("status") == "000" and d.get("list")]

    correction_count = {}
    for name, d in f001_lists.items():
        reports = d.get("list", []) if d.get("status") == "000" else []
        correction_count[name] = sum(1 for r in reports if "[기재정정]" in (r.get("report_nm") or ""))

    print(f"bizr_no 실값 온 비율: {bizr_filled}/{n}")
    print(f"jurir_no 실값 온 비율: {jurir_filled}/{n}")
    print(f"est_dt 공란: {est_dt_blank if est_dt_blank else '없음'}")
    print(f"acc_mt 12월 아닌 곳: {acc_mt_not_dec if acc_mt_not_dec else '없음(전부 12월)'}")
    print(f"F002(연결감사대상) 제출 회사: {f002_companies if f002_companies else '없음'}")
    print(f"[기재정정] 건수 (회사별): {correction_count}")
    print(f"zip 내부 파일 개수 (회사별): {zip_file_counts}")

    with open(BASE_DIR / "verify_stats_result.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "presence_matrix": presence_matrix,
                "zip_file_counts": zip_file_counts,
                "bizr_no_filled_ratio": f"{bizr_filled}/{n}",
                "jurir_no_filled_ratio": f"{jurir_filled}/{n}",
                "est_dt_blank": est_dt_blank,
                "acc_mt_not_december": acc_mt_not_dec,
                "f002_companies": f002_companies,
                "correction_report_count": correction_count,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    print(f"\n결과 저장: {BASE_DIR / 'verify_stats_result.json'}")


if __name__ == "__main__":
    main()
