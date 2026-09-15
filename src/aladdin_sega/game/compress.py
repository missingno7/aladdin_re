"""The game's compressed asset format (1B35D0 / 1B3818): blocks of Huffman-coded LZ77.

Both decompressors share one bit reader (a 32-bit buffer of little-endian
words from the stream, consumed low bit first) and one code-table
builder: per block, three canonical Huffman tables (up to 16 symbols of
4-bit code lengths each) for literal-run lengths, match distances and
match lengths.  A symbol below 2 is its own value; a symbol s >= 2 is
followed by s-1 extra bits and means 2**(s-1) plus those bits.  A block
is a literal run, then a count of (match, literal run) pairs; a match
copies length+2 bytes from distance+1 bytes back.

* ``decompress`` (1B3818) writes into RAM: a 4-byte big-endian size after
  a 4-byte tag, then 6 more header bytes, then blocks until the size is
  reached.  It loads level maps and attribute tables.
* ``decompress_to_vdp`` (1B35D0) writes through a 16 KB ring in RAM and
  sends every completed word to the VDP data port: 17 header bytes, a
  block count, then blocks.  It loads tiles and name tables into VRAM.

The reader keeps the original's register discipline (the buffer's high
word holds the next stream word, refills shift by the bits still valid)
so that its output is bit-exact with the ROM code on every asset.
"""


TRACE = None      # a list: every decode / get call appends (kind, a3, d6, d7) for the codec's own verification

# Outputs verified word for word / byte for byte against the original's decompressors in the oracle
# (the level 1 -> 2 change of the recording): source -> (variant, words or bytes, sha256).  A codec change that
# alters one of these must be re-verified against the oracle, never against the digest.
VERIFIED_DIGESTS = {
    0x13C374: ('vdp', 16080, '67f0fe048605b99465c71d275125df114ec09f8a061d07ffa0de65433fe53baf'),
    0x1313FD: ('vdp', 1792, '83e1c9ca360bae11c6fe553197c7735f7c2feb5d007ef926713c1051c3765c23'),
    0x136912: ('vdp', 16816, 'da3cafdc6fff5c4f1dd7a8bff88d221f99fe6f748f46b172046099ba3a658ff0'),
    0x1758E4: ('vdp', 17152, '7181ee4845a889074c0fdcc73e494e45adbdf95ec410c44077144ad0feebe2b8'),
    0x1434C4: ('ram', 16080, '4ccf1f7d95664cdc8c48a2aabe9a10f2cf2e14f2ab61a303111b940ffd09f3ea'),
    0x12A660: ('ram', 3584, '220f7101aa621ae563c3f2cec51067d03f89fc55c7bfe89014d91cf7681bf86c'),
    0x19759C: ('ram', 756, 'ff4494e3f86f7bc56985a4dfed21ddfdc514e3ad078b9e885e60f6cddebdd13a'),
}


class _Bits:
    __slots__ = ('rom', 'a3', 'd6', 'd7')

    def __init__(self, rom, position, d6_high=0):
        self.rom = rom
        self.a3 = position
        self.d7 = 0
        self.d6 = ((d6_high & 0xFFFF) << 16) | rom[position] | (rom[position + 1] << 8)

    def _refill(self, need):
        """1B3778: consume the bits still valid, bring the next stream word in, report the bits still needed."""
        self.d7 = (self.d7 + need) & 0xFF
        self.d6 = (self.d6 >> (self.d7 & 0x3F)) & 0xFFFFFFFF
        self.d6 = ((self.d6 << 16) | (self.d6 >> 16)) & 0xFFFFFFFF
        word = (self.rom[self.a3 + 3] << 8) | self.rom[self.a3 + 2]
        self.a3 += 2
        self.d6 = (self.d6 & 0xFFFF0000) | word
        self.d6 = ((self.d6 << 16) | (self.d6 >> 16)) & 0xFFFFFFFF
        need = (need - self.d7) & 0xFF
        self.d7 = (16 - need) & 0xFF
        return need

    def get(self, mask, need):
        """1B376C: the masked low bits of the buffer, then drop ``need`` bits."""
        if TRACE is not None:
            TRACE.append(('get', self.a3, self.d6, self.d7))
        value = self.d6 & mask & 0xFFFF
        self.d7 = (self.d7 - need) & 0xFF
        if self.d7 & 0x80:
            need = self._refill(need)
        self.d6 = (self.d6 >> (need & 0x3F)) & 0xFFFFFFFF
        return value

    def resync(self, d0_high):
        """1B370E / 1B3892: after raw literal bytes were taken from the stream, splice the next word in above the valid bits.

        The original shifts a 32-bit register whose high word still holds
        what D0 last carried (FFFF after the pair-count read, 0 after a
        match); those bits land above the word and are consumed later, so
        the codec carries them too.
        """
        word = (self.rom[self.a3 + 1] << 8) | self.rom[self.a3]
        shifted = ((((d0_high & 0xFFFF) << 16) | word) << (self.d7 & 0x3F)) & 0xFFFFFFFF
        keep = ((1 << (self.d7 & 0x3F)) - 1) & 0xFFFF
        self.d6 = ((self.d6 & keep) | shifted) & 0xFFFFFFFF


