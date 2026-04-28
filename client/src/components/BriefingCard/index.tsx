import type { BriefingCard as BC } from '@/types/briefing';
import { CompanyIdentityBar } from './CompanyIdentityBar';
import { OpeningLine } from './OpeningLine';
import { ProductLine } from './ProductLine';
import { AftermarketFootprint } from './AftermarketFootprint';
import { BoothContact } from './BoothContact';
import { CompanySnapshot } from './CompanySnapshot';
import { SourcesFooter } from './SourcesFooter';

export function BriefingCard({ b }: { b: BC }) {
  return (
    <div className="max-w-[900px] mx-auto px-4 sm:px-6 pb-28 pt-6 sm:pt-8">
      <CompanyIdentityBar b={b} />
      <OpeningLine text={b.openingLine} />
      {/*
        4-card layout:
        Row 1 (paired, equal height): ProductLine | CompanySnapshot
        Row 2 (paired, equal height): Aftermarket | BoothContact
        On mobile: single column, stacked in priority order.
      */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 sm:gap-5 mb-4 sm:mb-5 items-stretch">
        <div className="h-full"><ProductLine text={b.productLine} sources={b.productLineSources} /></div>
        <div className="h-full"><CompanySnapshot data={b.snapshot} /></div>
        <div className="h-full"><AftermarketFootprint data={b.aftermarket} /></div>
        <div className="h-full"><BoothContact data={b.boothContact} /></div>
      </div>
      <SourcesFooter sources={b.allSources} />
    </div>
  );
}
