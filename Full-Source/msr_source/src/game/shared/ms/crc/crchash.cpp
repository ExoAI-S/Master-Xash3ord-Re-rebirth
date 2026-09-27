#include "checksum_crc.h"
#include "crchash.h"

#include <fstream>

// Hashes the file in 16 KB pieces. Reading it whole into one buffer needed 55 MB of contiguous
// address space for the merged Big World map; on a 32-bit server fragmented by earlier map loads
// that allocation failed, the checksum came back 0 and FN rejected the map. CRC32_ProcessBuffer
// carries its running value between calls, so the result equals one call over the whole file.
static unsigned int ComputeCRC32ForFile(const char* path)
{
	if (!path || !path[0])
		return 0;

	std::ifstream file(path, std::ios_base::in | std::ios_base::binary);
	if (!file.is_open())
		return 0;

	char buffer[16 * 1024];
	VCRC32_t crc;
	CRC32::CRC32_Init(&crc);
	for (;;)
	{
		file.read(buffer, sizeof(buffer));
		const std::streamsize got = file.gcount();
		if (got > 0)
			CRC32::CRC32_ProcessBuffer(&crc, buffer, (int)got);
		if (!file) // end of file, or a read error
			break;
	}
	if (file.bad())
		return 0;

	CRC32::CRC32_Final(&crc);
	return crc;
}

bool MatchFileCheckSum(const char* FilePath, unsigned int CheckSum)
{
	return (ComputeCRC32ForFile(FilePath) == CheckSum);
}

unsigned int GetFileCheckSum(const char* FilePath)
{
	return ComputeCRC32ForFile(FilePath);
}
