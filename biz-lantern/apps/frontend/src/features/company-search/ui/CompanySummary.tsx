// 가짜 데이터 입니다 추후 삭제 예정
// 화면을 만들기 위한 간이 요소입니다.
import type { Company } from '../../company/model/company-data';

interface CompanySummaryProps {
  company: Company;
}

export function CompanySummary({
  company,
}: CompanySummaryProps) {
  return (
    <section className="space-y-4">
      <div>
        <h2 className="font-semibold">기업 개요</h2>
        <p className="mt-2 text-muted-foreground">
          {company.summary.overview}
        </p>
      </div>

      <div>
        <h2 className="font-semibold">재무 요약</h2>
        <p className="mt-2 text-muted-foreground">
          {company.summary.financial}
        </p>
      </div>

      <div>
        <h2 className="font-semibold">투자 요약</h2>
        <p className="mt-2 text-muted-foreground">
          {company.summary.investment}
        </p>
      </div>

      <div>
        <h2 className="font-semibold">특허 요약</h2>
        <p className="mt-2 text-muted-foreground">
          {company.summary.patent}
        </p>
      </div>
    </section>
  );
}