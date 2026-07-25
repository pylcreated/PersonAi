CREATE TABLE personal_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    description TEXT NOT NULL,
    scope TEXT NOT NULL DEFAULT 'week'
        CHECK (scope IN ('day', 'week')),
    task_date TEXT,
    week_start TEXT NOT NULL,
    completed INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE INDEX idx_personal_tasks_week
    ON personal_tasks(week_start, completed, id);

CREATE INDEX idx_personal_tasks_date
    ON personal_tasks(task_date, completed, id);
