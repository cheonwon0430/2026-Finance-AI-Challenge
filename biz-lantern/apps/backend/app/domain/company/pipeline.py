"""
회사명 하나로 DART·국세청 원천 데이터를 모으는 수집 파이프라인.

api/ 와 parser/ 는 건드리지 않는다. 이미 있는 함수들이 돌려주는 값을 여기서 받아
조합하고 저장하기만 한다.

수집은 두 단계로 나뉜다.

    [1단계] 회사명(자연어) -> corp_search.search_by_name -> 후보 리스트
            부분 일치라 "핀" 하나로도 수십 건이 나온다. 자동으로 고르지 않고
            호출하는 쪽(라우터 / CLI)이 corp_code 를 확정한다.

    [2단계] corp_code -> collect() -> 원천 데이터 파일 + CollectResult

collect() 가 sync 인 이유: async 인 건 corp_search(-> dart_corp_code) 뿐이고 그건
1단계 전용이다. 2단계가 부르는 dart_company / dart_disclosure_list / dart_document /
nts_api 는 전부 sync 라 asyncio.to_thread 로 감쌀 이유가 없다. 라우터는 collect 를
def 핸들러(비-async)로 노출하면 FastAPI 가 스레드풀에서 돌려 이벤트 루프를 막지 않는다.

계층 순서대로 위에서 아래로 읽으면 된다.

    [1] 설정
    [2] 진행 상황 알림   단계마다 이벤트를 낸다. 실패도 조용히 지나가지 않는다.
    [3] 저장             받은 원본을 가공 없이 파일로 남긴다.
    [4] 단계별 수집      한 단계가 함수 하나. 어디까지가 치명적 실패인지 각자 정한다.
    [5] 파이프라인       단계를 순서대로 엮는다.
    [6] CLI

사용법:
    python -m app.domain.company.pipeline 핀샷
    python -m app.domain.company.pipeline 핀 --corp-code 01836952
    python -m app.domain.company.pipeline --corp-code 01836952
"""
import argparse
import asyncio
import json
import logging
import re
from collections.abc import Callable
from pathlib import Path
from typing import Literal, TypedDict

from app.domain.company.api.corp_search import search_by_name
from app.domain.company.api.dart_company import get_company
from app.domain.company.api.dart_disclosure_list import get_disclosure_list
from app.domain.company.api.dart_document import extract_xml, fetch_document_raw
from app.domain.company.api.nts_api import is_operating_business
from app.domain.company.parser.document_clean import clean_document, save_outputs

# ---------------------------------------------------------------------------
# [1] 설정
# ---------------------------------------------------------------------------
RAW_DIR = Path("data/raw")          # 받은 응답 원본. data/ 는 gitignore 대상이다

# bgn_de 를 주지 않으면 DART 는 최근 3개월치만 준다. 감사보고서는 연 1회라 그 범위로는
# 대부분 0건으로 나오므로 시작일을 명시적으로 고정한다.
F001_BGN_DE = "20180101"
F001 = "F001"                       # 공시유형 상세: 감사보고서

DART_OK = "000"                     # 정상 응답
DART_NO_DATA = "013"                # 조회된 데이터 없음. 오류가 아니다

TOTAL_STEPS = 5

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# [2] 진행 상황 알림
# ---------------------------------------------------------------------------
# 수집은 네트워크를 다섯 번 타서 수 초~수십 초가 걸린다. 어느 단계를 지나는 중인지,
# 어디서 실패했는지가 보여야 한다.
#
# 여기서 print 로 직접 찍지 않고 콜백으로 이벤트만 내보낸다. CLI 는 화면에 찍고,
# 나중에 라우터가 붙으면 같은 이벤트를 SSE 로 프론트에 흘리면 된다. 그때 이 파일을
# 다시 고칠 일이 없다.
Status = Literal["start", "ok", "skip", "fail"]


class Progress(TypedDict):
    step: int
    total: int
    name: str
    status: Status
    detail: str | None


class _Reporter:
    """이벤트를 콜백으로 흘리면서 동시에 결과용 요약을 모은다."""

    def __init__(self, on_progress: Callable[[Progress], None] | None):
        # 콜백을 안 주더라도 조용히 사라지지는 않게 로거로 남긴다
        self._on_progress = on_progress or _log_progress
        self.steps: list[Progress] = []

    def __call__(self, step: int, name: str, status: Status, detail: str | None = None) -> None:
        event: Progress = {
            "step": step,
            "total": TOTAL_STEPS,
            "name": name,
            "status": status,
            "detail": detail,
        }

        # steps 에는 끝난 단계만 담는다. start 까지 넣으면 요약이 두 배로 길어지는데,
        # 결과만 보는 쪽이 알고 싶은 건 "무엇이 됐고 무엇이 실패했나" 뿐이다.
        if status != "start":
            self.steps.append(event)

        try:
            self._on_progress(event)
        except Exception:
            # 알림이 깨졌다고 수집까지 망가뜨리지는 않는다
            logger.exception("진행 상황 콜백에서 예외 발생 (수집은 계속한다)")


