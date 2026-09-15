"""The narrow ROM fact extractor must fail closed on a changed machine contract."""
import importlib.util
from pathlib import Path

import pytest


spec = importlib.util.spec_from_file_location('collection_sound_sites',
    Path(__file__).resolve().parents[3] / 'scripts' / 'aladdin' / 'collection_sound_sites.py')
sites = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sites)


def test_current_collection_sound_sites_share_the_exact_abi():
    path = Path('assets/Aladdin (USA).md')
    if not path.exists():
        pytest.skip('Original USA ROM required')
    result = sites.collection_sites(path.read_bytes())
    assert len(result) == 16
    assert {value['command'] for value in result.values()} == {11, 12, 13, 93, 100, 103, 105}
    assert all(value['enabled_prefix'] == {'cycles': 108, 'instructions': 5}
               for value in result.values())
    assert result['1AF53E']['resume'] == result['1AF4A0']['resume']


@pytest.mark.parametrize('offset', [0, 6, 9, 17, 23, 28, 32])
def test_changed_branch_frame_target_or_restore_is_rejected(offset):
    # Deliberately independent byte fixture for the known ABI, not an assembler.
    sequence = bytearray.fromhex(
        '4a3900fff57d671a48e7c0c2487800694eb9001e58b84eb9001e589a588f4cdf4303')
    sequence[offset] ^= 1
    with pytest.raises(ValueError, match='Unsupported collection sound'):
        sites.sound_site(bytes(sequence), 28)
