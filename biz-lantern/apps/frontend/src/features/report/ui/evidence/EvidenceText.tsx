interface EvidenceTextProps {
  rawContent: string;
}

/**
 * 주석·문단·요약 근거. 원문 스냅샷을 그대로 보여준다.
 *
 * 줄이거나 다듬지 않는다 - 스냅샷을 손대면 근거가 아니라 인용이 된다.
 */
export function EvidenceText({ rawContent }: EvidenceTextProps) {
  return (
    <p className="max-h-72 overflow-y-auto text-sm leading-relaxed whitespace-pre-wrap wrap-break-word">
      {rawContent}
    </p>
  );
}
