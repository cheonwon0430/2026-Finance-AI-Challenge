"""
회사명으로 DART corp_code를 찾는 조회 유틸.

이 파일은 아래 계층 순서대로 위에서 아래로 읽으면 된다.

    [1] 설정      경로 / URL / 캐시 만료 기간
    [2] 인증키    .env 의 DART_API_KEY 또는 --key
    [3] API 계층  HTTP 호출만 한다. 응답 "원본 bytes"를 가공 없이 그대로 반환.
    [4] 파싱 계층 받아둔 bytes 를 dict/list 로 변환. XML 은 xmltodict, JSON 은 json.
    [5] 캐시 계층 CORPCODE.xml 이 있으면 그대로 쓰고, 2주가 지났으면 재발급.
    [6] 검색      회사명 부분 일치
    [7] 호환 함수 기존 이름 그대로 유지 (API 계층 + 파싱 계층 조합). run_pipeline.py 가 사용.
    [8] CLI       main()

사용법:
    python corp_lookup.py 삼성전자              # 캐시가 신선하면 API 호출 없이 바로 검색
    python corp_lookup.py 삼성전자 --refresh    # 캐시를 무시하고 CORPCODE 강제 재발급
    python corp_lookup.py 삼성전자 --overview   # 첫 매칭 회사의 기업개황까지 조회
    python corp_lookup.py 삼성전자 --key XXX    # .env 대신 이 인증키 사용
"""
import argparse
import io
import json
import os
import sys
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

import requests
import xmltodict
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# [1] 설정
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent

ZIP_PATH = BASE_DIR / "CORPCODE.zip"   # corpCode API 응답(ZIP) 원본 그대로
XML_PATH = BASE_DIR / "CORPCODE.xml"   # 위 ZIP 에서 푼 것. 검색·만료판정 대상

MAX_AGE = timedelta(days=14)           # CORPCODE.xml 이 이보다 오래되면 재발급
API_BASE = "https://opendart.fss.or.kr/api"

# CORPCODE.xml 의 <list> 하나에서 뽑아 쓰는 필드
CORP_FIELDS = ("corp_code", "corp_name", "corp_eng_name", "stock_code", "modify_date")


