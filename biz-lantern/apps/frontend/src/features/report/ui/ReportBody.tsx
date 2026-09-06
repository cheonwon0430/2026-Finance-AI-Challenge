import type { SectionNarrative } from '@/entities/report';

import type { EvidenceIndex } from '../lib/evidence-index';
import { ParagraphBlock } from './ParagraphBlock';

interface ReportBodyProps {
  sections: SectionNarrative[];
  index: EvidenceIndex;
}

/**
 * 보고서 본문. 절 -> 문단 -> 문장 순서다.
 *
 * 항목(G-1, B-1 …)은 여기에 나오지 않는다. 그것은 우리가 판정을 내린 단위이지 읽는
 * 사람이 읽을 단위가 아니다. 항목별 판정과 근거는 '확인 범위와 한계' 에 그대로 있다.
 */
export function ReportBody({ sections, index }: ReportBodyProps) {
  if (sections.length === 0) {
    return null;
  }

  return (
    <div className="space-y-10">
      {sections.map((section) => (
        <section key={section.section} className="space-y-4">
          <h2 className="border-b border-border pb-2 text-xl font-semibold">
            {section.title}
          </h2>

          <div className="space-y-5">
            {section.paragraphs.map((paragraph, position) => (
              <ParagraphBlock
                key={`${section.section}-${position}`}
                paragraph={paragraph}
                index={index}
              />
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
