/**
 * Project JobHunter V3 - Settings Page
 */

import { useState } from 'react';
import { 
  Settings, 
  User, 
  Key, 
  Bell, 
  Shield, 
  Monitor,
  Save,
  Eye,
  EyeOff
} from 'lucide-react';
import { clsx } from 'clsx';

export function SettingsPage() {
  const [activeTab, setActiveTab] = useState('profile');

  const tabs = [
    { id: 'profile', label: 'Profile', icon: User },
    { id: 'credentials', label: 'Credentials', icon: Key },
    { id: 'notifications', label: 'Notifications', icon: Bell },
    { id: 'security', label: 'Security', icon: Shield },
    { id: 'display', label: 'Display', icon: Monitor },
  ];

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="p-2 rounded-lg bg-slate-500/20">
          <Settings className="w-6 h-6 text-slate-400" />
        </div>
        <div>
          <h1 className="text-xl font-semibold text-slate-200">Settings</h1>
          <p className="text-sm text-slate-400">
            Configure your agent and preferences
          </p>
        </div>
      </div>

      <div className="flex gap-6">
        {/* Sidebar */}
        <div className="w-48 space-y-1">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={clsx(
                  'w-full flex items-center gap-3 px-3 py-2 rounded-lg text-left transition-colors',
                  activeTab === tab.id
                    ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                    : 'text-slate-400 hover:bg-slate-700/50 hover:text-slate-300'
                )}
              >
                <Icon className="w-4 h-4" />
                <span className="text-sm">{tab.label}</span>
              </button>
            );
          })}
        </div>

        {/* Content */}
        <div className="flex-1">
          {activeTab === 'profile' && <ProfileSettings />}
          {activeTab === 'credentials' && <CredentialsSettings />}
          {activeTab === 'notifications' && <NotificationSettings />}
          {activeTab === 'security' && <SecuritySettings />}
          {activeTab === 'display' && <DisplaySettings />}
        </div>
      </div>
    </div>
  );
}

function ProfileSettings() {
  return (
    <div className="card space-y-6">
      <h2 className="text-lg font-semibold text-slate-200">Profile Settings</h2>
      
      <div className="space-y-4">
        <div>
          <label className="block text-sm text-slate-400 mb-1">Full Name</label>
          <input type="text" className="input-primary w-full" placeholder="John Doe" />
        </div>
        
        <div>
          <label className="block text-sm text-slate-400 mb-1">Email</label>
          <input type="email" className="input-primary w-full" placeholder="john@example.com" />
        </div>
        
        <div>
          <label className="block text-sm text-slate-400 mb-1">Resume (for auto-fill)</label>
          <div className="border-2 border-dashed border-slate-600 rounded-lg p-8 text-center">
            <p className="text-slate-400 text-sm">Drag and drop your resume or click to upload</p>
          </div>
        </div>
      </div>

      <button className="btn-primary flex items-center gap-2">
        <Save className="w-4 h-4" />
        Save Changes
      </button>
    </div>
  );
}

function CredentialsSettings() {
  const [showLinkedIn, setShowLinkedIn] = useState(false);
  
  return (
    <div className="card space-y-6">
      <h2 className="text-lg font-semibold text-slate-200">Site Credentials</h2>
      <p className="text-sm text-slate-400">
        Store credentials for job sites (encrypted locally)
      </p>
      
      <div className="space-y-4">
        <CredentialField 
          label="LinkedIn" 
          placeholder="username@email.com"
          showPassword={showLinkedIn}
          onTogglePassword={() => setShowLinkedIn(!showLinkedIn)}
        />
        
        <CredentialField 
          label="Indeed"
          placeholder="username@email.com"
        />
        
        <CredentialField 
          label="Glassdoor"
          placeholder="username@email.com"
        />
      </div>

      <button className="btn-primary flex items-center gap-2">
        <Save className="w-4 h-4" />
        Save Credentials
      </button>
    </div>
  );
}

interface CredentialFieldProps {
  label: string;
  placeholder: string;
  showPassword?: boolean;
  onTogglePassword?: () => void;
}

