import { Link } from 'react-router';

// 가짜 데이터 입니다 추후 삭제 예정
// 화면을 만들기 위한 간이 요소입니다.
import type { Company } from '../../company/model/company-data';

interface CompanyCardProps {
  company: Company;
}

export function CompanyCard({ company }: CompanyCardProps) {
  return (
    <Link
      to={`/companies/${company.id}`}
      className="block rounded-lg border p-4 transition hover:bg-muted"
    >
      <div className="flex items-start justify-between">
        <div>
          <h2 className="font-semibold">{company.name}</h2>

          <p className="mt-1 text-sm text-muted-foreground">
            {company.industry} · {company.category}
          </p>
        </div>

        <span className="text-sm text-muted-foreground">
          {company.companySize}
        </span>
      </div>

      <div className="mt-3 text-sm">
        <p>대표자: {company.representative}</p>
        <p>설립: {company.foundedAt}</p>
      </div>
    </Link>
  );
}