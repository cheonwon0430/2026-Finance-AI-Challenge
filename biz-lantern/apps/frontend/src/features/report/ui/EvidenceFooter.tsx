import { ExternalLink } from 'lucide-react';

import type { EvidenceSource } from '@/entities/report';

import { formatAsOf } from '../lib/labels';

interface EvidenceFooterProps {
  source: EvidenceSource;
}

/**
 * 근거 공통 푸터 - 출처명 · 기준일 · 원문 링크.
 *
 * 기준일에 `as_of_kind`(조회일/기준일/발행일)를 반드시 함께 적는다. 같은 날짜라도 "조회한
 * 날" 과 "회계 기준일" 은 뜻이 전혀 다르다.
 */
export function EvidenceFooter({ source }: EvidenceFooterProps) {
  const asOf = formatAsOf(source.as_of, source.as_of_kind);

  return (
    <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-border pt-2 text-xs text-muted-foreground">
      <span>{source.name}</span>

      {asOf && <span>{asOf}</span>}

      {source.rcept_no && <span>접수번호 {source.rcept_no}</span>}

      {source.document_url && (
        <a
          href={source.document_url}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-1 text-primary underline-offset-2 hover:underline"
        >
          DART 원문
          <ExternalLink className="size-3 shrink-0" />
        </a>
      )}
    </div>
  );
}
