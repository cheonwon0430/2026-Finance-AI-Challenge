"""
회사명으로 DART corp_code 를 찾는다.

corpcode.xml 이 2주 이내면 그걸로 바로 검색하고, 없거나 오래됐으면 새로 받아서 검색한다.

이 모듈은 pipeline.py 가 쓰는 하위 구현이다. 직접 실행하는 진입점을 따로 두지 않는다.
검색만 해보고 싶다면 `python -m app.domain.company.pipeline 핀샷` 을 쓴다.
"""
import re
import time
from pathlib import Path

import xmltodict

from app.domain.company.api.dart_corp_code import fetch_corp_code_xml

CACHE_PATH = Path("data/raw/corpcode.xml")
MAX_AGE_DAYS = 14

# CORPCODE.xml 의 <list> 하나에서 뽑아 쓰는 필드
CORP_FIELDS = ("corp_code", "corp_name", "stock_code", "modify_date")

_AFFIX = re.compile(r"^(주식회사|㈜|\(주\))|(주식회사|㈜|\(주\))$")


def normalize(name: str) -> str:
    """공백 제거 후 주식회사·㈜·(주) 를 앞뒤에서 떼어낸다.

    DART 의 corp_name 은 "트래블월렛" 인데 사용자는 "주식회사 트래블월렛" 으로 검색한다.
    양쪽에 같은 규칙을 적용해야 서로 만난다.
    """
    return _AFFIX.sub("", re.sub(r"\s+", "", name))


def _age_days(path: Path) -> float:
    """파일 수정시각 기준 경과 일수. 시계 오차로 미래 시각이면 0 으로 본다."""
    return max(0.0, (time.time() - path.stat().st_mtime) / 86400)


async def ensure_corpcode_xml() -> Path:
    """CORPCODE.xml 을 쓸 수 있는 상태로 만들고 경로를 반환.

    파일이 있고 2주 이내면 API 를 부르지 않는다.
    """
    if CACHE_PATH.exists() and _age_days(CACHE_PATH) <= MAX_AGE_DAYS:
        return CACHE_PATH

    xml_bytes = await fetch_corp_code_xml()
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_bytes(xml_bytes)

    return CACHE_PATH


def load_corps(xml_bytes: bytes) -> list[dict]:
    """CORPCODE.xml bytes -> 회사 dict 리스트.

    구조는 <result><list>...</list><list>...</list></result> 이다.
    """
    items = xmltodict.parse(xml_bytes).get("result", {}).get("list", [])

    # xmltodict 특성상 항목이 1건이면 dict, 여러 건이면 list 로 오므로 리스트로 통일
    if isinstance(items, dict):
        items = [items]

    # 빈 태그(<stock_code> </stock_code>)는 None 으로 오므로 빈 문자열로 맞춘다
    return [{field: (item.get(field) or "").strip() for field in CORP_FIELDS} for item in items]


def search(corps: list[dict], keyword: str) -> list[dict]:
    """정규화한 회사명 부분 일치 검색."""
    target = normalize(keyword)

    return [corp for corp in corps if target in normalize(corp["corp_name"])]


async def search_by_name(keyword: str) -> list[dict]:
    """회사명으로 검색. 캐시 확인 -> 파싱 -> 부분 일치."""
    xml_path = await ensure_corpcode_xml()

    return search(load_corps(xml_path.read_bytes()), keyword)
