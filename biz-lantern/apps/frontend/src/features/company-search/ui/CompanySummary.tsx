import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

// 가짜 데이터 입니다 추후 삭제 예정
// CompanyDetailPage 는 여전히 이 가짜 데이터 기반 요약을 사용하므로 그대로 둔다.
import type { Company as LegacyCompany } from '../../company/model/company-data';

import type { CompanyOverviewResponse } from '@/entities/company';
import { Alert, AlertDescription, AlertTitle, Skeleton } from '@/shared/ui';
import { ReportCreateButton } from '@/features/report';

import { AuditReportCard, NtsStatusCard } from './AuditReportCard';
import { CompanyInfoCard } from './CompanyInfoCard';
import { PatentDetailDialog } from './PatentDetailDialog';
import { PatentSummaryCard } from './PatentSummaryCard';
import { PipelineStatus } from './PipelineStatus';

interface CompanySummaryProps {
  // CompanyDetailPage 는 여전히 이 가짜 데이터 기반 요약을 사용하므로 그대로 둔다.
  company?: LegacyCompany;

  // GET /companies/{companyName} 의 실제 응답.
  overview?: CompanyOverviewResponse;
  isOverviewLoading?: boolean;
  isOverviewError?: boolean;
}

export function CompanySummary({
  company,
  overview,
  isOverviewLoading = false,
  isOverviewError = false,
}: CompanySummaryProps) {
  const [isPatentDialogOpen, setIsPatentDialogOpen] = useState(false);

  // 어느 감사보고서의 정리 문서를 펼쳐 볼지. null 이면 최신 1건(목록이 최신순이다).
  const [selectedRceptNo, setSelectedRceptNo] = useState<string | null>(null);

  const auditReports = overview?.pipeline.audit_reports ?? [];
  const selectedReport =
    auditReports.find((report) => report.rcept_no === selectedRceptNo) ??
    auditReports[0] ??
    null;

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

      {isOverviewLoading && (
        <div className="space-y-4">
          <Skeleton className="h-48 w-full" />
          <div className="grid gap-4 md:grid-cols-2">
            <Skeleton className="h-40 w-full" />
            <Skeleton className="h-40 w-full" />
          </div>
          <Skeleton className="h-56 w-full" />
          <Skeleton className="h-24 w-full" />
        </div>
      )}

      {!isOverviewLoading && isOverviewError && (
        <Alert variant="destructive">
          <AlertTitle>기업분석 정보를 불러오지 못했습니다</AlertTitle>
          <AlertDescription>잠시 후 다시 시도해 주세요.</AlertDescription>
        </Alert>
      )}

      {!isOverviewLoading && !isOverviewError && overview && (
        <div className="space-y-4">
          <ReportCreateButton
            corpCode={overview.pipeline.company.corp_code}
          />

          <CompanyInfoCard company={overview.pipeline.company} />

          <div className="grid gap-4 md:grid-cols-2">
            <AuditReportCard
              auditReports={auditReports}
              selectedRceptNo={selectedReport?.rcept_no ?? null}
              onSelect={setSelectedRceptNo}
            />
            <NtsStatusCard
              nts={overview.pipeline.nts}
              ntsError={overview.pipeline.nts_error}
            />
          </div>

          <PipelineStatus steps={overview.pipeline.steps} />

          <PatentSummaryCard
            count={overview.patents.count}
            onClick={() => setIsPatentDialogOpen(true)}
          />

          <PatentDetailDialog
            open={isPatentDialogOpen}
            onOpenChange={setIsPatentDialogOpen}
            count={overview.patents.count}
            items={overview.patents.items}
          />

          {selectedReport && (
            <div>
              <h2 className="font-semibold">감사보고서 정리 문서</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                {selectedReport.report_nm} · 위 목록에서 다른 연도를 고를 수 있습니다.
              </p>
              <div className="markdown-body mt-2">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {selectedReport.document}
                </ReactMarkdown>
              </div>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
