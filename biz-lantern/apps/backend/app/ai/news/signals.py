"""
후보 기사 하나에서 뽑아내는 판단 재료. 네트워크를 타지 않는 순수 함수만 둔다.

원래 __main__.py 안에 CLI 표시용으로 있던 것을 여기로 옮겼다. rerank 가 LLM 입력으로도
같은 값을 써야 하는데, 화면에 찍히는 값과 LLM 이 보는 값이 다르면 결과를 해석할 수 없다.
"""
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
