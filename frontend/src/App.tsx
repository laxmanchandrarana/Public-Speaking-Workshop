import { useState, useEffect, useRef } from 'react';
import { Header } from './components/Header';
import { Hero } from './components/Hero';
import { Countdown } from './components/Countdown';
import { Benefits } from './components/Benefits';
import { WorkshopInfo } from './components/WorkshopInfo';
import { RegistrationForm } from './components/RegistrationForm';
import { RegistrationSuccess } from './components/RegistrationSuccess';
import { Footer } from './components/Footer';
import type { Workshop, RegistrationResponse } from './types';
import { fetchWorkshop } from './api';
import { AlertCircle, RefreshCw } from 'lucide-react';

export function App() {
  const [workshop, setWorkshop] = useState<Workshop | null>(null);
  const [loadingWorkshop, setLoadingWorkshop] = useState(true);
  const [workshopError, setWorkshopError] = useState<string | null>(null);

  // Success state after registration
  const [registrationResult, setRegistrationResult] = useState<{
    data: RegistrationResponse;
    isNew: boolean;
  } | null>(null);

  const registrationSectionRef = useRef<HTMLElement | null>(null);

  const loadWorkshopData = async () => {
    setLoadingWorkshop(true);
    setWorkshopError(null);
    try {
      const data = await fetchWorkshop();
      setWorkshop(data);
    } catch (err: unknown) {
      console.error('Failed to load workshop data from Django backend:', err);
      setWorkshopError('Could not load current workshop schedule. Please click retry.');
    } finally {
      setLoadingWorkshop(false);
    }
  };

  useEffect(() => {
    let ignore = false;
    fetchWorkshop()
      .then((data) => {
        if (!ignore) {
          setWorkshop(data);
          setLoadingWorkshop(false);
        }
      })
      .catch((err) => {
        if (!ignore) {
          console.error('Failed to load workshop data from Django backend:', err);
          setWorkshopError('Could not load current workshop schedule. Please click retry.');
          setLoadingWorkshop(false);
        }
      });

    return () => {
      ignore = true;
    };
  }, []);

  const scrollToRegistration = () => {
    if (registrationSectionRef.current) {
      registrationSectionRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  };

  const scrollToInfo = () => {
    const el = document.getElementById('workshop-info');
    if (el) {
      el.scrollIntoView({ behavior: 'smooth' });
    }
  };

  return (
    <div className="min-h-screen bg-[#090a10] text-gray-100 flex flex-col selection:bg-indigo-600/30 selection:text-white">
      {/* Top Loading Progress Bar */}
      {loadingWorkshop && (
        <div 
          className="fixed top-0 left-0 right-0 h-0.5 bg-gradient-to-r from-indigo-500 via-purple-500 to-indigo-500 animate-pulse z-[60]" 
          role="progressbar" 
          aria-label="Loading workshop information" 
        />
      )}

      {/* Navigation Header */}
      <Header onReserveClick={scrollToRegistration} />

      {/* Main Content Area */}
      <main className="flex-1">
        {/* Backend Warning Banner if initial fetch fails */}
        {workshopError && (
          <div className="pt-24 max-w-4xl mx-auto px-4">
            <div className="p-3.5 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-300 text-xs sm:text-sm flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <AlertCircle className="w-4 h-4 text-amber-400 shrink-0" />
                <span>{workshopError}</span>
              </div>
              <button
                onClick={loadWorkshopData}
                className="inline-flex items-center gap-1.5 px-3 py-1 bg-amber-500/20 hover:bg-amber-500/30 rounded-lg text-xs font-semibold text-amber-200 transition-colors"
              >
                <RefreshCw className="w-3 h-3" />
                <span>Retry</span>
              </button>
            </div>
          </div>
        )}

        {/* Hero Section */}
        <Hero
          workshop={workshop}
          onReserveClick={scrollToRegistration}
          onLearnMoreClick={scrollToInfo}
        />

        {/* Live Countdown Section */}
        <Countdown
          scheduledAt={workshop?.scheduled_at || '2026-09-18T15:30:00+05:30'}
          timezone={workshop?.timezone || 'Asia/Kolkata'}
        />

        {/* Benefits Section */}
        <Benefits />

        {/* Workshop Overview / Details Section */}
        <WorkshopInfo workshop={workshop} />

        {/* Registration Section */}
        <section
          id="register"
          ref={registrationSectionRef}
          className="py-20 sm:py-28 relative overflow-hidden"
          aria-labelledby="registration-heading"
        >
          {/* Subtle Ambient Radial Glow */}
          <div 
            className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-indigo-600/10 rounded-full blur-[140px] pointer-events-none -z-10" 
            aria-hidden="true" 
          />

          <div className="max-w-4xl mx-auto px-4 sm:px-6">
            <div className="sr-only">
              <h2 id="registration-heading">Workshop Seat Reservation</h2>
            </div>

            {registrationResult ? (
              <RegistrationSuccess
                response={registrationResult.data}
                isNew={registrationResult.isNew}
                onReset={() => {
                  setRegistrationResult(null);
                  window.scrollTo({ top: 0, behavior: 'smooth' });
                }}
              />
            ) : (
              <RegistrationForm
                onSuccess={(data, isNew) => {
                  setRegistrationResult({ data, isNew });
                }}
              />
            )}
          </div>
        </section>
      </main>

      {/* Footer */}
      <Footer />
    </div>
  );
}

export default App;
