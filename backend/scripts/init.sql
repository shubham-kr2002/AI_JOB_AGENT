-- =============================================================================
-- Project JobHunter V3 - PostgreSQL Initialization Script
-- Creates the World Model and core tables
-- =============================================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- =============================================================================
-- WORLD MODEL: Site Knowledge Database
-- Maps domains to known selectors, behaviors, and performance profiles
-- =============================================================================

CREATE TABLE IF NOT EXISTS sites (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    domain VARCHAR(255) UNIQUE NOT NULL,          -- e.g., "greenhouse.io"
    
    -- Login configuration
    login_config JSONB DEFAULT '{}'::jsonb,       -- {"requires_2fa": false, "login_url": "/login"}
    
    -- Known selectors that work for this site
    selectors JSONB DEFAULT '{}'::jsonb,          -- {"job_card": ".job-item", "apply_btn": "#apply"}
    
    -- Site behavior profile
    behavior JSONB DEFAULT '{}'::jsonb,           -- {"rate_limit": 5, "needs_stealth": true}
    
    -- Performance metrics
    avg_execution_time_ms INTEGER DEFAULT 0,
    success_rate DECIMAL(5,2) DEFAULT 0.00,
    total_attempts INTEGER DEFAULT 0,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_sites_domain ON sites(domain);

-- =============================================================================
-- TASKS: Autonomous task tracking
-- =============================================================================

CREATE TYPE task_status AS ENUM (
    'pending',
    'planning', 
    'queued',
    'running',
    'paused',        -- Waiting for human input (2FA, CAPTCHA)
    'verifying',
    'completed',
    'failed',
    'cancelled'
);

CREATE TABLE IF NOT EXISTS tasks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID,                                  -- References users table
    
    -- Task definition
    raw_prompt TEXT NOT NULL,                      -- Original user input
    parsed_goal JSONB,                             -- Compiled intent JSON
    constraints JSONB DEFAULT '{}'::jsonb,         -- Filters: location, salary, etc.
    
    -- Execution plan (DAG)
    task_graph JSONB,                              -- NetworkX serialized DAG
    
    -- Status tracking
    status task_status DEFAULT 'pending',
    progress_percent INTEGER DEFAULT 0,
    current_step VARCHAR(255),
    
    -- Results
    result_summary JSONB,                          -- {"applied": 10, "failed": 2, "skipped": 3}
    error_message TEXT,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_tasks_user_id ON tasks(user_id);
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_created_at ON tasks(created_at DESC);

-- =============================================================================
-- TASK STEPS: Individual nodes in the DAG
-- =============================================================================

CREATE TYPE step_status AS ENUM (
    'pending',
    'running',
    'waiting_dependency',
    'paused',
    'completed',
    'failed',
    'skipped'
);

CREATE TYPE action_type AS ENUM (
    'search',
    'scrape',
    'filter',
    'apply',
    'login',
    'verify',
    'custom'
);

CREATE TABLE IF NOT EXISTS task_steps (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    
    -- Step definition
    step_order INTEGER NOT NULL,
    action action_type NOT NULL,
    target_url VARCHAR(2048),
    target_domain VARCHAR(255),
    
    -- Execution config
    payload JSONB DEFAULT '{}'::jsonb,            -- Action-specific parameters
    depends_on UUID[],                            -- Parent step IDs (DAG edges)
    
    -- Status
    status step_status DEFAULT 'pending',
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    
    -- Results
    result JSONB,
    error_message TEXT,
    screenshot_path VARCHAR(512),
    
    -- Timing
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    execution_time_ms INTEGER,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_task_steps_task_id ON task_steps(task_id);
CREATE INDEX idx_task_steps_status ON task_steps(status);

-- =============================================================================
-- EXECUTION LOGS: Detailed logging for debugging
-- =============================================================================

CREATE TYPE log_level AS ENUM ('debug', 'info', 'warning', 'error', 'critical');

CREATE TABLE IF NOT EXISTS execution_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    task_id UUID REFERENCES tasks(id) ON DELETE CASCADE,
    step_id UUID REFERENCES task_steps(id) ON DELETE CASCADE,
    
    level log_level DEFAULT 'info',
    agent VARCHAR(50),                            -- planner, executor, critic, recovery
    message TEXT NOT NULL,
    
    -- Context
    metadata JSONB DEFAULT '{}'::jsonb,
    screenshot_path VARCHAR(512),
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_execution_logs_task_id ON execution_logs(task_id);
CREATE INDEX idx_execution_logs_created_at ON execution_logs(created_at DESC);

-- =============================================================================
-- USERS (V3 Enhanced)
-- =============================================================================

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255),
    
    -- Subscription
    subscription_tier VARCHAR(50) DEFAULT 'free',  -- free, pro, enterprise
    tokens_used_this_month INTEGER DEFAULT 0,
    max_monthly_tokens INTEGER DEFAULT 100000,
    
    -- Settings
    preferences JSONB DEFAULT '{}'::jsonb,
    
    -- Auth
    is_active BOOLEAN DEFAULT true,
    is_verified BOOLEAN DEFAULT false,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_users_email ON users(email);

-- =============================================================================
-- PROFILES: User resume and preferences
-- =============================================================================

CREATE TABLE IF NOT EXISTS profiles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- Contact info
    full_name VARCHAR(255),
    phone VARCHAR(50),
    linkedin_url VARCHAR(512),
    portfolio_url VARCHAR(512),
    github_url VARCHAR(512),
    
    -- Location
    city VARCHAR(100),
    country VARCHAR(100),
    timezone VARCHAR(50),
    
    -- Work preferences
    job_preferences JSONB DEFAULT '{}'::jsonb,    -- {"remote": true, "salary_min": 100000}
    
    -- Raw resume storage
    resume_text TEXT,
    resume_parsed JSONB,                          -- Structured resume data
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- =============================================================================
-- JOB APPLICATIONS: Track all applications
-- =============================================================================

CREATE TYPE application_status AS ENUM (
    'draft',
    'submitted',
    'acknowledged',
    'interviewing',
    'rejected',
    'offer',
    'withdrawn'
);

CREATE TABLE IF NOT EXISTS job_applications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    task_id UUID REFERENCES tasks(id),
    
    -- Job info
    company_name VARCHAR(255) NOT NULL,
    job_title VARCHAR(255) NOT NULL,
    job_url VARCHAR(2048),
    job_description TEXT,
    
    -- Application details
    status application_status DEFAULT 'draft',
    applied_at TIMESTAMP WITH TIME ZONE,
    
    -- What we sent
    resume_version JSONB,                         -- Tailored resume used
    cover_letter TEXT,
    answers JSONB,                                -- Form answers submitted
    
    -- Tracking
    confirmation_screenshot VARCHAR(512),
    confirmation_text TEXT,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_job_applications_user_id ON job_applications(user_id);
CREATE INDEX idx_job_applications_status ON job_applications(status);
CREATE INDEX idx_job_applications_company ON job_applications(company_name);

-- =============================================================================
-- LEARNING HISTORY: Corrections for self-improvement
-- =============================================================================

CREATE TABLE IF NOT EXISTS learning_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    
    question_hash VARCHAR(64) NOT NULL,           -- SHA256 of normalized question
    question_text TEXT NOT NULL,
    original_answer TEXT,
    corrected_answer TEXT NOT NULL,
    
    field_type VARCHAR(50),
    job_context TEXT,                             -- JD or URL context
    
    times_used INTEGER DEFAULT 0,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_learning_history_question_hash ON learning_history(question_hash);
CREATE INDEX idx_learning_history_user_id ON learning_history(user_id);

-- =============================================================================
-- Trigger: Auto-update updated_at timestamp
-- =============================================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply trigger to all tables with updated_at
CREATE TRIGGER update_sites_updated_at BEFORE UPDATE ON sites
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_tasks_updated_at BEFORE UPDATE ON tasks
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_profiles_updated_at BEFORE UPDATE ON profiles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_job_applications_updated_at BEFORE UPDATE ON job_applications
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_learning_history_updated_at BEFORE UPDATE ON learning_history
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- Insert some initial World Model data for common job sites
-- =============================================================================

INSERT INTO sites (domain, login_config, selectors, behavior) VALUES
(
    'greenhouse.io',
    '{"requires_login": false, "application_type": "direct"}'::jsonb,
    '{"job_card": ".opening", "apply_button": ".btn-apply", "first_name": "#first_name", "last_name": "#last_name", "email": "#email", "resume_upload": "#resume"}'::jsonb,
    '{"rate_limit_per_minute": 10, "needs_stealth": false}'::jsonb
),
(
    'lever.co',
    '{"requires_login": false, "application_type": "direct"}'::jsonb,
    '{"job_card": ".posting", "apply_button": ".posting-apply", "first_name": "input[name=\"name\"]", "email": "input[name=\"email\"]", "resume_upload": "input[type=\"file\"]"}'::jsonb,
    '{"rate_limit_per_minute": 10, "needs_stealth": false}'::jsonb
),
(
    'linkedin.com',
    '{"requires_login": true, "login_url": "/login", "requires_2fa": false}'::jsonb,
    '{"job_card": ".job-card-container", "easy_apply": ".jobs-apply-button", "next_button": "button[aria-label=\"Continue to next step\"]"}'::jsonb,
    '{"rate_limit_per_minute": 5, "needs_stealth": true, "human_delay_ms": 2000}'::jsonb
),
(
    'workday.com',
    '{"requires_login": true, "application_type": "account_required"}'::jsonb,
    '{"job_search": "input[data-automation-id=\"searchBox\"]", "apply_button": "button[data-automation-id=\"applyButton\"]"}'::jsonb,
    '{"rate_limit_per_minute": 3, "needs_stealth": true, "human_delay_ms": 3000}'::jsonb
)
ON CONFLICT (domain) DO NOTHING;

-- Log completion
DO $$
BEGIN
    RAISE NOTICE 'JobHunter V3 database initialized successfully!';
END $$;
