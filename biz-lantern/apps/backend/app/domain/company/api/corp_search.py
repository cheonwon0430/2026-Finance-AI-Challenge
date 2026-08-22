"""
회사명으로 DART corp_code 를 찾는다.

corpcode.xml 이 2주 이내면 그걸로 바로 검색하고, 없거나 오래됐으면 새로 받아서 검색한다.

사용법:
    python -m app.domain.company.api.corp_search 핀샷
"""
import asyncio
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


    Args:
        name: 정규화할 회사명 (DART corp_name 또는 사용자 검색어).

    Returns:
        공백과 앞뒤 법인 접두/접미어를 제거한 문자열.

    """
    return _AFFIX.sub("", re.sub(r"\s+", "", name))


def _age_days(path: Path) -> float:
    """파일 수정시각 기준 경과 일수. 시계 오차로 미래 시각이면 0 으로 본다.

    Args:
        path: 경과 일수를 잴 파일 경로.

    Returns:
        현재 시각과 파일 mtime 의 차이(일 단위). 음수는 나오지 않는다.
    """
    return max(0.0, (time.time() - path.stat().st_mtime) / 86400)


async def ensure_corpcode_xml() -> Path:
    """CORPCODE.xml 을 쓸 수 있는 상태로 만들고 경로를 반환.

    파일이 있고 2주 이내면 API 를 부르지 않는다.

    Returns:
        최신 상태로 확인/갱신된 CORPCODE.xml 의 로컬 경로(CACHE_PATH).
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

    Args:
        xml_bytes: CORPCODE.xml 파일의 바이트 내용.

    Returns:
        CORP_FIELDS(corp_code, corp_name, stock_code, modify_date) 키를 가진
        dict 의 리스트. 값이 비어있던 태그는 빈 문자열("")로 채워진다.
    """
    items = xmltodict.parse(xml_bytes).get("result", {}).get("list", [])

    # xmltodict 특성상 항목이 1건이면 dict, 여러 건이면 list 로 오므로 리스트로 통일
    if isinstance(items, dict):
        items = [items]

    # 빈 태그(<stock_code> </stock_code>)는 None 으로 오므로 빈 문자열로 맞춘다
    return [{field: (item.get(field) or "").strip() for field in CORP_FIELDS} for item in items]


def search(corps: list[dict], keyword: str) -> list[dict]:
    """정규화한 회사명 부분 일치 검색.

    Args:
        corps: load_corps() 가 반환한 회사 dict 리스트.
        keyword: 검색어(회사명 전체 또는 일부).

    Returns:
        정규화된 keyword 를 정규화된 corp_name 이 포함하는 회사만 남긴 리스트.
    """
    target = normalize(keyword)

    return [corp for corp in corps if target in normalize(corp["corp_name"])]


async def search_by_name(keyword: str) -> list[dict]:
    """회사명으로 검색. 캐시 확인 -> 파싱 -> 부분 일치.

    Args:
        keyword: 검색할 회사명(전체 또는 일부).

    Returns:
        keyword 와 부분 일치하는 회사 dict 리스트 (search() 참고).
    """
    xml_path = await ensure_corpcode_xml()

    # return search(load_corps(xml_path.read_bytes()), keyword)
    # [{'corp_code': '01345812', 'corp_name': '삼성전자서비스씨에스', 'stock_code': '', 'modify_date': '20230125'}]
    # corp_name == keyword 
    # TODO : 기업 조회시 여러개 말고 한개가 나오게 해야함.
    return search(load_corps(xml_path.read_bytes()), keyword)


if __name__ == "__main__":
    import sys

    # python -m app.domain.company.api.corp_search 핀샷
    matches = asyncio.run(search_by_name(sys.argv[1]))
    print(f"'{sys.argv[1]}' 검색 결과: {len(matches)}건")

    for corp in matches[:20]:
        listed = f"상장({corp['stock_code']})" if corp["stock_code"] else "비상장"
        print(f"  {corp['corp_code']}  {corp['corp_name']:<20} {listed}  수정일:{corp['modify_date']}")

    if len(matches) > 20:
        print(f"  ... 외 {len(matches) - 20}건")

# 사소한 지적 - 전민우 : archive.namelist()[0]으로 zip 안의 첫 번째 파일을 그냥 가져오는데, 
# DART corpCode.xml zip은 항상 CORPCODE.xml 파일 하나만 들어있는 구조라 실제로 문제는 없습니다. 
# 다만 아주 엄격하게 하려면 .xml로 끝나는 파일명을 찾아서 읽는 게 더 안전하긴 합니다 (지금은 필요 없는 수준의 엄격함).
