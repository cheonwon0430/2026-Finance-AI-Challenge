import { TriangleAlert } from 'lucide-react';

import { Alert, AlertDescription, AlertTitle } from '@/shared/ui';

/** 상단 고정 면책. AI 생성의 한계와 투자 책임을 화면 맨 위에서 먼저 말한다. */
export function ReportDisclaimer() {
  return (
    <Alert variant="warning">
      <TriangleAlert />
      <AlertTitle>이 보고서는 AI가 공시 원문에서 생성한 것이다</AlertTitle>
      <AlertDescription>
        <p>
          모든 문장은 근거 조각으로 되돌아갈 수 있고, 문장 아래 토글에서 DART
          원문을 직접 확인할 수 있다. 다만 수집·판정·서술 각 단계에 한계가 있어
          누락과 오류가 있을 수 있다.
        </p>
        <p>투자 판단과 그 결과에 대한 책임은 이용자 본인에게 있다.</p>
      </AlertDescription>
    </Alert>
  );
}
