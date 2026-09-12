# External Components and Machine Ownership Policy

## Status

This document defines the dependency and machine-ownership policy for `aladdin_re`.

It is subordinate to the main project assignment. If this document and the main assignment ever disagree, the main assignment wins.

The purpose of this policy is to prevent two opposite failures:

1. wasting time reimplementing already solved low-level hardware behavior without evidence that doing so is useful;
2. accidentally turning `aladdin_re` into a thin wrapper around somebody else's Genesis emulator, losing control over timing, state, snapshots, tracing, progressive replacement, and verification.

The project is not attempting to prove that every machine component should be written in Python.

It is also not attempting to replace working, already verified project components merely because an external library exists.

The central rule is:

> **Reuse proven component implementations where they reduce risk, but never outsource ownership of the machine.**

A more operational version is:

> **Do not reimplement solved chip-level behavior without a reason. Do not replace an already verified project implementation merely to use a library. The scheduler, authoritative state, replay semantics, replacement system, and verification remain project-owned.**

---

# 1. Project Context

`aladdin_re` has one initial target:

> the specific user-supplied Mega Drive / Genesis ROM of Disney's Aladdin selected by the project profile.

The project exists to progressively transform execution from:

```text
original machine code
```

through:

```text
original machine code
+
editable carrier source
+
recovered mechanisms
```

toward:

```text
predominantly normal editable game source
+
an explicit hardware compatibility layer
```

The dependency architecture must support that progression.

External component decisions must therefore be judged primarily by whether they preserve:

* deterministic execution,
* explicit virtual time,
* inspectable state,
* replay compatibility,
* snapshot/restore,
* tracing,
* original/hybrid comparison,
* progressive replacement,
* eventual removal of the original M68000 execution path.

Performance is important, but performance alone does not own the architecture.

---

# 2. Existing Verified Work Comes First

Before choosing a new external implementation for a component, inspect the existing Sega implementation available in the local PortForge workspace.

For each relevant component determine:

* what implementation is already used;
* whether it has tests;
* whether Aladdin already exercised it;
* what timing granularity it actually provides;
* whether snapshots expose enough state;
* whether the integration has known gaps;
* whether its license permits reuse in this project;
* whether transferring it is simpler and safer than introducing another implementation.

The initial preference order is:

```text
1. reuse a verified existing project implementation/integration;
2. adapt a proven external component when needed;
3. implement a new component only when neither of the above is suitable.
```

Do not interpret this as an instruction to copy the whole PortForge architecture.

Transfer:

* verified behavior,
* focused implementations,
* tests,
* known timing rules,
* known integration details.

Do not automatically transfer:

* generic registries,
* historical compatibility layers,
* abandoned mechanisms,
* framework abstractions,
* multi-platform architecture not required by Aladdin.

---

# 3. One Production Backend Per Component

Do not maintain several interchangeable production implementations merely because they are available.

In particular, avoid architecture such as:

```text
M68000 backend:
    Python
    Musashi
    emulator-core backend
    JIT backend
```

unless a later concrete requirement justifies it.

During initial development there should normally be **one authoritative runtime implementation** of each machine component.

Independent implementations may exist as:

* test references,
* conformance oracles,
* offline research tools,
* temporary migration aids.

They are not automatically production backends.

The distinction is important:

```text
production runtime implementation
        !=
independent reference implementation
```

---

# 4. Machine Ownership

`aladdin_re` owns the machine.

That includes the authoritative definitions of:

* virtual time,
* scheduler ordering,
* machine reset,
* memory map,
* MMIO behavior,
* bus ownership,
* interrupts,
* DMA coordination,
* controller input delivery,
* CPU/device coordination,
* snapshots,
* replay semantics,
* state hashing,
* tracing,
* replacement dispatch,
* original/hybrid execution modes,
* verification boundaries.

No external library may become the hidden authority for those concepts.

External components may implement local semantics.

For example:

```text
external component may know:

"what does this YM2612 register write do?"
```

but not:

```text
"when in the global machine timeline should this write occur?"
```

Similarly:

```text
CPU implementation may know:

"what are the effects of ADD.W?"
```

but the project must own:

```text
memory
MMIO
interrupt delivery
scheduler integration
replacement boundaries
```

---

# 5. Initial M68000 Policy

## 5.1 Initial runtime direction

The initial production M68000 path should be based on the already existing and verified Sega CPU model from PortForge, adapted to the new project and its Python-first architecture.

