/**
 * 판정값·문장 종류·근거 유형의 표시 라벨과 배지 variant.
 *
 * 백엔드는 영문 enum 을 내려보내고 화면 문구는 전부 여기에서 나온다. 특히 판정값 다섯은
 * **색을 뭉개면 안 된다** - ABSENT(확인했으나 없었다)와 SOURCE_UNAVAILABLE(확인하지
 * 못했다)은 서로 다른 사건이고, 이 둘을 같게 보이게 하는 것이 이 프로젝트가 가장 경계하는
 * 실수다. EXTRACTION_FAILED 와 SOURCE_UNAVAILABLE 은 같은 warning 이지만 라벨과 아이콘이
 * 다르다 - destructive 로 올리면 "실패" 로 읽혀 과하다.
 */
import {
  CircleCheck,
  CircleMinus,
  CircleQuestionMark,
  FileX,
  Slash,
  type LucideIcon,
} from 'lucide-react';

import type {
  EvidenceType,
  Sentence,
  Verdict,
} from '@/entities/report';

/** badge.tsx 의 variant 이름. Badge 가 타입을 내보내지 않아 여기서 좁힌다. */
type BadgeVariant =
  | 'default'
  | 'secondary'
  | 'outline'
  | 'success'
  | 'warning'
  | 'destructive'
  | 'muted';

interface VerdictDisplay {
  label: string;
  variant: BadgeVariant;
  icon: LucideIcon;
  /** 배지만으로 뜻이 전달되지 않으므로 title 로 한 줄 더 붙인다. */
  description: string;
}

export const VERDICT_DISPLAY: Record<Verdict, VerdictDisplay> = {
  CONFIRMED: {
    label: '확인',
    variant: 'success',
    icon: CircleCheck,
    description: '값을 확보했다',
  },
  ABSENT: {
    label: '부재 확인',
    variant: 'muted',
    icon: CircleMinus,
    description: '확인했으나 없었다',
  },
  NOT_REQUIRED: {
    label: '해당 없음',
    variant: 'outline',
    icon: Slash,
    description: '애초에 공시의무가 없다',
  },
  EXTRACTION_FAILED: {
    label: '읽지 못함',
    variant: 'warning',
    icon: FileX,
    description: '문서는 있는데 파싱하지 못했다',
  },
  SOURCE_UNAVAILABLE: {
    label: '확인 불가',
    variant: 'warning',
    icon: CircleQuestionMark,
    description: '문서·출처 자체를 확보하지 못했다',
  },
};

/**
 * 문장 종류의 배지. confirmed 는 기본값이라 배지를 붙이지 않는다 - 전부에 배지를 달면
 * 정작 구분해야 할 추론·참고가 묻힌다.
 */
export const SENTENCE_KIND_DISPLAY: Record<
  Sentence['kind'],
  { label: string; variant: BadgeVariant } | null
> = {
  confirmed: null,
  inferred: { label: '추론', variant: 'default' },
  reference: { label: '참고', variant: 'secondary' },
};

export const EVIDENCE_TYPE_LABELS: Record<EvidenceType, string> = {
  api_field: 'API 필드',
  summary: '공시 요약정보',
  account: '재무제표 계정',
  table: '표',
  paragraph: '문단',
  note: '주석',
  derived: '파생 계산',
  conflict: '출처 충돌',
  news: '뉴스',
};

/** 충돌 유형. 백엔드가 영문 enum 으로 내려준다(evidence.CONFLICT_KIND_LABELS 와 짝). */
export const CONFLICT_KIND_LABELS: Record<string, string> = {
  timing: '시점 차이',
  reliability: '신뢰도 차이',
  identity: '식별자 대조 불가',
};

export const RESOLUTION_LABELS: Record<string, string> = {
  both: '병기',
  dart_first: 'DART 채택',
};

/** `2026-09-06` 과 `조회일` 을 합쳐 `조회일 2026-09-06` 으로. 둘 다 없으면 null. */
export const formatAsOf = (
  asOf: string | null,
  asOfKind: string | null,
): string | null => {
  if (!asOf) {
    return null;
  }

  return asOfKind ? `${asOfKind} ${asOf}` : asOf;
};

/** `20260906020309` 형태의 report_id 꼬리를 사람이 읽는 시각으로. */
export const formatTimestamp = (value: string | null): string | null => {
  if (!value) {
    return null;
  }

  const parsed = new Date(value);

  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return parsed.toLocaleString('ko-KR');
};
