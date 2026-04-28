import type { BriefingCard as BC } from '@/types/briefing';
import { CompanySummary } from './CompanySummary';
import { CompanyIdentityBar } from './CompanyIdentityBar';
import { OpeningLine } from './OpeningLine';
import { ProductLine } from './ProductLine';
import { AftermarketFootprint } from './AftermarketFootprint';
import { BoothContact } from './BoothContact';
import { CompanySnapshot } from './CompanySnapshot';
import { SourcesFooter } from './SourcesFooter';

export function BriefingCard({ b }: { b: BC }) {
  const sections = [
    (b.productLine || b.snapshot.tags.length > 0)
      ? <div key="product" className="h-full"><ProductLine text={b.productLine} tags={b.snapshot.tags} sources={b.productLineSources} /></div>
      : null,
    <div key="snapshot" className="h-full"><CompanySnapshot data={b.snapshot} /></div>,
    (b.aftermarket.description || b.aftermarket.hasPortal !== null || b.aftermarket.emails.length > 0 || b.aftermarket.sources.length > 0)
      ? <div key="aftermarket" className="h-full"><AftermarketFootprint data={b.aftermarket} /></div>
      : null,
    (b.boothContact.name || b.boothContact.title || b.boothContact.email || b.boothContact.sourceUrl)
      ? <div key="contact" className="h-full"><BoothContact data={b.boothContact} /></div>
      : null,
  ].filter(Boolean);

  return (
    <div className="max-w-[900px] mx-auto px-4 sm:px-6 pb-28 pt-6 sm:pt-8">
      <CompanyIdentityBar b={b} />
      {b.companySummaryShort && <CompanySummary companyName={b.companyName} text={b.companySummaryShort} />}
      {b.openingLine && <OpeningLine text={b.openingLine} />}
      {/*
        4-card layout:
        Row 1 (paired, equal height): ProductLine | CompanySnapshot
        Row 2 (paired, equal height): Aftermarket | BoothContact
        On mobile: single column, stacked in priority order.
      */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 sm:gap-5 mb-4 sm:mb-5 items-stretch">
        {sections}
      </div>
      {b.allSources.length > 0 && <SourcesFooter sources={b.allSources} />}
    </div>
  );
}
