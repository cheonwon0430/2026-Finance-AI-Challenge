import type { EvidenceAccount } from '@/entities/report';

interface EvidenceAccountViewProps {
  rawContent: string;
  account?: EvidenceAccount;
}

/**
 * 재무제표 계정 근거.
 *
 * `raw` 는 문서가 인쇄한 문자열 그대로다(콤마 포함). `value` 로 덮어쓰지 않는다 -
 * 원문을 절대 덮어쓰지 않는다는 것이 파싱 계층의 기준선이고 후검증도 이 값으로 한다.
 */
export function EvidenceAccountView({
  rawContent,
  account,
}: EvidenceAccountViewProps) {
  const periods = Object.entries(account?.periods ?? {});

  return (
    <div className="space-y-3">
      {periods.length > 0 && (
        <dl className="grid gap-x-6 gap-y-2 sm:grid-cols-2">
          {periods.map(([key, period]) => (
            <div key={key} className="min-w-0">
              <dt className="text-xs text-muted-foreground">
                {period.header || key}
              </dt>
              <dd className="mt-0.5 text-sm font-medium wrap-break-word">
                {period.raw}
              </dd>
            </div>
          ))}
        </dl>
      )}

      <p className="text-sm whitespace-pre-wrap wrap-break-word">{rawContent}</p>

      {account && (
        <p className="text-xs text-muted-foreground">
          계정코드 {account.code || '없음'} · {account.logical_name}
        </p>
      )}
    </div>
  );
}
