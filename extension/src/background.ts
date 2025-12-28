/**
 * JobHunter Extension - Background Service Worker
 * Handles extension lifecycle and messaging
 */

console.log('[JobHunter] Background service worker started');

// Listen for extension install
chrome.runtime.onInstalled.addListener((details) => {
  console.log('[JobHunter] Extension installed:', details.reason);
  
  if (details.reason === 'install') {
    // Open onboarding page
    chrome.tabs.create({
      url: 'http://localhost:8001/docs'
    });
  }
});

// Handle messages from content scripts
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  console.log('[JobHunter] Background received:', message);

  if (message.action === 'newFieldsDetected') {
    // Could show a notification or update badge
    chrome.action.setBadgeText({ 
      text: String(message.totalFields),
      tabId: sender.tab?.id 
    });
    chrome.action.setBadgeBackgroundColor({ 
      color: '#22c55e' 
    });
  }

  return true;
});

// Listen for tab updates to detect job pages
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status === 'complete' && tab.url) {
    const jobSites = [
      'greenhouse.io',
      'lever.co',
      'workday.com',
      'icims.com',
      'jobs.smartrecruiters.com',
      'linkedin.com/jobs',
      'indeed.com',
      'glassdoor.com',
    ];

    const isJobSite = jobSites.some((site) => tab.url?.includes(site));
    
    if (isJobSite) {
      // Set badge to indicate job page detected
      chrome.action.setBadgeText({ text: '!', tabId });
      chrome.action.setBadgeBackgroundColor({ color: '#22c55e' });
    } else {
      chrome.action.setBadgeText({ text: '', tabId });
    }
  }
});

export {};
