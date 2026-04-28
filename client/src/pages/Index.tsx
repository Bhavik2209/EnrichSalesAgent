import { useState } from 'react';
import { Header } from '@/components/Header';
import { InputForm } from '@/components/InputForm';
import { ProgressView } from '@/components/ProgressView';
import { BriefingCard } from '@/components/BriefingCard';
import { StickyActionBar } from '@/components/StickyActionBar';
import { ErrorView } from '@/components/ErrorView';
import { useEnrichStream } from '@/hooks/useEnrichStream';

export default function Index() {
  const [submittedCompany, setSubmittedCompany] = useState<string | null>(null);
  const { progressSteps, briefing, isLoading, error, startEnrich, reset, completedStepCount } = useEnrichStream();

  const handleSubmit = (company: string, context: string) => {
    setSubmittedCompany(company);
    startEnrich(company, context);
  };

  const handleReset = () => {
    reset();
    setSubmittedCompany(null);
  };

  // STATE 3: result
  const showResult = !!briefing && !isLoading;
  // STATE 2: progress
  const showProgress = isLoading || (submittedCompany && !briefing && !error);
  // STATE 1: input
  const showInput = !submittedCompany && !error;

  return (
    <div className="min-h-screen bg-background flex flex-col">
      <Header />
      <main className="flex-1">
        {error && <ErrorView message={error} onRetry={handleReset} />}
        {!error && showInput && (
          <div className="max-w-[1200px] mx-auto px-6 pb-20">
            <InputForm onSubmit={handleSubmit} />
          </div>
        )}
        {!error && showProgress && submittedCompany && (
          <ProgressView
            companyName={submittedCompany}
            steps={progressSteps}
            briefing={briefing}
            completedStepCount={completedStepCount}
          />
        )}
        {!error && showResult && briefing && <BriefingCard b={briefing} />}
      </main>
      {showResult && briefing && <StickyActionBar briefing={briefing} onReset={handleReset} />}
    </div>
  );
}
