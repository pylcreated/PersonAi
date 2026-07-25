# Data directory

本目录保存本地运行数据，不保存源码。

```text
data/
├── database/
│   └── goals_assistant.db
└── backups/
    ├── backup_YYYYMMDD_HHMMSS_microseconds.db
    └── pre_restore_YYYYMMDD_HHMMSS_microseconds.db
```

日报成功后会自动生成在线 SQLite 备份，并保留最近 30 份。恢复前的现有
数据库会以 `pre_restore_` 前缀暂存，便于恢复失败时回退。

所有数据库文件均被 `.gitignore` 忽略。自动化测试使用内存或隔离目录中的
SQLite，不读写这里的真实数据库。
