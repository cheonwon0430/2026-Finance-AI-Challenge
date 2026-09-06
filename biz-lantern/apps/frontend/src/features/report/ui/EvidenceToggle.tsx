import { useState, type ReactNode } from 'react';
import { ChevronDown } from 'lucide-react';

import { cn } from '@/shared/lib';

interface EvidenceToggleProps {
  label: ReactNode;
  /** 라벨 오른쪽에 붙는 보조 문구. 근거 건수 같은 것. */
  hint?: string;
  defaultOpen?: boolean;
  className?: string;
  children: ReactNode;
}

/**
 * 접기·펼치기 껍데기.
 *
 * Radix collapsible 을 이 화면 하나를 위해 새로 깔지 않는다. 근거는 파생·충돌을 거쳐 여러
 * 단으로 중첩되는데, 그런 구조에는 노드마다 로컬 상태를 두는 편이 단순하다.
 */
export function EvidenceToggle({
  label,
  hint,
  defaultOpen = false,
  className,
  children,
}: EvidenceToggleProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <div className={className}>
      <button
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        aria-expanded={isOpen}
        className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm text-muted-foreground transition-colors hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
      >
        <ChevronDown
          className={cn(
            'size-4 shrink-0 transition-transform',
            isOpen && 'rotate-180',
          )}
        />

        <span className="min-w-0 flex-1">{label}</span>

        {hint && <span className="shrink-0 text-xs">{hint}</span>}
      </button>

      {isOpen && <div className="mt-2">{children}</div>}
    </div>
  );
}