Do not replace it with Musashi before measuring the actual Aladdin workload.

The first questions are:

* Is the transferred implementation correct enough for the selected ROM?
* Does it support the instructions and exception behavior Aladdin actually exercises?
* What percentage of execution time does it consume?
* Does it prevent the first original → replay → snapshot → replacement milestones?
* Does moving it native materially improve end-to-end iteration time?

Only measurements should answer the final performance question.

The initial architecture should therefore resemble:

```text
Python machine
    |
    +-- project-owned M68000 implementation
    +-- project-owned/adapted VDP
    +-- project-owned scheduler
    +-- project-owned bus
    +-- project-owned replay/snapshot
    |
    +-- native audio components where justified
```

---

# 6. Musashi Policy

Musashi is useful, but it is **not the mandatory initial production M68000 implementation**.

Suitable roles include:

### Independent CPU reference

Use Musashi to compare selected instruction behavior, register results, exceptions, flags, or execution traces against the project implementation.

### Conformance testing

It may be useful for targeted generated instruction tests where an independent implementation improves confidence.

### Later native accelerator

If profiling demonstrates that the Python M68000 implementation is a major performance bottleneck, Musashi may become a candidate for replacing or accelerating the original-instruction execution path.

Such a change must preserve the same project-owned contracts:

```text
GenesisBus
virtual timeline
interrupt scheduling
snapshot semantics
replacement dispatch
trace semantics
replay semantics
```

A move to Musashi must not require recovered Python game logic to change.

### Not allowed by default

Do not introduce Musashi merely because:

* it is mature,
* it is faster,
* writing CPU code ourselves appears redundant,
* it may eventually be useful.

The project assignment explicitly requires measurement before introducing additional native acceleration.

---

# 7. Static M68000 Decoding

A separate structured decoder may be used for offline recovery tooling.

**Capstone M68K** is a reasonable candidate.

Its possible roles include:

* instruction decoding,
* operand extraction,
* branch discovery,
* direct call discovery,
* addressing-mode analysis,
* ROM/RAM reference extraction,
* CFG construction,
* support for the small Aladdin-specific emitter.

This is an offline/recovery concern.

It does not imply that Capstone owns runtime execution.

Preferred separation:

```text
runtime execution:
    transferred project M68000 model

offline analysis:
    Capstone M68K or another structured decoder

source emission:
    project-owned small Aladdin-specific emitter
```

Do not build a universal compiler framework around the decoder.

The emitter should grow only in response to patterns required by actual Aladdin regions.

---

# 8. Z80 Policy

Z80 is a real execution dependency and must not be reduced to an audio-register wrapper.

The first step is to inspect the existing PortForge Sega Z80 implementation or integration.

If it is:

* already verified,
* suitable for the required timing model,
* snapshot-compatible,
* straightforward to transfer,

reuse it.

If the existing implementation is unsuitable, a small proven external core such as Jolly Good Z80 may be considered.

Do not maintain both as permanent production backends.

The decision order is:

```text
existing verified PortForge Z80 path
        |
        | suitable?
       / \
     yes  no
      |    |
   reuse   evaluate small proven external core
```

The project still owns:

* Z80 scheduling,
* Z80-visible memory map,
* bus-request behavior,
* communication with M68000,
* reset behavior,
* snapshots,
* trace integration,
* virtual-time relationship to the rest of the machine.

---

# 9. YM2612 / YM3438 Policy

FM synthesis is a strong candidate for external native reuse.

The first preference is to reuse the already proven Nuked OPN2 integration from PortForge if available and suitable.

This is exactly the class of component where an external implementation is beneficial:

* the chip semantics are complex;
* the subsystem is narrow;
* mature implementations exist;
* there is little value in writing another FM synthesizer;
* the machine can still retain scheduling authority.

The project must control when chip time advances.

Avoid opaque interfaces of the form:

```text
render_audio(frame_count)
```

if they internally advance an unknown amount of virtual hardware time.

Prefer a project wrapper with semantics conceptually equivalent to:

```text
create
destroy
reset

advance_to(virtual_time)

write_at(virtual_time, port, value)
read_at(virtual_time, port)

save_state
load_state

drain_pcm
```

These are requirements of the project wrapper, not assumptions about the upstream library API.

The wrapper owns conversion from project virtual time into the chip's clock domain.

---

# 10. PSG Policy

The PSG should also use an existing proven implementation when available.

