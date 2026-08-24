import { AlertTriangle, FileCheck2, HelpCircle, ScrollText } from 'lucide-react';

import type { AuditReport, NtsOperatingStatus } from '@/entities/company';
import { formatDate } from '@/entities/company';
import {
  Alert,
  AlertDescription,
  AlertTitle,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/shared/ui';

interface AuditReportCardProps {
  auditReport: AuditReport | null;
}

export function AuditReportCard({ auditReport }: AuditReportCardProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <ScrollText className="size-4 text-muted-foreground" />
          감사보고서
        </CardTitle>
      </CardHeader>

      <CardContent>
        {!auditReport ? (
          <p className="text-sm text-muted-foreground">
            확인된 감사보고서가 없습니다.
          </p>
        ) : (
          <div className="space-y-4">
            <div className="flex items-start gap-2">
              <FileCheck2 className="mt-0.5 size-4 shrink-0 text-primary" />
              <p className="text-sm font-semibold wrap-break-word">
                {auditReport.report_nm}
              </p>
            </div>

            <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-2">
              <div>
                <dt className="text-xs text-muted-foreground">기업명</dt>
                <dd className="mt-1 text-sm">{auditReport.corp_name}</dd>
              </div>

              <div>
                <dt className="text-xs text-muted-foreground">
                  제출인 / 회계법인
                </dt>
                <dd className="mt-1 text-sm">{auditReport.flr_nm}</dd>
              </div>

              <div>
                <dt className="text-xs text-muted-foreground">접수번호</dt>
                <dd className="mt-1 text-sm">{auditReport.rcept_no}</dd>
              </div>

              <div>
                <dt className="text-xs text-muted-foreground">접수일</dt>
                <dd className="mt-1 text-sm">
                  {formatDate(auditReport.rcept_dt)}
                </dd>
              </div>
            </dl>

            {auditReport.rm && (
              <p className="text-xs text-muted-foreground">
                {auditReport.rm}
              </p>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

interface NtsStatusCardProps {
  ntsOperating: NtsOperatingStatus | null;
  ntsError: string | null;
}

export function NtsStatusCard({ ntsOperating, ntsError }: NtsStatusCardProps) {
  const entries = ntsOperating ? Object.entries(ntsOperating) : [];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <FileCheck2 className="size-4 text-muted-foreground" />
          국세청 사업자 상태
        </CardTitle>
      </CardHeader>

      <CardContent>
        {ntsOperating ? (
          <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-2">
            {entries.map(([key, value]) => (
              <div key={key} className="min-w-0">
                <dt className="text-xs text-muted-foreground">{key}</dt>
                <dd className="mt-1 text-sm wrap-break-word">{String(value)}</dd>
              </div>
            ))}
          </dl>
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
