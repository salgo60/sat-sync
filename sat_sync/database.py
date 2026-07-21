from pathlib import Path
import sqlite3

DB = Path.home() / ".sat-sync.sqlite"

def connect():
    return sqlite3.connect(DB)