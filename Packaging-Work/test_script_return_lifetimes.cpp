// Exercises extracted production formatters, msstring, and hashed getter dispatch.
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <algorithm>
#include <cctype>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <map>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

template<class A, class B> auto V_min(A a, B b) { return a < b ? a : b; }
#include "actual_msstring.inc"
using msstringlist = std::vector<msstring>;
struct Vector { float x, y, z; };
#include "actual_formatters.inc"

static void Require(bool ok, const char* message) {
    if (!ok) throw std::runtime_error(message);
}
__declspec(noinline) static void ClobberStack() {
    volatile unsigned char data[16384];
    for (unsigned int i = 0; i < sizeof(data); ++i) data[i] = 0xa5;
}
static void RequireStable(const char* result) {
    ULONG_PTR low = 0, high = 0;
    GetCurrentThreadStackLimits(&low, &high);
    auto address = reinterpret_cast<ULONG_PTR>(result);
    // Check ownership before dereferencing: catches old code without reading dead objects.
    Require(result && !(address >= low && address < high), "returned text points into the current thread stack");
}
static void Check(const char* result, const char* expected) {
    RequireStable(result);
    ClobberStack();
    Require(std::strcmp(result, expected) == 0, "returned text did not survive stack clobber");
}

class CScript {
    using Getter = msstring (CScript::*)(msstring&, msstring&, msstringlist&);
    struct Command {
        Getter function;
        Getter GetFunc() const { return function; }
    };
    msstring Scalar(msstring&, msstring&, msstringlist&) { return RETURN_FLOAT(-27.5f); }
    msstring Position(msstring&, msstring&, msstringlist&) { return VecToString({123.25f, -456.5f, 79.0f}, false); }
    msstring Nested(msstring&, msstring&, msstringlist&) {
        msstring copied = GetVar("vector");
        return copied;
    }
public:
    __declspec(noinline) const char* GetVar(const char* expression) {
        static msstring Return;
        msstring FullName = expression;
        msstring ParserName = expression;
        msstringlist Params;
        const std::map<std::string, Command> getters{
            {"scalar", {&CScript::Scalar}}, {"vector", {&CScript::Position}}, {"nested", {&CScript::Nested}}
        };
        auto iFunc = getters.find(expression);
        Require(iFunc != getters.end(), "unknown fixture getter");
        // Verbatim body of the production CScript::GetVar hashed getter dispatch.
#include "actual_dispatch.inc"
    }
};

int main() {
    try {
        Check(RETURN_FLOAT_PRECISION(-1.25f), "-1.250000");
        Check(RETURN_FLOAT(23.5f), "23.50");
        Check(RETURN_INT(-42), "-42");
        Check(RETURN_VECTOR({1.25f, -2.5f, 3.0f}), "(1.25,-2.50,3.00)");
        Check(VecToString({123.25f, -456.5f, 79.0f}, false), "(123.25,-456.50,79.00)");
        Check(VecToString({123.25f, -456.5f, 79.0f}, true), "(123.25,-456.50)");

        std::vector<const char*> pending;
        for (int i = 0; i < 16; ++i) {
            const char* value = RETURN_INT(100 + i);
            RequireStable(value);
            pending.push_back(value);
        }
        ClobberStack();
        for (int i = 0; i < 16; ++i)
            Require(std::string(pending[i]) == std::to_string(100 + i), "outstanding formatter result overwritten too early");

        const char* vector = VecToString({1, 2, 3}, false);
        const char* scalar = RETURN_FLOAT(2.5f);
        Check(vector, "(1.00,2.00,3.00)");
        Check(scalar, "2.50");
        const char* threadValue = RETURN_INT(777);
        std::thread worker([] { for (int i = 0; i < 64; ++i) RETURN_INT(i); });
        worker.join();
        Check(threadValue, "777");

        CScript script;
        Check(script.GetVar("scalar"), "-27.50");
        Check(script.GetVar("vector"), "(123.25,-456.50,79.00)");
        Check(script.GetVar("nested"), "(123.25,-456.50,79.00)");
        std::cout << "PASS: actual formatters, 16 outstanding results, thread isolation, actual getter dispatch and nested getter lifetime\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
