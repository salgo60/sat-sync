import typer

#from .sync import run as sync_run
from .audit import run as audit_run
from .status import run as status_run
from sat_sync.sources.sat import SATSource

app = typer.Typer(help="SAT Sync")


#@app.command()
#def sync():
#    """Synchronize all data sources."""
#    sync_run()


@app.command()
def audit():
    """Audit local cache."""
    audit_run()


#def main():
#    source = SATSource()
#    identities = source.load()
#    print(f"Loaded {len(identities)} identities") 
#    app()
def main():

    from pathlib import Path
    from sat_sync.sources.sat import SATSource
    source = SATSource()
    identities = source.identities(Path("sat_sync/data/sat.json"))
    print(identities)


@app.command()
def status():
    """Show database status."""
    status_run()
    
if __name__ == "__main__":
    main()
    
