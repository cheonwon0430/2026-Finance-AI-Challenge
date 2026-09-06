import type { ReportStep } from '@/entities/report';
import { Badge } from '@/shared/ui';
import { cn } from '@/shared/lib';

interface ReportStepsProps {
  steps: ReportStep[];
}

/** 수집 진행 기록. 어디까지 갔는지가 실패의 근거다. */
export function ReportSteps({ steps }: ReportStepsProps) {
  if (steps.length === 0) {
    return null;
  }

  return (
    <ul className="space-y-3">
      {steps.map((step) => {
        const isOk = step.status === 'ok';

        return (
          <li key={`${step.step}-${step.name}`} className="flex gap-3">
            <span
              className={cn(
                'mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold',
                isOk
                  ? 'bg-primary-container text-primary-container-foreground'
                  : 'bg-destructive-container text-destructive-container-foreground',
              )}
            >
              {step.step}
            </span>

            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-sm font-medium">{step.name}</span>
                <Badge variant={isOk ? 'success' : 'destructive'}>
                  {isOk ? '성공' : '실패'}
                </Badge>
              </div>

              {step.detail && (
                <p className="mt-1 text-sm text-muted-foreground wrap-break-word">
                  {step.detail}
                </p>
              )}
            </div>
          </li>
        );
      })}
    </ul>
  );
}
