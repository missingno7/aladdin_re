"""Check the concrete 1B7262 semantic mutation without rebuilding."""
from semantic_edit_check import edit_cli


if __name__ == '__main__':
    raise SystemExit(edit_cli(needle='(record, 0x3A)', replacement='(record, 0x3B)',
                              description='spawn_upper_variant_caller: (record, 0x3A) -> (record, 0x3B) in a disposable source copy'))
