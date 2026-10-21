# PS4SX2 — Jaguar Cache V1 (experimental)

This branch is built specifically to test cache and thread-topology improvements on a base PS4 using AMD Jaguar CPU cores. The changes have **not** yet been benchmarked on a console. No 60 FPS or 100% speed guarantee.

## Changes to actual C++ runtime

- `pcsx2/MTVU.cpp`: disable nonessential per-command VU diagnostic-history writes by default; full history available with `vm-vu-history` marker.
- `ps4/vm/main.cpp`: shrink MTVU producer/consumer ring effective wrap size from 16 MiB to 1 MiB by default (only an active range of the already allocated buffer; total allocation remains unchanged). Small ring may boost cache locality on Jaguar but increases wraps and could harm compatibility; alternate sizes are selectable.
- `ps4/core/ThreadAffinityPS4.cpp`: EE stays on core 2; GS stays on core 4; VU1 attempts core 5 rather than 3 so EE no longer shares its four-core L2 cache with the VU1 worker. Falls back to the prior VU1 core if the PS4 rejects the affinity change. PS4 policies and actual core placement must be confirmed from logs.

## Reversible options (FTP, empty files)

All markers are files inside `/data/PS4SX2/`. Restart the emulator after adding or removing markers.

| Marker name | Effect |
|---|---|
| `vm-jaguar-affinity-legacy` | Restore former EE=2, VU1=3, GS=4 mapping |
| `vm-no-thread-affinity` | Let the OS schedule all emulation workers |
| `vm-jaguar-ring-legacy` | Restore 16384 KiB VU ring (old behavior) |
| `vm-jaguar-ring-512` | Try a 512 KiB VU ring |
| `vm-jaguar-ring-2048` | Try a 2048 KiB VU ring |
| `vm-vu-history` | Restore per-packet VU diagnostic history; normally disabled |

If multiple ring markers exist, legacy wins, then 512, then 2048. A missing ring marker selects 1024 KiB. Remove markers between benchmark runs. With `vm-jaguar-affinity-legacy` **and** `vm-jaguar-ring-legacy` **and** `vm-vu-history`, this experiment restores those three controls to their prior behavior without downgrading the PKG.

## Recommended Budokai 3 test

1. Preserve the prior tested PKG, your save data and your game image; use identical NTSC game region and the same cutscene/scene.
2. Capture a baseline using the prior PKG at 1× internal resolution, for 90–120 s (ignore first 30 s).
3. Install this PKG and measure the same scene with all Jaguar optimization markers **absent**.
4. If there are missing textures, cutscene corruption or hangs, **first** create `vm-jaguar-ring-legacy` and restart the emulator; if needed create `vm-jaguar-affinity-legacy` as well.
5. Compare `Speed_pct` median and p10 plus `EE_ms`, `GS_ms`, `VU1_ms` with the Python performance lab:

```bash
python3 tools/optimization/ps4_perf_lab.py compare \
  baseline.log jaguar-v1.log --warmup 30 --json jaguar-diff.json
```

6. Repeat 3 times, with equal segments. Do not compare different cinematics or rely only on an instantaneous overlay.

## Important performance and safety notes

- Lower VU ring size and thread placement are **hypotheses**, not measured gains. If the game slows down, use the opt-out markers.
- Keep BIOS, game images, and savedata **out** of GitHub uploads and issue logs.
- `PS2_Hz` and `Speed_pct` represent virtual PS2 cadence; `Game_FPS` may reflect an internal-FPS heuristic rather than genuine game update count.
- The PS4 `-march=btver2`, SSE4/JIT, Fastmem and MTVU paths already existed in this fork; this change does not falsely advertise new CPU features.
- Build success and generated PKG prove compilation only; stability and performance require console testing.
