"""
URL 검증과 중복 판정. 네트워크를 타지 않는 순수 함수만 둔다.

**두 함수의 역할을 섞지 않는다.**

    is_extractable_url   원문을 뽑아 볼 만한 주소인가        -> 후보에서 뺄지 말지
    canonical_key        둘이 같은 리소스를 가리키는가       -> 중복 판정에만 쓴다

canonical_key 는 무엇을 막는 함수가 아니다. 키가 같다고 Extract 를 건너뛰거나 하지 않고,
결과에 싣는 URL 은 언제나 Tavily 가 준 원본 문자열 그대로다.

app/domain/news 의 같은 로직을 옮겨 왔다. import 로 끌어 쓰지 않은 것은 app/ai 가
실험 단계인 app/domain/news 에 묶이지 않게 하려는 것이다.
"""
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

# 본문 텍스트를 뽑을 수 없는 형식. 이미지·동영상·오디오·압축파일이다.
#
# .pdf 는 일부러 넣지 않았다. Tavily Extract 가 PDF 에서 텍스트를 뽑아 주고, 이 서비스가
# 찾는 것은 뉴스 기사가 아니라 기업의 제품·서비스·사업 정보다 - IR 자료·제품 브로슈어·
# 공시 문서가 PDF 로 오는 일이 많아 버릴 이유가 없다.
BINARY_SUFFIXES = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".zip", ".mp4", ".mp3")

# 같은 기사인데 URL 만 다르게 만드는 추적 파라미터
TRACKING_PARAMS = ("fbclid", "gclid", "igshid", "ref", "refer", "source")
TRACKING_PREFIXES = ("utm_",)


def is_extractable_url(url: str) -> bool:
    """원문을 뽑아 볼 만한 URL 인지. http/https 에 호스트가 있어야 한다.

    상대경로, javascript:, mailto:, 빈 문자열, 그리고 본문 텍스트를 뽑을 수 없는
    이미지·동영상·압축파일을 걸러낸다.

    **http 도 정상적인 Extract 대상이다.** scheme 이 http 라는 이유로 막지 않는다 -
    http 와 https 를 같은 리소스로 보는 건 canonical_key 의 몫이고, 여기서는 둘 다 통과다.
    """
    if not url or not url.strip():
        return False

    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return False

    return not parsed.path.lower().endswith(BINARY_SUFFIXES)


def _is_tracking(key: str) -> bool:
    lowered = key.lower()

    return lowered in TRACKING_PARAMS or lowered.startswith(TRACKING_PREFIXES)


def canonical_key(url: str) -> str:
    """중복 판정용 키를 만든다. 원본 URL 문자열은 건드리지 않는다.

    같은 기사가 http/https, www 유무, 추적 파라미터, #앵커, 끝 슬래시만 다르게 여러 번
    잡힌다. 결과에 싣는 건 어디까지나 원본 URL 이고 이 키는 비교에만 쓴다.
    """
    parsed = urlparse(url.strip())

    host = parsed.netloc.lower().removeprefix("www.")

    path = parsed.path.rstrip("/")

    # 파라미터 순서가 달라도 같은 기사이므로 정렬해서 비교한다
    query = urlencode(
        sorted(
            (key, value)
            for key, value in parse_qsl(parsed.query, keep_blank_values=True)
            if not _is_tracking(key)
        )
    )

    # scheme 은 키에 넣지 않는다. http 와 https 는 같은 리소스를 가리키는 표기 차이일 뿐이라
    # 남겨 두면 Tavily 가 두 벌로 준 같은 기사가 중복 제거를 빠져나간다(실측: smedaily.co.kr).
    # is_extractable_url 이 이미 http/https 외에는 걸러내므로 뺀다고 다른 것이 섞이지 않는다.
    return urlunparse(("", host, path, "", query, ""))
