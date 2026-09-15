# External components and machine ownership policy

Current policy, written 13 September 2026 for Aladdin and unchanged by the
multi-game split: the machine it describes is the one shared machine
(`native/machine.cpp`, `src/genesis_re/machine.py`), and "Aladdin" below reads
as "the game being recovered".  Paths are the current ones where they
matter; historical names (`aladdin_sega.machine`, `libaladdin_native.dll`)
appear only where the policy quotes them.  The goal is editable game source
in Python, with progressively less original M68000 execution.  Windows x64 is
the supported development and verification host.

## Ownership and reuse

Use only what this specific Aladdin recovery needs. The project must own its
recovery control and policy; it need not own the implementation of every machine
component. A concrete current limitation, rather than a hypothetical second game
or backend, must justify new abstraction or component replacement. See the
[current necessity review](../archive/project/architecture-review.md) for measured evidence.

PortForge is a bootstrap donor of useful implementations. It is neither the
permanent owner of this project nor an indivisible engine dependency. Reuse its
working CPU, board, VDP and scheduler components while they meet our needs.
Do not rewrite a CPU or scheduler merely to claim ownership or move it to Python.
Project ownership means control of interfaces, state, policy and future changes;
it does not require every implementation to have been written here.

Use one production implementation per component. A preserved older build or an
independent emulator may serve as an offline reference, never as a second live
state authority or as the recovered function's answer provider.

Classify dependencies by their actual role:

- **DIRECT-UPSTREAM:** independently maintained libraries such as Nuked OPN2 and
  Nuked PSG. Compile directly from pinned upstream sources with original notices.
  Do not keep a second compiled copy hidden under the donor tree.
- **ABSORB-CANDIDATE:** Genesis-specific integration, state adapters, bus/device
  models and small scheduling pieces. Absorb a coherent slice when editing it
  or removing its surrounding dependencies has a concrete benefit.
- **KEEP-WHILE-USEFUL:** working implementations whose current boundary supports
  recovery, deterministic execution and verification. Retention is a decision,
  not a promise of permanent architecture.
- **FRAMEWORK-GLUE:** donor sessions, census, carrier/island lifecycle, replay
  policy and verdict infrastructure. Do not adopt these as project APIs. Remove
  unused runtime dependencies; isolate useful test-only consumers.

The compiler-observed inventory, reasons and next removal triggers live in
[component-migration.md](../archive/aladdin/component-migration.md). Do not infer runtime ownership
from directory names or from a broad dependency lock alone.

## The machine boundary

`machine.py` owns the Python binding; `native/machine.cpp` owns the C ABI and
native integration. Recovered functions see only narrow project operations:
live memory reads, registers, gate/continuation control, and admitted effects.
They must not import donor namespaces, sessions, region-boundary types, chip
structs, replay policies, or verification results.

The current native GenesisEngine remains useful for instruction-boundary
scheduling, Z80 catch-up, IRQ/VDP admission and bounded atomic operations.
Keep it behind the ABI while these facilities work. Extract it when a needed
scheduler change or framework entanglement warrants that work; no speculative
second engine or Python scheduler is required now.

Each machine owns one mutable RAM/device state. Python reads live storage and
stages bounded ordered effects; it does not maintain shadow gameplay objects
that are copied back every tick. Immutable ROM reads may use an immutable copy.
Native allocations and borrowed views have explicit lifetimes. One active
machine per worker process is the current supported execution arrangement.

Master ticks belong to the machine. Wall time paces presentation only. Atomic
replacements must prove that relevant observers cannot see intermediate effects,
charge modeled time, and refuse before mutation when the domain is unsupported.
A failure after effects invalidates execution; never rerun the original over a
partially applied replacement. Keep bus, IRQ, DMA and sound timing limitations
visible in the qualification contract.

## Snapshots, recording and provenance

Replay, snapshot containers, input ordering, verification, recovery policy and
presentation are project-owned Python code. Machine state is an opaque payload
exported, validated and restored by the native boundary. Python may check the
container's lengths and hashes; it may not decode private CPU/chip layouts or
patch offsets into a native snapshot.

Persist explicit machine fields at a safe completed-operation boundary. A raw
C struct dump, native pointer, Python stack or generator is not a save format.
Recovered locals must be materialized in machine state or a small explicit
continuation before a suspension point. The current staged regions leave no
suspended Python frame to serialize.

Player caches declare cache contract 3 and machine-state contract 1 (the
snapshot containers of the pre-history model were archive version 2). Validate
ROM, behavioral profile, contract and archive integrity. Native import validates
its own codec and identity before committing state. Unsupported early versions
fail clearly; regenerate captures instead of accumulating source-transition
registries, migration chains or format negotiation frameworks.

Source/build hashes are provenance, separate from the behavioral profile and
state contract. A comment-only rebuild does not create a new machine model.
Bump the profile for behavioral configuration changes and the state contract
when persisted state or continuation semantics change. An unchanged contract
is not an equivalence verdict: affected replay tests still qualify each change.
Execution receipts identify exact Python modules, native binary, adapter, locks,
upstream revisions, toolchain, artifact and comparison contract.

User originals are immutable. Regenerated files use new paths and retain parent
hashes and derivation facts. Replaying existing user inputs does not establish
new human coverage. Do not commit ROMs or private recordings.

## Recovery and qualification

Editable source and qualified replacement are separate axes. Recover connected
control flow with explicit unknown exits, then strengthen each supported domain.
Keep game behavior in `recovered.py`, gate/admission selection in `recovery.py`,
and witnesses/verdicts outside both. Do not recreate donor carrier manifests,
island registries, or a generic intermediate language.

An explicit legacy exit must preserve a valid original continuation. The initial
open region conservatively declines from its unchanged entry when it encounters
an unrecovered branch. Widen that route only with a concrete continuation test.
Composition should remove guest call transitions and duplicate bookkeeping.
Measure admitted calls, instructions replaced, fallback reasons and remaining
legacy execution rather than counting renamed wrappers or deleted tests.

Use short witnesses during editing and full replay gates for integration.
Compare state, frame, PCM, timing and continuation in fresh processes. Test wrong
output, wrong continuation and wrong timing mutants. Same-model agreement checks
recovery equivalence; it does not establish independent hardware accuracy.
No full native rebuild or package reinstall is required for a Python game edit.

## Dependencies and enforcement

Pin exact upstream revisions and file hashes, preserve licenses, list local
patches explicitly, and verify hashes on every native build. Vendored core bytes
must survive Git checkout without newline conversion. Keep donor runtime and
test closures separate; a runtime-only build must work without donor session,
census, input-script or verdict headers.

`scripts/check_architecture.py` rejects donor framework and native codec leakage
into normal project Python and policy imports into recovered behavior. Binding
and receipt modules are explicit boundary owners. This lightweight guard is
backed by an intentional-leak test; it is not a substitute for review of effects
or aliasing. Avoid building a general architecture-analysis framework.

No top-level license was found in the inspected donor. Direct upstream notices
are retained, but public redistribution of the combined project remains
unresolved. See [third-party notices](../../third_party/README.md).
