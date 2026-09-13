# Contact reaction control flow

This map describes original USA ROM control flow, not the current candidate's
admitted domain. Qualification and replay coverage must be reported separately.

The type-`7B` callback at `1AE9D4` calls `1AE4F8` and resumes at `1AE9D8`.
The contact entry has these branches:

| Original location | Condition / effect | Next region |
| --- | --- | --- |
| `1AE4F8`–`1AE51C` | Any of `FFF0E7`, `FFF0E6`, `FFF0E9`, `FFF0F2` is nonzero | Return at `1AE5E0` |
| `1AE520`–`1AE558` | First nonzero of `FFF0BE`, `FFF0D0`, `FFF0D7`, `FFF0CD`, `FFF0D4`, or zero `FFF0C1` in original test order | Test `FFF173` at `1AE5E2` |
| `1AE55C` | `FFF173` nonzero | Reaction at `1AE5EA` |
| `1AE566` | `FFF0CC` nonzero | Reset at `1AE58E` |
| `1AE56E`–`1AE57C` | `FFEFFF` or `FFF11F` nonzero | Test `FFF173` at `1AE5E2` |
| `1AE57E` | Publish pointer `1226CE` to `FF7E60`; clear `FF7E77` | Reset at `1AE58E` |
| `1AE5E2` | `FFF173` zero / nonzero | Reset / reaction |

The ordered early tests have different path lengths. Sharing a semantic outcome
does not imply equal prefix timing at the current exact machine boundary.

## Reset and the existing sound service

At `1AE58E`, clear the word at `FFF0B0` and byte at `FFF0CC`. If sound enable
`FFF57D` is nonzero, save `D0/D1/A0/A1/A6`, push command **`0x31` (49 decimal)**,
and execute original callees `1E58B8` then `1E589A`. The second return is `1AE5B6`.
Restore the saved registers and continue at `1AE5BC`.

The repeated sound-site recognizer in `scripts/collection_sound_sites.py`
accepts this site unchanged with `resume=0x1AE5B6`. The call sequence uses the
same argument and saved-register layout as the collection family. The first
call writes return address `1AE5B0`; the second overwrites that slot with
`1AE5B6`. Return recognition must check the latter after both calls execute.

Call `1B03F2` once. Call it again if `FF7E21 != 0`; after that second call,
call it a third time if `FF7E21 != 1`. Each call sees the preceding call's writes. All reset routes
eventually return at `1AE5E0`.

At `1B03F2`, return without changes if `FFF0E9`, `FFF0E6` or `FF7E20` is nonzero.
Otherwise, a zero `FFEFFA` sets `FFF0E6` to 10. A nonzero `FFEFFA` is decremented
and `FFF0F2` set to `0x28` only when `FFF0F2` was zero. These gates mean repeated
calls are not equivalent to subtracting the number of calls from the counter.

## Reaction

At `1AE5EA`, publish pointer `1226B2` to `FF7E60`, clear `FF7E77`, set `FFF0E7`
to `FF` and `FFF0E9` to `32` hexadecimal. If `FFF0D8` is zero, set `FFEFFF`
to 1 and return at `1AE618`; otherwise return through `1AE5E0`.

These effect-based names intentionally leave uncertain gameplay meanings open.
RAM remains authoritative. No independent object graph or new continuation
state is implied by the map.
