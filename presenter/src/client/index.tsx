import { Suspense } from 'react';
import { renderApp } from 'modelence/client';
import { RouterProvider } from 'react-router-dom';
import { router } from './router';
import './index.css';

const Fallback = (
  <div className="min-h-screen bg-slate-900 flex items-center justify-center text-slate-400">
    Loading…
  </div>
);

renderApp({
  routesElement: (
    <Suspense fallback={Fallback}>
      <RouterProvider router={router} />
    </Suspense>
  ),
  loadingElement: Fallback,
});
