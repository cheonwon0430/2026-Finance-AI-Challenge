"""
샘플 5개사에 대해 DART OpenAPI 4종을 호출하고 응답 원본을 dump/에 그대로 저장한다.

파싱/가공/기본값 채우기/재시도 없음. 저장은 항상 resp.content 바이트를 그대로 write한다.
실패한 호출은 실패한 상태 그대로 _manifest.json에 남기고 다음으로 진행한다.

사용법:
    python dump_dart_raw.py
"""
import io
import json
import os
import re
import sys
import time
import zipfile
from datetime import date, datetime
from pathlib import Path
from xml.etree import ElementTree as ET

import requests
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
DUMP_DIR = BASE_DIR / "dump"
API_BASE = "https://opendart.fss.or.kr/api"
SLEEP_SEC = 0.5

TARGETS = [
    "주식회사 트래블월렛",
    "주식회사 센트비",
    "주식회사 핀샷",
    "주식회사 이롬넷",
    "주식회사 아이씨비",
]
DETAIL_TYPES = ["F001", "F002", "F005"]
BGN_DE = "20200101"
END_DE = date.today().strftime("%Y%m%d")

MANIFEST = []


def mask(params: dict) -> dict:
    """crtfc_key 값만 가린 사본. dump/는 gitignore 대상이 아니라서 키를 그대로 남기지 않는다."""
    return {k: ("***" if k == "crtfc_key" else v) for k, v in params.items()}


def log(api: str, params: dict, *, corp_code=None, resp=None, saved_as=None,
        error=None, skipped=None, extra=None) -> None:
    """호출 1건을 매니페스트에 기록. 값이 없는 필드는 키 자체를 넣지 않는다."""
    rec = {"timestamp": datetime.now().isoformat(timespec="seconds"), "api": api}
    if corp_code:
        rec["corp_code"] = corp_code
    rec["params"] = mask(params)
    rec["url"] = f"{API_BASE}/{api}"
    if resp is not None:
        rec["http_status"] = resp.status_code
        rec["bytes"] = len(resp.content)
        ctype = resp.headers.get("Content-Type", "")
        if ctype:
            rec["content_type"] = ctype
        if "json" in ctype.lower():
            # 매니페스트 기록 목적의 읽기일 뿐, 저장 파일은 원본 바이트 그대로다.
            try:
                body = resp.json()
                if "status" in body:
                    rec["dart_status"] = body["status"]
                if "message" in body:
                    rec["dart_message"] = body["message"]
            except ValueError:
                pass
    if saved_as:
        rec["saved_as"] = saved_as
    if skipped:
        rec["skipped"] = skipped
    if error:
        rec["error"] = error
    if extra:
        rec.update(extra)
    MANIFEST.append(rec)


def call(api: str, params: dict, *, corp_code=None, save_as=None):
    """GET 1회 + 원본 바이트 저장. 재시도/우회 없음. 실패 시 (None, None)."""
    url = f"{API_BASE}/{api}"
    try:
        resp = requests.get(url, params=params, timeout=60)
    except Exception as e:
        log(api, params, corp_code=corp_code, error=f"{type(e).__name__}: {e}")
        print(f"    요청 실패: {type(e).__name__}: {e}")
        return None, None

    saved = None
    if save_as:
        path = DUMP_DIR / save_as
        path.write_bytes(resp.content)  # 원본 바이트 그대로
        saved = save_as
    log(api, params, corp_code=corp_code, resp=resp, saved_as=saved)
    return resp, saved


def normalize(name: str) -> str:
    """공백 제거 → 주식회사/(주)/㈜ 접두·접미 제거. 대상명과 corp_name에 동일 적용."""
    s = re.sub(r"\s+", "", name)
    s = re.sub(r"^(주식회사|㈜|\(주\))", "", s)
    s = re.sub(r"(주식회사|㈜|\(주\))$", "", s)
    return s


