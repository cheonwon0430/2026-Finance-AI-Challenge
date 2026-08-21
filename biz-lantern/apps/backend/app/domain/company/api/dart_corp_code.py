import io
import json
import zipfile

import httpx
import xmltodict

from app.common.config import settings

URL = "https://opendart.fss.or.kr/api/corpCode.xml"


def get_corp_code_list() -> str:
    """고유번호 전체 파일(corpCode.xml) 조회.

    응답이 CORPCODE.xml 을 담은 ZIP 이라 압축을 풀고 xmltodict 로 변환해 JSON 문자열로 반환.
    """
    params = {"crtfc_key": settings.dart_api_key}

    response = httpx.get(URL, params=params, timeout=120, follow_redirects=True)
    response.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        xml_bytes = archive.read(archive.namelist()[0])

    return json.dumps(xmltodict.parse(xml_bytes), ensure_ascii=False, indent=2)


if __name__ == "__main__":
    # 출력이 25MB 안팎이라 파일로 리다이렉트할 것. data/ 는 gitignore 대상이다
    # python -m app.domain.company.api.dart_corp_code > data/raw/corpcode.json
    print(get_corp_code_list())
