// Opt-in Xash3D "Big World" support.
//
// Starting the server with -bigworld asks the engine for
// ENGINE_WRITE_LARGE_COORD: engine WRITE_COORD then carries whole units up to
// +-32767 instead of eighths up to +-4096, so maps can use a 65536-unit world.
// Entity origins additionally need the widened delta.lst shipped with the big
// world. Without -bigworld nothing changes.

#include "extdll.h"
#include "util.h"
#include "msr_bigworld.h"

#include <cstring>
#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <psapi.h>
#endif

namespace
{
constexpr int kPhysicsInterfaceVersion = 6;		 // SV_PHYSICS_INTERFACE_VERSION (engine/physint.h)
constexpr unsigned int kEngineWriteLargeCoord = 1u << 0; // ENGINE_WRITE_LARGE_COORD (common/enginefeatures.h)

// Layout of physics_interface_t for SV_PHYSICS_INTERFACE_VERSION 6 (Xash3D FWGS engine/physint.h).
// Only SV_CheckFeatures is provided; the engine null-checks every callback.
struct PhysicsInterfaceV6
{
	int version;
	void *SV_CreateEntity;
	void *SV_PhysicsEntity;
	void *SV_LoadEntities;
	void *SV_UpdatePlayerBaseVelocity;
	void *SV_AllowSaveGame;
	void *SV_TriggerTouch;
	unsigned int (*SV_CheckFeatures)(void);
	void *DrawDebugTriangles;
	void *DrawNormalTriangles;
	void *DrawOrthoTriangles;
	void *ClipMoveToEntity;
	void *ClipPMoveToEntity;
	void *SV_EndFrame;
	void *pfnPrepWorldFrame;
	void *pfnCreateEntitiesInRestoreList;
	void *pfnAllocString;
	void *pfnMakeString;
	void *pfnGetString;
	void *pfnRestoreDecal;
	void *PM_PlayerTouch;
	void *Mod_ProcessUserData;
	void *SV_HullForBsp;
	void *SV_PlayerThink;
	void *pfnVoiceData;
};

bool g_BigWorld = false;

// MSR's enginefuncs_t predates pfnCheckParm; the DLL shares the engine's process.
bool CommandLineHas(const char *parm)
{
#ifdef _WIN32
	const char *cmd = GetCommandLineA();
	const size_t len = strlen(parm);
	for (const char *p = cmd; (p = strstr(p, parm)) != NULL; p += len)
	{
		const bool starts = (p == cmd || p[-1] == ' ' || p[-1] == '"');
		const bool ends = (p[len] == '\0' || p[len] == ' ' || p[len] == '"');
		if (starts && ends)
			return true;
	}
#endif
	return false;
}

// The Big World installer puts msr/bigworld.enable next to the merged map, so servers the
// launcher starts (which pass no -bigworld) get it too. The engine asks once, at DLL load.
bool BigWorldInstalled()
{
	int length = 0;
	byte *pFile = LOAD_FILE_FOR_ME((char *)"bigworld.enable", &length);
	if (!pFile)
		return false;
	FREE_FILE(pFile);
	return true;
}

unsigned int MSR_CheckFeatures(void)
{
	const bool fromCommandLine = CommandLineHas("-bigworld");
	g_BigWorld = fromCommandLine || BigWorldInstalled();
	if (g_BigWorld)
		ALERT(at_console, "MSR: Big World enabled (large coordinates, +-32767 units; %s)\n", fromCommandLine ? "-bigworld" : "bigworld.enable");
	return g_BigWorld ? kEngineWriteLargeCoord : 0;
}
} // namespace

bool MSR_BigWorld()
{
	return g_BigWorld;
}

float MSR_WorldExtent()
{
	return g_BigWorld ? 32767.0f : 4096.0f;
}

void MSR_LogMemory(const char *when)
{
#ifdef _WIN32
	PROCESS_MEMORY_COUNTERS_EX counters = {};
	counters.cb = sizeof(counters);
	K32GetProcessMemoryInfo(GetCurrentProcess(), (PROCESS_MEMORY_COUNTERS *)&counters, sizeof(counters));

	SYSTEM_INFO info;
	GetSystemInfo(&info);
	size_t used = 0, largestFree = 0;
	MEMORY_BASIC_INFORMATION region;
	for (const char *p = (const char *)info.lpMinimumApplicationAddress; p < (const char *)info.lpMaximumApplicationAddress;
		 p = (const char *)region.BaseAddress + region.RegionSize)
	{
		if (VirtualQuery(p, &region, sizeof(region)) != sizeof(region))
			break;
		if (region.State == MEM_FREE)
			largestFree = region.RegionSize > largestFree ? region.RegionSize : largestFree;
		else
			used += region.RegionSize;
	}
	const double MB = 1024.0 * 1024.0;
	const double total = ((const char *)info.lpMaximumApplicationAddress - (const char *)info.lpMinimumApplicationAddress) / MB;
	g_engfuncs.pfnServerPrint(UTIL_VarArgs("MSR: memory (%s): private %.0f MB, address space used %.0f of %.0f MB, largest free block %.0f MB\n",
		when, counters.PrivateUsage / MB, used / MB, total, largestFree / MB));
#endif
}

// cdecl, matching the engine's PHYSICAPI typedef (the server's DLLEXPORT macro is __stdcall).
extern "C" __declspec(dllexport) int Server_GetPhysicsInterface(int iVersion, void *pfuncsFromEngine, PhysicsInterfaceV6 *pFunctionTable)
{
	if (iVersion != kPhysicsInterfaceVersion || !pFunctionTable)
		return FALSE;

	memset(pFunctionTable, 0, sizeof(*pFunctionTable));
	pFunctionTable->version = kPhysicsInterfaceVersion;
	pFunctionTable->SV_CheckFeatures = MSR_CheckFeatures;
	return TRUE;
}
