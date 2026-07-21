import typer

from .sync import run as sync_run
from .audit import run as audit_run

app = typer.Typer(help="SAT Sync")


@app.command()
def sync():
    """Synchronize all data sources."""
    sync_run()


@app.command()
def audit():
    """Audit local cache."""
    audit_run()


def main():
    app()


if __name__ == "__main__":
    main()