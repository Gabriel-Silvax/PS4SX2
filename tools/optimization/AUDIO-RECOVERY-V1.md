# PS4SX2 Audio Recovery V1 — base PS4 Jaguar

**Experimental build; audio quality and performance are not verified on the actual console yet.**

## Confirmed source-level regression risk

- In Jaguar Cache V1, `PS4ThreadAffinity::PinCurrentThread("VU1", 3)` was overridden to pin VU1 to **core 5**.
- `PS4AudioStream::Run` already calls `PS4ThreadAffinity::PinCurrentThread("Audio", 5)`. That put both CPU-heavy VU1 and real-time AudioOut on core 5. It can starve AudioOut of scheduling time and lead to crackling, but we still need PS4 logs to establish its impact.
- The 1 MiB MTVU ring was also a speculative cache experiment. It increases wrap frequency and may hurt games that stream a lot of VU commands.

## C++ corrections in this branch

1. Restore the dedicated pinned roles: EE=2; VU1=3; GS=4; AudioOut=5. Existing marker `vm-no-thread-affinity` still lets the OS decide; inspect logs for any affinity API error.
2. Restore a 16 MiB MTVU ring by default. Keep *opt-in* 512 KiB, 1 MiB and 2 MiB ring experiments for future benchmark tests.
3. Keep unnecessary per-packet VU diagnostic history off by default from Jaguar V1, with `vm-vu-history` available for diagnostics.
4. Keep the existing audio output path and TimeStretch parameters unchanged until we have A/B comparison logs. TimeStretch at 60-65% emulation speed can still sound bad; this is not solely a scheduling issue.

## Reversible control files

Create zero-byte marker files using FTP in `/data/PS4SX2/` and restart the emulator:

| Marker | Effect |
|---|---|
| `vm-no-thread-affinity` | Let OS schedule all worker threads; experiment only |
| `vm-jaguar-ring-1024` | Try the prior 1 MiB ring |
| `vm-jaguar-ring-512` | Try 512 KiB |
| `vm-jaguar-ring-2048` | Try 2 MiB |
| `vm-jaguar-ring-legacy` | Force original 16 MiB ring even when smaller markers exist |
| `vm-audio-legacy-stretch` | Try default-like 50ms audio buffer and 30/20/10ms TimeStretch values |
| `vm-vu-history` | Re-enable detailed VU packet tracing (diagnostics only; adds overhead) |

The old marker `vm-jaguar-affinity-legacy` from Jaguar V1 is no longer needed here; the old CPU placement is the default again.

## A/B procedure

1. Back up PS4SX2 files/settings and previous PKG.
2. Test Budokai 3 at 1x using the same disc region and cutscene, for 90-120 seconds per version.
3. First try your existing Jaguar V1 PKG with empty `vm-jaguar-affinity-legacy` and `vm-jaguar-ring-legacy` marker files: this restores the two main experiments *without* installing a new PKG.
4. Install Audio Recovery V1 and repeat the cutscene without optional markers. Do not promise an FPS increase: the goal is fewer audio glitches and no regression in game speed.
5. Compare performance with `tools/optimization/ps4_perf_lab.py`; compare audio counters with:

```bash
python3 tools/optimization/ps4_audio_diagnostics.py original.log recovery.log
```

`input_short` measures the number of audio reads that lacked enough samples. It may increase when the *game itself* runs slowly, even when AudioOut scheduling is fine. Correlate the short-read rate with speed and queue minimum, and listen for clipping, stutter, pitch warping and lip-sync.

## Investigation still needed

- Inspect whether the AudioOut worker is being preempted or the source (SPU2) is simply producing data slower than playback. Check `PS4 audio output`, `PS4 audio queue`, and `PS4 audio signal` log lines.
- Do not blindly add `AsyncMix`: this PCSX2 snapshot only has `Disabled` and `TimeStretch` SPU2 synchronization modes (`pcsx2/Pcsx2Config.cpp`). Historical guides describing AsyncMix do not match this build.
- Investigate whether EE, VU1, or GS is the dominant *CPU-time* cost from consistent profiles; measured frame milliseconds from different parallel threads must not be summed.
