import { useCallback, useRef, useState } from 'react';
import type { BriefingCard, ProgressStep, ProgressStepType } from '@/types/briefing';
import { parseResearchResponse } from '@/utils/research';

const MOCK_KRONES: BriefingCard = {
  companyName: 'Krones AG',
  snapshot: {
    officialName: 'Krones AG',
    parentCompany: null,
    hqLocation: 'Neutraubling, Bavaria, Germany',
    hqCountry: 'Germany',
    founded: '1951',
    employeeRange: '~18,000',
    revenue: '~€4.6B (2023)',
    revenueConfidence: 'confirmed',
    geographyStatus: 'target',
    sources: ['https://www.krones.com/en/company/krones-group.php'],
  },
  productLine:
    'Krones manufactures complete filling and packaging lines for the beverage, food, and liquid-food industries — including bottling lines, labelers, packers, and palletizers. Their machines handle everything from PET bottles to glass and cans at speeds exceeding 100,000 containers per hour. They also produce process technology for breweries and soft-drink manufacturers.',
  productLineSources: ['https://www.krones.com/en/products/'],
  aftermarket: {
    hasPortal: true,
    portalUrl: 'https://www.krones.com/en/services/digital-services/syskron/',
    description:
      'Krones operates a digital services division called Syskron offering a customer portal, remote monitoring, and parts ordering. The portal is clearly customer-facing and aftermarket-focused.',
    confidence: 'confirmed',
    sources: ['https://www.krones.com/en/services/'],
  },
  boothContact: {
    name: null,
    title: 'VP of Digital Services / Head of Lifecycle Services',
    email: null,
    reasoning:
      'Krones has a dedicated Lifecycle Services and Digital Services division. A VP or Director from that unit owns the aftermarket conversation and is a more productive contact than a regional sales rep.',
    isVerified: false,
    sourceUrl: null,
    sourceLabel: null,
  },
  recentSignals: [
    {
      date: '2024-03-12',
      headline: 'Krones expands Syskron digital platform with predictive maintenance module',
      sourceName: 'Krones Press Room',
      sourceUrl: 'https://www.krones.com/en/press/',
      tags: ['digital transformation', 'aftermarket', 'predictive maintenance'],
    },
    {
      date: '2024-01-08',
      headline: 'Krones reports record order intake in FY2023 driven by service growth',
      sourceName: 'Krones Investor Relations',
      sourceUrl: 'https://www.krones.com/en/investor-relations/',
      tags: ['aftermarket', 'revenue growth'],
    },
  ],
  openingLine:
    'I noticed Krones just expanded the predictive maintenance layer in Syskron — we work with manufacturers at exactly that inflection point between selling a machine and selling uptime. Worth two minutes?',
  allSources: [
    'https://www.krones.com/en/company/krones-group.php',
    'https://www.krones.com/en/products/',
    'https://www.krones.com/en/services/',
    'https://www.krones.com/en/services/digital-services/syskron/',
    'https://www.krones.com/en/press/',
    'https://www.krones.com/en/investor-relations/',
  ],
  generatedAt: new Date().toISOString(),
};

interface MockStep {
  id: string;
  message: string;
  type: ProgressStepType;
}

const MOCK_STEPS: MockStep[] = [
  { id: '1', message: 'Starting enrichment for {COMPANY}...', type: 'search' },
  { id: '2', message: 'Running web search: "{COMPANY} company overview"...', type: 'search' },
  { id: '3', message: 'Fetching company website — overview page...', type: 'fetch' },
  { id: '4', message: 'Extracting snapshot: HQ, employees, revenue, founded...', type: 'fetch' },
  { id: '5', message: 'Geography check: classifying target market...', type: 'fetch' },
  { id: '6', message: 'Scanning for aftermarket / service / portal sections...', type: 'fetch' },
  { id: '7', message: 'Aftermarket portal analysis complete', type: 'fetch' },
  { id: '8', message: 'Searching recent news: aftermarket and digital transformation...', type: 'news' },
  { id: '9', message: 'Found relevant signals from the last 12 months', type: 'news' },
  { id: '10', message: 'Checking leadership / team page for verified contact...', type: 'person' },
  { id: '11', message: 'Returning role estimate (no named individual verified)', type: 'person' },
  { id: '12', message: 'Synthesizing briefing card and drafting opening line...', type: 'synthesis' },
  { id: '13', message: 'Briefing complete. Ready.', type: 'done' },
];

// Which step (index) reveals which section
export const REVEAL_AFTER: Record<string, number> = {
  identity: 4,        // after step 4
  geography: 5,
  productLine: 4,
  aftermarket: 7,
  signals: 9,
  boothContact: 9,
  openingLine: 10,
  sources: 11,
};

function nowStamp(): string {
  const d = new Date();
  return d.toTimeString().slice(0, 8);
}

