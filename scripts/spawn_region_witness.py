"""Qualify one of the four recovered spawn allocation arms."""
from pathlib import Path

from aladdin_sega.boundary import SPAWN_REGION_ENTRIES
from return_region_witness import qualify_return_region, witness_cli


def run(fixture: Path, output: Path, *, entry: int | None = None) -> dict:
    return qualify_return_region(fixture, output, entries=SPAWN_REGION_ENTRIES,
                                 provenance='spawn-region', entry=entry)


if __name__ == '__main__':
    witness_cli(run, __doc__)
