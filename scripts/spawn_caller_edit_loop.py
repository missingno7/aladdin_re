"""Check the concrete spawn_caller semantic mutation without rebuilding."""
from semantic_edit_check import edit_cli


if __name__ == '__main__':
    raise SystemExit(edit_cli(needle='read(record + 2, 2) + 8', replacement='read(record + 2, 2) + 9',
                              description='spawn_caller: read(record + 2, 2) + 8 -> read(record + 2, 2) + 9 in a disposable source copy'))
