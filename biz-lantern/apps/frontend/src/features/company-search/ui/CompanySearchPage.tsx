import { useSearchParams } from "react-router";
import { companyQueries } from "@/entities/company";
import { useQuery } from "@tanstack/react-query";

import { CompanySearchForm } from "@/features/company-search";
import { CompanySummary } from "./CompanySummary";

export function CompanySearchPage() {
  const [searchParams, setSearchParams] = useSearchParams();

  const companyName = searchParams.get("query") ?? "";

  // 회사명이 곧 GET /companies/{companyName} 의 입력값이다. companyId 를
  // 미리 확보할 방법이 없으므로(DB 미적재) 검색어를 그대로 조회에 쓴다.
  const { data, isPending, isError } = useQuery({
    ...companyQueries.detail(companyName),
    enabled: companyName.length > 0,
  });

  const handleSearch = (nextQuery: string) => {
    setSearchParams({ query: nextQuery });
  };

  return (
    <main className="mx-auto max-w-5xl p-8">
      <h1 className="mb-6">기업 검색</h1>

      <CompanySearchForm onSearch={handleSearch} />

      {!companyName && <p className="mt-8">분석할 기업을 검색하세요.</p>}

      {companyName && isError && (
        <p className="mt-8">'{companyName}' 기업을 조회하지 못했습니다.</p>
      )}

      {companyName && !isError && (
        <div className="mt-8">
          {data && (
            <h2 className="mb-4 text-2xl font-bold">
              {data.data.company_name}
            </h2>
          )}

          <CompanySummary
            documentMarkdown={data?.data.pipeline.document}
            isDocumentLoading={isPending}
            isDocumentError={isError}
          />
        </div>
      )}
    </main>
  );
}
