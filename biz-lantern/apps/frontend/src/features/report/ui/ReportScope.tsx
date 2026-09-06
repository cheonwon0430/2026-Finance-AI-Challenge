import type { Finding, ItemNarrative } from '@/entities/report';

import type { EvidenceIndex } from '../lib/evidence-index';
import { EvidenceToggle } from './EvidenceToggle';
import { ItemCard } from './ItemCard';

interface ReportScopeProps {
  findings: Record<string, Finding>;
  items: Record<string, ItemNarrative>;
  index: EvidenceIndex;
}

/**
 * 확인 범위와 한계.
 *
 * 본문에 쓰지 않은 것을 여기에 전부 모은다 - 게이트 판정(우리가 판정할 자격이 있는지
 * 확인한 절차)과, 확인하지 못했거나 대상이 아니었던 항목들.
 *
 * **숨기지 않고 자리를 옮기는 것이다.** "확인하지 못했다" 를 화면에서 빼는 것은
 * ABSENT 와 SOURCE_UNAVAILABLE 을 뭉개는 것과 같은 종류의 실수다. 다만 그것들이
 * 보고서 맨 앞에서 카드 여덟 장으로 도배되면 읽는 사람은 본문에 닿지도 못한다.
 */
export function ReportScope({ findings, items, index }: ReportScopeProps) {
  const all = Object.values(findings);

  const confirmed = all.filter((finding) => finding.verdict === 'CONFIRMED');
  const unconfirmed = all.filter((finding) => finding.verdict !== 'CONFIRMED');

  if (all.length === 0) {
    return null;
  }

  return (
    <section className="space-y-4">
      <div>
        <h2 className="border-b border-border pb-2 text-xl font-semibold">
          확인 범위와 한계
        </h2>
        <p className="mt-2 text-sm text-muted-foreground">
          {all.length}개 항목을 확인해 {confirmed.length}개에서 값을 확보했고{' '}
          {unconfirmed.length}개는 확보하지 못했다. 확보하지 못한 이유는 항목마다
          다르다 &mdash; 확인했으나 없었던 것과 확인 자체를 하지 못한 것은 서로 다른
          사실이다.
        </p>
      </div>

      {unconfirmed.length > 0 && (
        <EvidenceToggle
          label="값을 확보하지 못한 항목"
          hint={`${unconfirmed.length}건`}
          defaultOpen
        >
          <div className="space-y-4">
            {unconfirmed.map((finding) => (
              <ItemCard
                key={finding.item_id}
                finding={finding}
                narrative={items[finding.item_id]}
                index={index}
              />
            ))}
          </div>
        </EvidenceToggle>
      )}

      <EvidenceToggle
        label="확보한 항목의 판정과 근거 전체"
        hint={`${confirmed.length}건`}
      >
        <div className="space-y-4">
          {confirmed.map((finding) => (
            <ItemCard
              key={finding.item_id}
              finding={finding}
              narrative={items[finding.item_id]}
              index={index}
            />
          ))}
        </div>
      </EvidenceToggle>
    </section>
  );
}
