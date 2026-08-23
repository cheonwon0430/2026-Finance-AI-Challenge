import type { PaginationRequest, PaginationResponse } from "@/shared/api";
import { httpClient } from "@/shared/api";

export interface CompanyDTO {
  id: number;
  name: string;
  representative: string | null;
  foundedAt: string | null;
  industry: string | null;
  address: string | null;
  companySize: string | null;
}

export interface CompanySearchParams extends PaginationRequest {
  query: string;
}

export type CompanySearchResponse = PaginationResponse<CompanyDTO>;

export const getCompanies = (params: CompanySearchParams) => {
  return httpClient.get<CompanySearchResponse>("/companies", {
    params,
  });
};

/**
 * GET /companies/{companyName} 의 응답.
 *
 * patents/pipeline 은 KIPRIS/DART 원천 데이터를 그대로 담아 구조가 동적이라
 * 백엔드(CompanyOverviewResponse)와 마찬가지로 느슨한 타입으로 둔다.
 * document_markdown 은 pipeline.paths.document_clean_md 가 가리키는 감사보고서
 * 정리본 마크다운의 실제 내용이며, 감사보고서가 없으면 null 이다.
 */
export interface CompanyOverviewResponse {
  company_name: string;
  patents: {
    count: number;
    items: unknown[];
  };
  pipeline: {
    corp_code: string;
    company: Record<string, unknown>;
    nts_operating: boolean | null;
    nts_error: string | null;
    audit_report: Record<string, unknown> | null;
    paths: Record<string, string>;
    steps: unknown[];
  };
  document_markdown: string | null;
}

export const getCompany = (companyName: string) => {
  return httpClient.get<CompanyOverviewResponse>(`/companies/${companyName}`);
};

export { companyQueries } from "./queries";
