import { Badge } from '@/shared/ui';

import { splitNewsContent } from '../../lib/parse-table';
import { EvidenceToggle } from '../EvidenceToggle';

interface EvidenceNewsProps {
  label: string;
  rawContent: string;
}

/**
 * 뉴스 근거. `참고` 배지가 고정이다 - 공시가 아니고, 수치는 공시로 다시 확인해야 한다.
 *
 * 추출 본문에 내비게이션 찌꺼기(`![한국경제](...)`, `ADVERTISEMENT`)가 섞여 있다.
 * **정제하지 않는다** - 손대는 순간 근거가 아니게 된다. 대신 접어서 스크롤 박스에 가둔다.
 * 마크다운으로 렌더하면 찌꺼기 이미지가 실제로 로드되므로 평문으로 둔다.
 */
export function EvidenceNews({ label, rawContent }: EvidenceNewsProps) {
  const { body } = splitNewsContent(rawContent);

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-start gap-2">
        <Badge variant="secondary">참고</Badge>

        <span className="min-w-0 text-sm font-medium wrap-break-word">
          {label}
        </span>
      </div>

      {body && (
        <EvidenceToggle label="추출 원문 보기" hint="정제하지 않은 그대로">
          <p className="max-h-64 overflow-y-auto rounded-md bg-muted p-3 text-xs leading-relaxed whitespace-pre-wrap wrap-break-word">
            {body}
          </p>
        </EvidenceToggle>
      )}
    </div>
  );
}
