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
  lines.push(`HQ: ${b.snapshot.hqLocation}`);
  lines.push(`Founded: ${b.snapshot.founded ?? '—'} · Employees: ${b.snapshot.employeeRange ?? '—'} · Revenue: ${b.snapshot.revenue ?? '—'}`);
  lines.push(`Geography: ${b.snapshot.geographyStatus.toUpperCase()}`);
  lines.push('');
  lines.push('## Opening Line');
  lines.push(b.openingLine);
  lines.push('');
  lines.push('## What They Make');
  lines.push(b.productLine);
  lines.push('');
  lines.push('## Aftermarket Footprint');
  lines.push(b.aftermarket.description);
  if (b.aftermarket.portalUrl) lines.push(`Portal: ${b.aftermarket.portalUrl}`);
  lines.push('');
  lines.push('## Right Person at the Booth');
  if (b.boothContact.name) lines.push(`${b.boothContact.name} — ${b.boothContact.title}`);
  else lines.push(`Suggested role: ${b.boothContact.title}`);
  if (b.boothContact.email) lines.push(`Email: ${b.boothContact.email}`);
  if (b.boothContact.sourceLabel) lines.push(`Source: ${b.boothContact.sourceLabel}`);
  lines.push(b.boothContact.reasoning);
  lines.push('');
  lines.push('## Sources');
  b.allSources.forEach((s,i) => lines.push(`${i+1}. ${s}`));
  return lines.join('\n');
}
