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

/** DART 기업개황(company.json) 조회 결과. */
export interface Company {
  status: string;
  message: string;
  corp_code: string;
  corp_name: string;
  corp_name_eng: string;
  stock_name: string;
  stock_code: string;
  ceo_nm: string;
  corp_cls: string;
  jurir_no: string;
  bizr_no: string;
  adres: string;
  hm_url: string;
  ir_url: string;
  phn_no: string;
  fax_no: string;
  induty_code: string;
  est_dt: string;
  acc_mt: string;
}

/** KIPRIS 특허 행정처리 이력(최신 1건). */
export interface AdministrativeHistory {
  applicationNumber: string;
  documentNumber: string;
  documentDate: string;
  documentTitle: string;
  documentTitleEng: string;
  status: string;
  statusEng: string;
  step: string;
  trialNumber: string | null;
  registrationNumber: string | null;
}

export interface Patent {
  application_number: string;
  invention_name: string;
  applicant: string;
  application_date: string;
  status: string;
  administrative_history: AdministrativeHistory | null;
}

/** DART 감사보고서(F001) 목록 중 선택된 최신 1건. */
export interface AuditReport {
  corp_code: string;
  corp_name: string;
  stock_code: string;
  corp_cls: string;
  report_nm: string;
  rcept_no: string;
  flr_nm: string;
  rcept_dt: string;
  rm: string;
}

export interface PipelineStep {
  step: number;
  total: number;
  name: string;
  status: 'ok' | 'fail';
  detail: string;
}

/**
 * 국세청 사업자상태 조회 결과.
 * 현재 백엔드에서 실제로 확인된 케이스는 timeout 으로 인한 null 뿐이라
 * 정상 응답의 필드 구조는 아직 알 수 없다. 임의로 필드를 지어내지 않도록
 * 느슨한 레코드 타입으로 둔다.
 */
export type NtsOperatingStatus = Record<string, unknown>;

/**
 * GET /companies/{companyName} 의 응답 중 pipeline 필드.
 *
 * document 는 pipeline.paths.document_clean_md 가 가리키는 감사보고서
 * 정리본 마크다운의 실제 내용이며, 감사보고서가 없으면 null 이다.
 */
export interface Pipeline {
  corp_code: string;
  company: Company;
  nts_operating: NtsOperatingStatus | null;
  nts_error: string | null;
  audit_report: AuditReport | null;
  document: string | null;
  steps: PipelineStep[];
}

/** GET /companies/{companyName} 의 응답. */
export interface CompanyOverviewResponse {
  company_name: string;
  patents: {
    count: number;
    items: Patent[];
  };
  pipeline: Pipeline;
}

export const getCompany = (companyName: string) => {
  return httpClient.get<CompanyOverviewResponse>(`/companies/${companyName}`);
};

export { companyQueries } from "./queries";
