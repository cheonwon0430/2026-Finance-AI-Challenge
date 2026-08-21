import { queryOptions } from "@tanstack/react-query";

import { getCompanies, getCompany, type CompanySearchParams } from "./index";

export const companyQueries = {
  all: () => ["company"] as const,

  detail: (companyId: number) =>
    queryOptions({
      queryKey: [...companyQueries.all(), "detail", companyId],
      queryFn: () => getCompany(companyId),
    }),

  list: (params: CompanySearchParams) =>
    queryOptions({
      queryKey: [...companyQueries.all(), "list", params],
      queryFn: () => getCompanies(params),
    }),
};
