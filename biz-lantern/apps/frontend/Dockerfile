# biz-lantern 프론트엔드. Vite 로 빌드해 nginx 가 정적 파일로 서빙한다.
#
# 빌드 컨텍스트는 이 디렉터리가 아니라 biz-lantern/ 루트다 - pnpm 워크스페이스라
# pnpm-lock.yaml 과 pnpm-workspace.yaml 이 루트에 있다.

FROM node:22-alpine AS build

RUN corepack enable

WORKDIR /repo

# 매니페스트만 먼저 넣어 의존성 레이어를 캐시한다
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/frontend/package.json apps/frontend/
RUN pnpm install --frozen-lockfile

COPY apps/frontend apps/frontend

# Vite 는 빌드 시점에 VITE_ 값을 코드에 인라인한다. 기본을 상대경로로 두는 것이 핵심이다 -
# 서버 IP 를 박으면 IP 가 바뀔 때마다 이미지를 다시 만들어야 한다.
ARG VITE_API_BASE_URL=/api/v1
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

RUN pnpm --filter frontend build


FROM nginx:alpine

COPY apps/frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /repo/apps/frontend/dist /usr/share/nginx/html

EXPOSE 80
