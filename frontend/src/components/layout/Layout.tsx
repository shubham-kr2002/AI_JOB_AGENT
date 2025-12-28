/**
 * Project JobHunter V3 - Main Layout
 * Split view with Command Input and Live Feed
 */

import { Sidebar } from './Sidebar';
import { clsx } from 'clsx';

interface LayoutProps {
  children: React.ReactNode;
}

export function Layout({ children }: LayoutProps) {
  return (
    <div className="flex h-screen bg-slate-900 overflow-hidden">
      {/* Sidebar */}
      <Sidebar />

      {/* Main Content Area */}
      <main
        className={clsx(
          'flex-1 flex flex-col overflow-hidden',
          'transition-all duration-300'
        )}
      >
        {/* Header */}
        <header className="h-14 flex items-center justify-between px-6 border-b border-slate-700 bg-slate-900/50 backdrop-blur">
          <div className="flex items-center gap-4">
            <h1 className="text-lg font-semibold text-slate-200">
              Mission Control
            </h1>
            <div className="h-4 w-px bg-slate-700" />
            <span className="text-sm text-slate-500 terminal-text">
              {new Date().toLocaleDateString('en-US', { 
                weekday: 'short', 
                month: 'short', 
                day: 'numeric',
                year: 'numeric'
              })}
            </span>
          </div>

          {/* Status Indicators */}
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-slate-800 border border-slate-700">
              <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              <span className="text-xs text-slate-400 terminal-text">READY</span>
            </div>
          </div>
        </header>

        {/* Content */}
        <div className="flex-1 overflow-auto">
          {children}
        </div>
      </main>
    </div>
  );
}

export { Sidebar };
