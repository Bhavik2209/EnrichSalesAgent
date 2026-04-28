export type GeographyStatus = 'target' | 'flagged' | 'unknown';
export type ConfidenceLevel = 'confirmed' | 'uncertain' | 'unconfirmed';

export interface CompanySnapshot {
  officialName: string;
  parentCompany: string | null;
  hqLocation: string | null;
  hqCountry: string | null;
  founded: string | null;
  employeeRange: string | null;
  revenue: string | null;
  revenueConfidence: ConfidenceLevel;
  geographyStatus: GeographyStatus;
  website: string | null;
  linkedinUrl: string | null;
  phone: string | null;
  tags: string[];
  siteEmails: string[];
  sources: string[];
}

export interface AftermarketFootprint {
  hasPortal: boolean | null;
  portalUrl: string | null;
  description: string | null;
  confidence: ConfidenceLevel;
  emails: string[];
  sources: string[];
}

export interface BoothContact {
  name: string | null;
  title: string | null;
  email: string | null;
  confidence: string | null;
  reasoning: string | null;
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
  productLine: string | null;
  productLineSources: string[];
  aftermarket: AftermarketFootprint;
  boothContact: BoothContact;
  recentSignals: RecentSignal[];
  openingLine: string | null;
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
  stage?: string;
}
