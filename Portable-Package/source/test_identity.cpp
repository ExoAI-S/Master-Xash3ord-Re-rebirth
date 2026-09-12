#include "MasterSwordRebirth/src/game/server/fn/StandaloneIdentity.h"
#include <cassert>
#include <cstdio>
#include <string>
#include <unordered_set>
int main()
{
    using StandaloneFN::AccountId;
    assert(AccountId(nullptr) == 0);
    assert(AccountId("") == 0);
    assert(AccountId("ID_LAN") == 0);
    assert(AccountId("STEAM_0:0:7019991") == 0);
    assert(AccountId("0123456789abcdef0123456789abcdeF") == 0);
    assert(AccountId("0123456789abcdef0123456789abcdef;") == 0);
    assert(AccountId("0123456789abcdef0123456789abcdef") == 0x81527c9731f0ff55ULL);
    std::unordered_set<std::uint64_t> ids;
    for (unsigned i = 0; i < 10000; ++i)
    {
        char key[33];
        std::snprintf(key, sizeof(key), "%032x", i);
        auto id = AccountId(key);
        assert(id >= (1ULL << 63));
        assert(ids.insert(id).second);
    }
    puts("Identity tests passed: invalid keys, stable vector, private namespace, 10000 distinct profiles.");
}
