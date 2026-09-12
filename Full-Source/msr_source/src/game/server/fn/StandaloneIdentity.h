#pragma once
#include <cstdint>
#include <cstring>

namespace StandaloneFN
{
// A launcher-generated 128-bit profile key is portable between private hosts.
// Retain FN's decimal uint64 wire field; the high bit separates private IDs
// from Steam's public individual-account range. No Steam identity is asserted.
inline std::uint64_t AccountId(const char* profile)
{
    if (!profile || std::strlen(profile) != 32) return 0;
    std::uint64_t hash = 14695981039346656037ULL;
    for (int i = 0; i < 32; ++i)
    {
        const unsigned char c = static_cast<unsigned char>(profile[i]);
        if (!((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'))) return 0;
        hash = (hash ^ c) * 1099511628211ULL;
    }
    return hash | 0x8000000000000000ULL;
}
}
