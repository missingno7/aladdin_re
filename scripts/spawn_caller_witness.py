"""Qualify the recorded reverse-spawn caller at 1B6802."""
from pathlib import Path

from aladdin_sega.boundary import SPAWN_REVERSE_CALLER_ENTRY
from return_region_witness import qualify_return_region, witness_cli


def run(fixture: Path, output: Path, *, entry: int | None = None) -> dict:
    return qualify_return_region(fixture, output, entries=(SPAWN_REVERSE_CALLER_ENTRY,),
                                 provenance='spawn-caller', entry=entry)


if __name__ == '__main__':
    witness_cli(run, __doc__)
