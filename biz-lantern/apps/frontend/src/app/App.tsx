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

export default function App() {
  return (
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
  );
}