# Frozen historical evidence

This report preserves ROM mapping, qualification, and recovery decisions at its source freeze. It is not current operating guidance: use the immutable cold-start input-history workflow in [../history.md](../../common/history-and-replay.md). Current commands do not promise to load legacy replay or snapshot artifacts referenced below.

# Upper variant dispatcher callback `1B7262`

`1B7262..1B728C` compares `FFEFE2` with `0x3939`, returns through its saved
caller word on equality, and otherwise composes the established `1B5266`
upper allocator. A successful record receives type `0x3A`, script `0x122BD8`,
and `A5+0x29 = 1`; allocation exhaustion returns directly.

The callback has 51 recorded direct entries. Four original snapshots cover both
saved returns `1AE46E` and `1AE4EA` and first/second allocator slots (862/55
and 902/59). Cap, exhaustion, aliases and coordinate carry are original-ROM
synthetic controls. The boundary preserves cap/exhaustion incoming X and the
common tail's final Y-coordinate addition supplies X for successful allocation.

It reuses live-RAM allocator/initializer/placement semantics, planning views,
`AtomicPlan`, and the ordinary return witness/edit/audit tools. No new machine
seam, continuation, registry, or native interface is introduced.

Frozen evidence: `artifacts/grinding/terra/upper-variant/final-suite.xml`
contains 1,196 passing tests in 55.951 seconds. Both strict recorded-return
witnesses pass full state/frame/PCM, 150 native future instructions and fresh
restore at `witness-1AE46E/report.json` and `witness-1AE4EA/report.json`. The
semantic type mutation edit check passes without rebuilding at
`edit-loop/result.json`. `final-replay-audit.json` binds all six explicit
recordings to current source and `build/libaladdin_native.dll`.