def _log_progress(event: Progress) -> None:
    """콜백을 주지 않았을 때의 기본 동작."""
    level = logging.ERROR if event["status"] == "fail" else logging.INFO
    logger.log(
        level,
        "[%d/%d] %s %s%s",
        event["step"],
        event["total"],
        event["name"],
        event["status"],
        f" - {event['detail']}" if event["detail"] else "",
    )


# httpx 의 HTTPStatusError 는 요청 URL 을 메시지에 그대로 담는다. DART 도 국세청도
# 인증키를 쿼리스트링으로 받으므로 그대로 두면 키가 로그와 steps 에 실려 나간다.
# steps 는 나중에 SSE 로 프론트까지 갈 값이라 여기서 반드시 지운다.
_SECRET_PARAM = re.compile(r"([?&](?:serviceKey|crtfc_key)=)[^&\s'\"]+", re.IGNORECASE)


def _reason(error: Exception) -> str:
    """예외를 알림에 실을 한 줄로. 타입을 남겨야 무엇이 터졌는지 알 수 있다.

    인증키를 지우고 첫 줄만 남긴다. httpx 는 메시지에 안내 링크까지 붙여 여러 줄로 오는데
    그대로 흘리면 한 줄짜리 진행 표시가 무너진다.
    """
    message = _SECRET_PARAM.sub(r"\1***", str(error))

    return f"{type(error).__name__}: {(message.splitlines() or [''])[0]}"


# ---------------------------------------------------------------------------
# [3] 저장 - 받은 원본을 가공 없이 남긴다
# ---------------------------------------------------------------------------
def company_dir(corp_code: str) -> Path:
    """회사별 원본 디렉터리. 없으면 만든다."""
    path = RAW_DIR / corp_code
    path.mkdir(parents=True, exist_ok=True)

    return path


