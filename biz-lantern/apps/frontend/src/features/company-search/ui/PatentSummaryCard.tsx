import { ChevronRight, FileStack } from 'lucide-react';

import { cn } from '@/shared/lib';

interface PatentSummaryCardProps {
  count: number;
  onClick: () => void;
  className?: string;
}

export function PatentSummaryCard({
  count,
  onClick,
  className,
}: PatentSummaryCardProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'flex w-full items-center justify-between gap-4 rounded-lg border border-border bg-card p-6 text-left shadow-sm transition-colors hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none',
        className,
      )}
    >
      <div className="flex items-center gap-4">
        <div className="flex size-11 shrink-0 items-center justify-center rounded-full bg-primary-container text-primary-container-foreground">
          <FileStack className="size-5" />
        </div>

        <div>
          <p className="text-sm text-muted-foreground">특허</p>
          <p className="text-2xl font-bold">{count}건</p>
        </div>
      </div>

      <div className="flex items-center gap-1 text-sm text-muted-foreground">
        상세보기
        <ChevronRight className="size-4" />
      </div>
    </button>
  );
}
