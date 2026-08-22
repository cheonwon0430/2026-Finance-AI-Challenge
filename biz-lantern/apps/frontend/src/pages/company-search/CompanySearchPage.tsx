import { useMemo, useState } from 'react';

import {
  CompanyCard,
  searchCompanies,
} from '@/features/company';

export function CompanySearchPage() {
  const [query, setQuery] = useState('');
  const [submittedQuery, setSubmittedQuery] = useState('');

  const companies = useMemo(
    () => searchCompanies(submittedQuery),
    [submittedQuery],
  );

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSubmittedQuery(query);
  };

  return (
    <main className="mx-auto max-w-5xl p-8">
      <header>
        <h1 className="text-2xl font-bold">
          기업 검색
        </h1>

        <p className="mt-2 text-muted-foreground">
          분석하고 싶은 기업을 검색하세요.
        </p>
      </header>

      <form
        onSubmit={handleSubmit}
        className="mt-8 flex gap-2"
      >
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="기업명을 입력하세요"
          className="flex-1 rounded-md border px-4 py-2"
        />

        <button
          type="submit"
          className="rounded-md bg-primary px-5 py-2 text-primary-foreground"
        >
          검색
        </button>
      </form>

      <section className="mt-8">
        {submittedQuery && (
          <p className="mb-4 text-sm text-muted-foreground">
            '{submittedQuery}' 검색 결과 {companies.length}개
          </p>
        )}

        <div className="space-y-3">
          {companies.map((company) => (
            <CompanyCard
              key={company.id}
              company={company}
            />
          ))}
        </div>

        {companies.length === 0 && (
          <p className="py-12 text-center text-muted-foreground">
            검색 결과가 없습니다.
          </p>
        )}
      </section>
    </main>
  );
}