First inspect what PortForge currently uses and whether that integration is already tested.

Do not assume the PSG is another Nuked component merely because OPN2 is.

If the existing PortForge integration is appropriate:

> transfer it.

Otherwise select a small proven implementation with acceptable licensing and controllable timing.

The same ownership rule applies:

```text
external core:
    chip semantics

aladdin_re:
    when writes happen
    when time advances
    snapshot boundary
    audio routing
    machine timeline
```

There is no project value in implementing another PSG merely because the hardware is relatively simple.

---

# 11. Native Code Policy

Native code is initially expected mainly around audio chips.

Do not prematurely move the entire machine runtime into native code.

Initial expected shape:

```text
Python
    machine ownership
    scheduler
    bus
    M68000
    Z80 if practical
    VDP
    replay
    snapshot
    verification
    carrier
    recovered logic

Native
    OPN2 wrapper
    PSG wrapper if justified
```

This shape is not permanent law.

Profiling may later show that another component dominates execution time.

If so, a focused native acceleration is allowed.

Examples:

```text
M68000 execution is dominant
    -> evaluate Musashi or another focused native implementation

VDP rendering dominates
    -> evaluate a narrow VDP hot-path acceleration

FFI overhead dominates
    -> batch calls more aggressively
```

Any optimization must preserve:

* replay format,
* project state model,
* public machine API,
* recovered game source,
* verification semantics.

The optimization must not silently become a second game engine.

---

# 12. Python / Native FFI Boundary

Do not cross the Python/native boundary for every master clock.

Avoid:

```python
for tick in range(...):
    native.clock_opn2()
```

or equivalent very fine-grained FFI traffic.

Prefer batching.

For audio, the intended pattern is approximately:

```text
Python scheduler
       |
       | advance_to(T)
       v
native wrapper
       |
       +-- internally clocks component efficiently
       |
       v
component state at T
```

The native wrapper must not skip project-visible events.

For example, do not batch across a boundary where:

* a register status read matters,
* an interrupt becomes visible,
* another device observes the result,
* the ordering of writes is relevant.

Batching is an optimization of execution, not a change of timing semantics.

---

# 13. VDP Policy

The VDP remains part of the project-owned Sega machine model.

This does **not** mean it must be rewritten from scratch.

Prefer transferring the already existing and tested PortForge Sega VDP behavior where appropriate.

The resulting implementation must expose enough state and timing information for the project to own:

* VRAM,
* CRAM,
* VSRAM,
* VDP registers,
* control/data port behavior,
* DMA,
* FIFO/latches where relevant,
* interrupt state,
* frame/scanline progression at the actual supported granularity,
* state required for snapshot/restore,
* observable writes and effects needed by the verifier.

Do not hide the VDP behind a whole-system emulator API such as:

```text
run_one_genesis_frame()
```

where internal ordering and state become inaccessible.

If a third-party VDP implementation is ever adapted, it must behave as a project component, not as an opaque machine owner.

---

# 14. Do Not Claim Accuracy You Do Not Have

Using an external component does not automatically make the whole machine cycle-accurate.

Similarly, transferring an implementation from PortForge does not prove that its timing granularity is sufficient.

Document the actual model.

Examples:

```text
instruction-granular M68000 timing
scanline-granular VDP event
master-clock scheduled audio
```

must not be summarized as:

```text
cycle accurate Genesis
```

unless that claim is genuinely demonstrated.

External library marketing or upstream claims do not automatically transfer to the integrated machine.

---

# 15. Memory and Bus Ownership

There is one authoritative machine state.

All device-visible and side-effectful accesses must preserve project bus semantics.

MMIO must go through the project-owned bus/interface.

Examples include:

* VDP ports,
* Z80 windows,
* YM2612 ports,
* controller IO,
* bus control registers,
* other side-effectful hardware registers.

Plain RAM access may use direct fast paths inside controlled project code when appropriate.

The important invariant is not:

> every byte load must pass through one generic function.

The important invariant is:

> no optimization may bypass observable machine behavior or create a second mutable authority.

A direct RAM path must preserve any required:

* code-cache invalidation,
* tracing,
* aliasing semantics,
* endianness,
* width behavior,
* authoritative storage.

---

# 16. One Authoritative RAM

Game views do not own copied state.

Recovered game code should operate through:

* the authoritative machine RAM,
* named views into that RAM,
* qualified value snapshots where a specific mechanism contract allows them.

