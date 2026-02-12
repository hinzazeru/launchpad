import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Layout } from '@/components/Layout';
import { Dashboard } from '@/pages/Dashboard';
import { GetJobs } from '@/pages/GetJobs';
import { JobMatches } from '@/pages/JobMatches';
import { Library } from '@/pages/Library';
import { Analytics } from '@/pages/Analytics';
import { Settings } from '@/pages/Settings';
import { ErrorBoundary } from '@/components/ErrorBoundary';
import { ToastProvider } from '@/components/ui/toast';
import { SearchStatusIndicator } from '@/components/SearchStatusIndicator';

function App() {
  return (
    <ErrorBoundary>
      <ToastProvider>
        <BrowserRouter>
          <Layout>
            <ErrorBoundary>
              <Routes>
                <Route path="/" element={<GetJobs />} />
                <Route path="/analyze" element={<Dashboard />} />
                <Route path="/matches" element={<JobMatches />} />
                <Route path="/library" element={<Library />} />
                <Route path="/analytics" element={<Analytics />} />
                <Route path="/settings" element={<Settings />} />
              </Routes>
            </ErrorBoundary>
          </Layout>
          <SearchStatusIndicator />
        </BrowserRouter>
      </ToastProvider>
    </ErrorBoundary>
  );
}

export default App;
