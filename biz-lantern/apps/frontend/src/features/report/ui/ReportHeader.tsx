import { Link } from 'react-router';

import type { ReportResponse, ReportStatus } from '@/entities/report';
import { Badge } from '@/shared/ui';

import { formatTimestamp } from '../lib/labels';

interface ReportHeaderProps {
  report: ReportResponse;
}

const STATUS_DISPLAY: Record<
  ReportStatus,
  { label: string; variant: 'secondary' | 'success' | 'destructive' }
> = {
  PENDING: { label: '생성 중', variant: 'secondary' },
  COMPLETED: { label: '생성 완료', variant: 'success' },
  FAILED: { label: '생성 실패', variant: 'destructive' },
};

export function ReportHeader({ report }: ReportHeaderProps) {
  const status = STATUS_DISPLAY[report.status];
  const completedAt = formatTimestamp(report.completed_at);

  return (
    <header>
      <Link to="/companies" className="text-sm text-muted-foreground">
        ← 기업 검색
      </Link>

      <div className="mt-6 flex flex-wrap items-center gap-3">
        <h1 className="text-3xl font-bold">
          {report.company_name ?? report.corp_code}
        </h1>

        <Badge variant={status.variant}>{status.label}</Badge>
      </div>

      <dl className="mt-4 grid gap-x-6 gap-y-2 sm:grid-cols-3">
        <div>
          <dt className="text-xs text-muted-foreground">DART 고유번호</dt>
          <dd className="mt-0.5 text-sm">{report.corp_code}</dd>
        </div>

        <div>
          <dt className="text-xs text-muted-foreground">판정 기준일</dt>
          <dd className="mt-0.5 text-sm">{report.as_of ?? '-'}</dd>
        </div>

        <div>
          <dt className="text-xs text-muted-foreground">생성 완료</dt>
          <dd className="mt-0.5 text-sm">{completedAt ?? '-'}</dd>
        </div>
      </dl>
    </header>
  );
}
