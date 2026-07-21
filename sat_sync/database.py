from pathlib import Path
import sqlite3

DB = Path.home() / ".sat-sync.sqlite"

def connect():
    return sqlite3.connect(DB)
    
def initialize():
    db = connect()

    db.execute("""
    CREATE TABLE IF NOT EXISTS identity(
        sat_id TEXT PRIMARY KEY,
        osm_id INTEGER,
        wikidata TEXT,
        name TEXT
    )
    """)

    db.execute("""
    CREATE TABLE IF NOT EXISTS metadata(
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    """)

    db.execute("""
    INSERT OR IGNORE INTO metadata(key, value)
    VALUES ('schema_version', '1')
    """)

    db.commit()
    db.close()