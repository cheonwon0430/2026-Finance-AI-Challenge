"""
공시서류원본파일(document.xml) 조회.

계층 순서대로 위에서 아래로 읽으면 된다.

    [1] 설정
    [2] API 호출      HTTP 만 한다. 응답 원본 bytes 를 가공 없이 그대로 반환.
    [3] 이스케이프    DART 원문이 어긴 XML 규격을 파싱 가능하게 고친다.
    [4] 파싱          bytes -> XML 텍스트 -> JSON 문자열.
    [5] CLI

사용법:
    python -m app.domain.company.api.dart_document 20260414002654 > data/raw/document.json
"""
import io
import json
import re
import zipfile

import httpx
import xmltodict

from app.common.config import settings

# ---------------------------------------------------------------------------
# [1] 설정
# ---------------------------------------------------------------------------
URL = "https://opendart.fss.or.kr/api/document.xml"


# ---------------------------------------------------------------------------
# [2] API 호출 - 응답 원본 bytes 를 그대로 돌려주기만 한다
# ---------------------------------------------------------------------------
def fetch_document_raw(rcept_no: str) -> bytes:
    """document.xml API GET 1회. 응답 본문(ZIP) 바이트를 손대지 않고 그대로 반환.

    파싱도, 압축 해제도 여기서는 하지 않는다.
    """
    params = {
        "crtfc_key": settings.dart_api_key,
        "rcept_no": rcept_no,
    }

    response = httpx.get(URL, params=params, timeout=60, follow_redirects=True)
    response.raise_for_status()
    return response.content


# ---------------------------------------------------------------------------
# [3] 이스케이프 - DART 원문의 XML 규격 위반을 고친다
# ---------------------------------------------------------------------------
# DART 원문에는 <당기말> 같은 한글 텍스트가 이스케이프 없이 들어있어 XML 규격을 어긴다.
# 이대로 두면 파서가 <당기말> 을 여는 태그로 읽고 mismatched tag 로 죽는다.
#
# 얼마나 흔한가 (2026-08-20 실측, 감사보고서 F001 2026-04~06 공시 앞 25건):
#   escape 없이 ET.fromstring 실패      7건 / 25건 (28%)
#   escape 적용 후 전부 성공            7건 / 7건
#   bare '<' 보유 6건, bare '&' 보유 1건
# 드문 예외가 아니라 네 건 중 한 건꼴이다. 이 함수는 없어도 되는 방어가 아니다.
#
# lxml 의 recover=True 로도 넘어갈 수는 있지만 그쪽은 깨진 부분을 조용히 삭제한다.
# (실측: 실패한 7건에서 escape 방식이 lxml recover 보다 본문 156자를 더 보존했다)
# 실체 참조로 바꾸면 본문 텍스트로 온전히 보존되므로 이 방식을 쓴다.
#
# OpenDartReader·dart-fss 어느 쪽도 이 처리를 하지 않는다. 자세한 근거는
# document_clean.py 상단 '왜 라이브러리를 쓰지 않는가' 참조.
_LT = re.compile(r"<(?![A-Za-z/!?])")  # 실제 태그·닫는태그·주석·선언이 아닌 '<'
_AMP = re.compile(r"&(?!#?\w{1,10};)")  # 실체 참조가 아닌 '&'


def escape_bare_tags(text: str) -> str:
    """태그·실체참조로 오해되는 문자를 &lt; &gt; &amp; 로 바꿔 파싱 가능한 XML 로 만든다.

    <당기말> 뿐 아니라 <1분기>, 100 < 200, 이스케이프 안 된 & 도 함께 처리한다.
    정상 실체 참조(&amp; &#65;)와 주석(<!-- -->)은 건드리지 않는다.
    """
    return _LT.sub("&lt;", _AMP.sub("&amp;", text))


# ---------------------------------------------------------------------------
# [4] 파싱 - 받아둔 bytes 를 XML 텍스트 / JSON 으로 바꾸기만 한다
# ---------------------------------------------------------------------------
def extract_xml(raw: bytes) -> dict[str, str]:
    """응답 ZIP 원본 bytes -> {파일명: XML 텍스트}.

    이스케이프 전 원본 그대로 돌려준다. 고치는 일은 호출하는 쪽의 몫이다.
    """
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        return {name: archive.read(name).decode("utf-8") for name in archive.namelist()}


def get_document(rcept_no: str) -> str:
    """공시원문(document.xml) 조회.

    응답이 XML 을 담은 ZIP 이라 압축을 풀고 xmltodict 로 변환해 JSON 문자열로 반환.
    ZIP 안에 파일이 여러 개면 {파일명: 변환결과} 형태로 담는다.
    """
    documents = {
        name: xmltodict.parse(escape_bare_tags(text))
        for name, text in extract_xml(fetch_document_raw(rcept_no)).items()
    }

    if len(documents) == 1:
        documents = next(iter(documents.values()))

    return json.dumps(documents, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# [5] CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    # python -m app.domain.company.api.dart_document 20260414002654
    print(get_document(sys.argv[1]))