Do not introduce an external runtime or library that requires duplicating the whole game state into another authoritative object model.

This policy applies equally to CPU integrations and future optimizations.

---

# 17. Scheduler Ownership

There is one deterministic virtual timeline.

The project controls:

* conversion between clock domains,
* residual clock fractions,
* ordering of simultaneous events,
* interrupt deadlines,
* DMA interaction,
* bus ownership,
* device advancement.

External components are advanced because the scheduler tells them to advance.

Do not allow several libraries to independently derive simulation time from host time or audio callback frequency.

The host wall clock is presentation pacing only.

---

# 18. Snapshot Ownership

The project defines snapshot semantics.

An external component may provide internal save/load functionality, but that does not make its format the project snapshot format.

The project snapshot must capture all state required for deterministic continuation, including as applicable:

* M68000 state,
* Z80 state,
* RAM,
* VRAM,
* CRAM,
* VSRAM,
* VDP internal state,
* DMA/FIFO/latches,
* pending interrupts,
* bus ownership,
* controller protocol state,
* audio-chip state,
* virtual time,
* clock remainders,
* pending input,
* hybrid continuation metadata.

External component state must be wrapped into a versioned compatibility contract.

Do not treat an arbitrary `memcpy` of a C struct as a stable persistent format unless compatibility is explicitly constrained and tested.

---

# 19. Replay Ownership

External components never define replay timing.

The replay uses project virtual time.

A machine replay should describe external events such as:

```text
(virtual_time, controller_port, button_state)
```

It must remain usable whether the machine currently uses:

* a Python M68000 implementation,
* a later native M68000 implementation,
* original execution,
* hybrid execution,
* increasingly recovered source.

Changing a component implementation must not silently redefine the replay clock.

---

# 20. Replacement Ownership

Progressive source replacement is a core project capability.

No external CPU or emulator library may prevent the machine from deciding:

```text
at this guest PC:
    execute original code
```

or:

```text
at this guest PC:
    enter carrier/recovered source
```

The replacement dispatcher must remain project-owned.

The architecture must support progression from:

```text
single replacement
```

to:

```text
open carrier region
```

to:

```text
connected source region
```

to:

```text
large recovered subsystem
```

without constructing a second machine.

---

# 21. Reference Emulators

Whole-system Genesis emulators are useful, but their role is primarily external reference.

Potential references include implementations such as:

* Nuked-MD,
* BlastEm,
* Genesis Plus GX,
* other suitable test cores discovered during implementation.

Do not make any of them the architectural runtime foundation merely to obtain quick booting.

Their useful roles include:

* targeted device traces,
* CPU behavior comparison,
* reset-state investigation,
* VDP behavior investigation,
* DMA/interrupt comparison,
* frame comparison,
* independent evidence when validating the project machine.

Avoid building a universal adapter framework for every emulator.

Implement only the concrete comparison needed for the current uncertainty.

---

# 22. Independent Oracle Policy

The project's own original execution mode is necessary but is not automatically an independent hardware oracle.

If:

```text
carrier
```

is compared against:

```text
project interpreter
```

and both share the same incorrect semantics, they may agree while both are wrong.

Therefore distinguish:

```text
internal equivalence
```

from:

```text
independent hardware/reference evidence
```

Use external cores or test corpora selectively where independent evidence matters.

This is especially relevant for:

* unusual CPU semantics,
* flags,
* exceptions,
* VDP timing,
* DMA,
* interrupt ordering,
* Z80/M68000 interaction.

Do not require an external emulator to run in lockstep during every ordinary product replay.

---

# 23. Differential Testing

Differential testing is useful when targeted at a real uncertainty.

Examples:

```text
project M68000 vs Musashi
```

for a suspicious instruction case;

```text
project VDP trace vs independent emulator
```

for a DMA boundary;

```text
project OPN2 wrapper vs known core behavior
```

for save/restore correctness.

Do not create broad multi-emulator infrastructure without a concrete need.

The goal is evidence, not an emulator benchmarking framework.

---

# 24. External Library Wrappers

Project code should not depend on third-party APIs everywhere.

External components should be isolated behind narrow adapters.

For example:

```text
native/
    audio/
        opn2_wrapper.*
        psg_wrapper.*
```

and later, if profiling justifies it:

```text
native/
    cpu/
        m68k_wrapper.*
```

The rest of the machine should depend on project contracts.

