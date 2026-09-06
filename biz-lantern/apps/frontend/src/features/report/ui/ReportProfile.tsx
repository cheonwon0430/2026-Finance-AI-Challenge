import type { Finding } from '@/entities/report';
import { Card, CardContent } from '@/shared/ui';

/** 머리말에 나열할 항목. 값 자체가 결론이라 서술할 것이 없다. */
const PROFILE_ITEMS = ['A-1', 'A-2', 'A-3'];

interface ReportProfileProps {
  findings: Record<string, Finding>;
}

/**
 * 법인 기본정보. 문장으로 풀지 않고 그대로 나열한다.
 *
 * "(주)센트비의 대표는 최성욱이며 2015-09-23에 설립됐다" 는 값을 문장으로 늘린 것일
 * 뿐이라 읽는 사람에게 이득이 없다. 이 자리는 표가 맞다.
 */
export function ReportProfile({ findings }: ReportProfileProps) {
  const rows = PROFILE_ITEMS.map((itemId) => findings[itemId]).filter(
    (finding): finding is Finding => Boolean(finding?.value),
  );

  if (rows.length === 0) {
    return null;
  }

  return (
    <Card>
      <CardContent className="pt-6">
        <dl className="grid gap-x-6 gap-y-4 sm:grid-cols-2">
          {rows.map((finding) => (
            <div key={finding.item_id} className="min-w-0">
              <dt className="text-xs text-muted-foreground">
                {finding.label}
              </dt>
              <dd className="mt-1 text-sm font-medium wrap-break-word">
                {finding.value}
              </dd>
            </div>
          ))}
        </dl>

        {rows.some((finding) => finding.warnings.length > 0) && (
          <ul className="mt-4 space-y-1 border-t border-border pt-3">
            {rows.flatMap((finding) =>
              finding.warnings.map((warning) => (
                <li
                  key={`${finding.item_id}-${warning}`}
                  className="text-xs text-muted-foreground wrap-break-word"
                >
                  {warning}
                </li>
              )),
            )}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
