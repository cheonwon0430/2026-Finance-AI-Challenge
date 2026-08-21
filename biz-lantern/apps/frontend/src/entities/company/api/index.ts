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

export const getCompany = (companyId: number) => {
  return httpClient.get<CompanyDTO>(`/companies/${companyId}`);
};

export { companyQueries } from "./queries";
