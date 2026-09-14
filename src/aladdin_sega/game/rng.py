"""The game's random number generator: one global 32-bit seed at ``FF7DEA``.

Every consumer calls ``1B3032``, which advances the seed by a linear
congruential step and hands back a 16-bit value.  This is game state, not
machine state: the seed is the only persistent datum.
"""

SEED_ADDRESS = 0xFF7DEA
MULTIPLIER, INCREMENT = 13, 7


def advance_rng(seed):
    """Return ``(new_seed, output)`` for one call of the generator.

    ``new_seed = 13 * seed + 7`` modulo 2**32 (the ROM computes it as
    ``seed + 7 + 4 * seed + 8 * seed``); the output is the low word of the
    new seed exclusive-or its high word.
    """
    new_seed = (MULTIPLIER * seed + INCREMENT) & 0xFFFFFFFF
    output = ((new_seed & 0xFFFF) ^ (new_seed >> 16)) & 0xFFFF
    return new_seed, output


def rng_writes(new_seed):
    """The seed bytes the generator stores back."""
    return [(SEED_ADDRESS + index, (new_seed >> (8 * (3 - index))) & 0xFF) for index in range(4)]