function getApiBaseUrl(): string {
  return (import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000').trim();
}

const LIVE_PROGRESS_STEPS: MockStep[] = [
  { id: '1', message: 'Starting research for {COMPANY}...', type: 'search' },
  { id: '2', message: 'Resolving official website and company identity...', type: 'search' },
  { id: '3', message: 'Pulling company profile and about-page details...', type: 'fetch' },
  { id: '4', message: 'Extracting snapshot fields like HQ, employees, and revenue...', type: 'fetch' },
  { id: '5', message: 'Classifying geography and operating footprint...', type: 'fetch' },
  { id: '6', message: 'Checking service, support, and portal signals...', type: 'fetch' },
  { id: '7', message: 'Aftermarket footprint analysis complete...', type: 'fetch' },
  { id: '8', message: 'Estimating the best booth contact...', type: 'person' },
  { id: '9', message: 'Returning verified contact or best-fit role...', type: 'person' },
  { id: '10', message: 'Synthesizing the briefing card...', type: 'synthesis' },
];

export function useEnrichStream() {
  const [progressSteps, setProgressSteps] = useState<ProgressStep[]>([]);
  const [briefing, setBriefing] = useState<BriefingCard | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [completedStepCount, setCompletedStepCount] = useState(0);
  const cancelRef = useRef<{ cancelled: boolean } | null>(null);

  const reset = useCallback(() => {
    if (cancelRef.current) cancelRef.current.cancelled = true;
    setProgressSteps([]);
    setBriefing(null);
    setIsLoading(false);
    setError(null);
    setCompletedStepCount(0);
  }, []);

  const startEnrich = useCallback(async (companyName: string, context: string) => {
    setProgressSteps([]);
    setBriefing(null);
    setError(null);
    setIsLoading(true);
    setCompletedStepCount(0);

    const token = { cancelled: false };
    cancelRef.current = token;

    const mock = (import.meta.env.VITE_MOCK_MODE ?? 'false') === 'true';

    if (mock) {
      const company = companyName.trim() || 'Krones AG';
      // Build a per-company mock by templating the Krones briefing's company name
      const card: BriefingCard = {
        ...MOCK_KRONES,
        companyName: company,
        snapshot: { ...MOCK_KRONES.snapshot, officialName: company },
        generatedAt: new Date().toISOString(),
      };

      // Stream steps
      for (let i = 0; i < MOCK_STEPS.length; i++) {
        if (token.cancelled) return;
        const s = MOCK_STEPS[i];
        // Add as active first
        setProgressSteps(prev => [
          ...prev,
          {
            id: s.id,
            timestamp: nowStamp(),
            message: s.message.replace('{COMPANY}', company),
            type: s.type,
            status: 'active',
          },
        ]);
        await new Promise(r => setTimeout(r, 700));
        if (token.cancelled) return;
        // Mark done
        setProgressSteps(prev =>
          prev.map(p => (p.id === s.id ? { ...p, status: 'done' } : p)),
        );
        setCompletedStepCount(i + 1);
      }
      if (token.cancelled) return;
      setBriefing(card);
      setIsLoading(false);
      return;
    }

    // Real API path
    let intervalId: number | null = null;
    try {
      const base = getApiBaseUrl();
      let progressIndex = 0;
      const advanceProgress = () => {
        if (token.cancelled || progressIndex >= LIVE_PROGRESS_STEPS.length) return;
        const step = LIVE_PROGRESS_STEPS[progressIndex];
        setProgressSteps(prev => [
          ...prev,
          {
            id: step.id,
            timestamp: nowStamp(),
            message: step.message.replace('{COMPANY}', companyName),
            type: step.type,
            status: 'done',
          },
        ]);
        progressIndex += 1;
        setCompletedStepCount(progressIndex);
      };

      advanceProgress();
      intervalId = window.setInterval(advanceProgress, 1500);

      const res = await fetch(`${base}/research`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ company_name: companyName, extra_context: context }),
      });

      if (intervalId !== null) {
        window.clearInterval(intervalId);
      }
      if (!res.ok) {
        let message = `Request failed (${res.status})`;
        try {
          const errorPayload = await res.json();
          if (typeof errorPayload?.detail === 'string' && errorPayload.detail.trim()) {
            message = errorPayload.detail;
          }
        } catch {
          // Keep the HTTP fallback message if the server did not return JSON.
        }
        throw new Error(message);
      }

      const parsedBriefing = await parseResearchResponse(res);
      if (token.cancelled) return;
      setProgressSteps(prev => {
        const completedIds = new Set(prev.map(step => step.id));
        const remaining = LIVE_PROGRESS_STEPS
          .filter(step => !completedIds.has(step.id))
          .map(step => ({
            id: step.id,
            timestamp: nowStamp(),
            message: step.message.replace('{COMPANY}', companyName),
            type: step.type,
            status: 'done' as const,
          }));

        return [
          ...prev,
          ...remaining,
          {
            id: 'done',
            timestamp: nowStamp(),
            message: 'Briefing complete. Ready.',
            type: 'done' as ProgressStepType,
            status: 'done',
          },
        ];
      });
      setCompletedStepCount(LIVE_PROGRESS_STEPS.length + 1);
      setBriefing(parsedBriefing);
      setIsLoading(false);
    } catch (e: unknown) {
      if (intervalId !== null) {
        window.clearInterval(intervalId);
      }
      if (!token.cancelled) {
        setError(e instanceof Error ? e.message : 'Something went wrong');
        setIsLoading(false);
      }
    }
  }, []);

  return { progressSteps, briefing, isLoading, error, startEnrich, reset, completedStepCount };
}
