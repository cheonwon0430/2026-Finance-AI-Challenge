/** "20200504" → "2020.05.04". 형식이 다르면 원본을 그대로 반환한다. */
export function formatDate(value: string | null | undefined): string | null {
  if (!value) return null;

  const match = /^(\d{4})(\d{2})(\d{2})$/.exec(value);

  if (!match) return value;

  const [, year, month, day] = match;

  return `${year}.${month}.${day}`;
}

/** DART corp_cls 코드 → 표시 라벨. */
const CORP_CLS_LABEL: Record<string, string> = {
  Y: '유가증권시장',
  K: '코스닥',
  N: '코넥스',
  E: '기타법인',
};

export function corpClsLabel(code: string | null | undefined): string | null {
  if (!code) return null;

  return CORP_CLS_LABEL[code] ?? code;
}
