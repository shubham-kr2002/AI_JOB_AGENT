/**
 * Project JobHunter V3 - Main App Component
 * Sets up routing and layout
 */

import { useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Layout } from '@/components/layout';
import { MissionControlPage, TaskHistoryPage, SettingsPage } from '@/pages';
import { WorldModelPage } from '@/components/world-model';
import { useUIStore } from '@/store';

function AppRoutes() {
  return (
    <Routes>
      <Route 
        path="/" 
        element={
          <PageWrapper page="mission">
            <MissionControlPage />
          </PageWrapper>
        } 
      />
      <Route 
        path="/history" 
        element={
          <PageWrapper page="history">
            <TaskHistoryPage />
          </PageWrapper>
        } 
      />
      <Route 
        path="/world-model" 
        element={
          <PageWrapper page="world-model">
            <WorldModelPage />
          </PageWrapper>
        } 
      />
      <Route 
        path="/settings" 
        element={
          <PageWrapper page="settings">
            <SettingsPage />
          </PageWrapper>
        } 
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

interface PageWrapperProps {
  page: 'mission' | 'history' | 'world-model' | 'settings';
  children: React.ReactNode;
}

function PageWrapper({ page, children }: PageWrapperProps) {
  const { setCurrentPage } = useUIStore();

  useEffect(() => {
    setCurrentPage(page);
  }, [page, setCurrentPage]);

  return <>{children}</>;
}

export default function App() {
  return (
    <BrowserRouter>
      <Layout>
        <AppRoutes />
      </Layout>
    </BrowserRouter>
  );
}
