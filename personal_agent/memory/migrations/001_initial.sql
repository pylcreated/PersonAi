CREATE TABLE IF NOT EXISTS goals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    goal_id INTEGER NOT NULL,
    description TEXT NOT NULL,
    week_start TEXT NOT NULL,
    completed INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY(goal_id) REFERENCES goals(id)
);

CREATE TABLE IF NOT EXISTS reflections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    goal_id INTEGER NOT NULL,
    question_type TEXT NOT NULL,
    user_answer TEXT NOT NULL,
    ai_summary TEXT,
    FOREIGN KEY(goal_id) REFERENCES goals(id)
);

CREATE TABLE IF NOT EXISTS settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    reminder_hour INTEGER,
    setup_complete INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS error_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    task_name TEXT NOT NULL,
    error_msg TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chat_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_date TEXT NOT NULL UNIQUE,
    started_at TEXT NOT NULL,
    closed_at TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    last_error TEXT
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    goal_id INTEGER,
    task_id INTEGER,
    FOREIGN KEY(session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE,
    FOREIGN KEY(goal_id) REFERENCES goals(id),
    FOREIGN KEY(task_id) REFERENCES tasks(id)
);

CREATE TABLE IF NOT EXISTS daily_analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_date TEXT NOT NULL UNIQUE,
    summary TEXT NOT NULL,
    progress TEXT NOT NULL,
    obstacles TEXT NOT NULL,
    patterns TEXT NOT NULL,
    mood TEXT NOT NULL,
    next_actions TEXT NOT NULL,
    model_name TEXT NOT NULL,
    message_count INTEGER NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL,
    content TEXT NOT NULL,
    importance REAL NOT NULL DEFAULT 0.5
        CHECK (importance BETWEEN 0 AND 1),
    confidence REAL NOT NULL DEFAULT 0.5
        CHECK (confidence BETWEEN 0 AND 1),
    source TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'expired', 'archived', 'deleted')),
    use_count INTEGER NOT NULL DEFAULT 0,
    last_used_at TEXT
);

CREATE TABLE IF NOT EXISTS candidate_memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    type TEXT NOT NULL,
    importance REAL NOT NULL DEFAULT 0.5
        CHECK (importance BETWEEN 0 AND 1),
    confidence REAL NOT NULL DEFAULT 0.5
        CHECK (confidence BETWEEN 0 AND 1),
    source_conversation INTEGER,
    source_date TEXT,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'accepted', 'rejected')),
    created_at TEXT NOT NULL,
    reviewed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_session
    ON chat_messages(session_id, id);
CREATE INDEX IF NOT EXISTS idx_reflections_goal_timestamp
    ON reflections(goal_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_tasks_week_goal
    ON tasks(week_start, goal_id);
CREATE INDEX IF NOT EXISTS idx_memories_status_type
    ON memories(status, type);
CREATE INDEX IF NOT EXISTS idx_candidate_status
    ON candidate_memories(status, id);

INSERT OR IGNORE INTO settings (id, reminder_hour, setup_complete)
VALUES (1, NULL, 0);
