"""Check the concrete spawn_region semantic mutation without rebuilding."""
from semantic_edit_check import edit_cli


if __name__ == '__main__':
    raise SystemExit(edit_cli(needle='(clear_address, 0)]', replacement='(clear_address, 1)]',
                              description='spawn_region: (clear_address, 0)] -> (clear_address, 1)] in a disposable source copy'))
