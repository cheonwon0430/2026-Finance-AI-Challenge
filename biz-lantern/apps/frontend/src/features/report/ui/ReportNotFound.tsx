import { Link } from 'react-router';

import { Alert, AlertDescription, AlertTitle } from '@/shared/ui';

interface ReportNotFoundProps {
  reportId: string;
}

/**
 * 그런 보고서가 없다.
 *
 * 생성에 실패한 보고서(FAILED)와 **다른 사건이다.** 그쪽은 만들려다 실패한 기록이 남아
 * 있고, 이쪽은 애초에 그런 id 가 없다.
 */
export function ReportNotFound({ reportId }: ReportNotFoundProps) {
  return (
    <div className="space-y-4">
      <Alert>
        <AlertTitle>그런 보고서가 없다</AlertTitle>
        <AlertDescription>
          <p className="wrap-break-word">
            보고서 <span className="font-medium">{reportId}</span> 를 찾을 수
            없다. 주소가 잘못됐거나 아직 생성한 적이 없는 보고서다.
          </p>
        </AlertDescription>
      </Alert>

      <Link
        to="/companies"
        className="inline-flex rounded-md bg-primary px-5 py-3 text-primary-foreground"
      >
        기업 검색으로 가기
      </Link>
    </div>
  );
}
