import { createBrowserRouter, RouterProvider } from 'react-router-dom';
import { Home } from './pages/Home';
import { DocPage } from './pages/DocPage';
import { NotFound } from './pages/NotFound';
import { PluginBuilder } from './pages/PluginBuilder';
import { DocsLayout } from './layouts/DocsLayout';
import { Header } from './components/Header';

function RootLayout() {
  return (
    <>
      <Header />
      <DocsLayout />
    </>
  );
}

function HomeLayout() {
  return (
    <>
      <Header />
      <Home />
    </>
  );
}

function PluginBuilderLayout() {
  return (
    <>
      <Header />
      <PluginBuilder />
    </>
  );
}

const router = createBrowserRouter([
  {
    path: '/',
    element: <HomeLayout />,
  },
  {
    path: '/plugin-builder',
    element: <PluginBuilderLayout />,
  },
  {
    path: '/docs',
    element: <RootLayout />,
    children: [
      { path: 'quickstart', element: <DocPage /> },
      { path: 'jit-guide', element: <DocPage /> },
      { path: 'plugin-guide', element: <DocPage /> },
      { path: 'architecture', element: <DocPage /> },
      { path: 'api-reference', element: <DocPage /> },
      { path: 'hardware-reference', element: <DocPage /> },
      { path: 'features', element: <DocPage /> },
      { path: 'benchmarks', element: <DocPage /> },
      { path: 'cli', element: <DocPage /> },
      { path: 'contributing', element: <DocPage /> },
      { path: 'guides', element: <DocPage /> },
      { path: 'how-uhcr-works', element: <DocPage /> },
      { path: 'multi-isa', element: <DocPage /> },
      { path: 'network', element: <DocPage /> },
      { path: 'plugins', element: <DocPage /> },
      { path: 'reference', element: <DocPage /> },
      { path: 'runtime', element: <DocPage /> },
      { path: 'storage', element: <DocPage /> },
    ],
  },
  {
    path: '*',
    element: <><Header /><NotFound /></>,
  },
]);

export function Router() {
  return <RouterProvider router={router} />;
}
