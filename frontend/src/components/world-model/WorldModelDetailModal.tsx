/**
 * Project JobHunter V3 - World Model Detail Modal
 * Shows full selector JSON and site statistics
 */

import { useEffect, useState } from 'react';
import { 
  X, 
  Brain, 
  Globe, 
  Copy, 
  Check,
  Clock,
  TrendingUp,
  AlertCircle,
  ChevronDown,
  ChevronRight,
  Code
} from 'lucide-react';
import { clsx } from 'clsx';
import { useUIStore, useWorldModelStore } from '@/store';
import type { SiteConfig } from '@/types';

export function WorldModelDetailModal() {
  const { showWorldModelDetail, selectedDomain, setShowWorldModelDetail } = useUIStore();
  const { sites } = useWorldModelStore();
  const [copied, setCopied] = useState(false);
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set(['selectors']));

  const site = sites.find(s => s.domain === selectedDomain);

  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setShowWorldModelDetail(false);
      }
    };
    
    window.addEventListener('keydown', handleEscape);
    return () => window.removeEventListener('keydown', handleEscape);
  }, [setShowWorldModelDetail]);

  if (!showWorldModelDetail || !site) return null;

  const handleCopy = async () => {
    await navigator.clipboard.writeText(JSON.stringify(site.selectors, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const toggleSection = (section: string) => {
    const newExpanded = new Set(expandedSections);
    if (newExpanded.has(section)) {
      newExpanded.delete(section);
    } else {
      newExpanded.add(section);
    }
    setExpandedSections(newExpanded);
  };

  const successRate = getSuccessRate(site);
  const selectorCount = countSelectors(site.selectors);

  return (
    <div 
      className="modal-backdrop"
      onClick={() => setShowWorldModelDetail(false)}
    >
      <div 
        className="modal-content max-w-4xl max-h-[85vh] overflow-hidden flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-slate-700">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-emerald-500/20 flex items-center justify-center">
              <Globe className="w-5 h-5 text-emerald-400" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-slate-200">{site.domain}</h2>
              <p className="text-sm text-slate-400">{site.name}</p>
            </div>
          </div>
          <button
            onClick={() => setShowWorldModelDetail(false)}
            className="p-2 hover:bg-slate-700 rounded-lg transition-colors"
          >
            <X className="w-5 h-5 text-slate-400" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {/* Stats Grid */}
          <div className="grid grid-cols-4 gap-4">
            <StatBox 
              label="Selectors" 
              value={selectorCount}
              icon={<Brain className="w-4 h-4 text-purple-400" />}
            />
            <StatBox 
              label="Success Rate" 
              value={`${successRate.toFixed(1)}%`}
              icon={<TrendingUp className="w-4 h-4 text-emerald-400" />}
            />
            <StatBox 
              label="Successes" 
              value={site.success_count}
              icon={<Check className="w-4 h-4 text-green-400" />}
            />
            <StatBox 
              label="Failures" 
              value={site.failure_count}
              icon={<AlertCircle className="w-4 h-4 text-red-400" />}
            />
          </div>

          {/* Metadata */}
          <CollapsibleSection
            title="Metadata"
            icon={<Clock className="w-4 h-4" />}
            isExpanded={expandedSections.has('metadata')}
            onToggle={() => toggleSection('metadata')}
          >
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <div className="text-slate-500 mb-1">Category</div>
                <div className="text-slate-200 capitalize">{site.category.replace('_', ' ')}</div>
              </div>
              <div>
                <div className="text-slate-500 mb-1">Status</div>
                <div className={clsx(
                  'inline-flex items-center gap-1',
                  site.is_active ? 'text-emerald-400' : 'text-slate-500'
                )}>
                  {site.is_active ? 'Active' : 'Inactive'}
                </div>
              </div>
              <div>
                <div className="text-slate-500 mb-1">Created</div>
                <div className="text-slate-200">
                  {new Date(site.created_at).toLocaleString()}
                </div>
              </div>
              <div>
                <div className="text-slate-500 mb-1">Last Updated</div>
                <div className="text-slate-200">
                  {new Date(site.updated_at).toLocaleString()}
                </div>
              </div>
            </div>
          </CollapsibleSection>

          {/* Selectors JSON */}
          <CollapsibleSection
            title="Learned Selectors"
            icon={<Code className="w-4 h-4" />}
            isExpanded={expandedSections.has('selectors')}
            onToggle={() => toggleSection('selectors')}
            action={
              <button
                onClick={handleCopy}
                className="flex items-center gap-1 px-2 py-1 text-xs bg-slate-700 hover:bg-slate-600 rounded transition-colors"
              >
                {copied ? (
                  <>
                    <Check className="w-3 h-3 text-emerald-400" />
                    <span className="text-emerald-400">Copied!</span>
                  </>
                ) : (
                  <>
                    <Copy className="w-3 h-3" />
                    <span>Copy</span>
                  </>
                )}
              </button>
            }
          >
            <div className="bg-slate-950 rounded-lg p-4 overflow-x-auto">
              <JsonTree data={site.selectors} />
            </div>
          </CollapsibleSection>

          {/* Workflows */}
          {site.workflows && Object.keys(site.workflows).length > 0 && (
            <CollapsibleSection
              title="Learned Workflows"
              icon={<Brain className="w-4 h-4" />}
              isExpanded={expandedSections.has('workflows')}
              onToggle={() => toggleSection('workflows')}
            >
              <div className="bg-slate-950 rounded-lg p-4 overflow-x-auto">
                <JsonTree data={site.workflows} />
              </div>
            </CollapsibleSection>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-slate-700 flex justify-end gap-3">
          <button
            onClick={() => setShowWorldModelDetail(false)}
            className="btn-secondary"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

interface StatBoxProps {
  label: string;
  value: number | string;
  icon: React.ReactNode;
}

function StatBox({ label, value, icon }: StatBoxProps) {
  return (
    <div className="bg-slate-800/50 rounded-lg p-3 text-center">
      <div className="flex items-center justify-center gap-2 text-sm text-slate-400 mb-1">
        {icon}
        {label}
      </div>
      <div className="text-xl font-bold text-slate-200">{value}</div>
    </div>
  );
}

interface CollapsibleSectionProps {
  title: string;
  icon: React.ReactNode;
  isExpanded: boolean;
  onToggle: () => void;
  action?: React.ReactNode;
  children: React.ReactNode;
}

function CollapsibleSection({ 
  title, 
  icon, 
  isExpanded, 
  onToggle, 
  action,
  children 
}: CollapsibleSectionProps) {
  return (
    <div className="bg-slate-800/30 rounded-lg overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between p-3 hover:bg-slate-700/30 transition-colors"
      >
        <div className="flex items-center gap-2 text-slate-300">
          {isExpanded ? (
            <ChevronDown className="w-4 h-4" />
          ) : (
            <ChevronRight className="w-4 h-4" />
          )}
          {icon}
          <span className="font-medium">{title}</span>
        </div>
        {action && (
          <div onClick={(e) => e.stopPropagation()}>
            {action}
          </div>
        )}
      </button>
      {isExpanded && (
        <div className="p-3 pt-0">
          {children}
        </div>
      )}
    </div>
  );
}

interface JsonTreeProps {
  data: unknown;
  level?: number;
}

function JsonTree({ data, level = 0 }: JsonTreeProps) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  
  // Expand first level by default
  useEffect(() => {
    if (level === 0 && typeof data === 'object' && data !== null) {
      setExpanded(new Set(Object.keys(data)));
    }
  }, [data, level]);

  if (data === null) {
    return <span className="text-slate-500">null</span>;
  }

  if (typeof data === 'string') {
    return <span className="text-emerald-400">"{data}"</span>;
  }

  if (typeof data === 'number') {
    return <span className="text-cyan-400">{data}</span>;
  }

  if (typeof data === 'boolean') {
    return <span className="text-purple-400">{data.toString()}</span>;
  }

  if (Array.isArray(data)) {
    if (data.length === 0) {
      return <span className="text-slate-500">[]</span>;
    }
    
    return (
      <div className="pl-4">
        <span className="text-slate-500">[</span>
        {data.map((item, index) => (
          <div key={index} className="pl-4">
            <JsonTree data={item} level={level + 1} />
            {index < data.length - 1 && <span className="text-slate-500">,</span>}
          </div>
        ))}
        <span className="text-slate-500">]</span>
      </div>
    );
  }

  if (typeof data === 'object') {
    const entries = Object.entries(data);
    if (entries.length === 0) {
      return <span className="text-slate-500">{'{}'}</span>;
    }

    return (
      <div>
        {entries.map(([key, value], index) => {
          const isExpandable = typeof value === 'object' && value !== null;
          const isOpen = expanded.has(key);

          return (
            <div key={key} className={clsx(level > 0 && 'pl-4')}>
              <div className="flex items-start gap-1">
                {isExpandable && (
                  <button
                    onClick={() => {
                      const newExpanded = new Set(expanded);
                      if (newExpanded.has(key)) {
                        newExpanded.delete(key);
                      } else {
                        newExpanded.add(key);
                      }
                      setExpanded(newExpanded);
                    }}
                    className="text-slate-500 hover:text-slate-300 mt-0.5"
                  >
                    {isOpen ? (
                      <ChevronDown className="w-3 h-3" />
                    ) : (
                      <ChevronRight className="w-3 h-3" />
                    )}
                  </button>
                )}
                {!isExpandable && <span className="w-3" />}
                <span className="text-blue-400">"{key}"</span>
                <span className="text-slate-500">: </span>
                {isExpandable ? (
                  isOpen ? (
                    <div className="flex-1">
                      <JsonTree data={value} level={level + 1} />
                    </div>
                  ) : (
                    <span className="text-slate-500">
                      {Array.isArray(value) 
                        ? `[${value.length} items]` 
                        : `{${Object.keys(value).length} keys}`
                      }
                    </span>
                  )
                ) : (
                  <JsonTree data={value} level={level + 1} />
                )}
                {index < entries.length - 1 && <span className="text-slate-500">,</span>}
              </div>
            </div>
          );
        })}
      </div>
    );
  }

  return <span className="text-slate-400">{String(data)}</span>;
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
