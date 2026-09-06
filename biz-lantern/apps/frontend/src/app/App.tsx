import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import {
  BrowserRouter,
  Navigate,
  Route,
  Routes,
} from 'react-router';

import {
  CompanyDetailPage,
  CompanySearchPage,
  HealthPage,
  ReportPage,
} from '@/pages';
// ✅ 챗봇 컴포넌트 임포트 (경로는 프로젝트 환경에 맞게 수정하세요)
import { ChatbotWidget } from '@/features/chatbot'; 

const queryClient = new QueryClient();

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        
        {/* ✅ 라우트(화면)와 상관없이 항상 렌더링되는 영역 */}
        <ChatbotWidget />

        <Routes>
          <Route
            path="/"
            element={<Navigate to="/companies" replace />}
          />

          <Route
            path="/health"
            element={<HealthPage />}
          />

          <Route
            path="/companies"
            element={<CompanySearchPage />}
          />

          <Route
            path="/companies/:companyId"
            element={<CompanyDetailPage />}
          />

          <Route
            path="/reports/:reportId"
            element={<ReportPage />}
          />

          <Route
            path="*"
            element={<Navigate to="/companies" replace />}
          />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}