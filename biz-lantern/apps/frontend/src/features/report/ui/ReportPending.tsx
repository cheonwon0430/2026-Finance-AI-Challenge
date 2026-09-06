import { useEffect, useState } from 'react';
import { LoaderCircle } from 'lucide-react';

import { Card, CardContent } from '@/shared/ui';

interface ReportPendingProps {
  createdAt: string;
}

const TICK_MS = 1000;
const SECONDS_PER_MINUTE = 60;

const elapsedSeconds = (createdAt: string) => {
  const started = new Date(createdAt).getTime();

  if (Number.isNaN(started)) {
    return null;
  }

  return Math.max(0, Math.floor((Date.now() - started) / 1000));
};

const formatElapsed = (seconds: number) => {
  const minutes = Math.floor(seconds / SECONDS_PER_MINUTE);
  const rest = seconds % SECONDS_PER_MINUTE;

  return minutes > 0 ? `${minutes}분 ${rest}초` : `${rest}초`;
};

/**
 * 생성 중 화면.
 *
 * PENDING 동안에는 본문이 전부 비어 있다 - `steps` 도 아직 없으므로 진행률을 보여줄 방법이
 * 없다. 없는 진행률을 지어내는 대신 경과 시간만 정직하게 센다.
 */
export function ReportPending({ createdAt }: ReportPendingProps) {
  const [seconds, setSeconds] = useState(() => elapsedSeconds(createdAt));

  useEffect(() => {
    const timer = setInterval(
      () => setSeconds(elapsedSeconds(createdAt)),
      TICK_MS,
    );

    return () => clearInterval(timer);
  }, [createdAt]);

  return (
    <Card>
      <CardContent className="flex items-start gap-3 pt-6">
        <LoaderCircle className="mt-0.5 size-5 shrink-0 animate-spin text-muted-foreground" />

        <div>
          <p className="font-medium">보고서를 만들고 있다</p>

          <p className="mt-1 text-sm text-muted-foreground">
            DART 감사보고서 3개년과 뉴스를 수집해 25개 항목을 판정한다. 수십
            초에서 몇 분이 걸리며, 완료되면 이 화면이 자동으로 바뀐다.
          </p>

          {seconds !== null && (
            <p className="mt-2 text-sm text-muted-foreground">
              경과 {formatElapsed(seconds)}
            </p>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
