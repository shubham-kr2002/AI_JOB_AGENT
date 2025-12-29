/**
 * JobHunter Extension - Background Service Worker
 * Handles extension lifecycle, messaging, and persistent task tracking
 */

console.log('[JobHunter] Background service worker started');

// Store for active task polling
interface TaskPollingState {
  taskId: string;
  status: string;
  progress: number;
  currentStep: string;
  message: string;
  thoughtProcess: string[];
  lastUpdated: number;
}

let activePolling: { [taskId: string]: NodeJS.Timeout } = {};

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

// Handle messages from popup
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  console.log('[JobHunter] Background received:', message);

  if (message.action === 'startTaskPolling') {
    startPollingTask(message.taskId, message.initialState);
    sendResponse({ success: true });

  } else if (message.action === 'stopTaskPolling') {
    stopPollingTask(message.taskId);
    sendResponse({ success: true });

  } else if (message.action === 'getTaskState') {
    chrome.storage.local.get(['activeTask'], (result) => {
      sendResponse({ task: result.activeTask || null });
    });
    return true; // Keep channel open for async response

  } else if (message.action === 'clearTaskState') {
    chrome.storage.local.remove(['activeTask']);
    sendResponse({ success: true });

  } else if (message.action === 'newFieldsDetected') {
    // Could show a notification or update badge
    chrome.action.setBadgeText({ 
      text: String(message.totalFields),
      tabId: sender.tab?.id 
    });
    chrome.action.setBadgeBackgroundColor({ 
      color: '#22c55e' 
    });

  } else if (message.action === 'startInTabTask') {
    // Start in-tab execution flow: claim task on backend then send executeSteps to active tab
    const { taskId, planNodes } = message as { taskId: string; planNodes: any[] };

    fetch(`http://localhost:8001/api/v1/agent/tasks/${taskId}/claim`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode: 'in_tab' }),
    }).then(() => {
      chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
        const tab = tabs[0];
        if (!tab || !tab.id) {
          console.error('[JobHunter] No active tab to run in-tab task');
          return;
        }

        chrome.tabs.sendMessage(tab.id, { action: 'executeSteps', taskId, steps: planNodes }, (resp) => {
          console.log('[JobHunter] executeSteps response:', resp);
        });
      });
    }).catch((err) => console.error('[JobHunter] Claim task error:', err));

    sendResponse({ success: true });

  } else if (message.action === 'stepResult') {
    // Received a step result from a content script; forward to backend and update local state
    const { taskId, stepId, stepName, success, data, error, meta } = message as {
      taskId: string;
      stepId: string;
      stepName?: string;
      success: boolean;
      data?: any;
      error?: string;
      meta?: any;
    };

    const outgoingMeta = { forwarded_at: Date.now(), ...(meta || {}) };

    fetch(`http://localhost:8001/api/v1/agent/tasks/${taskId}/report`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ step_id: stepId, step_name: stepName, success, data, error, meta: outgoingMeta }),
    }).then((r) => r.json()).then((json) => {
      chrome.storage.local.get(['activeTask'], (result) => {
        const state = result.activeTask || {};
        state.status = json.status || state.status;
        state.progress = json.progress || state.progress;
        state.currentStep = stepName || state.currentStep;
        state.lastUpdated = Date.now();
        state.thoughtProcess = [...(state.thoughtProcess || []).slice(-5), `🔄 ${stepName} - ${success ? 'ok' : 'fail'}`];
        chrome.storage.local.set({ activeTask: state });
      });
    }).catch((err) => console.error('[JobHunter] step report error:', err));

    sendResponse({ success: true });


  return true;
});

