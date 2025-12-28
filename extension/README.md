# JobHunter Chrome Extension

AI-powered job application auto-filler built with Plasmo, React, TypeScript, and Tailwind CSS.

## Tech Stack

- **Framework**: Plasmo v0.90.5
- **UI**: React 18 + Tailwind CSS
- **Language**: TypeScript 5.3
- **Target**: Chrome Manifest V3

## Project Structure

```
extension/
├── src/
│   ├── popup.tsx          # Main popup UI component
│   ├── background.ts      # Service worker for extension lifecycle
│   ├── contents/
│   │   └── jobhunter.ts   # Content script for form manipulation
│   ├── lib/
│   │   ├── api.ts         # API client for backend communication
│   │   └── form-utils.ts  # DOM scraping and form filling utilities
│   ├── types/
│   │   └── index.ts       # TypeScript type definitions
│   └── styles/
│       └── globals.css    # Tailwind CSS styles
├── assets/
│   └── icon.png           # Extension icon (512x512)
├── popup.tsx              # Symlink to src/popup.tsx
├── background.ts          # Symlink to src/background.ts
├── contents/              # Symlink to src/contents
├── package.json           # Plasmo configuration
├── tsconfig.json          # TypeScript configuration
├── tailwind.config.js     # Tailwind CSS configuration
└── postcss.config.js      # PostCSS configuration
```

## Features

- **Form Scraping (FR-01, FR-02)**: Detects and extracts form fields from job application pages
- **Event Simulation (FR-03)**: Properly fills fields with synthetic events
- **Iterative DOM Re-scan (NFR-03)**: 2-second interval monitoring for dynamic forms
- **JD Scraping (FR-07)**: Extracts job description context for better answers
- **Feedback Capture (AIR-03)**: Captures user corrections for learning loop
- **Hallucination Guard (FR-08)**: Validates AI responses against resume

## Development

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build

# Package for distribution
npm run package
```

## Loading in Chrome

1. Build the extension: `npm run build`
2. Open Chrome and go to `chrome://extensions/`
3. Enable "Developer mode" (top right)
4. Click "Load unpacked"
5. Select the `build/chrome-mv3-prod` folder

## API Endpoints

The extension communicates with the backend at `http://localhost:8001/api/v1`:

- `GET /health` - Health check
- `POST /generate-answers` - Generate answers for form fields
- `POST /feedback` - Submit user corrections
- `GET /resume/status` - Check resume upload status

## Usage

1. Navigate to a job application page
2. Click the JobHunter extension icon
3. Click "Auto-Fill Application" to fill form fields
4. Review and edit any flagged answers
5. Click "Capture Corrections" before submitting to improve future suggestions
