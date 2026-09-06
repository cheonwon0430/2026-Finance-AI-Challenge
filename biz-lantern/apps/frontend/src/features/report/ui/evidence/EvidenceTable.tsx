import { parseEvidenceTable } from '../../lib/parse-table';

interface EvidenceTableProps {
  rawContent: string;
}

/** 표 근거. 파이프로 굳어 있는 원문을 같은 내용의 표로 되살린다. */
export function EvidenceTable({ rawContent }: EvidenceTableProps) {
  const { caption, header, rows } = parseEvidenceTable(rawContent);

  if (!header) {
    return (
      <p className="text-sm whitespace-pre-wrap wrap-break-word">{rawContent}</p>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-sm">
        {caption && (
          <caption className="mb-1 text-left text-xs text-muted-foreground">
            {caption}
          </caption>
        )}

        <thead>
          <tr>
            {header.map((cell, columnIndex) => (
              <th
                key={`${cell}-${columnIndex}`}
                scope="col"
                className="border border-border bg-muted px-2 py-1 text-left font-semibold whitespace-nowrap"
              >
                {cell}
              </th>
            ))}
          </tr>
        </thead>

        <tbody>
          {rows.map((cells, rowIndex) => (
            <tr key={`${cells.join('|')}-${rowIndex}`}>
              {cells.map((cell, columnIndex) => (
                <td
                  key={`${cell}-${columnIndex}`}
                  className="border border-border px-2 py-1 align-top"
                >
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
