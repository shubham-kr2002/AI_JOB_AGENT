/**
 * Project JobHunter V3 - Sidebar Navigation
 * Terminal/Hacker themed navigation with green accents
 */

import { 
  Target, 
  History, 
  Brain, 
  Settings, 
  ChevronLeft, 
  ChevronRight,
  Zap,
  Activity
} from 'lucide-react';
import { clsx } from 'clsx';
import { useUIStore } from '@/store';

interface NavItem {
  id: 'mission' | 'history' | 'world-model' | 'settings';
  label: string;
  icon: React.ReactNode;
  description: string;
}

const navItems: NavItem[] = [
  {
    id: 'mission',
    label: 'Mission Control',
    icon: <Target className="w-5 h-5" />,
    description: 'Launch new missions',
  },
  {
    id: 'history',
    label: 'Task History',
    icon: <History className="w-5 h-5" />,
    description: 'Past operations',
  },
  {
    id: 'world-model',
    label: 'World Model',
    icon: <Brain className="w-5 h-5" />,
    description: 'Learned knowledge',
  },
  {
    id: 'settings',
    label: 'Settings',
    icon: <Settings className="w-5 h-5" />,
    description: 'Configuration',
  },
];

export function Sidebar() {
  const { sidebarCollapsed, toggleSidebar, currentPage, setCurrentPage } = useUIStore();

  return (
    <aside
      className={clsx(
        'flex flex-col h-screen bg-slate-900 border-r border-slate-700',
        'transition-all duration-300 ease-in-out',
        sidebarCollapsed ? 'w-16' : 'w-64'
      )}
    >
      {/* Logo/Brand */}
      <div className="flex items-center h-16 px-4 border-b border-slate-700">
        <div className="flex items-center gap-3">
          <div className="relative">
            <Zap className="w-8 h-8 text-emerald-500" />
            <Activity className="w-3 h-3 text-emerald-400 absolute -bottom-1 -right-1 animate-pulse" />
          </div>
          {!sidebarCollapsed && (
            <div className="flex flex-col">
              <span className="font-bold text-emerald-500 glow-text">JobHunter</span>
              <span className="text-xs text-slate-500 terminal-text">v3.0 AUTONOMOUS</span>
            </div>
          )}
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-4 overflow-y-auto">
        <ul className="space-y-1 px-2">
          {navItems.map((item) => (
            <li key={item.id}>
              <button
                onClick={() => setCurrentPage(item.id)}
                className={clsx(
                  'w-full flex items-center gap-3 px-3 py-3 rounded-lg',
                  'transition-all duration-200',
                  'group relative',
                  currentPage === item.id
                    ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                    : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'
                )}
              >
                {/* Active indicator */}
                {currentPage === item.id && (
                  <div className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-8 bg-emerald-500 rounded-r" />
                )}
                
                <span className={clsx(
                  'flex-shrink-0',
                  currentPage === item.id && 'text-emerald-400'
                )}>
                  {item.icon}
                </span>
                
                {!sidebarCollapsed && (
                  <div className="flex flex-col items-start">
                    <span className="font-medium text-sm">{item.label}</span>
                    <span className="text-xs text-slate-500">{item.description}</span>
                  </div>
                )}

                {/* Tooltip for collapsed state */}
                {sidebarCollapsed && (
                  <div className={clsx(
                    'absolute left-full ml-2 px-2 py-1 rounded',
                    'bg-slate-800 text-slate-200 text-sm whitespace-nowrap',
                    'opacity-0 group-hover:opacity-100 transition-opacity',
                    'pointer-events-none z-50'
                  )}>
                    {item.label}
                  </div>
                )}
              </button>
            </li>
          ))}
        </ul>
      </nav>

      {/* System Status */}
      {!sidebarCollapsed && (
        <div className="p-4 border-t border-slate-700">
          <div className="flex items-center gap-2 text-xs text-slate-500">
            <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            <span className="terminal-text">SYSTEM ONLINE</span>
          </div>
          <div className="mt-2 text-xs text-slate-600 terminal-text">
            Backend: localhost:8000
          </div>
        </div>
      )}

      {/* Collapse Toggle */}
      <button
        onClick={toggleSidebar}
        className={clsx(
          'flex items-center justify-center h-12',
          'border-t border-slate-700',
          'text-slate-500 hover:text-emerald-400 hover:bg-slate-800',
          'transition-colors'
        )}
      >
        {sidebarCollapsed ? (
          <ChevronRight className="w-5 h-5" />
        ) : (
          <ChevronLeft className="w-5 h-5" />
        )}
      </button>
    </aside>
  );
}
