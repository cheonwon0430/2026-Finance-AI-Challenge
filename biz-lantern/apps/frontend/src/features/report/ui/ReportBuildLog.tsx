import type { ReportResponse } from '@/entities/report';

import { EvidenceToggle } from './EvidenceToggle';
import { ReportSteps } from './ReportSteps';

interface ReportBuildLogProps {
  report: ReportResponse;
}

/**
 * 생성 기록.
 *
 * `errors` 가 있어도 **보고서는 정상이다.** LLM 이 일부 죽어도 룰베이스 정형문이 남아
 * 25항목 전부 문장이 있다. 그래서 이것을 오류 배너로 올리지 않고 접힌 채로 맨 아래 둔다 -
 * 숨기는 게 아니라 무게를 맞추는 것이다.
 */
export function ReportBuildLog({ report }: ReportBuildLogProps) {
  const hasLog =
    report.steps.length > 0 ||
    report.errors.length > 0 ||
    report.orphan_derived.length > 0;

  if (!hasLog) {
    return null;
  }

  return (
    <section>
      <EvidenceToggle label="생성 기록" hint={`수집 ${report.steps.length}단계`}>
        <div className="space-y-4 rounded-lg border border-border p-4">
          <ReportSteps steps={report.steps} />

          {report.errors.length > 0 && (
            <div>
              <h3 className="text-sm font-medium">서술 단계에서 생긴 문제</h3>
              <ul className="mt-2 space-y-1">
                {report.errors.map((error, errorIndex) => (
                  <li
                    key={`${error.item_id ?? 'all'}-${errorIndex}`}
                    className="text-sm text-muted-foreground wrap-break-word"
                  >
                    {error.item_id ?? '보고서 전체'} · {error.message}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {report.orphan_derived.length > 0 && (
            <div>
              <h3 className="text-sm font-medium">
                어느 항목에도 붙지 않은 파생 근거
              </h3>
              <ul className="mt-2 space-y-1">
                {report.orphan_derived.map((evidenceId) => (
                  <li
                    key={evidenceId}
                    className="text-sm text-muted-foreground wrap-break-word"
                  >
                    {evidenceId}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </EvidenceToggle>
    </section>
  );
}
