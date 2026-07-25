ALTER TABLE candidate_memories
    ADD COLUMN source_report_id INTEGER
    REFERENCES daily_analyses(id);

ALTER TABLE candidate_memories
    ADD COLUMN created_reason TEXT;

CREATE TABLE candidate_memory_evidence (
    candidate_id INTEGER NOT NULL,
    evidence_id INTEGER NOT NULL,
    PRIMARY KEY(candidate_id, evidence_id),
    FOREIGN KEY(candidate_id)
        REFERENCES candidate_memories(id) ON DELETE CASCADE,
    FOREIGN KEY(evidence_id)
        REFERENCES daily_report_evidence(id) ON DELETE CASCADE
);

CREATE TABLE memory_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    memory_id INTEGER NOT NULL,
    source_type TEXT NOT NULL,
    source_id TEXT,
    created_reason TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(memory_id) REFERENCES memories(id) ON DELETE CASCADE
);

CREATE TABLE memory_evidence (
    memory_id INTEGER NOT NULL,
    evidence_id INTEGER NOT NULL,
    PRIMARY KEY(memory_id, evidence_id),
    FOREIGN KEY(memory_id) REFERENCES memories(id) ON DELETE CASCADE,
    FOREIGN KEY(evidence_id)
        REFERENCES daily_report_evidence(id) ON DELETE RESTRICT
);

CREATE INDEX idx_memory_sources_memory
    ON memory_sources(memory_id, id);
