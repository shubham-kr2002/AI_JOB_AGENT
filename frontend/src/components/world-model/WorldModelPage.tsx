/**
 * Project JobHunter V3 - World Model Page
 * Displays learned site configurations and selectors
 */

import { useEffect, useState } from 'react';
import { 
  Brain, 
  Globe, 
  Clock, 
  CheckCircle2, 
  XCircle,
  ChevronRight,
  Search,
  RefreshCw,
  TrendingUp
} from 'lucide-react';
import { clsx } from 'clsx';
import { useWorldModelStore, useUIStore } from '@/store';
import { api } from '@/lib/api';
import type { SiteConfig } from '@/types';
import { WorldModelDetailModal } from './WorldModelDetailModal';

export function WorldModelPage() {
  const { sites, isLoading, error, setSites, setLoading, setError } = useWorldModelStore();
  const { setShowWorldModelDetail } = useUIStore();
  const [searchQuery, setSearchQuery] = useState('');
  const [sortBy, setSortBy] = useState<'domain' | 'success_rate' | 'last_used'>('domain');

  useEffect(() => {
    loadSites();
  }, []);

  const loadSites = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await api.getSites();
      if (response.success && response.data) {
        setSites(response.data);
      } else {
        setError(response.error || 'Failed to load sites');
      }
    } catch (err) {
      setError('Failed to load World Model data');
    } finally {
      setLoading(false);
    }
  };

  // Filter and sort sites
  const filteredSites = sites
    .filter(site => 
      site.domain.toLowerCase().includes(searchQuery.toLowerCase()) ||
      site.name.toLowerCase().includes(searchQuery.toLowerCase())
    )
    .sort((a, b) => {
      switch (sortBy) {
        case 'success_rate':
          return getSuccessRate(b) - getSuccessRate(a);
        case 'last_used':
          return new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime();
        default:
          return a.domain.localeCompare(b.domain);
      }
    });

  // Calculate stats
  const stats = {
    totalDomains: sites.length,
    totalSelectors: sites.reduce((sum, site) => sum + countSelectors(site.selectors), 0),
    avgSuccessRate: sites.length > 0
      ? sites.reduce((sum, site) => sum + getSuccessRate(site), 0) / sites.length
      : 0,
    activeSites: sites.filter(site => site.is_active).length,
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-emerald-500/20">
            <Brain className="w-6 h-6 text-emerald-400" />
          </div>
          <div>
            <h1 className="text-xl font-semibold text-slate-200">World Model</h1>
            <p className="text-sm text-slate-400">
              Learned knowledge about job sites and selectors
            </p>
          </div>
        </div>
        
        <button
          onClick={loadSites}
          disabled={isLoading}
          className="btn-secondary flex items-center gap-2"
        >
          <RefreshCw className={clsx('w-4 h-4', isLoading && 'animate-spin')} />
          Refresh
        </button>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-4 gap-4">
        <StatCard
          label="Known Domains"
          value={stats.totalDomains}
          icon={<Globe className="w-5 h-5 text-blue-400" />}
        />
        <StatCard
          label="Learned Selectors"
          value={stats.totalSelectors}
          icon={<Brain className="w-5 h-5 text-purple-400" />}
        />
        <StatCard
          label="Avg Success Rate"
          value={`${stats.avgSuccessRate.toFixed(1)}%`}
          icon={<TrendingUp className="w-5 h-5 text-emerald-400" />}
        />
        <StatCard
          label="Active Sites"
          value={stats.activeSites}
          icon={<CheckCircle2 className="w-5 h-5 text-green-400" />}
        />
      </div>

      {/* Search and Filter */}
      <div className="flex items-center gap-4">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search domains..."
            className="w-full pl-10 input-primary"
          />
        </div>
        
        <select
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value as typeof sortBy)}
          className="input-primary"
        >
          <option value="domain">Sort by Domain</option>
          <option value="success_rate">Sort by Success Rate</option>
          <option value="last_used">Sort by Last Used</option>
        </select>
      </div>

      {/* Sites Table */}
      <div className="card overflow-hidden">
        {error ? (
          <div className="p-8 text-center text-red-400">
            <XCircle className="w-8 h-8 mx-auto mb-2" />
            <p>{error}</p>
          </div>
        ) : isLoading ? (
          <div className="p-8 text-center text-slate-400">
            <RefreshCw className="w-8 h-8 mx-auto mb-2 animate-spin" />
            <p>Loading World Model data...</p>
          </div>
        ) : filteredSites.length === 0 ? (
          <div className="p-8 text-center text-slate-500">
            <Brain className="w-8 h-8 mx-auto mb-2" />
            <p>No sites learned yet. Start applying to jobs to build knowledge!</p>
          </div>
        ) : (
          <table className="w-full">
            <thead>
              <tr className="border-b border-slate-700 text-left">
                <th className="px-4 py-3 text-sm font-medium text-slate-400">Domain</th>
                <th className="px-4 py-3 text-sm font-medium text-slate-400">Category</th>
                <th className="px-4 py-3 text-sm font-medium text-slate-400">Last Visited</th>
                <th className="px-4 py-3 text-sm font-medium text-slate-400">Selectors</th>
                <th className="px-4 py-3 text-sm font-medium text-slate-400">Success Rate</th>
                <th className="px-4 py-3 text-sm font-medium text-slate-400">Status</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody>
              {filteredSites.map((site) => (
                <SiteRow 
                  key={site.domain} 
                  site={site} 
                  onViewDetails={() => setShowWorldModelDetail(true, site.domain)}
                />
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Detail Modal */}
      <WorldModelDetailModal />
    </div>
  );
}

interface StatCardProps {
  label: string;
  value: number | string;
  icon: React.ReactNode;
}

function StatCard({ label, value, icon }: StatCardProps) {
  return (
    <div className="card flex items-center gap-4">
      <div className="p-3 rounded-lg bg-slate-700/50">
        {icon}
      </div>
      <div>
        <div className="text-2xl font-bold text-slate-200">{value}</div>
        <div className="text-sm text-slate-400">{label}</div>
      </div>
    </div>
  );
}

interface SiteRowProps {
  site: SiteConfig;
  onViewDetails: () => void;
}

function SiteRow({ site, onViewDetails }: SiteRowProps) {
  const successRate = getSuccessRate(site);
  const selectorCount = countSelectors(site.selectors);
  const lastVisited = site.updated_at 
    ? new Date(site.updated_at).toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
      })
    : 'Never';

  return (
    <tr 
      className="border-b border-slate-700/50 hover:bg-slate-800/50 cursor-pointer transition-colors"
      onClick={onViewDetails}
    >
      <td className="px-4 py-3">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded bg-slate-700 flex items-center justify-center">
            <Globe className="w-4 h-4 text-slate-400" />
          </div>
          <div>
            <div className="font-medium text-slate-200">{site.domain}</div>
            <div className="text-xs text-slate-500">{site.name}</div>
          </div>
        </div>
      </td>
      <td className="px-4 py-3">
        <span className={clsx(
          'px-2 py-1 rounded text-xs font-medium',
          getCategoryClass(site.category)
        )}>
          {site.category}
        </span>
      </td>
      <td className="px-4 py-3">
        <div className="flex items-center gap-2 text-sm text-slate-400">
          <Clock className="w-4 h-4" />
          {lastVisited}
        </div>
      </td>
      <td className="px-4 py-3">
        <span className="text-slate-200 font-medium">{selectorCount}</span>
      </td>
      <td className="px-4 py-3">
        <div className="flex items-center gap-2">
          <div className="w-20 h-2 rounded-full bg-slate-700 overflow-hidden">
            <div 
              className={clsx(
                'h-full rounded-full',
                successRate >= 80 ? 'bg-emerald-500' :
                successRate >= 50 ? 'bg-yellow-500' : 'bg-red-500'
              )}
              style={{ width: `${successRate}%` }}
            />
          </div>
          <span className="text-sm text-slate-400">{successRate.toFixed(0)}%</span>
        </div>
      </td>
      <td className="px-4 py-3">
        {site.is_active ? (
          <span className="flex items-center gap-1 text-emerald-400 text-sm">
            <CheckCircle2 className="w-4 h-4" />
            Active
          </span>
        ) : (
          <span className="flex items-center gap-1 text-slate-500 text-sm">
            <XCircle className="w-4 h-4" />
            Inactive
          </span>
        )}
      </td>
      <td className="px-4 py-3">
        <ChevronRight className="w-4 h-4 text-slate-500" />
      </td>
    </tr>
  );
}

function getSuccessRate(site: SiteConfig): number {
  const total = site.success_count + site.failure_count;
  if (total === 0) return 0;
  return (site.success_count / total) * 100;
}

function countSelectors(selectors: Record<string, unknown>): number {
  let count = 0;
  
  function traverse(obj: unknown) {
    if (typeof obj === 'object' && obj !== null) {
      for (const value of Object.values(obj)) {
        if (typeof value === 'string') {
          count++;
        } else if (typeof value === 'object') {
          traverse(value);
        }
      }
    }
  }
  
  traverse(selectors);
  return count;
}

function getCategoryClass(category: string): string {
  switch (category) {
    case 'job_board':
      return 'bg-blue-500/20 text-blue-400';
    case 'ats':
      return 'bg-purple-500/20 text-purple-400';
    case 'company_career':
      return 'bg-orange-500/20 text-orange-400';
    case 'aggregator':
      return 'bg-cyan-500/20 text-cyan-400';
    default:
      return 'bg-slate-700 text-slate-400';
  }
}
