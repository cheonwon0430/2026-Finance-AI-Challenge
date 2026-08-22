import axios from 'axios';

// 백엔드에 요청을 보내는 인스턴스
export const httpClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1',
  withCredentials: true, // Sesstion Cookie 인증에 사용
});