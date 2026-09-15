"""The asset codec against outputs that were verified word for word against the original's decompressors.

The digests below were taken from oracle runs (scripts/.. verify_decompress:
every 1B35D0 / 1B3818 call of the level 1 -> level 2 change matched the
original's VDP port words and RAM output).  They pin the codec to those
outputs; a codec change that alters any of them must be re-verified
against the oracle, not against these numbers.
"""
import hashlib
import pytest
from aladdin_sega.profile import read_rom
from aladdin_sega.game import compress

rom = read_rom()

def _words_digest(words):
    return hashlib.sha256(b''.join(w.to_bytes(2, 'big') for w in words)).hexdigest()


def test_ram_variant_produces_the_declared_size():
    """Level table entries: +8 attributes -> FFAE84, +10 map -> FF0000, +1C plane B -> FF8884 (level 2)."""
    entry = 0x2C78 + 0x42 * 2
    for offset, expected in ((0x8, 16080), (0x10, 756), (0x1C, 3584)):
        source = int.from_bytes(rom[entry + offset:entry + offset + 4], 'big')
        size = int.from_bytes(rom[source + 4:source + 8], 'big')
        assert size == expected
        out = compress.decompress(rom, source)
        assert len(out) >= size


def test_vdp_variant_streams_whole_words():
    words = []
    ring = compress.decompress_to_vdp(rom, 0x1313FD, words.append)
    assert len(words) == 1792
    assert len(ring) == 0x4000
    assert b''.join(w.to_bytes(2, 'big') for w in words) == bytes(ring[:2 * 1792])


@pytest.mark.parametrize('source', sorted(compress.VERIFIED_DIGESTS))
def test_codec_reproduces_the_oracle_verified_outputs(source):
    variant, expected_size, expected_digest = compress.VERIFIED_DIGESTS[source]
    if variant == 'ram':
        out = compress.decompress(rom, source)[:expected_size]
        assert hashlib.sha256(out).hexdigest() == expected_digest
    else:
        words = []
        compress.decompress_to_vdp(rom, source, words.append)
        assert len(words) == expected_size
        assert _words_digest(words) == expected_digest
