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

const queryClient = new QueryClient();

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
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
            path="/companies/:companyId/report"
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