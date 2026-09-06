import { useState } from 'react';

import type { Paragraph } from '@/entities/report';
import { Badge } from '@/shared/ui';
import { cn } from '@/shared/lib';

import { paragraphEvidenceIds } from '../lib/citation';
import { SENTENCE_KIND_DISPLAY } from '../lib/labels';
import type { EvidenceIndex } from '../lib/evidence-index';
import { EvidenceList } from './EvidenceItem';

interface ParagraphBlockProps {
  paragraph: Paragraph;
  index: EvidenceIndex;
}

/**
 * 본문 문단 하나.
 *
 * 인용을 두 층으로 단다. 문장마다 번호를 붙여 그 문장의 근거만 열 수 있게 하고,
 * 문단 끝에는 그 문단이 쓴 근거 전체를 한 번에 연다. 문장마다 근거를 펼쳐 두면
 * 같은 조각이 여러 번 반복돼 글이 읽히지 않는다.
 */
export function ParagraphBlock({ paragraph, index }: ParagraphBlockProps) {
  const [openSentence, setOpenSentence] = useState<number | null>(null);

  const ids = paragraphEvidenceIds(paragraph.sentences);

  return (
    <div className="space-y-2">
      <p className="leading-relaxed">
        {paragraph.sentences.map((sentence, position) => {
          const kind = SENTENCE_KIND_DISPLAY[sentence.kind];
          const isOpen = openSentence === position;

          return (
            <span key={`${sentence.text}-${position}`}>
              {sentence.text}

              {kind && (
                <Badge variant={kind.variant} className="mx-1 align-middle">
                  {kind.label}
                </Badge>
              )}

              {sentence.evidence_ids.length > 0 && (
                <button
                  type="button"
                  onClick={() => setOpenSentence(isOpen ? null : position)}
                  aria-expanded={isOpen}
                  title="이 문장의 근거"
                  className={cn(
                    'mx-0.5 rounded-sm px-1 align-super text-[0.7em] transition-colors',
                    isOpen
                      ? 'bg-primary text-primary-foreground'
                      : 'bg-muted text-muted-foreground hover:bg-secondary',
                  )}
                >
                  {position + 1}
                </button>
              )}{' '}
            </span>
          );
        })}
      </p>

      {openSentence !== null && (
        <EvidenceList
          ids={paragraph.sentences[openSentence]?.evidence_ids ?? []}
          index={index}
        />
      )}

      {ids.length > 0 && (
        <EvidenceList ids={ids} index={index} toggleLabel="이 문단의 출처 확인" />
      )}
    </div>
  );
}
