/**
 * 비상장기업 분석 보고서 API.
 *
 * 타입 정의의 원본은 백엔드의 TypedDict 이고(`app/domain/report/`), 여기 DTO 는 실제 응답을
 * 열어 보고 확인된 필드만 옮겨 적은 것이다. 확인되지 않은 것은 지어내지 않고
 * `Record<string, unknown>` 으로 둔다 - `entities/company` 의 `NtsOperatingStatus` 와 같다.
 *
 * `companyQueries` 와 달리 queryFn 이 **axios 응답을 벗겨 본문만 반환한다.** 폴링 중단 조건이
 * `query.state.data.status` 를 읽어야 하는데 `.data.data.status` 는 조용히 어긋나기 쉽다.
 * 이 슬라이스에는 기존 소비처가 없어 파급이 없다. `entities/company` 는 그대로 둔다.
 */
import { httpClient } from '@/shared/api';

/** PENDING 이면 본문이 전부 비어 있다. LLM 이 전부 죽어도 COMPLETED 다. */
export type ReportStatus = 'PENDING' | 'COMPLETED' | 'FAILED';

/**
 * 판정값 다섯. 색으로 뭉개면 안 된다 - 특히 ABSENT(확인했으나 없었다)와
 * SOURCE_UNAVAILABLE(확인하지 못했다)은 서로 다른 사건이다.
 */
export type Verdict =
  | 'CONFIRMED'
  | 'ABSENT'
  | 'NOT_REQUIRED'
  | 'EXTRACTION_FAILED'
  | 'SOURCE_UNAVAILABLE';

/** 항목 25개가 묶이는 6개 블록. */
export type Section =
  | 'gate'
  | 'entity'
  | 'finance'
  | 'capital'
  | 'business'
  | 'risk';

/** 근거 조각의 유형. 화면은 이 값으로 렌더러를 고른다. */
export type EvidenceType =
  | 'api_field'
  | 'summary'
  | 'account'
  | 'table'
  | 'paragraph'
  | 'note'
  | 'derived'
  | 'conflict'
  | 'news';

/** 출처명·기준일·원문 링크. 판정이 CONFIRMED 가 아니어도 항상 채워진다. */
export interface EvidenceSource {
  name: string;
  as_of: string | null;
  as_of_kind: string | null;
  document_url: string | null;
  rcept_no: string | null;
}

/** 항목 하나의 판정. */
export interface Finding {
  item_id: string;
  label: string;
  section: Section;
  verdict: Verdict;
  value: string | null;
  evidence_ids: string[];
  source: EvidenceSource;
  warnings: string[];
}

/** 서술 문장 하나. origin 이 rule 이면 LLM 없이 나온 정형문이다. */
export interface Sentence {
  text: string;
  kind: 'confirmed' | 'inferred' | 'reference';
  evidence_ids: string[];
  origin: 'rule' | 'llm';
}

/** 후검증에서 폐기된 문장. 왜 버렸는지가 reasons 에 남는다. */
export interface Dropped {
  text: string;
  kind: string;
  evidence_ids: string[];
  reasons: string[];
  attempt: number;
}

/** 항목 하나의 서술. sentences 는 항상 1개 이상이고 맨 앞이 정형문이다. */
export interface ItemNarrative {
  item_id: string;
  sentences: Sentence[];
  dropped: Dropped[];
  pack_ids: string[];
  llm_status: string;
  llm_error: string | null;
}

/** 보고서 본문의 문단. */
export interface Paragraph {
  sentences: Sentence[];
}

/**
 * 보고서 본문 한 절. 항목 나열이 아니라 이어지는 문단이다.
 *
 * 같은 근거를 항목별로도(`items`) 절별로도(`sections`) 볼 수 있다. 본문은 절을 쓰고,
 * 항목은 부록('확인 범위와 한계')과 근거 추적에 쓴다.
 */
export interface SectionNarrative {
  section: Section;
  title: string;
  item_ids: string[];
  paragraphs: Paragraph[];
  dropped: Dropped[];
  pack_ids: string[];
  llm_status: string;
  llm_error: string | null;
}

/** 충돌 근거의 한쪽. based_on 으로 원본 조각까지 내려간다. */
export interface ConflictSide {
  label: string;
  value: string;
  as_of: string | null;
  as_of_kind: string | null;
  based_on: string;
}

/** 계정 근거의 회계연도별 값. raw 는 문서 원문 그대로다. */
export interface AccountPeriod {
  raw: string;
  value: number | null;
  header: string;
}

export interface EvidenceAccount {
  logical_name: string;
  code: string;
  statement: string;
  periods: Record<string, AccountPeriod>;
}

/**
 * 근거 조각.
 *
 * `based_on` 아래 필드는 type 에 따라 있고 없다 - derived 는 formula·rule_id,
 * conflict 는 conflict_kind·resolution·sides, account 는 account, api_field 는 context.
 * `locator` 는 kind 마다 필드가 갈려 느슨한 레코드로 둔다.
 */
export interface Evidence {
  evidence_id: string;
  type: EvidenceType;
  label: string;
  raw_content: string;
  numbers: string[];
  units: string[];
  locator: Record<string, unknown>;
  source: EvidenceSource;
  based_on?: string[];
  formula?: string;
  rule_id?: string;
  conflict_kind?: 'timing' | 'reliability' | 'identity';
  resolution?: 'both' | 'dart_first';
  sides?: ConflictSide[];
  account?: EvidenceAccount;
  context?: Record<string, unknown>;
  table?: Record<string, unknown>;
}

/** 서술 단계에서 터진 것. item_id 가 null 이면 전체 실패다. */
export interface ReportError {
  item_id: string | null;
  message: string;
}

/** 수집 진행 기록. PENDING 동안에는 비어 있다. */
export interface ReportStep {
  step: number;
  total: number;
  name: string;
  status: 'ok' | 'fail';
  detail: string;
}

/** POST 직후의 응답. 아직 만들어지지 않았다. */
export interface ReportAccepted {
  report_id: string;
  corp_code: string;
  status: ReportStatus;
  created_at: string;
}

/** GET 응답. FAILED 도 200 이다 - 404 는 그 id 의 보고서가 없을 때뿐이다. */
export interface ReportResponse {
  report_id: string;
  corp_code: string;
  status: ReportStatus;
  created_at: string;
  as_of: string | null;
  completed_at: string | null;
  company_name: string | null;
  failure: string | null;
  findings: Record<string, Finding>;
  items: Record<string, ItemNarrative>;
  sections: SectionNarrative[];
  evidence: Evidence[];
  derived: string[];
  errors: ReportError[];
  orphan_derived: string[];
  steps: ReportStep[];
}

/**
 * 보고서 생성을 접수한다. 즉시 202 로 돌아오고 본문은 아직 없다.
 * 회사명이 아니라 corp_code 를 받는다 - 이름은 부분 일치라 엉뚱한 회사를 고를 수 있다.
 */
export const createReport = async (corpCode: string) => {
  const response = await httpClient.post<ReportAccepted>('/reports', {
    corp_code: corpCode,
  });

  return response.data;
};

export const getReport = async (reportId: string) => {
  const response = await httpClient.get<ReportResponse>(`/reports/${reportId}`);

  return response.data;
};

export { reportQueries, REPORT_POLL_INTERVAL_MS } from './queries';
