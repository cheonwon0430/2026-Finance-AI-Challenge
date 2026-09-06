import type { Finding, ItemNarrative } from '@/entities/report';
import {
  Badge,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/shared/ui';

import { VERDICT_DISPLAY } from '../lib/labels';
import type { EvidenceIndex } from '../lib/evidence-index';
import { EvidenceList } from './EvidenceItem';
import { EvidenceToggle } from './EvidenceToggle';
import { SentenceRow } from './SentenceRow';

interface ItemCardProps {
  finding: Finding;
  narrative?: ItemNarrative;
  index: EvidenceIndex;
}

/** LLM 을 부르지 않은 것은 실패가 아니다 - CONFIRMED 가 아닌 항목은 아예 부르지 않는다. */
const NORMAL_LLM_STATUS = ['ok', 'skipped'];

/**
 * 항목 카드 = 제목 + 판정 배지 + 문장 + 근거 토글.
 *
 * `finding.warnings` 를 따로 그리지 않는다. compose 가 경고를 원문 그대로 `reference`
 * 문장으로 승격시켜 두었으므로 여기서 또 그리면 같은 문장이 두 번 나온다.
 */
export function ItemCard({ finding, narrative, index }: ItemCardProps) {
  const verdict = VERDICT_DISPLAY[finding.verdict];
  const VerdictIcon = verdict.icon;

  const llmFailed =
    narrative !== undefined &&
    !NORMAL_LLM_STATUS.includes(narrative.llm_status);

  const dropped = narrative?.dropped ?? [];

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle className="flex items-center gap-2">
            <span className="text-xs font-normal text-muted-foreground">
              {finding.item_id}
            </span>
            {finding.label}
          </CardTitle>

          <Badge variant={verdict.variant} title={verdict.description}>
            <VerdictIcon className="size-3 shrink-0" />
            {verdict.label}
          </Badge>
        </div>
      </CardHeader>

      <CardContent className="space-y-3">
        <ul className="space-y-2">
          {narrative?.sentences.map((sentence, sentenceIndex) => (
            <SentenceRow
              key={`${sentence.text}-${sentenceIndex}`}
              sentence={sentence}
              index={index}
            />
          ))}
        </ul>

        {llmFailed && (
          <p className="text-xs text-muted-foreground">
            AI 서술을 생성하지 못해 기본 문장만 표시한다
            {narrative?.llm_error ? ` · ${narrative.llm_error}` : ''}
          </p>
        )}

        {dropped.length > 0 && (
          <EvidenceToggle
            label="검증에서 제외된 문장"
            hint={`${dropped.length}건`}
          >
            <ul className="space-y-2">
              {dropped.map((item, droppedIndex) => (
                <li
                  key={`${item.text}-${droppedIndex}`}
                  className="rounded-md border border-border border-dashed p-3"
                >
                  <p className="text-sm text-muted-foreground line-through wrap-break-word">
                    {item.text}
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {item.reasons.join(' · ')}
                  </p>
                </li>
              ))}
            </ul>
          </EvidenceToggle>
        )}

        <EvidenceList
          ids={finding.evidence_ids}
          index={index}
          toggleLabel="이 항목이 확인한 근거 전체"
        />
      </CardContent>
    </Card>
  );
}
