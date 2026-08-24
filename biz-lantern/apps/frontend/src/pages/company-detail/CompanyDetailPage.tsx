import { Link, useParams } from 'react-router';

import {
  CompanySummary,
  getCompanyById,
} from '@/features/company';

export function CompanyDetailPage() {
  const { companyId } = useParams();

  const company = getCompanyById(Number(companyId));

  if (!company) {
    return (
      <main className="mx-auto max-w-5xl p-8">
        <h1 className="text-xl font-semibold">
          기업을 찾을 수 없습니다.
        </h1>

        <Link
          to="/companies"
          className="mt-4 inline-block text-primary"
        >
          기업 검색으로 돌아가기
        </Link>
      </main>
    );
  }

  const latestFinancial =
    company.financials[company.financials.length - 1];

  const totalInvestment = company.investments.reduce(
    (total, investment) => total + investment.amount,
    0,
  );

  const registeredPatentCount = company.patents.filter(
    (patent) => patent.status === '등록',
  ).length;

  return (
    <main className="mx-auto max-w-6xl p-8">
      <div className="mb-8">
        <Link
          to="/companies"
          className="text-sm text-muted-foreground"
        >
          ← 기업 검색
        </Link>

        <div className="mt-6">
          <p className="text-sm text-muted-foreground">
            {company.industry} · {company.category}
          </p>

          <h1 className="mt-2 text-3xl font-bold">
            {company.name}
          </h1>

          <p className="mt-2 text-muted-foreground">
            {company.description}
          </p>
        </div>
      </div>

      {/* KPI */}
      <section className="grid gap-4 md:grid-cols-4">
        <div className="rounded-lg border p-5">
          <p className="text-sm text-muted-foreground">
            최근 매출
          </p>

          <p className="mt-2 text-xl font-semibold">
            {latestFinancial.revenue.toLocaleString()}원
          </p>
        </div>

        <div className="rounded-lg border p-5">
          <p className="text-sm text-muted-foreground">
            영업이익
          </p>

          <p className="mt-2 text-xl font-semibold">
            {latestFinancial.operatingProfit.toLocaleString()}원
          </p>
        </div>

        <div className="rounded-lg border p-5">
          <p className="text-sm text-muted-foreground">
            누적 투자
          </p>

          <p className="mt-2 text-xl font-semibold">
            {totalInvestment.toLocaleString()}원
          </p>
        </div>

        <div className="rounded-lg border p-5">
          <p className="text-sm text-muted-foreground">
            등록 특허
          </p>

          <p className="mt-2 text-xl font-semibold">
            {registeredPatentCount}건
          </p>
        </div>
      </section>

      {/* 기본정보 */}
      <section className="mt-10">
        <h2 className="text-xl font-semibold">
          기본정보
        </h2>

        <dl className="mt-4 grid gap-4 rounded-lg border p-6 md:grid-cols-2">
          <div>
            <dt className="text-sm text-muted-foreground">
              대표자
            </dt>
            <dd className="mt-1">{company.representative}</dd>
          </div>

          <div>
            <dt className="text-sm text-muted-foreground">
              설립일
            </dt>
            <dd className="mt-1">{company.foundedAt}</dd>
          </div>

          <div>
            <dt className="text-sm text-muted-foreground">
              업종
            </dt>
            <dd className="mt-1">
              {company.industry} · {company.category}
            </dd>
          </div>

          <div>
            <dt className="text-sm text-muted-foreground">
              기업 규모
            </dt>
            <dd className="mt-1">{company.companySize}</dd>
          </div>

          <div>
            <dt className="text-sm text-muted-foreground">
              소재지
            </dt>
            <dd className="mt-1">{company.address}</dd>
          </div>
        </dl>
      </section>

      {/* Summary */}
      <section className="mt-10">
        <h2 className="mb-4 text-xl font-semibold">
          기업분석 요약
        </h2>

        <CompanySummary company={company} />
      </section>

      {/* Financial */}
      <section className="mt-10">
        <h2 className="text-xl font-semibold">
          재무정보
        </h2>

        <div className="mt-4 overflow-x-auto rounded-lg border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left">
                <th className="p-4">연도</th>
                <th className="p-4">매출</th>
                <th className="p-4">영업이익</th>
                <th className="p-4">자산</th>
                <th className="p-4">부채</th>
              </tr>
            </thead>

            <tbody>
              {company.financials.map((financial) => (
                <tr
                  key={financial.year}
                  className="border-b last:border-0"
                >
                  <td className="p-4">{financial.year}</td>
                  <td className="p-4">
                    {financial.revenue.toLocaleString()}원
                  </td>
                  <td className="p-4">
                    {financial.operatingProfit.toLocaleString()}원
                  </td>
                  <td className="p-4">
                    {financial.assets.toLocaleString()}원
                  </td>
                  <td className="p-4">
                    {financial.liabilities.toLocaleString()}원
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Investment */}
      <section className="mt-10">
        <h2 className="text-xl font-semibold">
          투자정보
        </h2>

        <div className="mt-4 space-y-3">
          {company.investments.map((investment) => (
            <div
              key={`${investment.date}-${investment.stage}`}
              className="rounded-lg border p-5"
            >
              <div className="flex justify-between">
                <strong>{investment.stage}</strong>
                <span>{investment.date}</span>
              </div>

              <p className="mt-2">
                {investment.amount.toLocaleString()}원
              </p>

              <p className="mt-1 text-sm text-muted-foreground">
                투자자: {investment.investors.join(', ')}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* Patent */}
      <section className="mt-10">
        <h2 className="text-xl font-semibold">
          특허정보
        </h2>

        <div className="mt-4 space-y-3">
          {company.patents.map((patent) => (
            <div
              key={patent.applicationNumber}
              className="rounded-lg border p-5"
            >
              <div className="flex justify-between gap-4">
                <strong>{patent.title}</strong>
                <span className="text-sm">
                  {patent.status}
                </span>
              </div>

              <p className="mt-2 text-sm">
                출원번호: {patent.applicationNumber}
              </p>

              <p className="text-sm">
                등록번호: {patent.registrationNumber ?? '-'}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* News */}
      <section className="mt-10">
        <h2 className="text-xl font-semibold">
          최근 뉴스
        </h2>

        <div className="mt-4 space-y-3">
          {company.news.map((news) => (
            <a
              key={`${news.publishedAt}-${news.title}`}
              href={news.url}
              className="block rounded-lg border p-5 hover:bg-muted"
            >
              <p className="font-medium">
                {news.title}
              </p>

              <p className="mt-2 text-sm text-muted-foreground">
                {news.publisher} · {news.publishedAt}
              </p>
            </a>
          ))}
        </div>
      </section>

      {/* Report */}
      <section className="mt-10">
        <Link
          to={`/companies/${company.id}/report`}
          className="inline-flex rounded-md bg-primary px-5 py-3 text-primary-foreground"
        >
          기업분석 보고서 보기
        </Link>
      </section>
    </main>
  );
}