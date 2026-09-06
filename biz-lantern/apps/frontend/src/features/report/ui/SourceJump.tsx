import { useState } from 'react';
import { Check, Copy, ExternalLink } from 'lucide-react';

import type { Evidence } from '@/entities/report';

import { buildSearchTerm } from '../lib/citation';

interface SourceJumpProps {
  evidence: Evidence;
}

const COPIED_MS = 1600;

/**
 * 원문에서 이 대목을 직접 찾게 해 주는 줄.
 *
 * 링크만 달면 사용자가 수천 자 문서에서 어디를 봐야 하는지 직접 찾아야 한다. DART
 * 뷰어 구조상 문단 딥링크는 만들 수 없으므로, 원문에 그대로 있는 문구를 주고
 * 복사 -> 원문 열기 -> Ctrl+F 로 잇는다.
 */
export function SourceJump({ evidence }: SourceJumpProps) {
  const [copied, setCopied] = useState(false);
  const term = buildSearchTerm(evidence);

  if (!term) {
    return null;
  }

  const copy = () => {
    void navigator.clipboard?.writeText(term).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), COPIED_MS);
    });
  };

  return (
    <div className="mt-2 rounded-md bg-muted p-2">
      <p className="text-xs text-muted-foreground">
        원문에서 이 문구를 찾으면 된다
      </p>

      <div className="mt-1 flex flex-wrap items-center gap-2">
        <code className="min-w-0 flex-1 text-xs wrap-break-word">{term}</code>

        <button
          type="button"
          onClick={copy}
          className="inline-flex shrink-0 items-center gap-1 rounded-md border border-border px-2 py-1 text-xs transition-colors hover:bg-background focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
        >
          {copied ? <Check className="size-3" /> : <Copy className="size-3" />}
          {copied ? '복사됨' : '복사'}
        </button>

        {evidence.source.document_url && (
          <a
            href={evidence.source.document_url}
            target="_blank"
            rel="noreferrer"
            className="inline-flex shrink-0 items-center gap-1 rounded-md border border-border px-2 py-1 text-xs text-primary transition-colors hover:bg-background"
          >
            원문 열기
            <ExternalLink className="size-3" />
          </a>
        )}
      </div>
    </div>
  );
}
