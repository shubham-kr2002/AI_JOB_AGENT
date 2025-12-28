/**
 * Project JobHunter V3 - Command Input Component
 * FR-01: Intent-Based Input - Natural language mission prompt
 */

import { useState, useRef, useEffect } from 'react';
import { Send, Loader2, Sparkles, Terminal } from 'lucide-react';
import { clsx } from 'clsx';
import { useTaskStore, useUIStore } from '@/store';
import { api } from '@/lib/api';

const PLACEHOLDER_PROMPTS = [
  "Find 20 AI Engineering jobs in San Francisco that don't require 5+ years of experience",
  "Apply to remote Python developer positions at YCombinator startups",
  "Search for Senior Product Manager roles in NYC, avoid crypto companies",
  "Find Machine Learning positions at companies using LangChain or LlamaIndex",
];

export function CommandInput() {
  const [prompt, setPrompt] = useState('');
  const [placeholderIndex, setPlaceholderIndex] = useState(0);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  
  const { setPlan } = useTaskStore();
  const { isLoading, setLoading, setShowPlanPreview } = useUIStore();

  // Rotate placeholder prompts
  useEffect(() => {
    const interval = setInterval(() => {
      setPlaceholderIndex((prev) => (prev + 1) % PLACEHOLDER_PROMPTS.length);
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`;
    }
  }, [prompt]);

  const handleSubmit = async () => {
    if (!prompt.trim() || isLoading) return;

    setLoading(true, 'Compiling Intent...');

    try {
      const response = await api.createPlan(prompt);
      
      if (response.success && response.data) {
        setPlan(response.data.plan);
        setShowPlanPreview(true);
      } else {
        console.error('Failed to create plan:', response.error);
      }
    } catch (error) {
      console.error('Error creating plan:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="flex flex-col items-center justify-center p-8">
      {/* Header */}
      <div className="text-center mb-8">
        <div className="flex items-center justify-center gap-2 mb-2">
          <Terminal className="w-6 h-6 text-emerald-500" />
          <h2 className="text-2xl font-bold text-slate-200">
            What is your objective today?
          </h2>
        </div>
        <p className="text-slate-400 text-sm">
          Describe your mission in natural language. The AI will compile it into an executable plan.
        </p>
      </div>

      {/* Input Area */}
      <div className={clsx(
        'w-full max-w-3xl relative',
        'bg-slate-800 rounded-xl border-2',
        'transition-all duration-300',
        isLoading 
          ? 'border-yellow-500/50 animate-pulse' 
          : 'border-slate-600 focus-within:border-emerald-500 focus-within:glow-border'
      )}>
        {/* Decorative corner elements */}
        <div className="absolute -top-1 -left-1 w-3 h-3 border-t-2 border-l-2 border-emerald-500 rounded-tl" />
        <div className="absolute -top-1 -right-1 w-3 h-3 border-t-2 border-r-2 border-emerald-500 rounded-tr" />
        <div className="absolute -bottom-1 -left-1 w-3 h-3 border-b-2 border-l-2 border-emerald-500 rounded-bl" />
        <div className="absolute -bottom-1 -right-1 w-3 h-3 border-b-2 border-r-2 border-emerald-500 rounded-br" />

        <textarea
          ref={textareaRef}
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={PLACEHOLDER_PROMPTS[placeholderIndex]}
          disabled={isLoading}
          className={clsx(
            'w-full min-h-[120px] p-6 pr-16',
            'bg-transparent text-slate-200 text-lg',
            'placeholder-slate-500 resize-none',
            'focus:outline-none',
            'terminal-text'
          )}
        />

        {/* Submit Button */}
        <button
          onClick={handleSubmit}
          disabled={!prompt.trim() || isLoading}
          className={clsx(
            'absolute right-4 bottom-4',
            'p-3 rounded-lg',
            'transition-all duration-200',
            prompt.trim() && !isLoading
              ? 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg hover:shadow-emerald-500/25'
              : 'bg-slate-700 text-slate-500 cursor-not-allowed'
          )}
        >
          {isLoading ? (
            <Loader2 className="w-5 h-5 animate-spin" />
          ) : (
            <Send className="w-5 h-5" />
          )}
        </button>

        {/* Prefix indicator */}
        <div className="absolute left-4 top-4 flex items-center gap-2 text-emerald-500">
          <span className="terminal-text text-sm">$</span>
          <Sparkles className="w-3 h-3 animate-pulse" />
        </div>
      </div>

      {/* Loading State */}
      {isLoading && (
        <div className="mt-6 flex items-center gap-3 text-yellow-400">
          <Loader2 className="w-5 h-5 animate-spin" />
          <span className="terminal-text animate-pulse">Compiling Intent...</span>
        </div>
      )}

      {/* Quick Actions */}
      <div className="mt-8 flex flex-wrap justify-center gap-2">
        {['LinkedIn Jobs', 'Indeed Search', 'YC Companies', 'Remote Only'].map((tag) => (
          <button
            key={tag}
            onClick={() => setPrompt((prev) => prev + (prev ? ' ' : '') + tag.toLowerCase())}
            className={clsx(
              'px-3 py-1.5 rounded-full text-sm',
              'bg-slate-800 border border-slate-700',
              'text-slate-400 hover:text-emerald-400 hover:border-emerald-500/50',
              'transition-colors'
            )}
          >
            + {tag}
          </button>
        ))}
      </div>
    </div>
  );
}
