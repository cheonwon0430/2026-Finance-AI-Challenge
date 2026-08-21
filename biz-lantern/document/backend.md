uv add fastapi "uvicorn[standard]" "sqlalchemy[asyncio]" asyncpg pgvector pydantic-settings argon2-cffi httpx langchain langchain-community langgraph pytest pytest-asyncio ruff

FastAPI CLI 사용가능 라이브러리 => uvicorn[standard]

기존 .venv를 uv가 관리하도록 확인
`uv sync`

"Embedding / Vector Store 연동은 실제로 사용할 Embedding 모델과 LangChain integration을 확정한 뒤 설치하는 것을 권합니다.

예를 들어 BGE 계열을 로컬에서 직접 사용할지, API를 사용할지에 따라 패키지가 달라집니다."


uv run fastapi dev or uv run uvicorn app.main:app --reload 
uv run fastapi 이건 무슨 명령어?

DDD 구조
"Domain 중심 디렉터리 + AI 영역 + Infrastructure 영역을 분리한다."

app/domain/company/model.py
다만 실제 프로젝트에서는 Base를 별도의 Infrastructure 계층으로 빼는 것이 더 좋습니다. 지금은 SQLAlchemy 연결 테스트를 위한 최소 예제이므로 단순화했습니다.


Pydantic Schema
app/company/schema.py
Entity ≠ DTO

docker compose up -d
docker compose ps
winpty docker exec -it biz-lantern-postgres psql -U postgres -d biz_lantern
SELECT version();
SELECT extname FROM pg_extension; -- vector
CREATE EXTENSION IF NOT EXISTS vector;


miniconda 삭제

uv venv --python 3.13.0
uv sync

uv run python --version
uv run python -c "import sys; print(sys.executable)"
uv run python -c "import sys; print(sys.prefix)"

uv run python -c "from app.ai.graph import build_analysis_graph; print(build_analysis_graph())"
uv run pytest tests/test_database.py



환경
 ↓
의존성
 ↓
프로젝트 설정
 ↓
DDD 구조
 ↓
PostgreSQL
 ↓
SQLAlchemy
 ↓
pgvector
 ↓
ORM Domain Model
 ↓
AI/LangGraph 기본 연결
 ↓
[Embedding 방식 결정]
 ↓
Session 인증

---
# Session 인증

Browser
   │
   │ POST /auth/login
   ▼
FastAPI
   │
   ├─ email로 User 조회
   ├─ Argon2로 password 검증
   │
   ├─ Session 생성
   │
   ▼
PostgreSQL
   │
   └─ sessions
         ├─ session_id
         ├─ user_id
         ├─ expires_at
         └─ ...

## 흐름
FastAPI
   │
   │ Set-Cookie
   ▼
Browser
   │
   └─ HttpOnly Cookie
	 
	 
	 Browser
   │
   │ Cookie: session_id=...
   ▼
FastAPI
   │
   ├─ Session 조회
   ├─ 만료 여부 확인
   ├─ User 조회
   │
   ▼
Endpoint

## user
users
├── id
├── email
├── password_hash
├── is_active
├── created_at
└── updated_at

나중에 argon2-cffi로:

사용자 입력 password
        ↓
      Argon2
        ↓
password_hash
        ↓
DB

형태로 저장합니다.

## session
sessions
├── id
├── user_id
├── token_hash
├── expires_at
├── created_at
└── last_used_at

### User ↔ Session 관계

현재는 ORM에서 관계 객체를 굳이 추가하지 않겠습니다.

즉:

user.sessions
session.user

같은 SQLAlchemy relationship()은 아직 만들지 않습니다.

DB 수준에서는 이미:

sessions.user_id
        │
        ▼
users.id

라는 FK가 있습니다.

초기 인증 구현에서는 이것만으로 충분합니다.

나중에 실제 사용 패턴에서 ORM relationship이 필요하면 추가하면 됩니다.

이렇게 하는 이유는 처음부터 SQLAlchemy ORM 기능을 과도하게 사용하지 않고 인증 로직을 단순하게 유지하기 위해서입니다.


### app/infrastructure/database/models.py
가장 중요한 부분: Base.metadata 등록

여기서 현재 구조에서 문제가 하나 발생합니다.

다음 코드만 실행하면:

from app.infrastructure.database.base import Base


Base.metadata.create_all(...)

Base는 존재하지만 User, Session, Company가 metadata에 반드시 등록되어 있다는 보장이 없습니다.

SQLAlchemy ORM 모델은 Python에서 해당 모델 클래스가 import되어야 metadata에 등록됩니다.

따라서 중앙에서 모델을 import하는 파일을 하나 만들겠습니다.



