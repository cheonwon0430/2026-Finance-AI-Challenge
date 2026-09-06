import { AlertTriangle, FileCheck2, HelpCircle, ScrollText } from 'lucide-react';

import type { AuditReport, NtsStatus } from '@/entities/company';
import { formatDate } from '@/entities/company';
import {
  Alert,
  AlertDescription,
  AlertTitle,
  Badge,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/shared/ui';
import { cn } from '@/shared/lib';

interface AuditReportCardProps {
  /** 최신순 3개년. 비어 있으면 외감 대상이 아니다 */
  auditReports: AuditReport[];
  selectedRceptNo: string | null;
  onSelect: (rceptNo: string) => void;
}

export function AuditReportCard({
  auditReports,
  selectedRceptNo,
  onSelect,
}: AuditReportCardProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <ScrollText className="size-4 text-muted-foreground" />
          감사보고서
          {auditReports.length > 0 && (
            <span className="text-sm font-normal text-muted-foreground">
              {auditReports.length}건
            </span>
          )}
        </CardTitle>
      </CardHeader>

      <CardContent>
        {auditReports.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            확인된 감사보고서가 없습니다.
          </p>
        ) : (
          <ul className="space-y-2">
            {auditReports.map((report) => {
              const isSelected = report.rcept_no === selectedRceptNo;

              return (
                <li key={report.rcept_no}>
                  <button
                    type="button"
                    onClick={() => onSelect(report.rcept_no)}
                    aria-pressed={isSelected}
                    className={cn(
                      'w-full rounded-md border p-3 text-left transition-colors',
                      'hover:bg-muted/50',
                      isSelected ? 'border-primary bg-muted/40' : 'border-border',
                    )}
                  >
                    <div className="flex items-start gap-2">
                      <FileCheck2 className="mt-0.5 size-4 shrink-0 text-primary" />

                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-semibold wrap-break-word">
                          {report.report_nm}
                          {report.corrected && (
                            <Badge variant="secondary" className="ml-2 align-middle">
                              기재정정
                            </Badge>
                          )}
                        </p>

                        <dl className="mt-2 grid gap-x-4 gap-y-1 text-xs sm:grid-cols-2">
                          <div className="flex gap-1">
                            <dt className="text-muted-foreground">회계연도</dt>
                            <dd>{report.fiscal_year ?? '정보 없음'}</dd>
                          </div>

                          <div className="flex gap-1">
                            <dt className="text-muted-foreground">회계법인</dt>
                            <dd className="wrap-break-word">
                              {report.auditor ?? '정보 없음'}
                            </dd>
                          </div>

                          <div className="flex gap-1">
                            <dt className="text-muted-foreground">접수일</dt>
                            <dd>{formatDate(report.rcept_dt)}</dd>
                          </div>

                          <div className="flex gap-1">
                            <dt className="text-muted-foreground">접수번호</dt>
                            <dd>{report.rcept_no}</dd>
                          </div>
                        </dl>
                      </div>
                    </div>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

interface NtsStatusCardProps {
  nts: NtsStatus | null;
  ntsError: string | null;
}

export function NtsStatusCard({ nts, ntsError }: NtsStatusCardProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <FileCheck2 className="size-4 text-muted-foreground" />
          국세청 사업자 상태
        </CardTitle>
      </CardHeader>

      <CardContent>
        {nts ? (
          <div className="space-y-4">
            <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-2">
              <div className="min-w-0">
                <dt className="text-xs text-muted-foreground">사업자 상태</dt>
                <dd className="mt-1 text-sm wrap-break-word">
                  {nts.status ?? '정보 없음'}
                </dd>
              </div>

              <div className="min-w-0">
                <dt className="text-xs text-muted-foreground">과세 유형</dt>
                <dd className="mt-1 text-sm wrap-break-word">
                  {nts.tax_type ?? '정보 없음'}
                </dd>
              </div>

              <div className="min-w-0">
                <dt className="text-xs text-muted-foreground">폐업일</dt>
                <dd className="mt-1 text-sm">{nts.closed_at ?? '해당 없음'}</dd>
              </div>
            </dl>

            {/* 진위확인과 휴폐업은 다른 사실이다. 진위확인이 틀려도 폐업이 아닐 수 있어
                상태를 지우지 않고 따로 덧붙인다. */}
            {!nts.verified && (
              <Alert variant="warning">
                <AlertTriangle />
                <AlertTitle>진위확인 불일치</AlertTitle>
                <AlertDescription>
                  <p>
                    사업자번호와 등록 정보가 서로 맞지 않습니다
                    {nts.valid_code && ` (valid=${nts.valid_code})`}. 위 사업자
                    상태와는 별개입니다.
                  </p>
                </AlertDescription>
              </Alert>
            )}
          </div>
        ) : (
          <Alert variant="warning">
            <HelpCircle />
            <AlertTitle>국세청 조회 결과를 확인할 수 없습니다</AlertTitle>
            <AlertDescription>
              <p>사업자 상태를 조회하지 못했습니다. 정상, 휴업, 폐업 등은 추정할 수 없습니다.</p>

              {ntsError && (
                <p className="mt-1 flex items-center gap-1 text-xs opacity-80">
                  <AlertTriangle className="size-3 shrink-0" />
                  {ntsError}
                </p>
              )}
            </AlertDescription>
          </Alert>
        )}
      </CardContent>
    </Card>
  );
}
