// 검색이라는 사용자 행동만 담당

import { useState } from 'react';

interface CompanySearchFormProps {
  onSearch: (query: string) => void;
}

export function CompanySearchForm({
  onSearch,
}: CompanySearchFormProps) {
  const [query, setQuery] = useState('');

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    const trimmedQuery = query.trim();

    if (!trimmedQuery) {
      return;
    }

    onSearch(trimmedQuery);
  };

  return (
    <form onSubmit={handleSubmit} className="flex gap-2">
      <input
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder="기업명을 입력하세요"
        className="flex-1 rounded-md border px-4 py-2"
      />

      <button
        type="submit"
        className="rounded-md bg-primary px-4 py-2 text-primary-foreground"
      >
        검색
      </button>
    </form>
  );
}