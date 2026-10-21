// SPDX-License-Identifier: GPL-3.0+

#include "ThreadAffinityPS4.h"

#include <atomic>
#include <cstdio>
#include <cstring>
#include <pthread.h>
#include <unistd.h>

// OpenOrbis's public header declares these without parameters. Use the ABI
// verified by DolphinPS4 until the SDK declaration is corrected.
extern "C" void* scePthreadSelf();
extern "C" int scePthreadSetaffinity(void* thread, unsigned long long mask);

namespace PS4ThreadAffinity
{
	static bool IsEnabled()
	{
		static std::atomic<int> enabled{-1};
		int value = enabled.load(std::memory_order_acquire);
		if (value >= 0)
			return value != 0;

		value = access("/data/PS4SX2/vm-no-thread-affinity", F_OK) == 0 ? 0 : 1;
		enabled.store(value, std::memory_order_release);
		return value != 0;
	}

	void PinCurrentThread(const char* role, int core)
	{
		if (!IsEnabled())
		{
			std::printf("PS4 thread affinity: %s left to scheduler (disabled by marker)\n", role);
			std::fflush(stdout);
			return;
		}

		// Jaguar has two four-core L2 groups (0-3 and 4-7). In the original
		// PS4 port EE=2 and VU1=3 compete for the first group's shared L2,
		// while GS=4 sits alone in the second group. Try VU1=5 to put EE
		// on its own L2 group. This is a benchmark hypothesis, not a proven
		// faster layout: users can restore the prior placement with a marker.
		const bool use_legacy = access("/data/PS4SX2/vm-jaguar-affinity-legacy", F_OK) == 0;
		const bool split_vu = !use_legacy && role && std::strcmp(role, "VU1") == 0;
		const int requested_core = split_vu ? 5 : core;
		unsigned long long mask = 1ULL << requested_core;
		int result = scePthreadSetaffinity(scePthreadSelf(), mask);
		// Some console policies restrict CPU affinity. Fall back to the
		// original role's mask rather than leaving an unexpected layout.
		if (result != 0 && requested_core != core)
		{
			mask = 1ULL << core;
			result = scePthreadSetaffinity(scePthreadSelf(), mask);
		}
		std::printf("PS4 Jaguar affinity: %s requested_core=%d applied_mask=0x%llx legacy=%d result=0x%x\n",
			role, requested_core, mask, use_legacy ? 1 : 0, result);
		std::fflush(stdout);
	}
} // namespace PS4ThreadAffinity
