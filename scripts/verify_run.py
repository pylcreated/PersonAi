from pathlib import Path
import sqlite3
import os
import sys

from personal_agent.config import get_config
from personal_agent.memory.database import DB_PATH, init_db

def mask(s: str) -> str:
    if not s:
        return "(empty)"
    if "@" in s:
        user, _ = s.split("@",1)
        return user[0]+"***@..."
    return s[:3] + "***"

def main():
    print('Python executable:', sys.executable)
    env_path = Path(__file__).resolve().parents[1] / '.env'
    print('.env exists:', env_path.exists())
    if env_path.exists():
        print('.env content (masked):')
        for line in env_path.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                print('  ' + line)
                continue
            if '=' in line:
                k,v = line.split('=',1)
                print(f'  {k}={mask(v)}')
            else:
                print('  ' + line)

    cfg = get_config()
    print('\nLoaded config:')
    print('  llm_provider:', cfg.llm_provider)
    print('  llm_model_name:', cfg.llm_model_name)
    print('  ollama_base_url:', cfg.ollama_base_url)
    print('  default_ask_hour:', cfg.default_ask_hour)
    print('  openai_mock_mode:', cfg.openai_mock_mode)
    print('  openai_api_key present:', bool(cfg.openai_api_key))

    print('\nChecking DB and tables...')
    init_db()
    if not Path(DB_PATH).exists():
        print('  DB file not found:', DB_PATH)
        return
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cur.fetchall()]
        print('  tables:', tables)
        if 'settings' in tables:
            cur.execute("SELECT reminder_hour, setup_complete FROM settings WHERE id=1")
            row = cur.fetchone()
            print('  settings row:', row)
        else:
            print('  settings table missing')

    print('\nDiagnostic complete.')

if __name__ == '__main__':
    main()
