import { Link, useParams } from 'react-router';

import {
  getCompanyById,
} from '@/features/company';

export function ReportPage() {
  const { companyId } = useParams();

  const company = getCompanyById(Number(companyId));

  if (!company) {
    return (
      <main className="p-8">
        기업을 찾을 수 없습니다.
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-6xl p-8">
      <Link
        to={`/companies/${company.id}`}
        className="text-sm text-muted-foreground"
      >
        ← 기업 상세
      </Link>

      <header className="mt-6">
        <p className="text-sm text-muted-foreground">
          기업분석 보고서
        </p>

        <h1 className="mt-2 text-3xl font-bold">
          {company.name}
        </h1>

        <p className="mt-2 text-muted-foreground">
          분석 기준일: 2026-08-21
        </p>
      </header>

      <section className="mt-10">
        <h2 className="text-xl font-semibold">
          Executive Summary
        </h2>

        <div className="mt-4 rounded-lg border p-6">
          <p>{company.summary.overview}</p>
        </div>
      </section>

      <section className="mt-8">
        <h2 className="text-xl font-semibold">
          재무 분석
        </h2>

        <div className="mt-4 rounded-lg border p-6">
          <p>{company.summary.financial}</p>
        </div>
      </section>

      <section className="mt-8">
        <h2 className="text-xl font-semibold">
          투자 분석
        </h2>

        <div className="mt-4 rounded-lg border p-6">
          <p>{company.summary.investment}</p>
        </div>
      </section>

      <section className="mt-8">
        <h2 className="text-xl font-semibold">
          특허 분석
        </h2>

        <div className="mt-4 rounded-lg border p-6">
          <p>{company.summary.patent}</p>
        </div>
      </section>
    </main>
  );
}