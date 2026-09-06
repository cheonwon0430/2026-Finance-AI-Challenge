/**
 * 인용을 원문으로 되돌리는 도구.
 *
 * DART 뷰어는 프레임셋이고 실제 문서는 우리가 갖고 있지 않은 `dcmNo` 로 iframe 에 뜬다.
 * 그래서 **문단 단위 딥링크는 원리적으로 만들 수 없다.** 대신 우리는 원문 스냅샷을
 * 통째로 갖고 있으므로, 그 안에서 뽑은 고유한 문구를 준다. 원문 링크를 열고 Ctrl+F 로
 * 붙여넣으면 바로 그 자리로 간다 - 통짜 스냅샷만 주고 직접 찾으라고 하는 것보다 낫다.
 */
import type { Evidence } from '@/entities/report';

/** Ctrl+F 한 번에 걸릴 만큼 길고, 원문에 그대로 있을 만큼 짧게. */
const TERM_MIN = 10;
const TERM_MAX = 28;

const collapse = (text: string) => text.replace(/\s+/g, ' ').trim();

/** 문장 중간에서 끊지 않도록 마지막 공백에서 자른다. */
const clip = (text: string) => {
  const flat = collapse(text);

  if (flat.length <= TERM_MAX) {
    return flat;
  }

  const head = flat.slice(0, TERM_MAX);
  const lastSpace = head.lastIndexOf(' ');

  return lastSpace >= TERM_MIN ? head.slice(0, lastSpace) : head;
};

/** 표 원문에서 값이 든 첫 데이터 행을 고른다(단위 캡션·헤더 행은 건너뛴다). */
const tableTerm = (rawContent: string): string | null => {
  const rows = rawContent.split('\n').map((line) => line.split(' | '));

  for (const cells of rows) {
    // 숫자가 든 행이라야 원문에서 유일할 가능성이 높다
    const hit = cells.find((cell) => /\d/.test(cell) && cell.trim().length > 1);
    if (hit) {
      return clip(`${cells[0]} ${hit}`.trim());
    }
  }

  return rows.length > 0 ? clip(rows[0].join(' ')) : null;
};

/**
 * 이 근거를 원문에서 찾을 검색어. 원문이 없는 유형은 null 이다.
 *
 * 파생·충돌은 우리가 만든 중간 계층이라 DART 원문에 그 문자열이 없다. 그 둘은
 * `based_on` 을 따라 내려간 자식이 검색어를 갖는다 - 그것이 종착점이다.
 */
export const buildSearchTerm = (evidence: Evidence): string | null => {
  switch (evidence.type) {
    case 'derived':
    case 'conflict':
    case 'news':
      return null;

    case 'account': {
      // 금액 원문이 가장 찾기 쉽다. 콤마까지 문서 표기 그대로다.
      const periods = Object.values(evidence.account?.periods ?? {});
      const raw = periods.find((period) => period.raw)?.raw;

      return raw ? collapse(raw) : clip(evidence.raw_content);
    }

    case 'table':
      return tableTerm(evidence.raw_content);

    default:
      return clip(evidence.raw_content) || null;
  }
};

/** 문단이 인용한 근거 id 전체. 문장 순서를 지키고 중복은 없앤다. */
export const paragraphEvidenceIds = (
  sentences: { evidence_ids: string[] }[],
): string[] => [
  ...new Set(sentences.flatMap((sentence) => sentence.evidence_ids)),
];
