# Nuked-OPN2

Single machine-owned Genesis YM2612 implementation for status, timers and PCM.

Upstream: https://github.com/nukeykt/Nuked-OPN2
Pinned revision: `335747d78cb0abbc3b55b004e62dad9763140115`.
License: LGPL-2.1-or-later; see `LICENSE`.

Unmodified upstream files (SHA-256):

- `ym3438.c`: `8fa385546f0f2d1c975d097002af00cd729ae2ae097c068e9c883ce08ddf3a76`
- `ym3438.h`: `8e60e35f77049d0e600ad1a47bfc3dfc8b832483e614104473a83c1f33cd7189`
- `LICENSE`: `20c17d8b8c48a600800dfd14f95d5cb9ff47066a9641ddeab48dc54aec96e331`

The adapter clocks one internal tick per 42 master cycles and sums 24 lane
outputs per 1008-master frame, scaled by 11. This is a declared digital
output convention, not a measured board gain. The upstream DAC implementation
itself is labeled unverified. Snapshots carry the actual public chip value
and finite clock/accumulator state; observers are excluded.
