import { Badge } from '@/shared/ui';

interface EvidenceDerivedProps {
  rawContent: string;
  formula?: string;
  ruleId?: string;
}

/**
 * F 블록 파생 근거. 룰베이스가 계산한 것이고 LLM 은 이 결과를 문장으로 옮기기만 한다.
 *
 * 계산식을 반드시 함께 보여준다 - 무엇을 어떻게 더했는지가 파생값의 근거다.
 * 원본 조각으로 내려가는 `based_on` 확장은 EvidenceItem 이 아래에 붙인다.
 */
export function EvidenceDerived({
  rawContent,
  formula,
  ruleId,
}: EvidenceDerivedProps) {
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        {ruleId && <Badge variant="outline">{ruleId}</Badge>}

        <span className="text-sm font-medium wrap-break-word">
          {rawContent}
        </span>
      </div>

      {formula && (
        <p className="text-xs text-muted-foreground wrap-break-word">
          계산식 · {formula}
        </p>
      )}
    </div>
  );
}