def _save_text(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")

    return path


# ---------------------------------------------------------------------------
# [4] 단계별 수집
# ---------------------------------------------------------------------------
def _fetch_company(corp_code: str, report: _Reporter, paths: dict[str, str]) -> dict:
    """[1/5] 기업개황. 이게 실패하면 뒤 단계가 성립하지 않으므로 예외를 올린다."""
    name = "기업개황 조회"
    report(1, name, "start", f"corp_code={corp_code}")

    try:
        # get_company 는 이미 indent=2 로 정렬된 JSON 문자열을 돌려준다.
        # 그 문자열을 그대로 저장하고 그대로 파싱하므로 저장본과 처리본이 어긋날 수 없다.
        payload = get_company(corp_code)
        company = json.loads(payload)

        if company.get("status") != DART_OK:
            raise ValueError(
                f"DART 기업개황 조회 실패: status={company.get('status')} {company.get('message')}"
            )
    except Exception as error:
        # 예외를 올리기 전에 알린다. 그래야 위로 전파돼도 어느 단계에서 깨졌는지가 남는다.
        report(1, name, "fail", _reason(error))
        raise

    paths["company"] = str(_save_text(company_dir(corp_code) / "company.json", payload))
    report(1, name, "ok", company.get("corp_name"))

    return company


def _verify_nts(company: dict, report: _Reporter) -> tuple[bool | None, str | None]:
    """[2/5] 국세청 진위확인 + 상태조회. 서버가 불안정해 실패해도 수집을 멈추지 않는다.

    공동대표를 p_nm / p_nm2 로 쪼개는 규칙이 is_operating_business 안에 이미 있으므로
    여기서 payload 를 다시 만들지 않는다.
    """
    name = "국세청 사업자 확인"
    report(2, name, "start")

    bizr_no = (company.get("bizr_no") or "").strip()
    if not bizr_no:
        detail = "기업개황에 사업자등록번호(bizr_no)가 없음"
        report(2, name, "skip", detail)

        return None, detail

    try:
        operating = is_operating_business(
            bizr_no=bizr_no,
            ceo_nm=company["ceo_nm"],
            est_dt=company["est_dt"],
        )
    except Exception as error:  # noqa: BLE001 - 국세청 서버는 자주 죽는다. 무엇이 터지든 수집은 계속한다
        detail = _reason(error)
        report(2, name, "fail", f"{detail} (건너뛰고 계속)")

        return None, detail

    report(2, name, "ok", "계속사업자" if operating else "확인 실패(폐업·휴업 또는 정보 불일치)")

    return operating, None


def _find_audit_report(corp_code: str, report: _Reporter, paths: dict[str, str]) -> dict | None:
    """[3/5] 감사보고서(F001) 목록에서 최신 1건을 고른다.

    감사보고서 한 건에 당기·전기 2개년 비교 재무가 들어 있어 최신 1건으로 전년 대비까지 나온다.
    0건이면 외감 대상이 아닌 소규모 비상장이라는 뜻이므로 오류가 아니다.
    """
    name = "감사보고서 목록(F001) 조회"
    report(3, name, "start")

    try:
        payload = get_disclosure_list(
            corp_code,
            bgn_de=F001_BGN_DE,
            pblntf_detail_ty=F001,
        )
        disclosures = json.loads(payload)
        status = disclosures.get("status")

        if status not in (DART_OK, DART_NO_DATA):
            raise ValueError(
                f"DART 공시검색 실패: status={status} {disclosures.get('message')}"
            )
    except Exception as error:
        report(3, name, "fail", _reason(error))
        raise

    paths["disclosures"] = str(
        _save_text(company_dir(corp_code) / "disclosure_f001.json", payload)
    )

    items = disclosures.get("list") or []
    if not items:
        report(3, name, "skip", "감사보고서 없음 (외부감사 대상이 아닐 수 있음)")

        return None

    # 응답 순서에 기대지 않고 접수일자로 명시적으로 고른다
    latest = max(items, key=lambda item: item["rcept_dt"])
    report(3, name, "ok", f"{len(items)}건 중 최신 {latest['rcept_dt']} 선택")

    return latest


def _fetch_document(corp_code: str, rcept_no: str, report: _Reporter, paths: dict[str, str]) -> str:
    """[4/5] 감사보고서 원문 XML. 이미 받아둔 게 있으면 다시 받지 않는다.

    문서는 접수번호별로 불변이고 건당 수 MB 이며 DART 일일 한도가 2만 건이다.
    저장하는 건 이스케이프 전 원본이다. escape_bare_tags 는 clean_document 가
    안에서 하므로 파일에는 DART 가 준 그대로 남는다.
    """
    name = "감사보고서 원문"
    report(4, name, "start", f"rcept_no={rcept_no}")

    directory = company_dir(corp_code)

    # ZIP 안의 파일명은 {rcept_no}_00760.xml 처럼 접미사가 붙는다. 원본 이름을 지키려고
    # 접수번호로 시작하는 파일을 찾는 방식으로 캐시를 확인한다.
    cached = sorted(directory.glob(f"{rcept_no}*.xml"))
    if cached:
        paths["document_xml"] = str(cached[0])
        report(4, name, "ok", f"캐시 사용 ({cached[0].name})")

        return cached[0].read_text(encoding="utf-8")

    try:
        documents = extract_xml(fetch_document_raw(rcept_no))
        if not documents:
            raise ValueError(f"공시원문 ZIP 이 비어 있음: rcept_no={rcept_no}")
    except Exception as error:
        report(4, name, "fail", _reason(error))
        raise

    # ZIP 안의 파일을 전부 남기고 첫 번째를 정리 대상으로 삼는다
    saved = [_save_text(directory / filename, text) for filename, text in documents.items()]

    paths["document_xml"] = str(saved[0])
    report(4, name, "ok", f"{len(saved)}개 파일 저장 ({saved[0].name})")

    return documents[saved[0].name]


def _clean(rcept_no: str, xml_text: str, report: _Reporter, paths: dict[str, str]) -> dict:
    """[5/5] 원문 정리. load_xml() 은 접수번호로 API 를 다시 타므로 쓰지 않는다."""
    name = "원문 정리"
    report(5, name, "start")

    try:
        cleaned = clean_document(xml_text)
        json_path, md_path = save_outputs(cleaned, rcept_no)
    except Exception as error:
        report(5, name, "fail", _reason(error))
        raise

    paths["document_clean_json"] = str(json_path)
    paths["document_clean_md"] = str(md_path)
    report(5, name, "ok", f"{len(cleaned['sections'])}개 섹션 -> {json_path}")

    return cleaned


# ---------------------------------------------------------------------------
# [5] 파이프라인
# ---------------------------------------------------------------------------
class CollectResult(TypedDict):
    corp_code: str
    company: dict                # 기업개황 원본
    nts_operating: bool | None   # 진위확인+상태조회 통과 여부. 확인 못 했으면 None
    nts_error: str | None
    audit_report: dict | None    # 선택한 F001 1건의 메타
    document: dict | None        # document_clean 결과
    paths: dict[str, str]        # 저장한 파일 경로
    steps: list[Progress]        # 단계별 진행·실패 기록


def collect(
    corp_code: str,
    on_progress: Callable[[Progress], None] | None = None,
) -> CollectResult:
    """corp_code 하나로 원천 데이터를 모아 파일로 남기고 결과를 돌려준다.

    부분 실패를 허용한다. 국세청 조회가 실패하거나 감사보고서가 아예 없어도 나머지는
    끝까지 수집하고, 무엇이 빠졌는지 nts_error / audit_report / steps 에 남긴다.
    반대로 기업개황과 원문 처리가 깨지면 예외를 올린다 - 있다고 한 보고서를 못 읽는 건
    비어 있는 결과로 덮을 문제가 아니다.
    """
    report = _Reporter(on_progress)
    paths: dict[str, str] = {}

    company = _fetch_company(corp_code, report, paths)
    nts_operating, nts_error = _verify_nts(company, report)
    audit_report = _find_audit_report(corp_code, report, paths)

    document = None
    if audit_report is not None:
        rcept_no = audit_report["rcept_no"]
        document = _clean(rcept_no, _fetch_document(corp_code, rcept_no, report, paths), report, paths)

    return {
        "corp_code": corp_code,
        "company": company,
        "nts_operating": nts_operating,
        "nts_error": nts_error,
        "audit_report": audit_report,
        "document": document,
        "paths": paths,
        "steps": report.steps,
    }


# ---------------------------------------------------------------------------
# [6] CLI
# ---------------------------------------------------------------------------
_STATUS_LABEL = {"ok": "완료", "skip": "건너뜀", "fail": "실패"}


def _print_progress(event: Progress) -> None:
    """start 로 줄을 열고 끝난 상태로 같은 줄을 닫는다.

        [1/5] 기업개황 조회 (corp_code=01836952) ... 완료
    """
    detail = event["detail"]

    if event["status"] == "start":
        head = f"[{event['step']}/{event['total']}] {event['name']}"
        print(f"{head}{f' ({detail})' if detail else ''} ... ", end="", flush=True)

        return

    label = _STATUS_LABEL[event["status"]]
    print(f"{label}{f': {detail}' if detail else ''}", flush=True)


def _resolve_corp_code(company_name: str) -> str | None:
    """회사명으로 후보를 찾아 1건일 때만 corp_code 를 돌려준다.

    부분 일치라 여러 건이 흔하다. 자동으로 고르면 엉뚱한 회사를 분석하게 되므로
    후보만 보여주고 사용자가 --corp-code 로 정하게 한다.
    """
    matches = asyncio.run(search_by_name(company_name))

    if not matches:
        print(f"'{company_name}' 검색 결과 없음")

        return None

    if len(matches) == 1:
        return matches[0]["corp_code"]

    print(f"'{company_name}' 매칭 {len(matches)}건 - --corp-code 로 특정해주세요:")
    for corp in matches[:20]:
        listed = f"상장({corp['stock_code']})" if corp["stock_code"] else "비상장"
        print(f"  {corp['corp_code']}  {corp['corp_name']:<20} {listed}")

    if len(matches) > 20:
        print(f"  ... 외 {len(matches) - 20}건")

    return None


if __name__ == "__main__":
    import sys

    parser = argparse.ArgumentParser(description="회사명 또는 corp_code 로 원천 데이터를 수집한다")
    parser.add_argument("company", nargs="?", help="검색할 회사명")
    parser.add_argument("--corp-code", help="corp_code 직접 지정 (동명 다건일 때)")
    args = parser.parse_args()

    if not args.company and not args.corp_code:
        parser.error("회사명이나 --corp-code 중 하나는 있어야 합니다")

    target = args.corp_code or _resolve_corp_code(args.company)
    if target is None:
        sys.exit(1)

    try:
        result = collect(target, on_progress=_print_progress)
    except Exception as error:  # noqa: BLE001 - CLI 최상단. 어떤 실패든 사람이 읽을 한 줄로 바꿔 내보낸다
        # collect 는 치명적 실패를 예외로 올린다. 라이브러리 호출자에게는 그게 맞지만
        # CLI 에서 트레이스백만 뱉으면 무엇이 잘못됐는지가 묻힌다.
        # 어느 단계에서 깨졌는지는 이미 위에 fail 로 찍혔으므로 여기서는 사유만 덧붙인다.
        print()
        print(f"수집 실패: {_reason(error)}", file=sys.stderr)
        sys.exit(1)

    print()
    print(f"수집 완료: {result['company'].get('corp_name')} ({target})")
    for key, path in result["paths"].items():
        print(f"  {key:<22} {path}")

    failed = [step for step in result["steps"] if step["status"] in ("fail", "skip")]
    if failed:
        print()
        print("확인 필요:")
        for step in failed:
            print(f"  [{step['step']}/{step['total']}] {step['name']} - {step['detail']}")
