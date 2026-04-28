export type GeographyStatus = 'target' | 'flagged' | 'unknown';
export type ConfidenceLevel = 'confirmed' | 'uncertain' | 'unconfirmed';

export interface CompanySnapshot {
  officialName: string;
  parentCompany: string | null;
  hqLocation: string;
  hqCountry: string;
  founded: string | null;
  employeeRange: string | null;
  revenue: string | null;
  revenueConfidence: ConfidenceLevel;
  geographyStatus: GeographyStatus;
  sources: string[];
}

export interface AftermarketFootprint {
  hasPortal: boolean | null;
  portalUrl: string | null;
  description: string;
  confidence: ConfidenceLevel;
  sources: string[];
}

export interface BoothContact {
  name: string | null;
  title: string;
  email: string | null;
  reasoning: string;
  isVerified: boolean;
  sourceUrl: string | null;
  sourceLabel: string | null;
}

export interface RecentSignal {
  date: string;
  headline: string;
  sourceName: string;
  sourceUrl: string;
  tags: string[];
}

export interface BriefingCard {
  companyName: string;
  snapshot: CompanySnapshot;
  productLine: string;
  productLineSources: string[];
  aftermarket: AftermarketFootprint;
  boothContact: BoothContact;
  recentSignals: RecentSignal[];
  openingLine: string;
  allSources: string[];
  generatedAt: string;
}

export type ProgressStepStatus = 'pending' | 'active' | 'done' | 'failed';
export type ProgressStepType = 'search' | 'fetch' | 'person' | 'news' | 'synthesis' | 'done';

export interface ProgressStep {
  id: string;
  timestamp: string;
  message: string;
  status: ProgressStepStatus;
  type: ProgressStepType;
}