async function startPollingTask(taskId: string, initialState: TaskPollingState) {
  console.log('[JobHunter] Starting background polling for task:', taskId);
  
  // Store initial state
  await chrome.storage.local.set({ activeTask: { ...initialState, taskId } });
  
  // Clear any existing polling for this task
  if (activePolling[taskId]) {
    clearInterval(activePolling[taskId]);
  }
  
  // Start polling
  const pollInterval = setInterval(async () => {
    try {
      const response = await fetch(`http://localhost:8001/api/v1/agent/tasks/${taskId}`);
      if (!response.ok) {
        console.error('[JobHunter] Failed to fetch task status');
        return;
      }
      
      const data = await response.json();
      
      // Get current state
      const result = await chrome.storage.local.get(['activeTask']);
      const currentState = result.activeTask || initialState;
      
      const updatedState: TaskPollingState = {
        taskId,
        status: data.status,
        progress: data.progress_percent || currentState.progress,
        currentStep: data.current_step || currentState.currentStep,
        message: data.message || currentState.message,
        thoughtProcess: data.current_step 
          ? [...(currentState.thoughtProcess || []).slice(-5), `🔄 ${data.current_step}`]
          : currentState.thoughtProcess || [],
        lastUpdated: Date.now(),
      };
      
      // Check for completion
      if (data.status === 'completed' || data.status === 'success') {
        updatedState.status = 'complete';
        updatedState.message = data.message || 'Task completed successfully!';
        updatedState.progress = 100;
        updatedState.thoughtProcess = [...(updatedState.thoughtProcess || []).slice(-5), '✅ Task completed!'];
        
        // Stop polling
        stopPollingTask(taskId);
        
        // Show notification
        chrome.notifications.create({
          type: 'basic',
          iconUrl: 'assets/icon.png',
          title: 'JobHunter Task Complete',
          message: updatedState.message,
        });
      } else if (data.status === 'failed' || data.status === 'error') {
        updatedState.status = 'error';
        updatedState.message = data.error_message || 'Task failed';
        updatedState.thoughtProcess = [...(updatedState.thoughtProcess || []).slice(-5), `❌ ${data.error_message}`];
        
        // Stop polling
        stopPollingTask(taskId);
      } else if (data.status === 'waiting_intervention') {
        updatedState.status = 'waiting';
        updatedState.message = 'Waiting for your input...';
      }
      
      // Save updated state
      await chrome.storage.local.set({ activeTask: updatedState });
      
      // Update badge
      if (updatedState.status === 'complete') {
        chrome.action.setBadgeText({ text: '✓' });
        chrome.action.setBadgeBackgroundColor({ color: '#22c55e' });
      } else if (updatedState.status === 'error') {
        chrome.action.setBadgeText({ text: '!' });
        chrome.action.setBadgeBackgroundColor({ color: '#ef4444' });
      } else {
        chrome.action.setBadgeText({ text: `${Math.round(updatedState.progress)}%` });
        chrome.action.setBadgeBackgroundColor({ color: '#3b82f6' });
      }
      
    } catch (error) {
      console.error('[JobHunter] Polling error:', error);
    }
  }, 3000); // Poll every 3 seconds
  
  activePolling[taskId] = pollInterval;
}

function stopPollingTask(taskId: string) {
  if (activePolling[taskId]) {
    clearInterval(activePolling[taskId]);
    delete activePolling[taskId];
    console.log('[JobHunter] Stopped polling for task:', taskId);
  }
}

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
    
    // Only set job site badge if no active task
    chrome.storage.local.get(['activeTask'], (result) => {
      if (!result.activeTask || result.activeTask.status === 'complete' || result.activeTask.status === 'error') {
        if (isJobSite) {
          chrome.action.setBadgeText({ text: '!', tabId });
          chrome.action.setBadgeBackgroundColor({ color: '#22c55e' });
        } else {
          chrome.action.setBadgeText({ text: '', tabId });
        }
      }
    });
  }
});

// Clean up old tasks on startup
chrome.storage.local.get(['activeTask'], (result) => {
  if (result.activeTask) {
    const task = result.activeTask;
    // If task is more than 1 hour old and still "running", mark as stale
    if (Date.now() - task.lastUpdated > 60 * 60 * 1000) {
      if (task.status !== 'complete' && task.status !== 'error') {
        chrome.storage.local.set({
          activeTask: { ...task, status: 'error', message: 'Task timed out' }
        });
      }
    } else if (task.status !== 'complete' && task.status !== 'error') {
      // Resume polling for active task
      startPollingTask(task.taskId, task);
    }
  }
});

export {};
