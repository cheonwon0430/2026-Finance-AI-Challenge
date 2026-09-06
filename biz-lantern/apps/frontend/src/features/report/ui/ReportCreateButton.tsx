import { useNavigate } from 'react-router';
import { useMutation } from '@tanstack/react-query';
import { FileChartColumn, LoaderCircle } from 'lucide-react';

import { createReport } from '@/entities/report';
import { Button } from '@/shared/ui';

interface ReportCreateButtonProps {
  /** DART 고유번호 8자리. 회사명이 아니라 이것으로 접수한다. */
  corpCode: string;
  className?: string;
}

/**
 * 보고서 생성 버튼.
 *
 * POST 는 접수만 하고 즉시 202 로 돌아온다. 받은 `report_id` 로 이동하면 그 화면이 폴링을
 * 이어받는다 - id 가 주소에 들어가므로 새로고침·뒤로가기·링크 공유가 모두 동작한다.
 */
export function ReportCreateButton({
  corpCode,
  className,
}: ReportCreateButtonProps) {
  const navigate = useNavigate();

  const { mutate, isPending, isError } = useMutation({
    mutationFn: () => createReport(corpCode),
    onSuccess: (accepted) => {
      void navigate(`/reports/${accepted.report_id}`);
    },
  });

  return (
    <div className={className}>
      <Button type="button" onClick={() => mutate()} disabled={isPending}>
        {isPending ? <LoaderCircle className="animate-spin" /> : <FileChartColumn />}
        {isPending ? '보고서 생성 요청 중' : '분석 보고서 생성'}
      </Button>

      {isError && (
        <p className="mt-2 text-sm text-destructive">
          보고서 생성을 요청하지 못했습니다. 잠시 후 다시 시도해 주세요.
        </p>
      )}
    </div>
  );
}