This permits later changes without contaminating game or verification code.

Prefer:

```text
project interface
      |
thin adapter
      |
external component
```

over:

```text
external API calls spread across the project
```

---

# 25. External Component State

Any runtime component must be suitable for deterministic multi-instance use.

Before adopting an external component, verify:

* Can two independent machine instances exist in one process?
* Does the library contain mutable globals?
* Can its complete relevant state be saved?
* Can the state be restored deterministically?
* Does reset truly reset all relevant state?
* Can timing be controlled externally?
* Can register reads/writes occur at deterministic virtual timestamps?
* Are host pointers or process-specific values embedded in persistent state?

This matters because `verify` requires separate original and hybrid machine instances.

---

# 26. Licensing Policy

Before copying, vendoring, linking, or distributing an external component:

1. inspect its actual current license;
2. record the exact upstream source;
3. pin the exact revision;
4. record local modifications;
5. verify that intended use and distribution are permitted;
6. preserve required attribution and license files.

Do not select a dependency solely based on remembered license information.

Maintain a file such as:

```text
third_party/README.md
```

containing at least:

```text
component
purpose
upstream repository
revision
license
integration type
local modifications
```

A reference-only emulator may have different licensing implications from code linked into the product.

Keep that distinction explicit.

---

# 27. Vendoring and Reproducibility

Foundational dependencies must be reproducible.

Do not silently track mutable upstream branches.

Use:

* pinned commits,
* vendored exact revisions,
* or another deterministic dependency mechanism.

An upstream dependency update is a behavioral change.

Treat it accordingly:

```text
update dependency
        |
        v
run component tests
        |
        v
snapshot/restore tests
        |
        v
golden replay regression
```

Do not regenerate golden evidence merely because the dependency changed.

---

# 28. What Should Usually Be Reused

When available and suitable, strongly prefer reuse for narrow solved components such as:

* FM synthesis,
* PSG synthesis,
* generic instruction decoding,
* possibly a CPU core after profiling demonstrates the need.

These are not where the unique value of `aladdin_re` lies.

---

# 29. What Should Not Be Reimplemented Without Evidence

Do not begin a fresh implementation merely because the component appears interesting or small.

Examples:

* new YM2612 synthesizer,
* new PSG synthesizer,
* new generic M68K disassembler,
* second Z80 interpreter,
* second complete Genesis machine.

A new implementation needs a concrete reason such as:

* required state is inaccessible;
* scheduling cannot be controlled;
* licensing is unacceptable;
* observed behavior is wrong;
* integration prevents deterministic snapshots;
* architecture blocks progressive replacement;
* performance has been measured and no smaller fix is sufficient.

---

# 30. What Must Remain Project-Owned

The following are not candidates for outsourcing as opaque subsystems:

* authoritative machine state,
* virtual timeline,
* scheduler,
* replay semantics,
* snapshot semantics,
* input timing,
* memory/MMIO ownership,
* replacement dispatch,
* carrier continuation rules,
* recovered-game integration,
* verification logic,
* evidence tracking,
* source-recovery process.

These are the defining mechanisms of the project.

---

# 31. Initial Recommended Direction

The initial direction should be treated as:

```text
M68000 runtime
    transfer/adapt verified PortForge Sega implementation
    initially Python-first

M68000 independent reference
    Musashi when useful for targeted validation

M68000 static decoding
    Capstone M68K or equivalent structured decoder

Z80 runtime
    transfer verified PortForge integration if suitable
    otherwise choose one small proven core

YM2612 / YM3438
    reuse proven Nuked OPN2 integration through a thin
    native wrapper

PSG
    reuse proven PortForge integration if suitable
    otherwise one small proven external implementation

VDP
    project-owned/adapted PortForge Sega model

scheduler
    project-owned

bus / MMIO
    project-owned

snapshots
    project-owned

replays
    project-owned

replacement dispatch
    project-owned

whole-system emulators
    targeted independent reference only
```

This is a starting policy, not an instruction to add every listed dependency immediately.

---

# 32. Initial Native Boundary

At the start, prefer:

```text
+-------------------------------------------------+
| Python                                          |
|                                                 |
| GenesisMachine                                  |
|   scheduler                                     |
|   bus                                           |
|   M68000                                        |
|   Z80                                           |
|   VDP                                           |
|   input                                         |
|                                                 |
| replay / snapshot / verify                      |
| carrier / recovered logic                       |
+-----------------------+-------------------------+
                        |
                        | narrow FFI
                        v
+-------------------------------------------------+
| Native                                          |
|                                                 |
| OPN2 wrapper                                    |
| PSG wrapper if justified                        |
+-------------------------------------------------+
```

