import type { ReactNode } from 'react';

import type { ConflictSide } from '@/entities/report';
import { Badge } from '@/shared/ui';

import {
  CONFLICT_KIND_LABELS,
  RESOLUTION_LABELS,
  formatAsOf,
} from '../../lib/labels';

interface EvidenceConflictProps {
  sides?: ConflictSide[];
  conflictKind?: string;
  resolution?: string;
  rawContent: string;
  /**
   * 각 side 의 원본 조각을 그린다. EvidenceItem 이 넘겨준다 -
   * 여기서 직접 부르면 EvidenceItem 과 순환 임포트가 된다.
   */
  renderBasedOn: (evidenceId: string) => ReactNode;
}

/**
 * 출처 충돌 근거. **좌우 대조가 기본이고 한쪽만 보여주지 않는다.**
 *
 * `resolution` 이 `DART 채택` 이어도 버린 쪽을 지우지 않는다 - 무엇을 보고 무엇을 버렸는지가
 * 근거다. 충돌은 중간 계층이므로 각 side 에서 원본 조각까지 내려갈 수 있어야 한다.
 */
export function EvidenceConflict({
  sides,
  conflictKind,
  resolution,
  rawContent,
  renderBasedOn,
}: EvidenceConflictProps) {
  if (!sides || sides.length === 0) {
    return (
      <p className="text-sm whitespace-pre-wrap wrap-break-word">{rawContent}</p>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        {conflictKind && (
          <Badge variant="warning">
            {CONFLICT_KIND_LABELS[conflictKind] ?? conflictKind}
          </Badge>
        )}

        {resolution && (
          <Badge variant="outline">
            {RESOLUTION_LABELS[resolution] ?? resolution}
          </Badge>
        )}
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {sides.map((side) => {
          const asOf = formatAsOf(side.as_of, side.as_of_kind);

          return (
            <div
              key={side.based_on}
              className="rounded-md border border-border p-3"
            >
              <p className="text-xs text-muted-foreground">{side.label}</p>

              <p className="mt-1 text-sm font-medium wrap-break-word">
                {side.value}
              </p>

              {asOf && (
                <p className="mt-1 text-xs text-muted-foreground">{asOf}</p>
              )}

              <div className="mt-2">{renderBasedOn(side.based_on)}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
