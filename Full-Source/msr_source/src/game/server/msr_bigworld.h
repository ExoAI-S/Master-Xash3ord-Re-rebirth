#pragma once

// True when the server was started with -bigworld (engine large coordinates).
bool MSR_BigWorld();

// Largest usable absolute coordinate on any axis: 4096 normally, 32767 in Big World.
float MSR_WorldExtent();

// One "MSR: memory" line in the server log: private bytes, address space in use and the largest
// free block. The server is a 32-bit process; the free block shrinking is what runs it out of memory.
void MSR_LogMemory(const char *when);
