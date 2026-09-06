/**
 * 근거 조각 하나를 그린다. 유형으로 렌더러를 고르고, 파생·충돌은 원본까지 내려간다.
 *
 * **파생·충돌은 중간 계층이지 종착점이 아니다.** 어떤 경로로 열든 최종적으로 DART 원문
 * (표·문단) 스냅샷에 도달해야 한다. 그래서 `based_on` 확장을 반드시 붙인다.
 *
 * EvidenceItem 과 EvidenceList 가 서로를 부르므로 **같은 파일에 둔다** - 두 파일로 나누면
 * 순환 임포트가 되고 번들러에 따라 초기화 순서로 깨진다.
 */
import { Badge } from '@/shared/ui';
import type { Evidence } from '@/entities/report';

import { EVIDENCE_TYPE_LABELS } from '../lib/labels';
import { resolveEvidence, type EvidenceIndex } from '../lib/evidence-index';
import { EvidenceAccountView } from './evidence/EvidenceAccountView';
import { EvidenceApiField } from './evidence/EvidenceApiField';
import { EvidenceConflict } from './evidence/EvidenceConflict';
import { EvidenceDerived } from './evidence/EvidenceDerived';
import { EvidenceNews } from './evidence/EvidenceNews';
import { EvidenceTable } from './evidence/EvidenceTable';
import { EvidenceText } from './evidence/EvidenceText';
import { EvidenceFooter } from './EvidenceFooter';
import { SourceJump } from './SourceJump';
import { EvidenceToggle } from './EvidenceToggle';

/** 실측상 2단이면 원문에 닿는다. 그래도 무한 확장은 막는다. */
const MAX_DEPTH = 3;

interface EvidenceItemProps {
  evidence: Evidence;
  index: EvidenceIndex;
  depth: number;
  visited: ReadonlySet<string>;
}

function EvidenceBody({
  evidence,
  index,
  depth,
  visited,
}: EvidenceItemProps) {
  switch (evidence.type) {
    case 'table':
      return <EvidenceTable rawContent={evidence.raw_content} />;

    case 'account':
      return (
        <EvidenceAccountView
          rawContent={evidence.raw_content}
          account={evidence.account}
        />
      );

    case 'api_field':
      return (
        <EvidenceApiField
          rawContent={evidence.raw_content}
          context={evidence.context}
        />
      );

    case 'derived':
      return (
        <EvidenceDerived
          rawContent={evidence.raw_content}
          formula={evidence.formula}
          ruleId={evidence.rule_id}
        />
      );

    case 'conflict':
      return (
        <EvidenceConflict
          sides={evidence.sides}
          conflictKind={evidence.conflict_kind}
          resolution={evidence.resolution}
          rawContent={evidence.raw_content}
          renderBasedOn={(evidenceId) => (
            <EvidenceList
              ids={[evidenceId]}
              index={index}
              depth={depth + 1}
              visited={visited}
              toggleLabel="원본 근거"
            />
          )}
        />
      );

    case 'news':
      return (
        <EvidenceNews label={evidence.label} rawContent={evidence.raw_content} />
      );

    default:
      return <EvidenceText rawContent={evidence.raw_content} />;
  }
}

export function EvidenceItem({
  evidence,
  index,
  depth,
  visited,
}: EvidenceItemProps) {
  const nextVisited = new Set(visited).add(evidence.evidence_id);

  // 충돌은 side 안에서 각자 based_on 을 펼치므로 여기서 또 펼치면 같은 조각이 두 번 나온다.
  const showBasedOn =
    evidence.type !== 'conflict' && (evidence.based_on?.length ?? 0) > 0;

  return (
    <div className="rounded-md border border-border bg-card p-3">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <Badge variant="muted">{EVIDENCE_TYPE_LABELS[evidence.type]}</Badge>

        {evidence.type !== 'news' && (
          <span className="min-w-0 text-xs text-muted-foreground wrap-break-word">
            {evidence.label}
          </span>
        )}
      </div>

      <EvidenceBody
        evidence={evidence}
        index={index}
        depth={depth}
        visited={nextVisited}
      />

      {showBasedOn && (
        <EvidenceToggle
          className="mt-3"
          label="계산에 쓰인 근거"
          hint={`${evidence.based_on?.length}건`}
        >
          <EvidenceList
            ids={evidence.based_on ?? []}
            index={index}
            depth={depth + 1}
            visited={nextVisited}
          />
        </EvidenceToggle>
      )}

      <SourceJump evidence={evidence} />

      <EvidenceFooter source={evidence.source} />
    </div>
  );
}

interface EvidenceListProps {
  ids: string[];
  index: EvidenceIndex;
  depth?: number;
  visited?: ReadonlySet<string>;
  emptyText?: string;
  /** 지정하면 목록 전체를 그 라벨의 토글 안에 넣는다. */
  toggleLabel?: string;
}

const EMPTY_VISITED: ReadonlySet<string> = new Set();

/**
 * 근거 id 목록을 조각으로 그린다.
 *
 * 장부에 없는 id 를 **조용히 건너뛰지 않는다.** 문장이 셋을 인용했는데 둘만 뜨면 사용자는
 * 그 사실조차 알 수 없다.
 */
export function EvidenceList({
  ids,
  index,
  depth = 0,
  visited = EMPTY_VISITED,
  emptyText,
  toggleLabel,
}: EvidenceListProps) {
  const { found, missing } = resolveEvidence(index, ids);

  if (found.length === 0 && missing.length === 0) {
    return emptyText ? (
      <p className="text-sm text-muted-foreground">{emptyText}</p>
    ) : null;
  }

  const body = (
    <ul className="space-y-3">
      {found.map((evidence) => (
        <li key={evidence.evidence_id}>
          {visited.has(evidence.evidence_id) ? (
            <p className="rounded-md border border-border border-dashed p-3 text-xs text-muted-foreground wrap-break-word">
              위에서 이미 펼친 근거다 · {evidence.label}
            </p>
          ) : depth > MAX_DEPTH ? (
            <p className="rounded-md border border-border border-dashed p-3 text-xs text-muted-foreground wrap-break-word">
              더 깊이 펼치지 않는다 · {evidence.label}
            </p>
          ) : (
            <EvidenceItem
              evidence={evidence}
              index={index}
              depth={depth}
              visited={visited}
            />
          )}
        </li>
      ))}

      {missing.map((evidenceId) => (
        <li key={evidenceId}>
          <p className="rounded-md bg-tertiary-container p-3 text-xs text-tertiary-container-foreground wrap-break-word">
            근거 조각을 찾지 못했다 · {evidenceId}
          </p>
        </li>
      ))}
    </ul>
  );

  if (!toggleLabel) {
    return body;
  }

  return (
    <EvidenceToggle
      label={toggleLabel}
      hint={`${found.length + missing.length}건`}
    >
      {body}
    </EvidenceToggle>
  );
}
