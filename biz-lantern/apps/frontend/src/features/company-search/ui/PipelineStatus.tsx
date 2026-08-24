import { CheckCircle2, ListChecks, XCircle } from 'lucide-react';

import type { PipelineStep } from '@/entities/company';
import { Badge, Card, CardContent, CardHeader, CardTitle, Separator } from '@/shared/ui';
import { cn } from '@/shared/lib';

interface PipelineStatusProps {
  steps: PipelineStep[];
}

export function PipelineStatus({ steps }: PipelineStatusProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <ListChecks className="size-4 text-muted-foreground" />
          분석 파이프라인 처리 상태
        </CardTitle>
      </CardHeader>

      <CardContent>
        <ol className="space-y-3">
          {steps.map((step, index) => {
            const isOk = step.status === 'ok';

            return (
              <li key={step.step}>
                <div className="flex items-start gap-3">
                  <div
                    className={cn(
                      'mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold',
                      isOk
                        ? 'bg-primary-container text-primary-container-foreground'
                        : 'bg-destructive-container text-destructive-container-foreground',
                    )}
                  >
                    {isOk ? (
                      <CheckCircle2 className="size-4" />
                    ) : (
                      <XCircle className="size-4" />
                    )}
                  </div>

                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-sm font-medium">
                        {step.step}/{step.total}. {step.name}
                      </span>

                      <Badge variant={isOk ? 'success' : 'destructive'}>
                        {isOk ? '성공' : '실패'}
                      </Badge>
                    </div>

                    {step.detail && (
                      <p className="mt-1 text-xs break-words text-muted-foreground">
                        {step.detail}
                      </p>
                    )}
                  </div>
                </div>

                {index < steps.length - 1 && (
                  <Separator className="mt-3 ml-3" orientation="horizontal" />
                )}
              </li>
            );
          })}
        </ol>
      </CardContent>
    </Card>
  );
}
