import type { GeographyStatus } from '@/types/briefing';

const TARGET_COUNTRIES = ['Germany','France','United Kingdom','UK','Italy','Spain','Switzerland','Netherlands','Sweden','Denmark','Norway','Finland','Austria','Belgium','Poland','United States','USA','US','Canada','Japan','South Korea','Australia'];
const FLAGGED_COUNTRIES = ['China','Russia','Iran','North Korea','Belarus','Myanmar','Venezuela','Cuba'];

export function classifyGeography(country: string): GeographyStatus {
  if (!country) return 'unknown';
  const c = country.toLowerCase();
  if (TARGET_COUNTRIES.some(t => c.includes(t.toLowerCase()))) return 'target';
  if (FLAGGED_COUNTRIES.some(f => c.includes(f.toLowerCase()))) return 'flagged';
  return 'unknown';
}