### create_all()에서 모델 registry를 import
현재 models.py가 존재하지만, models.py를 import하지 않으면 SQLAlchemy가 Company, User, Session 클래스를 Base.metadata에 등록하지 않을 수 있습니다.

따라서 DB 테이블을 생성하는 코드를 별도로 만들어야 합니다.

저라면 지금 구조에서는 init.py를 사용하겠습니다.

app/infrastructure/database/
├── __init__.py
├── base.py
├── init.py        ← 추가
├── models.py
└── session.py

### 테이블 생성

uv run python -c "from app.infrastructure.database.base import Base; import app.infrastructure.database.models; print(sorted(Base.metadata.tables.keys()))"
['companies', 'sessions', 'users'] # 결과


uv run python -c "import asyncio; from app.infrastructure.database.init import init_database; asyncio.run(init_database())"
/// 테이블 생성 과정 및 쿼리 출력 됨 ///

winpty docker exec -it biz-lantern-postgres psql -U postgres -d biz_lantern -c "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename;"
생성한 테이블 확인




### Argon2 동작 테스트

아직 회원가입 API를 만들지 않았으므로 Python에서 직접 테스트합니다.

다음 명령을 실행하세요.

uv run python -c "from app.infrastructure.security.password import hash_password, verify_password; h=hash_password('test-password'); print(h); print(verify_password('test-password', h)); print(verify_password('wrong-password', h))"

정상적인 결과는 대략:

$argon2id$...
True
False


## 폴더 구조
app/
│
├── domain/
│   ├── company/
│   │   └── model.py
│   │
│   ├── user/
│   │   └── model.py
│   │
│   └── session/
│       └── model.py
│
└── infrastructure/
    │
    ├── database/
    │   ├── base.py
    │   ├── init.py
    │   ├── models.py
    │   └── session.py
    │
    └── security/
        └── password.py
				
				
				
### app/infrastructure/security/session_token.py

왜 secrets를 사용하는가?

Session Token은 일반적인 ID 생성과 목적이 다릅니다.

예를 들어:

uuid.uuid4()

도 충분히 랜덤해 보이지만, 인증 Token이라는 용도에서는 Python 표준 라이브러리의 secrets가 더 명확합니다.

secrets.token_urlsafe(32)

은 암호학적으로 안전한 난수 생성기를 사용합니다.

따라서:

User ID
    ↓
DB 식별자


Session Token
    ↓
인증 자격 증명

을 서로 다른 목적으로 취급합니다.

### cookie

httponly=True,  # JavaScript 코드로 Cookie를 읽을 수 없음. XSS에 의해 Session Token이 직접 탈취되는 위험을 줄이는 목적
secure=False,   # local: False / prod: True
samesite="lax"  # Cross-Site 요청에서 Cookie가 제한적으로 전송됩니다. CSRF 방어에도 도움이 되지만, CSRF 방어를 완전히 구현한 것은 아닙니다. 나중에 인증 API를 구성하면서 CSRF 정책을 별도로 결정




#### 여기에서 DB 조회까지 하지 않습니다.

이렇게 책임을 분리합니다.

cookie.py


Cookie 읽기/쓰기
        ↓
인증 서비스


Session 검증
        ↓
Repository


DB 조회
8. Session 검증은 다음 계층에서 담당

현재 Session 모델에는:

id
user_id
token_hash
expires_at
created_at
last_used_at

가 있으므로 최종 인증은 다음과 같이 이루어집니다.

Request
   │
   ▼
Cookie에서 raw token
   │
   ▼
SHA-256
   │
   ▼
token_hash
   │
   ▼
sessions 조회
   │
   ├── 없음 → 401
   │
   ├── expires_at < 현재시간 → 401
   │
   └── 정상
          │
          ▼
       user_id
          │
          ▼
        User

이 부분은 아직 구현하지 않습니다.


### 폴더 구조
app/
│
├── domain/
│   ├── company/
│   │   └── model.py
│   │
│   ├── user/
│   │   └── model.py
│   │
│   └── session/
│       └── model.py
│
└── infrastructure/
    │
    ├── database/
    │   ├── base.py
    │   ├── init.py
    │   ├── models.py
    │   └── session.py
    │
    └── security/
        ├── __init__.py
        ├── password.py
        ├── session_token.py
        └── cookie.py
				
				
### 인증의 보안 요소가 다음처럼 분리됩니다.
password.py
    │
    └── Argon2
          │
          ▼
    password_hash


session_token.py
    │
    ├── secrets
    │
    └── SHA-256
          │
          ▼
      token_hash


cookie.py
    │
    ├── HttpOnly
    ├── Secure
    ├── SameSite
    └── Max-Age