# ---------------------------------------------------------------------------
# [2] 인증키
# ---------------------------------------------------------------------------
def load_api_key(cli_key: str | None = None) -> str | None:
    """인증키를 구한다. 우선순위: --key > 가장 가까운 .env 의 DART_API_KEY.

    이 폴더에는 .env 가 없고 레포 루트에 있으므로 상위로 올라가며 찾는다.
    끝내 못 찾으면 None. (캐시가 신선하면 키 없이도 검색은 된다)
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
# [3] API 계층 - 호출만 하고 응답 원본 bytes 를 그대로 돌려준다
#     여기서는 파싱도, 기본값 채우기도, 재시도도 하지 않는다.
# ---------------------------------------------------------------------------
def _get_raw(api: str, params: dict) -> bytes:
    """GET 1회. 응답 본문 바이트를 손대지 않고 그대로 반환."""
    resp = requests.get(f"{API_BASE}/{api}", params=params, timeout=60)
    resp.raise_for_status()
    return resp.content


def fetch_corp_code_zip(api_key: str) -> bytes:
    """고유번호 전체 파일(corpCode.xml). 응답은 CORPCODE.xml 이 담긴 ZIP 바이트다."""
    return _get_raw("corpCode.xml", {"crtfc_key": api_key})


def fetch_company_overview_raw(corp_code: str, api_key: str) -> bytes:
    """기업개황(company.json) 응답 원본."""
    return _get_raw("company.json", {"crtfc_key": api_key, "corp_code": corp_code})


def fetch_disclosure_list_raw(
    corp_code: str,
    api_key: str,
    pblntf_detail_ty: str = "F001",
    bgn_de: str = "20200101",
    end_de: str = "20261231",
    page_count: int = 100,
) -> bytes:
    """공시검색(list.json) 응답 원본. pblntf_detail_ty=F001 은 감사보고서(외부감사관련)."""
    return _get_raw(
        "list.json",
        {
            "crtfc_key": api_key,
            "corp_code": corp_code,
            "pblntf_detail_ty": pblntf_detail_ty,
            "bgn_de": bgn_de,
            "end_de": end_de,
            "page_count": page_count,
        },
    )


# ---------------------------------------------------------------------------
# [4] 파싱 계층 - 위에서 받아둔 bytes 를 파이썬 자료구조로 바꾸기만 한다
# ---------------------------------------------------------------------------
def parse_json_response(raw: bytes) -> dict:
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


def parse_dart_error_xml(raw: bytes) -> dict:
    """인증키 오류 등으로 ZIP 대신 온 에러 XML -> {'status', 'message'}.

    응답 형태: <result><status>013</status><message>...</message></result>
    """
    try:
        result = xmltodict.parse(raw).get("result", {})
        return {"status": result.get("status"), "message": result.get("message")}
    except Exception:
        # 에러 XML 조차 아니면 앞부분만 잘라서 그대로 보여준다
        return {"status": None, "message": raw[:200].decode("utf-8", "replace")}


# ---------------------------------------------------------------------------
# [5] 캐시 계층 - 있으면 쓰고, 2주가 지났으면 다시 받는다
# ---------------------------------------------------------------------------
def file_age(path: Path) -> timedelta:
    """파일 수정시각 기준 경과 시간. 미래 시각(시계 오차)이면 0으로 본다."""
    age = datetime.now() - datetime.fromtimestamp(path.stat().st_mtime)
    return max(timedelta(0), age)


def age_days(path: Path) -> int:
    """메시지에 쓸 경과 일수. timedelta.days 는 내림이라 15일이 14일로 보이므로 반올림한다."""
    return round(file_age(path).total_seconds() / 86400)


def is_fresh(path: Path) -> bool:
    """파일이 있고 MAX_AGE(2주) 이내면 True."""
    return path.exists() and file_age(path) < MAX_AGE


def refresh_corpcode(api_key: str) -> None:
    """corpCode API 호출 -> ZIP 원본 저장 -> 그 안의 CORPCODE.xml 추출."""
    raw = fetch_corp_code_zip(api_key)

    # 원본을 먼저 저장한다. 뒤 단계가 실패해도 받은 응답 자체는 남는다.
    ZIP_PATH.write_bytes(raw)
    print(f"       응답 원본 저장: {ZIP_PATH.name} ({len(raw):,} bytes)")

    try:
        zf = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile:
        # 인증키 오류 등이면 ZIP 이 아니라 에러 XML 이 온다 -> DART 상태코드를 그대로 알린다
        err = parse_dart_error_xml(raw)
        raise RuntimeError(
            f"corpCode 응답이 ZIP 이 아님 "
            f"(DART status={err['status']}, message={err['message']})"
        ) from None

    inner_name = zf.namelist()[0]
    XML_PATH.write_bytes(zf.read(inner_name))
    print(f"       ZIP 에서 추출: {inner_name} -> {XML_PATH.name} "
          f"({XML_PATH.stat().st_size:,} bytes)")


def ensure_corpcode_xml(api_key: str | None = None, force: bool = False) -> Path:
    """CORPCODE.xml 을 쓸 수 있는 상태로 만들고 경로를 반환.

    분기는 네 갈래이고, 어느 길로 갔는지 매번 한 줄씩 출력한다.
        1) force=True          -> 재발급
        2) 파일 없음            -> 재발급
        3) 파일 있고 2주 초과    -> 재발급
        4) 파일 있고 2주 이내    -> API 호출 없이 그대로 사용
    """
    if force:
        reason = "--refresh 지정"
    elif not XML_PATH.exists():
        reason = f"{XML_PATH.name} 없음"
    elif not is_fresh(XML_PATH):
        reason = f"생성된 지 {age_days(XML_PATH)}일 경과 (기준 {MAX_AGE.days}일)"
    else:
        # 여기서 끝. API 를 부르지 않는다.
        print(f"[캐시] {XML_PATH.name} 그대로 사용 "
              f"({age_days(XML_PATH)}일 전 생성, API 호출 없음)")
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
# [6] 검색
# ---------------------------------------------------------------------------
def search_by_name(corps: list[dict], keyword: str) -> list[dict]:
    """회사명 부분 일치 검색."""
    return [c for c in corps if keyword in c["corp_name"]]


# ---------------------------------------------------------------------------
# [7] 호환 함수 - 기존 이름/시그니처 그대로. 내부만 [3]+[4] 조합으로 바뀌었다.
#     run_pipeline.py 가 이 이름들을 import 해서 쓴다.
# ---------------------------------------------------------------------------
def load_corp_index(xml_path: Path = XML_PATH) -> list[dict]:
    """디스크의 CORPCODE.xml 을 읽어 회사 리스트로 반환.

    여기서는 캐시 갱신을 하지 않는다. 순수하게 "읽어서 파싱"만 한다.
    갱신 여부 판단은 ensure_corpcode_xml() 의 몫이다.
    """
    return parse_corp_code_xml(Path(xml_path).read_bytes())


def fetch_company_overview(corp_code: str, api_key: str) -> dict:
    """기업개황 조회 (호출 + 파싱)."""
    return parse_json_response(fetch_company_overview_raw(corp_code, api_key))


def fetch_disclosure_list(
    corp_code: str,
    api_key: str,
    pblntf_detail_ty: str = "F001",
    bgn_de: str = "20200101",
    end_de: str = "20261231",
    page_count: int = 100,
) -> dict:
    """공시검색 조회 (호출 + 파싱)."""
    return parse_json_response(
        fetch_disclosure_list_raw(
            corp_code, api_key, pblntf_detail_ty, bgn_de, end_de, page_count
        )
    )


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
# [8] CLI
# ---------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(description="회사명으로 DART corp_code 검색")
    parser.add_argument("company", nargs="?", help="검색할 회사명(부분 일치)")
    parser.add_argument("--key", help="DART 인증키. 없으면 .env 의 DART_API_KEY 사용")
    parser.add_argument("--refresh", action="store_true",
                        help="캐시를 무시하고 CORPCODE 를 강제로 다시 받는다")
    parser.add_argument("--overview", action="store_true",
                        help="첫 매칭 회사의 기업개황까지 조회")
    args = parser.parse_args()

    if not args.company:
        print("회사명을 인자로 넘겨주세요. 예: python corp_lookup.py 삼성전자")
        return 1

    api_key = load_api_key(args.key)

    # (1) CORPCODE.xml 확보 - 있으면 그대로, 없거나 2주 지났으면 재발급
    try:
        xml_path = ensure_corpcode_xml(api_key, force=args.refresh)
    except (RuntimeError, requests.RequestException) as e:
        print(f"CORPCODE 준비 실패: {e}", file=sys.stderr)
        return 1

    # (2) 파싱
    print(f"{xml_path.name} 파싱 중...")
    corps = load_corp_index(xml_path)
    print(f"총 {len(corps):,}개 회사 로드 완료")

    # (3) 검색
    matches = search_by_name(corps, args.company)
    print(f"\n'{args.company}' 검색 결과: {len(matches)}건")
    for c in matches[:20]:
        listed = f"상장({c['stock_code']})" if c["stock_code"] else "비상장"
        print(f"  {c['corp_code']}  {c['corp_name']:<20} {listed}  수정일:{c['modify_date']}")
    if len(matches) > 20:
        print(f"  ... 외 {len(matches) - 20}건")

    # (4) 선택: 첫 매칭 회사의 기업개황
    if args.overview and matches:
        if not api_key:
            print("\n기업개황 조회에는 인증키가 필요합니다 (.env 의 DART_API_KEY 또는 --key)",
                  file=sys.stderr)
            return 1
        target = matches[0]
        print(f"\n첫 매칭 회사 '{target['corp_name']}'({target['corp_code']}) 기업개황 조회 중...")
        overview = fetch_company_overview(target["corp_code"], api_key)
        print(json.dumps(overview, ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
