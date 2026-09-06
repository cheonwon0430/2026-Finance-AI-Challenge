import { queryOptions } from '@tanstack/react-query';
import { isAxiosError } from 'axios';

import { getReport } from './index';

/** PENDING 동안의 재조회 간격. 생성은 수십 초~몇 분이 걸린다. */
export const REPORT_POLL_INTERVAL_MS = 3000;

/** 다시 물어도 답이 바뀌지 않는 상태 코드. */
const TERMINAL_STATUS = [400, 404];

const MAX_RETRY = 2;

export const reportQueries = {
  all: () => ['report'] as const,

  detail: (reportId: string) =>
    queryOptions({
      queryKey: [...reportQueries.all(), 'detail', reportId],
      queryFn: () => getReport(reportId),

      // 생성이 끝나면 폴링을 멈춘다. FAILED 도 종착 상태다.
      refetchInterval: (query) =>
        query.state.data?.status === 'PENDING' ? REPORT_POLL_INTERVAL_MS : false,

      // 없는 보고서를 세 번 더 묻지 않는다. 화면 전환만 늦어진다.
      retry: (failureCount, error) => {
        if (
          isAxiosError(error) &&
          TERMINAL_STATUS.includes(error.response?.status ?? 0)
        ) {
          return false;
        }

        return failureCount < MAX_RETRY;
      },
    }),
};
