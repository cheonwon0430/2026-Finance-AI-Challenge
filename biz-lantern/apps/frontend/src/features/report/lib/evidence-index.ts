/**
 * 근거 장부. `evidence[]` 는 65건 안팎이고 문장마다 id 로 참조하므로 한 번만 인덱싱한다.
 */
import type { Evidence } from '@/entities/report';

export type EvidenceIndex = Map<string, Evidence>;

export const buildEvidenceIndex = (evidence: Evidence[]): EvidenceIndex =>
  new Map(evidence.map((item) => [item.evidence_id, item]));

export interface ResolvedEvidence {
  found: Evidence[];
  /** 장부에 없는 id. 실측 0건이지만 조용히 건너뛰지 않고 화면에 드러낸다. */
  missing: string[];
}

/**
 * id 목록을 조각으로 바꾼다.
 *
 * 못 찾은 id 를 버리지 않는 것이 핵심이다. 문장이 근거 셋을 인용했는데 화면에 둘만 뜨면
 * 사용자는 그 사실조차 알 수 없다 - 조용한 누락은 이 시스템이 금지하는 것이다.
 */
export const resolveEvidence = (
  index: EvidenceIndex,
  ids: string[],
): ResolvedEvidence => {
  const found: Evidence[] = [];
  const missing: string[] = [];

  for (const id of ids) {
    const evidence = index.get(id);

    if (evidence) {
      found.push(evidence);
    } else {
      missing.push(id);
    }
  }

  return { found, missing };
};
