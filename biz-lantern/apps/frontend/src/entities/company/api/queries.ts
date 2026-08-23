import { queryOptions } from "@tanstack/react-query";

import { getCompanies, getCompany, type CompanySearchParams } from "./index";

export const companyQueries = {
  all: () => ["company"] as const,

  detail: (companyName: string) =>
    queryOptions({
      queryKey: [...companyQueries.all(), "detail", companyName],
      queryFn: () => getCompany(companyName),
    }),

  list: (params: CompanySearchParams) =>
    queryOptions({
      queryKey: [...companyQueries.all(), "list", params],
      queryFn: () => getCompanies(params),
    }),
};
