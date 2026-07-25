ALTER TABLE daily_analyses
    ADD COLUMN confidence REAL NOT NULL DEFAULT 0.5
    CHECK (confidence BETWEEN 0 AND 1);

CREATE TABLE daily_report_evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id INTEGER NOT NULL,
    message_id INTEGER NOT NULL,
    evidence_type TEXT NOT NULL
        CHECK (evidence_type IN (
            'summary', 'progress', 'obstacle', 'pattern', 'mood', 'next_action'
        )),
    claim TEXT NOT NULL,
    quote TEXT NOT NULL,
    message_created_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(report_id) REFERENCES daily_analyses(id) ON DELETE CASCADE
);

CREATE INDEX idx_daily_evidence_report
    ON daily_report_evidence(report_id, evidence_type, id);
