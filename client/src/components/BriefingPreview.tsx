/**
 * Skeleton + progressively-revealed briefing card during the progress phase.
 * Sections fill in as the agent reaches the matching step.
 */
import type { BriefingCard as BC, ProgressStep } from '@/types/briefing';
import { REVEAL_AFTER } from '@/hooks/useEnrichStream';
import { SkeletonBar } from './SkeletonCard';

interface Props {
  companyName: string;
  completedStepCount: number;
  briefing: BC | null;
  steps: ProgressStep[];
}

function reached(threshold: number, completed: number) {
  return completed >= threshold;
}

export function BriefingPreview({ companyName, completedStepCount, briefing }: Props) {
  const showIdentity = reached(REVEAL_AFTER.identity, completedStepCount);
  const showProduct = reached(REVEAL_AFTER.productLine, completedStepCount);
  const showGeo = reached(REVEAL_AFTER.geography, completedStepCount);
  const showAfter = reached(REVEAL_AFTER.aftermarket, completedStepCount);
  const showBooth = reached(REVEAL_AFTER.boothContact, completedStepCount);
  const showOpening = reached(REVEAL_AFTER.openingLine, completedStepCount);

  return (
    <div>
      <div className="eyebrow mb-2">BRIEFING CARD</div>
      <div className="space-y-4">
        {/* Identity bar */}
        <div className="card-surface p-5">
          {showIdentity && briefing ? (
            <div className="flex flex-col gap-2 animate-section-in">
              <div className="text-[22px] font-bold text-primary-ink">{briefing.companyName}</div>
              <div className="text-[13px] text-secondary-ink">{briefing.snapshot.hqLocation}</div>
              {showGeo && (
                <div className="mt-1">
                  {briefing.snapshot.geographyStatus === 'target' && (
                    <span className="inline-block bg-[hsl(var(--success-tint))] text-[hsl(var(--success))] border border-[hsl(var(--success-border))] text-[12px] font-semibold rounded px-2 py-0.5">
                      ✓ TARGET MARKET
                    </span>
                  )}
                  {briefing.snapshot.geographyStatus === 'flagged' && (
                    <span className="inline-block bg-[hsl(var(--danger-tint))] text-[hsl(var(--danger))] border border-[hsl(var(--danger-border))] text-[12px] font-semibold rounded px-2 py-0.5">
                      ⚠ FLAGGED MARKET
                    </span>
                  )}
                </div>
              )}
            </div>
          ) : (
            <div className="space-y-3">
              <SkeletonBar width={Math.max(160, companyName.length * 10)} height={20} />
              <SkeletonBar width="50%" height={12} />
              <SkeletonBar width={140} height={20} />
            </div>
          )}
        </div>

        {/* Opening line */}
        <div className="card-surface p-5" style={{ background: 'hsl(var(--primary-tint-strong))' }}>
          <div className="eyebrow mb-2" style={{ color: 'hsl(var(--primary))' }}>YOUR OPENING LINE</div>
          {showOpening && briefing ? (
            <p className="text-[15px] italic text-primary-ink leading-relaxed animate-section-in">{briefing.openingLine}</p>
          ) : (
            <div className="space-y-2">
              <SkeletonBar width="95%" />
              <SkeletonBar width="88%" />
              <SkeletonBar width="60%" />
            </div>
          )}
        </div>

        {/* What they make */}
        <div className="card-surface p-5">
          <div className="eyebrow mb-2">WHAT THEY MAKE</div>
          {showProduct && briefing ? (
            <p className="text-[14px] text-body-ink leading-relaxed animate-section-in">{briefing.productLine}</p>
          ) : (
            <div className="space-y-2">
              <SkeletonBar width="92%" /><SkeletonBar width="96%" /><SkeletonBar width="70%" />
            </div>
          )}
        </div>

        {/* Aftermarket */}
        <div className="card-surface p-5">
          <div className="eyebrow mb-2">AFTERMARKET FOOTPRINT</div>
          {showAfter && briefing ? (
            <p className="text-[14px] text-body-ink leading-relaxed animate-section-in">{briefing.aftermarket.description}</p>
          ) : (
            <div className="space-y-2">
              <SkeletonBar width="80%" /><SkeletonBar width="88%" />
            </div>
          )}
        </div>

        {/* Right person */}
        <div className="card-surface p-5">
          <div className="eyebrow mb-2">RIGHT PERSON AT THE BOOTH</div>
          {showBooth && briefing ? (
            <div className="animate-section-in">
              <div className="text-[14px] font-semibold text-primary-ink">{briefing.boothContact.name ?? briefing.boothContact.title}</div>
              {briefing.boothContact.name && (
                <div className="mt-1 text-[12px] text-secondary-ink">{briefing.boothContact.title}</div>
              )}
              {briefing.boothContact.email && (
                <div className="mt-1 text-[12px] font-medium text-[hsl(var(--info))]">{briefing.boothContact.email}</div>
              )}
              {briefing.boothContact.sourceLabel && (
                <div className="mt-1 text-[11px] uppercase tracking-[0.04em] text-muted-ink">
                  Source: {briefing.boothContact.sourceLabel}
                </div>
              )}
              <div className="text-[12px] text-secondary-ink italic mt-1">{briefing.boothContact.reasoning}</div>
            </div>
          ) : (
            <div className="space-y-2">
              <SkeletonBar width="60%" /><SkeletonBar width="85%" />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
