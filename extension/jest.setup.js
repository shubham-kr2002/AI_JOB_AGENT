// Jest setup: provide minimal chrome API globals for content script tests
global.chrome = {
  runtime: {
    sendMessage: jest.fn(),
    onMessage: {
      addListener: jest.fn((fn) => {
        // Optionally store fn for later tests
        global._chrome_onMessage = fn;
      }),
    },
  },
  storage: {
    local: {
      get: jest.fn((keys, cb) => cb({})),
      set: jest.fn((obj) => {}),
      remove: jest.fn(() => {}),
    },
  },
  tabs: {
    query: jest.fn((opts, cb) => cb([])),
  },
  action: {
    setBadgeText: jest.fn(() => {}),
    setBadgeBackgroundColor: jest.fn(() => {}),
  },
  notifications: {
    create: jest.fn(() => {}),
  },
};
