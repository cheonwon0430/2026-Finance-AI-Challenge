/**
 * 표 근거의 `raw_content` 를 다시 표로 되살린다.
 *
 * 백엔드는 표를 `셀 | 셀 | 셀` 줄바꿈 텍스트로 굳혀 둔다(원문 스냅샷이라 구조를 따로 싣지
 * 않는다). 그대로 `<pre>` 로 뿌리면 주주표 19행이 읽히지 않으므로 화면에서 되살린다.
 * 원문을 고치는 게 아니라 같은 내용을 표로 그리는 것뿐이다.
 */
const CELL_SEPARATOR = ' | ';

export interface ParsedTable {
  /** 열 수만큼 반복된 단위 표기 행. 없으면 null. */
  caption: string | null;
  header: string[] | null;
  rows: string[][];
}

const isRepeatedCell = (cells: string[]) =>
  cells.length > 1 && cells.every((cell) => cell === cells[0]);

export const parseEvidenceTable = (rawContent: string): ParsedTable => {
  const rows = rawContent
    .split('\n')
    .map((line) => line.split(CELL_SEPARATOR).map((cell) => cell.trim()))
    .filter((cells) => cells.some((cell) => cell.length > 0));

  if (rows.length === 0) {
    return { caption: null, header: null, rows: [] };
  }

  // `(단위: 주, %)` 가 열 수만큼 반복된 첫 행은 헤더가 아니라 캡션이다.
  const hasCaption = isRepeatedCell(rows[0]);
  const caption = hasCaption ? rows[0][0] : null;
  const body = hasCaption ? rows.slice(1) : rows;

  if (body.length === 0) {
    return { caption, header: null, rows: [] };
  }

  return { caption, header: body[0], rows: body.slice(1) };
};

/**
 * 뉴스 근거의 첫 줄은 `제목 | 언론사 | 발행일` 이고 그 뒤가 추출 본문이다.
 * 본문에는 내비게이션 찌꺼기가 섞여 있지만 **정제하지 않는다** - 손대는 순간 근거가 아니다.
 */
export const splitNewsContent = (rawContent: string) => {
  const lineBreak = rawContent.indexOf('\n');

  if (lineBreak === -1) {
    return { headline: rawContent.trim(), body: '' };
  }

  return {
    headline: rawContent.slice(0, lineBreak).trim(),
    body: rawContent.slice(lineBreak + 1).trim(),
  };
};
