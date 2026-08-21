"""
회사명으로 DART corp_code를 찾는 조회 유틸.

계층 순서대로 위에서 아래로 읽으면 된다.

    [1] 설정 / 인증키
    [2] API 호출      HTTP 만 한다. 응답 원본 bytes 를 가공 없이 그대로 반환.
    [3] 파싱          bytes -> 파이썬 자료구조. XML 은 xmltodict, JSON 은 json.
    [4] CORPCODE 캐시 파일이 있으면 그대로 쓰고, 2주가 지났으면 재발급.
    [5] 조회 · 검색   [2] 호출 + [3] 파싱 조합. run_pipeline.py 가 쓰는 이름들.
    [6] CLI

사용법:
    python corp_lookup.py 삼성전자
    python corp_lookup.py 삼성전자 --key YOUR_DART_KEY   # 기업개황까지 조회
"""
import argparse
import io
import json
import os
import sys
import zipfile
from datetime import datetime
from pathlib import Path

import requests
import xmltodict
from dotenv import load_dotenv


# ---------------------------------------------------------------------------
# [1] 설정 / 인증키
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent

ZIP_PATH = BASE_DIR / "CORPCODE.zip"   # corpCode API 응답(ZIP) 원본 그대로
XML_PATH = BASE_DIR / "CORPCODE.xml"   # 위 ZIP 에서 푼 것. 검색·만료판정 대상

MAX_AGE_DAYS = 14                      # CORPCODE.xml 이 이보다 오래되면 재발급
API_BASE = "https://opendart.fss.or.kr/api"

# CORPCODE.xml 의 <list> 하나에서 뽑아 쓰는 필드
CORP_FIELDS = ("corp_code", "corp_name", "corp_eng_name", "stock_code", "modify_date")


def load_api_key(cli_key: str | None = None) -> str | None:
    """인증키를 구한다. 우선순위: --key > 가장 가까운 .env 의 DART_API_KEY.

    이 폴더에는 .env 가 없고 레포 루트에 있으므로 상위로 올라가며 찾는다.
    끝내 못 찾으면 None. (CORPCODE.xml 이 신선하면 키 없이도 검색은 된다)
    """
    if cli_key:
        return cli_key

    for directory in (BASE_DIR, *BASE_DIR.parents):
        env_file = directory / ".env"
        if env_file.exists():
            load_dotenv(env_file)
            break

    return os.environ.get("DART_API_KEY")


# ---------------------------------------------------------------------------
# [2] API 호출 - 응답 원본 bytes 를 그대로 돌려주기만 한다
# ---------------------------------------------------------------------------
def fetch_raw(api: str, **params) -> bytes:
    """DART API GET 1회. 응답 본문 바이트를 손대지 않고 그대로 반환.

    파싱도, 기본값 채우기도, 재시도도 여기서는 하지 않는다.
        corpCode.xml  -> CORPCODE.xml 이 들어있는 ZIP 바이트
        company.json  -> 기업개황 JSON 바이트
        list.json     -> 공시검색 JSON 바이트
    """
    resp = requests.get(f"{API_BASE}/{api}", params=params, timeout=60)
    resp.raise_for_status()
    return resp.content


# ---------------------------------------------------------------------------
# [3] 파싱 - 받아둔 bytes 를 파이썬 자료구조로 바꾸기만 한다
# ---------------------------------------------------------------------------
def parse_json(raw: bytes) -> dict:
    """JSON 응답 원본 bytes -> dict."""
    return json.loads(raw.decode("utf-8"))


def parse_corp_code_xml(xml_bytes: bytes) -> list[dict]:
    """CORPCODE.xml 원본 bytes -> 회사 dict 리스트.

    구조는 <result><list>...</list><list>...</list></result> 이다.
    """
    doc = xmltodict.parse(xml_bytes)
    items = doc.get("result", {}).get("list", [])

    # xmltodict 특성상 항목이 1건이면 dict, 여러 건이면 list 로 오므로 리스트로 통일
    if isinstance(items, dict):
        items = [items]

    # 빈 태그(<stock_code> </stock_code>)는 None 으로 오므로 빈 문자열로 맞춘다
    return [{f: (item.get(f) or "").strip() for f in CORP_FIELDS} for item in items]


# ---------------------------------------------------------------------------
# [4] CORPCODE 캐시 - 있으면 그대로, 2주가 지났으면 다시 받는다
# ---------------------------------------------------------------------------
def age_days(path: Path) -> float:
    """파일 수정시각 기준 경과 일수. 시계 오차로 미래 시각이면 0으로 본다."""
    seconds = (datetime.now() - datetime.fromtimestamp(path.stat().st_mtime)).total_seconds()
    return max(0.0, seconds / 86400)


def refresh_corpcode(api_key: str) -> None:
    """corpCode API 호출 -> ZIP 원본 저장 -> 그 안의 CORPCODE.xml 추출."""
    raw = fetch_raw("corpCode.xml", crtfc_key=api_key)

    # 원본을 먼저 저장한다. 뒤 단계가 실패해도 받은 응답 자체는 남는다.
    ZIP_PATH.write_bytes(raw)
    print(f"       응답 원본 저장: {ZIP_PATH.name} ({len(raw):,} bytes)")

    try:
        zf = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile:
        # 인증키 오류 등이면 ZIP 대신 <result><status>013</status>...</result> 가 온다
        try:
            err = xmltodict.parse(raw).get("result", {})
            detail = f"DART status={err.get('status')}, message={err.get('message')}"
        except Exception:
            detail = raw[:200].decode("utf-8", "replace")
        raise RuntimeError(f"corpCode 응답이 ZIP 이 아님 ({detail})") from None

    inner_name = zf.namelist()[0]
    XML_PATH.write_bytes(zf.read(inner_name))
    print(f"       ZIP 에서 추출: {inner_name} -> {XML_PATH.name} "
          f"({XML_PATH.stat().st_size:,} bytes)")


