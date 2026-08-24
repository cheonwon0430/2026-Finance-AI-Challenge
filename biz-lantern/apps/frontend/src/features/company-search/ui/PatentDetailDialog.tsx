import type { AdministrativeHistory, Patent } from '@/entities/company';
import { formatDate } from '@/entities/company';
import {
  Badge,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  ScrollArea,
  Separator,
} from '@/shared/ui';

interface PatentDetailDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  count: number;
  items: Patent[];
}

export function PatentDetailDialog({
  open,
  onOpenChange,
  count,
  items,
}: PatentDetailDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] max-w-2xl gap-4 overflow-hidden">
        <DialogHeader>
          <DialogTitle>특허 상세정보</DialogTitle>
          <DialogDescription>
            총 {count}건의 특허가 확인되었습니다.
          </DialogDescription>
        </DialogHeader>

        <ScrollArea className="max-h-[65vh] pr-4">
          <div className="space-y-6">
            {items.map((patent, index) => (
              <div key={patent.application_number}>
                <PatentDetailItem patent={patent} />
                {index < items.length - 1 && <Separator className="mt-6" />}
              </div>
            ))}
          </div>
        </ScrollArea>
      </DialogContent>
    </Dialog>
  );
}

function patentStatusVariant(status: string) {
  if (status === '등록') return 'success' as const;
  if (status === '소멸') return 'muted' as const;
  return 'outline' as const;
}

function administrativeStatusVariant(status: string) {
  if (status === '수리') return 'success' as const;
  return 'outline' as const;
}

function PatentDetailItem({ patent }: { patent: Patent }) {
  const applicants = patent.applicant
    .split('|')
    .map((name) => name.trim())
    .filter(Boolean);

  return (
    <div className="space-y-3">
      <div>
        <div className="flex items-start justify-between gap-3">
          <h3 className="text-sm leading-snug font-semibold break-words">
            {patent.invention_name}
          </h3>

          <Badge variant={patentStatusVariant(patent.status)} className="shrink-0">
            {patent.status}
          </Badge>
        </div>

        <dl className="mt-3 grid gap-x-6 gap-y-2 text-xs sm:grid-cols-2">
          <div>
            <dt className="text-muted-foreground">출원번호</dt>
            <dd className="mt-0.5">{patent.application_number}</dd>
          </div>

          <div>
            <dt className="text-muted-foreground">출원일</dt>
            <dd className="mt-0.5">{formatDate(patent.application_date)}</dd>
          </div>

          <div className="sm:col-span-2">
            <dt className="text-muted-foreground">출원인</dt>
            <dd className="mt-0.5 break-words">{applicants.join(', ')}</dd>
          </div>
        </dl>
      </div>

      <AdministrativeHistoryPanel history={patent.administrative_history} />
    </div>
  );
}

function AdministrativeHistoryPanel({
  history,
}: {
  history: AdministrativeHistory | null;
}) {
  return (
    <div className="rounded-md bg-muted/50 p-3">
      <p className="text-xs font-semibold text-muted-foreground">
        행정처리 정보
      </p>

      {!history ? (
        <p className="mt-2 text-xs text-muted-foreground">
          확인된 행정처리 정보가 없습니다.
        </p>
      ) : (
        <div className="mt-2 space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant={administrativeStatusVariant(history.status)}>
              {history.status}
              {history.statusEng ? ` · ${history.statusEng}` : ''}
            </Badge>

            <Badge variant="secondary">단계 · {history.step}</Badge>
          </div>

          <dl className="grid gap-x-6 gap-y-2 text-xs sm:grid-cols-2">
            <div>
              <dt className="text-muted-foreground">출원번호</dt>
              <dd className="mt-0.5">{history.applicationNumber}</dd>
            </div>

            <div>
              <dt className="text-muted-foreground">문서번호</dt>
              <dd className="mt-0.5">{history.documentNumber}</dd>
            </div>

            <div>
              <dt className="text-muted-foreground">문서일자</dt>
              <dd className="mt-0.5">{formatDate(history.documentDate)}</dd>
            </div>

            <div>
              <dt className="text-muted-foreground">등록번호</dt>
              <dd className="mt-0.5">
                {history.registrationNumber ?? (
                  <span className="text-muted-foreground">해당 없음</span>
                )}
              </dd>
            </div>

            <div className="sm:col-span-2">
              <dt className="text-muted-foreground">문서명</dt>
              <dd className="mt-0.5 break-words">
                {history.documentTitle}
                {history.documentTitleEng && (
                  <span className="block text-muted-foreground">
                    {history.documentTitleEng}
                  </span>
                )}
              </dd>
            </div>

            <div className="sm:col-span-2">
              <dt className="text-muted-foreground">심판번호</dt>
              <dd className="mt-0.5">
                {history.trialNumber ?? (
                  <span className="text-muted-foreground">해당 없음</span>
                )}
              </dd>
            </div>
          </dl>
        </div>
      )}
    </div>
  );
}
