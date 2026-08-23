import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

// 가짜 데이터 입니다 추후 삭제 예정
// 화면을 만들기 위한 간이 요소입니다.
import type { Company } from '../../company/model/company-data';

interface CompanySummaryProps {
  // CompanyDetailPage 는 여전히 이 가짜 데이터 기반 요약을 사용하므로 그대로 둔다.
  company?: Company;

  // 실제 API(getCompany)가 돌려주는 감사보고서 정리본 마크다운.
  // 아직 조회 전이면 undefined, 조회했지만 감사보고서가 없으면 null이다.
  documentMarkdown?: string | null;
  isDocumentLoading?: boolean;
  isDocumentError?: boolean;
}

export function CompanySummary({
  company,
  documentMarkdown,
  isDocumentLoading = false,
  isDocumentError = false,
}: CompanySummaryProps) {
  return (
    <section className="space-y-4">
      {company && (
        <>
          <div>
            <h2 className="font-semibold">기업 개요</h2>
            <p className="mt-2 text-muted-foreground">
              {company.summary.overview}
            </p>
          </div>

          <div>
            <h2 className="font-semibold">재무 요약</h2>
            <p className="mt-2 text-muted-foreground">
              {company.summary.financial}
            </p>
          </div>

          <div>
            <h2 className="font-semibold">투자 요약</h2>
            <p className="mt-2 text-muted-foreground">
              {company.summary.investment}
            </p>
          </div>

          <div>
            <h2 className="font-semibold">특허 요약</h2>
            <p className="mt-2 text-muted-foreground">
              {company.summary.patent}
            </p>
          </div>
        </>
      )}

      {(isDocumentLoading || isDocumentError || documentMarkdown !== undefined) && (
        <div>
          <h2 className="font-semibold">기업분석 문서</h2>

          {isDocumentLoading && (
            <p className="mt-2 text-muted-foreground">문서를 불러오는 중입니다.</p>
          )}

          {!isDocumentLoading && isDocumentError && (
            <p className="mt-2 text-muted-foreground">문서를 불러오지 못했습니다.</p>
          )}

          {!isDocumentLoading && !isDocumentError && documentMarkdown === null && (
            <p className="mt-2 text-muted-foreground">확인된 감사보고서가 없습니다.</p>
          )}

          {!isDocumentLoading && !isDocumentError && documentMarkdown && (
            <div className="markdown-body mt-2">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {documentMarkdown}
              </ReactMarkdown>
            </div>
          )}
        </div>
      )}
    </section>
  );
}