def ensure_corpcode_xml(api_key: str | None = None) -> Path:
    """CORPCODE.xml 을 쓸 수 있는 상태로 만들고 경로를 반환.

    분기는 세 갈래이고, 어느 길로 갔는지 매번 한 줄씩 출력한다.
        1) 파일 없음             -> 재발급
        2) 파일 있고 2주 초과     -> 재발급
        3) 파일 있고 2주 이내     -> API 호출 없이 그대로 사용
    """
    if not XML_PATH.exists():
        reason = f"{XML_PATH.name} 없음"
    elif age_days(XML_PATH) > MAX_AGE_DAYS:
        reason = f"생성된 지 {age_days(XML_PATH):.0f}일 경과 (기준 {MAX_AGE_DAYS}일)"
    else:
        # 여기서 끝. API 를 부르지 않는다.
        print(f"[캐시] {XML_PATH.name} 그대로 사용 "
              f"({age_days(XML_PATH):.0f}일 전 생성, API 호출 없음)")
        return XML_PATH

    if not api_key:
        # 재발급이 필요한데 키가 없다. 낡았더라도 파일이 있으면 경고 후 쓴다.
        if XML_PATH.exists():
            print(f"[경고] 재발급 필요({reason})하지만 인증키가 없어 기존 파일을 그대로 사용")
            return XML_PATH
        raise RuntimeError(
            f"{XML_PATH.name} 이 없고 인증키도 없습니다. "
            f".env 에 DART_API_KEY 를 넣거나 --key 로 넘겨주세요."
        )

    print(f"[재발급] {reason} -> corpCode API 호출")
    refresh_corpcode(api_key)
    return XML_PATH


# ---------------------------------------------------------------------------
# [5] 조회 · 검색 - [2] 호출 + [3] 파싱 조합
# ---------------------------------------------------------------------------
def load_corp_index(xml_path: Path = XML_PATH) -> list[dict]:
    """디스크의 CORPCODE.xml 을 읽어 회사 리스트로 반환.

    여기서는 캐시 갱신을 하지 않는다. 순수하게 "읽어서 파싱"만 한다.
    갱신 여부 판단은 ensure_corpcode_xml() 의 몫이다.
    """
    return parse_corp_code_xml(Path(xml_path).read_bytes())


def search_by_name(corps: list[dict], keyword: str) -> list[dict]:
    """회사명 부분 일치 검색."""
    return [c for c in corps if keyword in c["corp_name"]]


def fetch_company_overview(corp_code: str, api_key: str) -> dict:
    """기업개황(company.json) 조회."""
    raw = fetch_raw("company.json", crtfc_key=api_key, corp_code=corp_code)
    return parse_json(raw)


def fetch_disclosure_list(
    corp_code: str,
    api_key: str,
    pblntf_detail_ty: str = "F001",
    bgn_de: str = "20200101",
    end_de: str = "20261231",
    page_count: int = 100,
) -> dict:
    """공시검색(list.json) 조회. pblntf_detail_ty=F001 은 감사보고서(외부감사관련)."""
    raw = fetch_raw(
        "list.json",
        crtfc_key=api_key,
        corp_code=corp_code,
        pblntf_detail_ty=pblntf_detail_ty,
        bgn_de=bgn_de,
        end_de=end_de,
        page_count=page_count,
    )
    return parse_json(raw)


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


# ---------------------------------------------------------------------------
# [6] CLI
# ---------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("company", nargs="?", help="검색할 회사명(부분 일치)")
    parser.add_argument("--key", help="DART 인증키. 넘기면 첫 매칭 회사의 기업개황까지 조회")
    args = parser.parse_args()

    if not args.company:
        print("회사명을 인자로 넘겨주세요. 예: python corp_lookup.py 삼성전자")
        return 1

    # 키는 --key 가 없으면 .env 에서 읽는다. CORPCODE 재발급에 필요하다.
    api_key = load_api_key(args.key)

    # CORPCODE.xml 확보 - 있으면 그대로, 없거나 2주 지났으면 재발급
    try:
        xml_path = ensure_corpcode_xml(api_key)
    except (RuntimeError, requests.RequestException) as e:
        print(f"CORPCODE 준비 실패: {e}", file=sys.stderr)
        return 1

    print(f"{xml_path.name} 파싱 중...")
    corps = load_corp_index(xml_path)
    print(f"총 {len(corps):,}개 회사 로드 완료")

    matches = search_by_name(corps, args.company)
    print(f"\n'{args.company}' 검색 결과: {len(matches)}건")
    for c in matches[:20]:
        listed = f"상장({c['stock_code']})" if c["stock_code"] else "비상장"
        print(f"  {c['corp_code']}  {c['corp_name']:<20} {listed}  수정일:{c['modify_date']}")
    if len(matches) > 20:
        print(f"  ... 외 {len(matches) - 20}건")

    # --key 를 명시한 경우에만 기업개황까지 조회 (원래 동작 유지)
    if args.key and matches:
        target = matches[0]
        print(f"\n첫 매칭 회사 '{target['corp_name']}'({target['corp_code']}) 기업개황 조회 중...")
        overview = fetch_company_overview(target["corp_code"], args.key)
        print(json.dumps(overview, ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
