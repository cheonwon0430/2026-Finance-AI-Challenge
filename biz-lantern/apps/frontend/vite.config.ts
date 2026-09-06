import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "node:path";

// https://vite.dev/config/
export default defineConfig({
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  plugins: [react(), tailwindcss()],

  // API 주소를 절대경로로 박지 않고 /api 로 두기 위한 개발용 프록시.
  // 배포에서는 nginx 가 같은 일을 한다(apps/frontend/nginx.conf). 덕분에 서버 IP 가
  // 바뀌어도 프론트를 다시 빌드할 필요가 없고, 같은 출처가 되어 CORS 도 안 탄다.
  server: {
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
