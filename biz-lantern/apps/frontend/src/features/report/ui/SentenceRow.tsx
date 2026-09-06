import type { Sentence } from '@/entities/report';
import { Badge } from '@/shared/ui';
import { cn } from '@/shared/lib';

import { SENTENCE_KIND_DISPLAY } from '../lib/labels';
import type { EvidenceIndex } from '../lib/evidence-index';
import { EvidenceList } from './EvidenceItem';

interface SentenceRowProps {
  sentence: Sentence;
  index: EvidenceIndex;
}

/**
 * 문장 하나 + 그 문장이 인용한 근거.
 *
 * 근거는 **그 문장의 `evidence_ids` 만** 연다. 항목 전체의 근거는 카드 하단에 따로 있다 -
 * 둘은 다른 질문이다("이 주장의 근거는?" vs "이 항목이 무엇을 봤나?").
 *
 * `origin`(rule/llm)은 배지로 드러내지 않는다. 룰베이스 정형문만 남은 보고서도 완결이고,
 * AI 생성이라는 사실은 상단 면책이 이미 말한다.
 */
export function SentenceRow({ sentence, index }: SentenceRowProps) {
  const kind = SENTENCE_KIND_DISPLAY[sentence.kind];
  // caveat 는 중립색으로 둔다. tertiary(teal)를 쓰면 SOURCE_UNAVAILABLE 배지와 같은 색이라
  // ABSENT 카드와 SOURCE_UNAVAILABLE 카드가 통째로 비슷해 보인다 - 구분은 배지가 한다.
  const isCaveat = sentence.kind === 'reference';

  return (
    <li
      className={cn(
        'rounded-md px-3 py-2',
        isCaveat && 'bg-muted text-muted-foreground',
      )}
    >
      <div className="flex flex-wrap items-start gap-2">
        {kind && <Badge variant={kind.variant}>{kind.label}</Badge>}

        <p className="min-w-0 flex-1 text-sm leading-relaxed wrap-break-word">
          {sentence.text}
        </p>
      </div>

      {sentence.evidence_ids.length > 0 && (
        <EvidenceList
          ids={sentence.evidence_ids}
          index={index}
          toggleLabel="이 문장의 근거"
        />
      )}
    </li>
  );
}
