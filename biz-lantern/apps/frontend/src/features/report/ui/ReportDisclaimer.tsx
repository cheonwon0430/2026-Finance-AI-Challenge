import { TriangleAlert } from 'lucide-react';

import { Alert, AlertDescription, AlertTitle } from '@/shared/ui';

/** 상단 고정 면책. AI 생성의 한계와 투자 책임을 화면 맨 위에서 먼저 말한다. */
export function ReportDisclaimer() {
  return (
    <Alert variant="warning">
      <TriangleAlert />
      <AlertTitle>이 보고서는 AI가 공시 원문에서 생성한 것입니다</AlertTitle>
      <AlertDescription>
        <p>
          본 보고서는 공개된 정보를 기반으로 AI를 활용하여 생성한 참고자료이며, 투자 권유 또는 투자판단을 위한 확정적 정보가 아닙니다.
        </p>
        <p>
          각 문장의 근거는 하단 토글을 통해 DART 원문에서 직접 확인할 수 있습니다. 다만 정보의 수집·처리·판정 및 서술 과정에서 오류나 누락이 발생할 수 있으므로, 원문과 근거를 직접 확인한 후 최종적인 판단과 의사결정을 하시기 바랍니다.
        </p>
        <p>또한, 최종적인 판단과 의사결정은 이용자가 제공된 근거를 확인한 후 이루어져야 합니다</p>
      </AlertDescription>
    </Alert>
  );
}
