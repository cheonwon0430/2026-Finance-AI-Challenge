"""
CORPCODE.xml을 파싱해서 회사명으로 DART corp_code를 찾는 조회 유틸.

사용법:
    python corp_lookup.py "삼성전자"
    python corp_lookup.py --company "회사명" --key YOUR_DART_KEY   # 기업개황까지 조회
"""
import argparse
import json
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

XML_PATH = Path(__file__).parent / "CORPCODE.xml"


def load_corp_index(xml_path: Path = XML_PATH) -> list[dict]:
    """CORPCODE.xml을 스트리밍 파싱해서 회사 리스트로 반환 (메모리 절약을 위해 iterparse 사용)."""
    corps = []
    for _, elem in ET.iterparse(xml_path, events=("end",)):
        if elem.tag == "list":
            corps.append(
                {
                    "corp_code": (elem.findtext("corp_code") or "").strip(),
                    "corp_name": (elem.findtext("corp_name") or "").strip(),
                    "corp_eng_name": (elem.findtext("corp_eng_name") or "").strip(),
                    "stock_code": (elem.findtext("stock_code") or "").strip(),
                    "modify_date": (elem.findtext("modify_date") or "").strip(),
                }
            )
            elem.clear()
    return corps


def search_by_name(corps: list[dict], keyword: str) -> list[dict]:
    return [c for c in corps if keyword in c["corp_name"]]


def fetch_company_overview(corp_code: str, api_key: str) -> dict:
    url = (
        "https://opendart.fss.or.kr/api/company.json"
        f"?crtfc_key={api_key}&corp_code={corp_code}"
    )
    with urllib.request.urlopen(url) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_disclosure_list(
    corp_code: str,
    api_key: str,
    pblntf_detail_ty: str = "F001",
    bgn_de: str = "20200101",
    end_de: str = "20261231",
    page_count: int = 100,
) -> dict:
    """공시검색 API. pblntf_detail_ty=F001은 감사보고서(외부감사관련)."""
    url = (
        "https://opendart.fss.or.kr/api/list.json"
        f"?crtfc_key={api_key}&corp_code={corp_code}"
        f"&pblntf_detail_ty={pblntf_detail_ty}"
        f"&bgn_de={bgn_de}&end_de={end_de}&page_count={page_count}"
    )
    with urllib.request.urlopen(url) as resp:
        return json.loads(resp.read().decode("utf-8"))


def check_audit_report_availability(corp_code: str, api_key: str) -> dict:
    """외감 대상 여부 판정: 기업개황(corp_cls)과 F001(감사보고서) 공시 존재 여부를 함께 확인."""
    overview = fetch_company_overview(corp_code, api_key)
    disclosures = fetch_disclosure_list(corp_code, api_key, pblntf_detail_ty="F001")

    corp_cls = overview.get("corp_cls")
    is_unlisted = corp_cls == "E"  # E = 기타법인(비상장 외감법인 등)
    has_audit_report = disclosures.get("status") == "000" and bool(disclosures.get("list"))

    return {
        "corp_name": overview.get("corp_name"),
        "corp_cls": corp_cls,
        "is_unlisted_audited_candidate": is_unlisted,
        "audit_report_status": disclosures.get("status"),
        "audit_report_message": disclosures.get("message"),
        "has_audit_report": has_audit_report,
        "audit_report_count": len(disclosures.get("list", [])),
        "audit_reports": disclosures.get("list", []),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("company", nargs="?", help="검색할 회사명(부분 일치)")
    parser.add_argument("--key", help="DART 인증키. 넘기면 첫 매칭 회사의 기업개황까지 조회")
    args = parser.parse_args()

    if not args.company:
        print("회사명을 인자로 넘겨주세요. 예: python corp_lookup.py 삼성전자")
        sys.exit(1)

    print(f"CORPCODE.xml 로딩 중... ({XML_PATH})")
    corps = load_corp_index()
    print(f"총 {len(corps):,}개 회사 로드 완료")

    matches = search_by_name(corps, args.company)
    print(f"\n'{args.company}' 검색 결과: {len(matches)}건")
    for c in matches[:20]:
        listed = f"상장({c['stock_code']})" if c["stock_code"] else "비상장"
        print(f"  {c['corp_code']}  {c['corp_name']:<20} {listed}  수정일:{c['modify_date']}")
    if len(matches) > 20:
        print(f"  ... 외 {len(matches) - 20}건")

    if args.key and matches:
        target = matches[0]
        print(f"\n첫 매칭 회사 '{target['corp_name']}'({target['corp_code']}) 기업개황 조회 중...")
        overview = fetch_company_overview(target["corp_code"], args.key)
        print(json.dumps(overview, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