def step1_corp_code(key: str):
    print("[1/4] corpCode.xml")
    resp, _ = call("corpCode.xml", {"crtfc_key": key}, save_as="corpCode.zip")
    if resp is None:
        return None
    print(f"    HTTP {resp.status_code}, {len(resp.content):,} bytes → dump/corpCode.zip")

    try:
        zf = zipfile.ZipFile(io.BytesIO(resp.content))
    except zipfile.BadZipFile as e:
        # 키 오류 등으로 zip이 아닌 에러 XML이 온 경우. 파일은 저장된 그대로 두고 중단.
        MANIFEST[-1]["error"] = f"BadZipFile: {e} (응답이 zip이 아님)"
        print(f"    응답이 zip이 아님: {e}")
        return None

    # 매칭 목적으로만 메모리에서 파싱. dump/corpCode.zip은 zip 그대로 유지된다.
    index = {}
    with zf.open(zf.namelist()[0]) as fp:
        for _, elem in ET.iterparse(fp, events=("end",)):
            if elem.tag != "list":
                continue
            corp_name = (elem.findtext("corp_name") or "").strip()
            index.setdefault(normalize(corp_name), []).append({
                "corp_code": (elem.findtext("corp_code") or "").strip(),
                "corp_name": corp_name,  # 원본 corp_name 그대로
                "stock_code": (elem.findtext("stock_code") or "").strip(),
                "modify_date": (elem.findtext("modify_date") or "").strip(),
            })
            elem.clear()
    print(f"    총 {sum(len(v) for v in index.values()):,}개 회사 로드")

    results = []
    for target in TARGETS:
        norm = normalize(target)
        cands = index.get(norm, [])
        results.append({
            "target": target,
            "normalized": norm,
            "matched": bool(cands),
            "candidates": cands,
        })
        if cands:
            desc = ", ".join(f"{c['corp_code']}({c['corp_name']})" for c in cands)
            print(f"    {target} → {len(cands)}건: {desc}")
        else:
            print(f"    {target} → 매칭 실패")

    (DUMP_DIR / "_corp_match.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return results


def main() -> int:
    load_dotenv(BASE_DIR / ".env")
    key = os.environ.get("DART_API_KEY")
    if not key:
        print(".env에 DART_API_KEY가 없습니다.", file=sys.stderr)
        return 1

    DUMP_DIR.mkdir(exist_ok=True)
    match_results = step1_corp_code(key)
    if match_results is None:
        (DUMP_DIR / "_manifest.json").write_text(
            json.dumps(MANIFEST, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print("corpCode 단계 실패 - 중단")
        return 1

    # 매칭 성공한 후보 전부 대상 (후보 2건 이상이면 각각 수행)
    codes = [(r["target"], c["corp_code"]) for r in match_results for c in r["candidates"]]

    print(f"\n[2/4] company.json ({len(codes)}건)")
    for target, cc in codes:
        time.sleep(SLEEP_SEC)
        resp, saved = call("company.json", {"crtfc_key": key, "corp_code": cc},
                           corp_code=cc, save_as=f"company_{cc}.json")
        st = MANIFEST[-1].get("dart_status", "-")
        print(f"    {target} {cc}: status={st} → {saved}")

    print(f"\n[3/4] list.json ({len(codes) * len(DETAIL_TYPES)}건)")
    f001_latest = {}  # corp_code -> rcept_no (선택 목적, 덤프 파일은 원본 유지)
    for target, cc in codes:
        for ty in DETAIL_TYPES:
            time.sleep(SLEEP_SEC)
            params = {
                "crtfc_key": key,
                "corp_code": cc,
                "bgn_de": BGN_DE,
                "end_de": END_DE,
                "pblntf_detail_ty": ty,
                "last_reprt_at": "N",
                "page_count": 100,
            }
            resp, saved = call("list.json", params, corp_code=cc,
                               save_as=f"list_{cc}_{ty}.json")
            st = MANIFEST[-1].get("dart_status", "-")
            n = "-"
            if ty == "F001" and resp is not None:
                try:
                    body = resp.json()
                except ValueError:
                    body = {}
                items = body.get("list") or []
                n = len(items)
                if body.get("status") == "000" and items:
                    # 접수번호 앞 8자리가 접수일자라 max가 곧 최신
                    f001_latest[cc] = max(i["rcept_no"] for i in items)
                else:
                    f001_latest[cc] = {
                        "status": body.get("status"),
                        "message": body.get("message"),
                        "count": len(items),
                    }
            print(f"    {target} {cc} {ty}: status={st} 건수={n} → {saved}")

    print(f"\n[4/4] document.xml")
    for target, cc in codes:
        latest = f001_latest.get(cc)
        if not isinstance(latest, str):
            reason = latest if latest is not None else {"note": "F001 응답 없음"}
            log("document.xml", {"crtfc_key": key}, corp_code=cc,
                skipped="F001 최근 1건 없음", extra={"f001_result": reason})
            print(f"    {target} {cc}: 생략 (F001 {reason})")
            continue

        time.sleep(SLEEP_SEC)
        fname = f"document_{cc}_{latest}.zip"
        resp, saved = call("document.xml", {"crtfc_key": key, "rcept_no": latest},
                           corp_code=cc, save_as=fname)
        if resp is None:
            continue

        # zip은 그대로 저장했고, namelist()와 각 파일 크기만 별도로 기록한다.
        # zip 내부 XML은 읽지도 파싱하지도 않는다.
        info_path = f"document_{cc}_{latest}_zipinfo.json"
        try:
            with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
                info = {
                    "rcept_no": latest,
                    "namelist": zf.namelist(),
                    "files": [
                        {"filename": i.filename, "file_size": i.file_size,
                         "compress_size": i.compress_size}
                        for i in zf.infolist()
                    ],
                }
            print(f"    {target} {cc} {latest}: {len(info['namelist'])}개 파일 → {saved}")
        except Exception as e:
            info = {"rcept_no": latest, "error": f"{type(e).__name__}: {e}"}
            print(f"    {target} {cc} {latest}: zip 열기 실패 {type(e).__name__}: {e}")
        (DUMP_DIR / info_path).write_text(
            json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        MANIFEST[-1]["zipinfo_saved_as"] = info_path

    (DUMP_DIR / "_manifest.json").write_text(
        json.dumps(MANIFEST, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n완료: {len(MANIFEST)}건 기록 → dump/_manifest.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
