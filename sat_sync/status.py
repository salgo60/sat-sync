from .database import connect
import typer


def run():
    db = connect()

    version = db.execute("""
        SELECT value
        FROM metadata
        WHERE key = 'schema_version'
    """).fetchone()

    count = db.execute("""
        SELECT COUNT(*)
        FROM identity
    """).fetchone()

    typer.echo(f"Schema version : {version[0]}")
    typer.echo(f"Identities     : {count[0]}")

    db.close()