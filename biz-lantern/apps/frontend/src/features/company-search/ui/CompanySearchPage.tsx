import { useSearchParams } from 'react-router';

import {
  companyQueries,
  type CompanyDTO,
} from '@/entities/company';
import { useQuery } from '@tanstack/react-query';

import { CompanySearchForm } from '@/features/company-search';

export function CompanySearchPage() {
  const [searchParams, setSearchParams] = useSearchParams();

  const query = searchParams.get('query') ?? '';
  const page = Number(searchParams.get('page') ?? '1');

  const { data, isPending, isError } = useQuery({
    ...companyQueries.list({
      query,
      page,
      size: 10,
    }),
    enabled: query.length > 0,
  });

  const handleSearch = (nextQuery: string) => {
    setSearchParams({
      query: nextQuery,
      page: '1',
    });
  };

  return (
    <main className="mx-auto max-w-5xl p-8">
      <h1 className="mb-6">기업 검색</h1>

      <CompanySearchForm onSearch={handleSearch} />

      {!query && (
        <p className="mt-8">
          분석할 기업을 검색하세요.
        </p>
      )}

      {isPending && (
        <p className="mt-8">기업을 검색하고 있습니다.</p>
      )}

      {isError && (
        <p className="mt-8">
          기업 검색에 실패했습니다.
        </p>
      )}

      {data && (
        <div className="mt-8 space-y-3">
          {data.data.content.map((company: CompanyDTO) => (
            <button
              key={company.id}
              type="button"
              className="block w-full rounded-md border p-4 text-left"
            //   window.location.href는 최종 구현에서는 React Router navigation으로 바꾼다.
              onClick={() => {
                window.location.href = `/companies/${company.id}`;
              }}
            >
              <strong>{company.name}</strong>

              <div className="mt-1 text-sm">
                {company.industry ?? '업종 정보 없음'}
              </div>

              <div className="text-sm">
                설립 {company.foundedAt ?? '-'}
              </div>
            </button>
          ))}
        </div>
      )}
    </main>
  );
}