class _Table:
    """One canonical Huffman table: 16 (mask, code) pairs, then per entry (length, symbol, extra-bit mask)."""
    __slots__ = ('entries',)

    def __init__(self):
        self.entries = []      # (mask, code, length, symbol, extra_mask)

    def build(self, bits: _Bits) -> None:
        """1B3790."""
        count = (bits.get(0x1F, 5) - 1) & 0xFFFF
        self.entries = []
        if count & 0x8000:
            return
        lengths = [bits.get(0xF, 4) for _ in range(count + 1)]
        step, length, code = 0x80000000, 1, 0
        while True:
            for symbol in range(count + 1):
                if lengths[symbol] != length:
                    continue
                mask = (1 << length) - 1
                reversed_code = 0
                top = (code >> 16) & 0xFFFF
                for _ in range(length):
                    reversed_code = (reversed_code >> 1) | ((top & 0x8000) << 0)
                    top = (top << 1) & 0xFFFF
                reversed_code = (reversed_code >> (16 - length)) & 0xFFFF
                extra = symbol - 1
                extra_mask = (((1 << (extra & 0x3F)) - 1) & 0xFFFF) if symbol else 0xFFFF
                self.entries.append((mask, reversed_code, length, symbol, extra_mask))
                code = (code + step) & 0xFFFFFFFF
            step >>= 1
            length += 1
            if length == 17:
                return

    def decode(self, bits: _Bits) -> int:
        """1B3736: match the buffer's low bits against the codes, then read the symbol's extra bits."""
        if TRACE is not None:
            TRACE.append(('decode', bits.a3, bits.d6, bits.d7))
        low = bits.d6 & 0xFFFF
        for mask, code, length, symbol, extra_mask in self.entries:
            if (low & mask) == code:
                break
        else:
            raise ValueError('no code matches the bit buffer')
        bits.d7 = (bits.d7 - length) & 0xFF
        if bits.d7 & 0x80:
            length = bits._refill(length)
        bits.d6 = (bits.d6 >> (length & 0x3F)) & 0xFFFFFFFF
        if symbol < 2:
            return symbol
        extra = symbol - 1
        value = bits.d6 & extra_mask & 0xFFFF
        bits.d7 = (bits.d7 - extra) & 0xFF
        if bits.d7 & 0x80:
            extra = bits._refill(extra)
        bits.d6 = (bits.d6 >> (extra & 0x3F)) & 0xFFFFFFFF
        return (value | (1 << (symbol - 1))) & 0xFFFF


def decompress(rom, source, d6_high=0) -> bytes:
    """1B3818: the RAM variant; the size is the big-endian long at source+4."""
    size = int.from_bytes(rom[source + 4:source + 8], 'big')
    bits = _Bits(rom, source + 8 + 0xA, d6_high)
    out = bytearray()
    literals, distances, lengths = _Table(), _Table(), _Table()
    bits.get(2, 2)
    while True:
        literals.build(bits); distances.build(bits); lengths.build(bits)
        pairs = (bits.get(0xFFFF, 16) - 1) & 0xFFFF      # the count word, then DBRA: count - 1 pairs
        run = literals.decode(bits)
        if run:
            out += rom[bits.a3:bits.a3 + run]
            bits.a3 += run
            bits.resync(0xFFFF)
        for _ in range(pairs):
            distance = distances.decode(bits)
            start = len(out) - 1 - distance
            length = lengths.decode(bits) + 2
            for i in range(length):
                out.append(out[start + i])
            run = literals.decode(bits)
            if run:
                out += rom[bits.a3:bits.a3 + run]
                bits.a3 += run
                bits.resync(0)
        if len(out) >= size:
            return bytes(out)


def decompress_to_vdp(rom, source, data, d6_high=0, window=None):
    """1B35D0: the VRAM variant; every completed word of the 16 KB ring goes to ``data(word)``.

    Returns the ring (the RAM window the original leaves behind at a1).
    """
    ring = window if window is not None else bytearray(0x4000)
    bits = _Bits(rom, source + 0x11 + 1, d6_high)
    blocks = rom[source + 0x11]
    position = 0
    literals, distances, lengths = _Table(), _Table(), _Table()
    bits.get(2, 2)

    def put(byte):
        nonlocal position
        ring[position] = byte
        if position & 1:
            data((ring[position - 1] << 8) | ring[position])
        position = (position + 1) & 0x3FFF

    for _ in range(blocks):
        literals.build(bits); distances.build(bits); lengths.build(bits)
        pairs = (bits.get(0xFFFF, 16) - 1) & 0xFFFF
        run = literals.decode(bits)
        for i in range(run):
            put(rom[bits.a3 + i])
        if run:
            bits.a3 += run
            bits.resync(0xFFFF)
        for _ in range(pairs):
            distance = distances.decode(bits)
            start = (position - 1 - distance) & 0x3FFF
            length = lengths.decode(bits) + 2
            for i in range(length):
                put(ring[(start + i) & 0x3FFF])
            run = literals.decode(bits)
            for i in range(run):
                put(rom[bits.a3 + i])
            if run:
                bits.a3 += run
                bits.resync(0)
    return ring
