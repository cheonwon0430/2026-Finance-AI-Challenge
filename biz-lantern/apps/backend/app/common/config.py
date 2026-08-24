from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    kipris_api_key: str | None = None
    dart_api_key: str
    nts_api_key: str
    # 뉴스 수집(app.domain.news)에서만 쓴다. 키가 없는 환경에서도 앱·테스트가 뜨도록
    # 선택 필드로 두고, 실제 호출 시점에 tavily_api / openai_api 가 확인한다.
    tavily_api_key: str | None = None

    # 뉴스 관련도 선별용 LLM. OpenAI 호환 게이트웨이를 쓰므로 주소와 모델도 설정으로 받는다.
    openai_base_url: str | None = None   # 예: https://mlapi.run/<...>/v1
    openai_api_key: str | None = None
    openai_model: str | None = None      # 예: openai/gpt-5.6-luna

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings() # pyright: ignore[reportCallIssue]