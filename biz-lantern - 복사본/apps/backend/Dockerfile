# biz-lantern 백엔드. python:3.13-slim + uv.
#
# 프로젝트 자체는 설치하지 않는다(--no-install-project). pyproject 에 build-system 이 없어
# 패키지로 빌드할 수 없고, 그럴 필요도 없다 - WORKDIR /app 에 app/ 을 두면 `app.main` 이
# 그대로 임포트된다. 그래서 실행도 `uv run` 이 아니라 venv 의 uvicorn 을 직접 부른다.
FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /uvx /bin/

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

# 의존성을 앱 코드보다 먼저 넣는다. 코드만 고쳤을 때 이 레이어가 캐시돼 재배포가 빨라진다.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY app ./app

# data/ 는 볼륨으로 마운트되지만, 마운트 전에도 경로가 있어야 한다.
# corp_search·pipeline·store 가 전부 CWD 기준 상대경로(data/...)를 쓰므로 WORKDIR 이 곧
# 기준점이다. 여기를 바꾸면 보고서 저장 위치가 통째로 어긋난다.
RUN mkdir -p /app/data/raw /app/data/clean /app/data/reports

EXPOSE 8000

# 워커는 1개다. report/service.py 가 asyncio.create_task 로 보고서를 만드는데, LLM 호출이
# 무거워 워커를 늘리면 동시 생성이 겹쳐 메모리와 요금이 튄다.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
