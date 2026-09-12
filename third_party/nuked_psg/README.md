# Nuked-PSG provenance

Vendored unchanged from [Nuked-PSG](https://github.com/nukeykt/Nuked-PSG) at
`d15a168c676f4669e23660be9225b34ad7c1764e` (YMPSG version 1.0.1).

Files `ympsg.c`, `ympsg.h`, and `LICENSE` are upstream GPLv2+ material and
remain unmodified. PortForge's machine adapter is
`src/platform/genesis/nuked_psg.hpp`.

The adapter's declared one-clock-per-15-master-cycles contract is supported by
[SMS Power's NTSC clock-rate note](https://www.smspower.org/Development/ClockRate)
(53.6931 MHz divided by 15 for PSG) and its
[integrated Genesis PSG note](https://www.smspower.org/Development/SN76489).
These references support the input-clock contract; they are not a claim that
this integration has measured hardware audio fidelity.
