import { Building2, ExternalLink } from "lucide-react";

import type { Company } from "@/entities/company";
import { corpClsLabel, formatDate } from "@/entities/company";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui";

interface InfoField {
  label: string;
  value: string | null;
  href?: string;
}
// URL 프로토콜 보정 헬퍼 함수
function formatUrl(url?: string | null): string | undefined {
  if (!url) return undefined;

  const trimmedUrl = url.trim();
  if (!trimmedUrl) return undefined;

  if (trimmedUrl.startsWith("http://")) {
    return trimmedUrl.replace(/^http:\/\//i, "https://");
  }
  if (!trimmedUrl.startsWith("https://")) {
    return `https://${trimmedUrl}`;
  }

  return trimmedUrl;
}

function buildInfoFields(company: Company): InfoField[] {
  const formattedHmUrl = formatUrl(company.hm_url);
  const formattedIrUrl = formatUrl(company.ir_url);

  return [
    { label: "기업명", value: company.corp_name.trim() || null },
    { label: "영문 기업명", value: company.corp_name_eng || null },
    { label: "대표자", value: company.ceo_nm || null },
    { label: "법인등록번호", value: company.jurir_no || null },
    { label: "사업자등록번호", value: company.bizr_no || null },
    { label: "기업구분", value: corpClsLabel(company.corp_cls) },
    { label: "산업분류코드", value: company.induty_code || null },
    { label: "설립일", value: formatDate(company.est_dt) },
    { label: "결산월", value: company.acc_mt ? `${company.acc_mt}월` : null },
    { label: "주소", value: company.adres || null },
    { label: "전화번호", value: company.phn_no || null },
    { label: "팩스번호", value: company.fax_no || null },
    {
      label: "홈페이지",
      value: formattedHmUrl || null,
      href: formattedHmUrl,
    },
    {
      label: "IR 페이지",
      value: formattedIrUrl || null,
      href: formattedIrUrl,
    },
    { label: "종목명", value: company.stock_name || null },
    { label: "주식코드", value: company.stock_code || null },
  ];
}

interface CompanyInfoCardProps {
  company: Company;
}

export function CompanyInfoCard({ company }: CompanyInfoCardProps) {
  const fields = buildInfoFields(company);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Building2 className="size-4 text-muted-foreground" />
          기업 기본정보
        </CardTitle>
      </CardHeader>

      <CardContent>
        <dl className="grid gap-x-6 gap-y-4 sm:grid-cols-2">
          {fields.map((field) => (
            <div key={field.label} className="min-w-0">
              <dt className="text-xs text-muted-foreground">{field.label}</dt>

              <dd className="mt-1 text-sm font-medium wrap-break-word">
                {field.value ? (
                  field.href ? (
                    <a
                      href={field.href}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1 text-primary underline-offset-2 hover:underline break-all"
                    >
                      {field.value}
                      <ExternalLink className="size-3 shrink-0" />
                    </a>
                  ) : (
                    field.value
                  )
                ) : (
                  <span className="text-muted-foreground">정보 없음</span>
                )}
              </dd>
            </div>
          ))}
        </dl>
      </CardContent>
    </Card>
  );
}
