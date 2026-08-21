import asyncio
import io
import json
import zipfile
from xml.parsers.expat import ExpatError

import httpx
import xmltodict

from app.common.config import settings

URL = "https://opendart.fss.or.kr/api/corpCode.xml"


async def fetch_corp_code_xml() -> bytes:
    """고유번호 전체 파일(corpCode.xml) 조회. 응답 ZIP 을 풀어 CORPCODE.xml bytes 를 반환.

    변환은 하지 않는다. 캐시로 저장하든 파싱하든 호출하는 쪽의 몫이다.
    """
    params = {"crtfc_key": settings.dart_api_key}

    async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
        response = await client.get(URL, params=params)
        response.raise_for_status()

    try:
        archive = zipfile.ZipFile(io.BytesIO(response.content))
    except zipfile.BadZipFile:
        # 인증키 오류 등이면 ZIP 대신 <result><status>013</status>...</result> 가 온다.
        # 그대로 두면 BadZipFile 만 올라와 원인을 알 수 없다.
        raise RuntimeError(f"corpCode 응답이 ZIP 이 아님 ({_error_detail(response.content)})") from None

    with archive:
        return archive.read(archive.namelist()[0])


def _error_detail(raw: bytes) -> str:
    """ZIP 이 아닌 응답에서 DART 의 status·message 를 뽑아낸다. 실패하면 앞부분을 그대로."""
    try:
        result = xmltodict.parse(raw).get("result", {})
        return f"DART status={result.get('status')}, message={result.get('message')}"
    except (ExpatError, UnicodeDecodeError):
        return raw[:200].decode("utf-8", "replace")


async def get_corp_code_list() -> str:
    """고유번호 전체 파일을 xmltodict 로 변환해 JSON 문자열로 반환."""
    xml_bytes = await fetch_corp_code_xml()

    return json.dumps(xmltodict.parse(xml_bytes), ensure_ascii=False, indent=2)


if __name__ == "__main__":
    # 출력이 25MB 안팎이라 파일로 리다이렉트할 것. data/ 는 gitignore 대상이다
    # python -m app.domain.company.api.dart_corp_code > data/raw/corpcode.json
    print(asyncio.run(get_corp_code_list()))
