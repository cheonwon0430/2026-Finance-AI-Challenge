import { useMemo } from 'react';
import { useParams } from 'react-router';
import { useQuery } from '@tanstack/react-query';
import { isAxiosError } from 'axios';

import { reportQueries } from '@/entities/report';
import { Alert, AlertDescription, AlertTitle, Skeleton } from '@/shared/ui';

import { buildEvidenceIndex } from '../lib/evidence-index';
import { ReportBody } from './ReportBody';
import { ReportBuildLog } from './ReportBuildLog';
import { ReportDisclaimer } from './ReportDisclaimer';
import { ReportFailed } from './ReportFailed';
import { ReportHeader } from './ReportHeader';
import { ReportNotFound } from './ReportNotFound';
import { ReportPending } from './ReportPending';
import { ReportProfile } from './ReportProfile';
import { ReportScope } from './ReportScope';

/**
 * 보고서 화면의 유일한 컨테이너. 자식은 전부 props 만 받는다.
 *
 * 화면 순서가 곧 읽는 순서다 - 머리말(법인 기본정보) -> 본문(절과 문단) ->
 * 확인 범위와 한계 -> 생성 기록. 판정 항목 25개를 늘어놓는 것은 체크리스트지
 * 보고서가 아니므로 본문에 두지 않는다.
 *
 * `status` 는 셋이고 **FAILED 도 200 이다.** 404 는 그 id 의 보고서가 없을 때뿐이라
 * 화면에서 반드시 구분한다.
 */
export function ReportPage() {
  const { reportId = '' } = useParams();

  const { data, isPending, error } = useQuery({
    ...reportQueries.detail(reportId),
    enabled: reportId.length > 0,
  });

  const evidenceIndex = useMemo(
    () => buildEvidenceIndex(data?.evidence ?? []),
    [data?.evidence],
  );

  const isNotFound = isAxiosError(error) && error.response?.status === 404;

  return (
    <main className="mx-auto max-w-4xl p-8">
      {isPending && (
        <div className="space-y-4">
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-40 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      )}

      {!isPending && isNotFound && <ReportNotFound reportId={reportId} />}

      {!isPending && error && !isNotFound && (
        <Alert variant="destructive">
          <AlertTitle>보고서를 불러오지 못했습니다</AlertTitle>
          <AlertDescription>잠시 후 다시 시도해 주세요.</AlertDescription>
        </Alert>
      )}

      {!isPending && !error && data && (
        <div className="space-y-8">
          <ReportHeader report={data} />

          {data.status === 'PENDING' && (
            <ReportPending createdAt={data.created_at} />
          )}

          {data.status === 'FAILED' && <ReportFailed report={data} />}

          {data.status === 'COMPLETED' && (
            <>
              <ReportDisclaimer />

              <ReportProfile findings={data.findings} />

              <ReportBody sections={data.sections} index={evidenceIndex} />

              <ReportScope
                findings={data.findings}
                items={data.items}
                index={evidenceIndex}
              />

              <ReportBuildLog report={data} />
            </>
          )}
        </div>
      )}
    </main>
  );
}
