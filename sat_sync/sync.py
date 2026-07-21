from .database import initialize, connect
import typer
from . import sat
from pathlib import Path

def run():
    typer.echo("Initializing database...")

    initialize()

    db = connect()

    datafile = Path(__file__).parent / "data" / "sat.json"
    for identity in sat.identities(datafile):
        db.execute("""
            INSERT OR IGNORE INTO identity
            (sat_id, name)
            VALUES (?, ?)
        """, (
			identity.sat_id,
	        identity.name        ))
    db.commit()
    db.close()
    
    typer.echo("Done.")