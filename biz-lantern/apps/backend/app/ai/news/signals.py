"""
후보 기사 하나에서 뽑아내는 판단 재료. 네트워크를 타지 않는 순수 함수만 둔다.

원래 __main__.py 안에 CLI 표시용으로 있던 것을 여기로 옮겼다. rerank 가 LLM 입력으로도
같은 값을 써야 하는데, 화면에 찍히는 값과 LLM 이 보는 값이 다르면 결과를 해석할 수 없다.
"""
from datetime import datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

# 사업화 Query 가 제 일을 했는지 보는 표지. 이 단어가 하나도 안 잡히면 Query 를 고쳐야 한다
BUSINESS_SIGNALS = ("공급", "수주", "계약", "도입", "납품", "고객", "판매", "협약", "체결", "구축")


def _normalize(text: str) -> str:
    return "".join(text.split()).lower()


def _haystack(item: dict) -> str:
    return f"{item.get('title') or ''} {item.get('content') or ''}"


def mentions_company(item: dict, company: str, aliases: tuple[str, ...] = ()) -> bool:
    """제목이나 스니펫에 회사명이 실제로 등장하는가. 띄어쓰기 차이는 무시한다.

    aliases 를 주면 그중 하나만 걸려도 참으로 본다. 지금은 별칭 데이터가 없어 비워 두지만,
    나중에 DART 기업정보(영문명 등)가 붙으면 그대로 연결하면 된다.
    """
    haystack = _normalize(_haystack(item))

    return any(_normalize(name) in haystack for name in (company, *aliases) if name.strip())


def business_signals(item: dict) -> list[str]:
    """제목·스니펫에 등장한 사업화 신호어."""
    haystack = _haystack(item)

    return [signal for signal in BUSINESS_SIGNALS if signal in haystack]


def source_of(url: str) -> str:
    """URL 에서 출처 도메인을 뽑는다.

    Tavily 검색 응답에는 source 필드가 없다(url·title·content·score·published_date 뿐).
    LLM 에게 어느 매체인지는 알려 줘야 판단이 되므로 호스트를 대신 쓴다.
    """
    host = urlparse((url or "").strip()).netloc.lower()

    return host.removeprefix("www.")


def published_on(raw: str | None) -> str | None:
    """발행일을 'YYYY-MM-DD' 로. 없으면 None, 못 읽으면 원본 그대로.

    Tavily 는 RFC 2822("Sat, 08 Aug 2026 13:00:00 GMT")로 주는데 형식이 한 가지가 아니다.
    시각을 빼고 오기도 하고, 어떤 매체는 ISO 로 온다. 앞에서 10자를 자르면 그중 RFC 2822 는
    "Sat, 08 Au" 가 된다 - 그래서 잘라 쓰지 않고 읽어서 다시 쓴다.

    적힌 시간대를 UTC 로 환산하지 않는다. 매체가 '8월 8일 기사'로 냈으면 8월 8일이다.

    못 읽는 값은 버리지 않고 그대로 돌려준다. 이상한 값이 왔다는 사실이 화면에 보여야 한다.
    """
    text = (raw or "").strip()
    if not text:
        return None

    # 실제 응답의 대부분이 이 형식이라 먼저 시도한다
    try:
        return parsedate_to_datetime(text).date().isoformat()
    except (TypeError, ValueError):
        pass

    # 시각이 없는 RFC 2822("Thu, 13 Nov 2026"). 같은 파서를 쓰려고 시각을 채워 준다 -
    # strptime("%a, %d %b %Y") 은 요일·월 이름이 LC_TIME 에 걸려 환경마다 달라진다
    try:
        return parsedate_to_datetime(f"{text} 00:00:00 +0000").date().isoformat()
    except (TypeError, ValueError):
        pass

    # ISO 8601. fromisoformat 은 날짜만 있어도 받는다
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return text