If profiling later proves the M68000 should move native:

```text
+-------------------------------------------------+
| Python                                          |
|                                                 |
| machine ownership                               |
| scheduler                                       |
| bus contract                                    |
| VDP                                             |
| replay / snapshot / verify                      |
| carrier / recovered logic                       |
+-----------------------+-------------------------+
                        |
                        v
+-------------------------------------------------+
| Native                                          |
|                                                 |
| M68000 accelerator/core                         |
| OPN2                                            |
| PSG                                             |
+-------------------------------------------------+
```

The transition must not redesign the game source.

---

# 33. Performance Decision Rule

Do not optimize from intuition.

Measure on the real selected Aladdin workload.

At minimum distinguish time spent in:

```text
M68000
Z80
VDP
audio
Python/native FFI
snapshotting
comparison/verifier
other machine code
```

Then optimize the dominant cost.

Examples:

### Case A

```text
M68000        12 %
VDP           48 %
audio         10 %
comparison    25 %
other          5 %
```

Replacing M68000 with Musashi is probably not the highest-value step.

### Case B

```text
M68000        78 %
VDP            9 %
audio          4 %
comparison     6 %
other          3 %
```

A native CPU path becomes a serious candidate.

### Case C

```text
native work    8 %
FFI calls     55 %
```

Do not rewrite the component.

Fix batching first.

---

# 34. Decision Rule for a New Dependency

Before adding any external runtime dependency, answer:

## A. Is there already a verified implementation in PortForge?

If yes, inspect it first.

Do not replace it automatically.

## B. Is this a small bounded component?

If yes, external reuse is more attractive.

## C. Can project virtual time explicitly control it?

If no, it is a poor runtime dependency.

## D. Can all relevant state be captured and restored?

If no, it may be unsuitable for the deterministic machine.

## E. Can independent machine instances coexist?

If no, `verify` may become unreliable.

## F. Does adopting it force game or recovered code to depend on its API?

If yes, the boundary is probably wrong.

## G. Is this solving a measured problem?

If not, defer the dependency.

## H. Could it instead be useful as an oracle?

If yes, use it as an oracle rather than making it part of the production architecture.

---

# 35. Decision Rule for Replacing an Existing Component

Replacing an already working component requires stronger evidence than choosing an implementation for a missing component.

A replacement should answer:

```text
What concrete problem does the current implementation cause?
```

Examples of valid answers:

* blocks realtime or acceptable iteration latency;
* produces demonstrated incorrect behavior;
* cannot preserve snapshot state;
* prevents two isolated instances;
* cannot represent required timing;
* has incompatible licensing;
* creates unacceptable maintenance cost.

Examples of weak answers:

```text
the external library is better known
the C version is probably faster
the new architecture looks cleaner
we may need this eventually
```

---

# 36. Milestone Compatibility

Dependency work must serve the project milestones.

The first dependency decisions should help reach:

```text
Aladdin boots and runs from ROM
        |
snapshot / restore works
        |
replay is deterministic
        |
one real Python replacement executes
        |
one open carrier region correctly returns to legacy execution
```

A dependency refactor that postpones this vertical path without solving a demonstrated blocker is probably premature.

Do not spend the early project phase constructing a theoretically ideal Genesis abstraction before the game runs.

---

# 37. Final Principle

When deciding whether to write, reuse, wrap, replace, or merely reference a component, use this hierarchy:

```text
Does existing verified project code already solve it?
        |
        +-- yes -> reuse unless evidence says not to
        |
        +-- no
             |
             v
Is there a small proven external component?
        |
        +-- yes -> use if machine ownership stays local
        |
        +-- no
             |
             v
Implement the minimum required behavior
for the actual Aladdin workload.
```

The project-specific value is not:

```text
another M68000 interpreter
another Z80 interpreter
another FM synthesizer
another generic Genesis emulator
```

The project-specific value is:

```text
one deterministic machine
        +
one authoritative state
        +
replay
        +
snapshot/restore
        +
observability
        +
editable carrier
        +
progressive source replacement
        +
continuous verification
        +
eventual removal of legacy execution
```

External components should make that loop easier.

They must never become a substitute for it.
