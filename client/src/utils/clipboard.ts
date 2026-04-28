import type { BriefingCard } from '@/types/briefing';

export async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}

export function formatBriefingForExport(b: BriefingCard): string {
  const lines: string[] = [];
  lines.push(`# ${b.companyName} — Tradeshow Briefing`);
  lines.push(`Generated: ${new Date(b.generatedAt).toLocaleString()}`);
  lines.push('');
  if (b.snapshot.hqLocation) lines.push(`HQ: ${b.snapshot.hqLocation}`);
  const facts = [
    b.snapshot.founded ? `Founded: ${b.snapshot.founded}` : null,
    b.snapshot.employeeRange ? `Employees: ${b.snapshot.employeeRange}` : null,
    b.snapshot.revenue ? `Revenue: ${b.snapshot.revenue}` : null,
  ].filter(Boolean);
  if (facts.length > 0) lines.push(facts.join(' · '));
  lines.push(`Geography: ${b.snapshot.geographyStatus.toUpperCase()}`);
  if (b.snapshot.phone) lines.push(`Phone: ${b.snapshot.phone}`);
  if (b.snapshot.website) lines.push(`Website: ${b.snapshot.website}`);
  if (b.snapshot.linkedinUrl) lines.push(`LinkedIn: ${b.snapshot.linkedinUrl}`);
  if (b.snapshot.tags.length > 0) lines.push(`Tags: ${b.snapshot.tags.join(', ')}`);
  if (b.snapshot.siteEmails.length > 0) lines.push(`Site emails: ${b.snapshot.siteEmails.join(', ')}`);
  lines.push('');
  if (b.openingLine) {
    lines.push('## Opening Line');
    lines.push(b.openingLine);
    lines.push('');
  }
  if (b.companySummaryShort) {
    lines.push('## Quick Company Summary');
    lines.push(b.companySummaryShort);
    lines.push('');
  }
  if (b.productLine) {
    lines.push('## What They Make');
    lines.push(b.productLine);
    lines.push('');
  }
  if (b.aftermarket.description || b.aftermarket.portalUrl || b.aftermarket.emails.length > 0) {
    lines.push('## Aftermarket Footprint');
    if (b.aftermarket.description) lines.push(b.aftermarket.description);
    if (b.aftermarket.portalUrl) lines.push(`Portal: ${b.aftermarket.portalUrl}`);
    if (b.aftermarket.emails.length > 0) lines.push(`Email signals: ${b.aftermarket.emails.join(', ')}`);
    lines.push('');
  }
  if (b.boothContact.name || b.boothContact.title || b.boothContact.email) {
    lines.push('## Right Person at the Booth');
    if (b.boothContact.name && b.boothContact.title) lines.push(`${b.boothContact.name} — ${b.boothContact.title}`);
    else if (b.boothContact.name) lines.push(b.boothContact.name);
    else if (b.boothContact.title) lines.push(`Suggested role: ${b.boothContact.title}`);
    if (b.boothContact.email) lines.push(`Email: ${b.boothContact.email}`);
    if (b.boothContact.confidence) lines.push(`Confidence: ${b.boothContact.confidence}%`);
    if (b.boothContact.sourceLabel) lines.push(`Source: ${b.boothContact.sourceLabel}`);
    if (b.boothContact.reasoning) lines.push(b.boothContact.reasoning);
    lines.push('');
  }
  if (b.allSources.length > 0) {
    lines.push('## Sources');
    b.allSources.forEach((s,i) => lines.push(`${i+1}. ${s}`));
  }
  return lines.join('\n');
}
