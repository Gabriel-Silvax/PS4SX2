"""Tests for PS4 AudioOut telemetry analysis (no console needed)."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("ps4_audio_diagnostics", Path(__file__).with_name("ps4_audio_diagnostics.py"))
audio = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audio)


class AudioTests(unittest.TestCase):
    def test_cumulative_short_read_delta(self):
        log = "\n".join([
            "PS4 audio output: status=1 buffers=100 pcm_buffers=97 input_short=8 paused=0",
            "PS4 audio queue: min_frames=33 max_frames=2000 refill_pending=3",
            "Performance: seconds=10 Speed_pct=64.0 Game_FPS=38.6",
            "PS4 audio output: status=1 buffers=300 pcm_buffers=280 input_short=18 paused=0",
            "PS4 audio queue: min_frames=0 max_frames=1500 refill_pending=4",
            "Performance: seconds=15 Speed_pct=65.0 Game_FPS=39.0",
            "PS4 audio-recovery affinity: Audio core=5 mask=0x20 result=0x0",
        ])
        result = audio.summarize(audio.parse_log(log)["sessions"][0])
        self.assertEqual(result["buffers_delta"], 200)
        self.assertEqual(result["input_short_delta"], 10)
        self.assertEqual(result["short_input_per_1000_buffers"], 50)
        self.assertEqual(result["min_queue_frames_seen"], 0)
        self.assertEqual(result["median_speed_pct"], 64.5)

    def test_session_boundary_on_counter_reset(self):
        text = "\n".join([
            "PS4 audio output: status=1 buffers=100 pcm_buffers=90 input_short=4 paused=0",
            "PS4 audio output: status=1 buffers=200 pcm_buffers=150 input_short=6 paused=0",
            "PS4 audio output: status=1 buffers=1 pcm_buffers=1 input_short=0 paused=0",
        ])
        self.assertEqual(len(audio.parse_log(text)["sessions"]), 2)

    def test_no_audio_marker(self):
        parsed = audio.parse_log("nonsense")
        self.assertEqual(parsed["sessions"], [])

    def test_single_snapshot_does_not_fake_rate(self):
        parsed = audio.parse_log("PS4 audio output: status=1 buffers=10 pcm_buffers=10 input_short=2 paused=0")
        report = audio.summarize(parsed["sessions"][0])
        self.assertIsNone(report["short_input_per_1000_buffers"])


if __name__ == "__main__":
    unittest.main()
