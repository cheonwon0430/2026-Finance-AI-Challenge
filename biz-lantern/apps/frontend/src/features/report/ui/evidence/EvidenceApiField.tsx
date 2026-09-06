interface EvidenceApiFieldProps {
  rawContent: string;
  /** 같은 응답의 형제 필드. 값 하나만 보면 어느 회사 것인지 알 수 없다. */
  context?: Record<string, unknown>;
}

const asText = (value: unknown) =>
  value === null || value === undefined ? '-' : String(value);

export function EvidenceApiField({
  rawContent,
  context,
}: EvidenceApiFieldProps) {
  const entries = Object.entries(context ?? {});

  return (
    <div className="space-y-3">
      <p className="text-sm font-medium wrap-break-word">{rawContent}</p>

      {entries.length > 0 && (
        <dl className="grid gap-x-6 gap-y-2 sm:grid-cols-2">
          {entries.map(([key, value]) => (
            <div key={key} className="min-w-0">
              <dt className="text-xs text-muted-foreground">{key}</dt>
              <dd className="mt-0.5 text-sm wrap-break-word">
                {asText(value)}
              </dd>
            </div>
          ))}
        </dl>
      )}
    </div>
  );
}
