"""Check the concrete spawn_upper_caller semantic mutation without rebuilding."""
from semantic_edit_check import edit_cli


if __name__ == '__main__':
    raise SystemExit(edit_cli(needle='(record, 0x40)', replacement='(record, 0x41)',
                              description='spawn_upper_caller: (record, 0x40) -> (record, 0x41) in a disposable source copy'))
