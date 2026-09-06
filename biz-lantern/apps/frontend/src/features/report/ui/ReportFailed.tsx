import { TriangleAlert } from 'lucide-react';

import type { ReportResponse } from '@/entities/report';
import {
  Alert,
  AlertDescription,
  AlertTitle,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/shared/ui';

import { ReportSteps } from './ReportSteps';

interface ReportFailedProps {
  report: ReportResponse;
}

/**
 * 생성에 실패한 보고서.
 *
 * "보고서를 못 만들었다" 는 조회 결과이지 조회 실패가 아니다 - 그래서 404 와 다르게 보여야
 * 한다. 어디까지 갔는지를 `steps` 로 함께 보여준다.
 */
export function ReportFailed({ report }: ReportFailedProps) {
  return (
    <div className="space-y-4">
      <Alert variant="destructive">
        <TriangleAlert />
        <AlertTitle>보고서를 만들지 못했다</AlertTitle>
        <AlertDescription>
          <p className="wrap-break-word">
            {report.failure ?? '사유가 기록되지 않았다.'}
          </p>
        </AlertDescription>
      </Alert>

      {report.steps.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>어디까지 진행됐나</CardTitle>
          </CardHeader>
          <CardContent>
            <ReportSteps steps={report.steps} />
          </CardContent>
        </Card>
      )}
    </div>
  );
}
