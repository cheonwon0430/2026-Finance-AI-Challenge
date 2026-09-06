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

/**
 * DART 감사보고서(F001) 한 건. 목록 메타와 정리된 본문을 함께 들고 있다.
 *
 * 백엔드가 3개년을 수집하면서 목록 메타(corp_name·flr_nm·rm)를 그대로 넘기던 구조에서
 * 필요한 것만 추린 구조로 바뀌었다. 제출인은 회계법인이라 auditor 로 이름이 바뀌었다.
 */
export interface AuditReport {
  rcept_no: string;
  rcept_dt: string;
  report_nm: string;
  /** 제출인. 감사보고서의 제출인은 회계법인이다 */
  auditor: string | null;
  /** report_nm 의 (2025.12) 를 회계연도 종료일로 편 값 */
  fiscal_year: string | null;
  /** [기재정정] 으로 다시 제출된 건 */
  corrected: boolean;
  /** 정리된 마크다운 본문 */
  document: string;
}

export interface PipelineStep {
  step: number;
  total: number;
  name: string;
  status: 'ok' | 'fail';
  detail: string;
}

/**
 * 국세청 사업자 조회 결과(pipeline.nts).
 *
 * verified 와 operating 은 다른 사실이다. verified 는 사업자번호·상호·개업일이 서로
 * 맞는지(진위확인)이고, operating 은 지금 영업 중인지(휴폐업)다. 진위확인이 틀려도
 * 폐업이 아닐 수 있어서 화면에서 둘을 섞으면 안 된다.
 */
export interface NtsStatus {
  verified: boolean;
  valid_code: string | null;
  operating: boolean | null;
  status_code: string | null;
  /** 예: "계속사업자" */
  status: string | null;
  /** 예: "부가가치세 일반과세자" */
  tax_type: string | null;
  closed_at: string | null;
}

/**
 * GET /companies/{companyName} 의 응답 중 pipeline 필드.
 *
 * 정리된 본문은 pipeline 이 아니라 audit_reports[].document 에 건별로 들어 있다.
 */
export interface Pipeline {
  corp_code: string;
  company: Company;
  /** 확인하지 못했으면 null. 사유는 nts_error 에 있다 */
  nts: NtsStatus | null;
  nts_error: string | null;
  /** 최신순 3개년. 비어 있으면 외감 대상이 아니다 */
  audit_reports: AuditReport[];
  /** DART F005 미제출신고. 감사보고서가 0건일 때만 조회한다 */
  non_submission: unknown[] | null;
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
