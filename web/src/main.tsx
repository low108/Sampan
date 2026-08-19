import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { App } from './App';
import { ErrorBoundary } from './components/ErrorBoundary';
import './app.css';
/* Defines <sampan-map>. Imported rather than loaded from public/ so the
 * bundler content-hashes it: a public/ script keeps its filename forever and
 * browsers went on serving a cached copy across deploys. */
import './sampan-map.js';

const host = document.getElementById('app');
if (!host) throw new Error('#app is missing from index.html');
createRoot(host).render(
  <StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </StrictMode>,
);