function CredentialField({ label, placeholder, showPassword, onTogglePassword }: CredentialFieldProps) {
  const [localShowPassword, setLocalShowPassword] = useState(false);
  const isPasswordVisible = showPassword !== undefined ? showPassword : localShowPassword;
  const togglePassword = onTogglePassword || (() => setLocalShowPassword(!localShowPassword));

  return (
    <div className="p-4 bg-slate-800/50 rounded-lg space-y-3">
      <div className="font-medium text-slate-300">{label}</div>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-xs text-slate-500 mb-1">Username/Email</label>
          <input type="text" className="input-primary w-full text-sm" placeholder={placeholder} />
        </div>
        <div>
          <label className="block text-xs text-slate-500 mb-1">Password</label>
          <div className="relative">
            <input 
              type={isPasswordVisible ? 'text' : 'password'} 
              className="input-primary w-full text-sm pr-10" 
              placeholder="••••••••" 
            />
            <button
              type="button"
              onClick={togglePassword}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300"
            >
              {isPasswordVisible ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function NotificationSettings() {
  return (
    <div className="card space-y-6">
      <h2 className="text-lg font-semibold text-slate-200">Notification Preferences</h2>
      
      <div className="space-y-4">
        <ToggleSetting
          label="Task Completion Alerts"
          description="Get notified when a task finishes"
          defaultChecked={true}
        />
        <ToggleSetting
          label="Error Notifications"
          description="Alert when an error occurs during execution"
          defaultChecked={true}
        />
        <ToggleSetting
          label="Daily Summary"
          description="Receive a daily summary of all activities"
          defaultChecked={false}
        />
        <ToggleSetting
          label="Sound Effects"
          description="Play sounds for notifications"
          defaultChecked={false}
        />
      </div>
    </div>
  );
}

function SecuritySettings() {
  return (
    <div className="card space-y-6">
      <h2 className="text-lg font-semibold text-slate-200">Security Settings</h2>
      
      <div className="space-y-4">
        <ToggleSetting
          label="Stealth Mode"
          description="Use browser fingerprint masking and anti-detection"
          defaultChecked={true}
        />
        <ToggleSetting
          label="Headless Mode"
          description="Run browser without visible window"
          defaultChecked={false}
        />
        <ToggleSetting
          label="Proxy Usage"
          description="Route traffic through proxy servers"
          defaultChecked={false}
        />
      </div>

      <div className="pt-4 border-t border-slate-700">
        <label className="block text-sm text-slate-400 mb-1">Proxy URL</label>
        <input 
          type="text" 
          className="input-primary w-full" 
          placeholder="http://proxy.example.com:8080" 
          disabled
        />
      </div>
    </div>
  );
}

function DisplaySettings() {
  return (
    <div className="card space-y-6">
      <h2 className="text-lg font-semibold text-slate-200">Display Settings</h2>
      
      <div className="space-y-4">
        <div>
          <label className="block text-sm text-slate-400 mb-1">Theme</label>
          <select className="input-primary w-full">
            <option value="dark">Dark (Default)</option>
            <option value="hacker">Hacker Green</option>
            <option value="midnight">Midnight Blue</option>
          </select>
        </div>
        
        <div>
          <label className="block text-sm text-slate-400 mb-1">Font Size</label>
          <select className="input-primary w-full">
            <option value="small">Small</option>
            <option value="medium">Medium (Default)</option>
            <option value="large">Large</option>
          </select>
        </div>
        
        <ToggleSetting
          label="Compact Mode"
          description="Reduce spacing for more content on screen"
          defaultChecked={false}
        />
        
        <ToggleSetting
          label="Show Line Numbers in Terminal"
          description="Display line numbers in the live terminal"
          defaultChecked={true}
        />
      </div>
    </div>
  );
}

interface ToggleSettingProps {
  label: string;
  description: string;
  defaultChecked?: boolean;
}

function ToggleSetting({ label, description, defaultChecked }: ToggleSettingProps) {
  const [checked, setChecked] = useState(defaultChecked || false);
  
  return (
    <div className="flex items-center justify-between p-3 bg-slate-800/50 rounded-lg">
      <div>
        <div className="text-slate-200">{label}</div>
        <div className="text-sm text-slate-500">{description}</div>
      </div>
      <button
        onClick={() => setChecked(!checked)}
        className={clsx(
          'w-11 h-6 rounded-full transition-colors relative',
          checked ? 'bg-emerald-500' : 'bg-slate-600'
        )}
      >
        <span className={clsx(
          'absolute top-1 left-1 w-4 h-4 rounded-full bg-white transition-transform',
          checked && 'translate-x-5'
        )} />
      </button>
    </div>
  );
}
