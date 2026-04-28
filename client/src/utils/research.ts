import type {
  AftermarketFootprint,
  BoothContact,
  BriefingCard,
  CompanySnapshot,
  ConfidenceLevel,
  GeographyStatus,
  RecentSignal,
} from '@/types/briefing';

interface ResearchNewsItem {
  title?: string | null;
  url?: string | null;
  source?: string | null;
  date?: string | null;
}

interface ResearchResponse {
  company_name?: string | null;
  resolved_domain?: string | null;
  data?: Record<string, unknown>;
  field_sources?: Record<string, unknown>;
  sources?: string[];
  notes?: string[];
}

export interface ResearchStreamEvent {
  type: 'progress' | 'result' | 'error';
  timestamp?: string;
  stage?: string;
  status?: string;
  message?: string;
  data?: Record<string, unknown>;
  payload?: ResearchResponse;
}

function asString(value: unknown): string | null {
  if (typeof value !== 'string') return null;
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function asBoolean(value: unknown): boolean | null {
  if (typeof value === 'boolean') return value;
  return null;
}

function asStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.map(asString).filter((item): item is string => Boolean(item));
}

function mapGeographyStatus(flag: string | null): GeographyStatus {
  if (flag === 'target_market') return 'target';
  if (flag === 'flagged_market') return 'flagged';
  return 'unknown';
}

function mapRevenueConfidence(source: string | null, revenue: string | null): ConfidenceLevel {
  if (!revenue) return 'unconfirmed';
  if (!source) return 'uncertain';
  if (source.includes('heuristic') || source.includes('fallback') || source.includes('llm')) {
    return 'uncertain';
  }
  return 'confirmed';
}

function buildSnapshot(data: Record<string, unknown>, fieldSources: Record<string, unknown>, fallbackCompanyName: string): CompanySnapshot {
  const hqCity = asString(data.hq_city);
  const hqCountry = asString(data.hq_country);
  const hqLocation = [hqCity, hqCountry].filter(Boolean).join(', ') || null;
  const revenue = asString(data.revenue);
  const revenueSource = asString(fieldSources.revenue);

  return {
    officialName: asString(data.official_name) ?? fallbackCompanyName,
    parentCompany: asString(data.parent_company),
    hqLocation,
    hqCountry,
    founded: asString(data.founded_year),
    employeeRange: asString(data.employee_count) ?? asString(data.employee_count_display),
    revenue,
    revenueConfidence: mapRevenueConfidence(revenueSource, revenue),
    geographyStatus: mapGeographyStatus(asString(data.hq_geography_flag)),
    website: asString(data.website),
    linkedinUrl: asString(data.company_linkedin_url),
    phone: asString(data.company_phone),
    tags: asStringArray(data.company_tags),
    siteEmails: asStringArray(data.site_emails),
    sources: [
      ...asStringArray([data.source_url]),
      ...asStringArray([data.website]),
    ],
  };
}

function buildAftermarket(data: Record<string, unknown>): AftermarketFootprint {
  const footprint = asBoolean(data.aftermarket_footprint);
  const evidenceUrl =
    asString(data.parts_page) ??
    asString(data.service_page) ??
    asString(data.support_page) ??
    asString(data.customer_portal_page);
  const aftermarketDescription =
    asString(data.aftermarket_reason) ??
    (footprint === true
      ? 'Aftermarket footprint detected.'
      : footprint === false
        ? 'No aftermarket footprint detected.'
        : null);

  return {
    hasPortal: footprint,
    portalUrl: evidenceUrl,
    description: aftermarketDescription,
    confidence: footprint === null ? 'uncertain' : 'confirmed',
    emails: asStringArray(data.aftermarket_site_emails),
    sources: asStringArray([
      data.parts_page,
      data.service_page,
      data.support_page,
      data.source_url,
    ]),
  };
}

function buildBoothContact(data: Record<string, unknown>): BoothContact {
  const sourceUrl = asString(data.target_person_linkedin_url);
  const email = asString(data.target_person_email);
  const sourceLabel = asString(data.target_person_source);
  const title =
    asString(data.target_person_title) ??
    asString(data.suggested_target_title);
  const name = asString(data.target_person_name);
  const reasoning =
    asString(data.suggested_target_title_reasoning) ??
    (sourceLabel ? `Verified contact identified via ${sourceLabel}.` : null);

  return {
    name,
    title,
    email,
    confidence: asString(data.target_person_confidence),
    reasoning,
    isVerified: Boolean(name && (email || sourceUrl || sourceLabel)),
    sourceUrl,
    sourceLabel,
  };
}

function buildRecentSignals(data: Record<string, unknown>): RecentSignal[] {
  if (!Array.isArray(data.recent_news)) return [];

  return data.recent_news
    .filter((item): item is ResearchNewsItem => Boolean(item && typeof item === 'object'))
    .map((item) => {
      const sourceUrl = asString(item.url) ?? '';
      return {
        date: asString(item.date) ?? 'Recent',
        headline: asString(item.title) ?? 'Recent company signal',
        sourceName: asString(item.source) ?? 'Source',
        sourceUrl,
        tags: ['news'],
      };
    })
    .filter((item) => Boolean(item.sourceUrl));
}

export function parseResearchPayload(payload: ResearchResponse): BriefingCard {
  const data = (payload.data ?? {}) as Record<string, unknown>;
  const fieldSources = (payload.field_sources ?? {}) as Record<string, unknown>;
  const companyName =
    asString(data.official_name) ??
    asString(payload.company_name) ??
    'Unknown company';
  const snapshot = buildSnapshot(data, fieldSources, companyName);
  const recentSignals = buildRecentSignals(data);

  return {
    companyName,
    companySummaryShort: asString(data.company_summary_short),
    snapshot,
    productLine:
      asString(data.what_they_make) ??
      asString(data.description),
    productLineSources: asStringArray([data.source_url, payload.resolved_domain]),
    aftermarket: buildAftermarket(data),
    boothContact: buildBoothContact(data),
    recentSignals,
    openingLine: asString(data.personalized_opening_line),
    allSources: Array.from(new Set(asStringArray(payload.sources))),
    generatedAt: new Date().toISOString(),
  };
}

export async function parseResearchResponse(response: Response): Promise<BriefingCard> {
  const payload = (await response.json()) as ResearchResponse;
  return parseResearchPayload(payload);
}
