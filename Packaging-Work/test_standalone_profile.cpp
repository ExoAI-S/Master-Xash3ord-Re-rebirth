#include "standalone_profile.h"
#include <windows.h>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <thread>

namespace fs = std::filesystem;
static int checks = 0;
static void Require(bool result, const char* message)
{
    if (!result) throw std::runtime_error(message);
    ++checks;
}
static void Write(const fs::path& file, const std::string& content)
{
    std::ofstream output(file, std::ios::binary);
    output << content;
}
static std::string Read(const fs::path& file)
{
    std::ifstream input(file, std::ios::binary);
    return std::string(std::istreambuf_iterator<char>(input), {});
}
static std::string Json(const std::string& key)
{
    return "{\"profile_key\":\"" + key + "\"}";
}
int main()
{
    try
    {
        const fs::path root = fs::temp_directory_path() / (L"msr-profile-test-" + std::to_wstring(GetCurrentProcessId()) + L"-" + std::to_wstring(GetTickCount64()));
        if (fs::exists(root)) throw std::runtime_error("Test fixture already exists");
        const auto enhanced = root / L"Portable-Package";
        const auto stable = root / L"Stable-Base";
        fs::create_directories(enhanced);
        fs::create_directories(stable);
        const auto first = enhanced / L"player-profile.json";
        const auto second = stable / L"player-profile.json";
        std::string key, other, error;

        Require(StandaloneProfile::LoadOrCreate(enhanced, key, error), "Fresh profile creation failed");
        Require(key.size() == 32 && key.find_first_not_of("0123456789abcdef") == std::string::npos, "Generated key has wrong format");
        const auto firstOriginal = Read(first);
        Require(StandaloneProfile::LoadOrCreate(enhanced, other, error) && other == key, "Repeat launch changed identity");
        Require(Read(first) == firstOriginal, "Repeat launch rewrote profile");
        Require(StandaloneProfile::LoadOrCreate(stable, other, error) && other == key, "Sibling launch did not reuse identity");

        const std::string conflicting(32, key == std::string(32, 'a') ? 'b' : 'a');
        Write(second, Json(conflicting));
        const auto secondConflict = Read(second);
        Require(!StandaloneProfile::LoadOrCreate(enhanced, other, error) && other.empty(), "Conflicting profiles were accepted");
        Require(Read(first) == firstOriginal && Read(second) == secondConflict, "Conflict overwrote a profile");

        for (const auto& malformed : {std::string("{broken"), Json(std::string(32, 'A')), std::string("{\"profile_key\":42}"),
            std::string("{\"profile_key\":\"") + key + "\",\"profile_key\":\"" + key + "\"}"})
        {
            Write(second, malformed);
            Require(!StandaloneProfile::LoadOrCreate(enhanced, other, error), "Malformed sibling was accepted");
            Require(Read(second) == malformed && Read(first) == firstOriginal, "Malformed profile overwritten");
        }

        Write(second, "\xef\xbb\xbf{\"profile_key\":\"" + key + "\",\"note\":\"preserved metadata\"}\r\n");
        const auto withMetadata = Read(second);
        Require(StandaloneProfile::LoadOrCreate(stable, other, error) && other == key, "UTF-8 BOM or metadata rejected");
        Require(Read(second) == withMetadata, "Existing metadata rewritten");

        HANDLE held = CreateFileW(first.c_str(), GENERIC_READ, 0, nullptr, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
        Require(held != INVALID_HANDLE_VALUE, "Could not prepare sharing violation test");
        std::thread release([held]() { Sleep(100); CloseHandle(held); });
        bool afterSharingViolation = StandaloneProfile::LoadOrCreate(enhanced, other, error);
        release.join();
        Require(afterSharingViolation && other == key, "Brief sharing violation was not retried");

        const auto race = root / L"race";
        fs::create_directories(race / L"Portable-Package");
        fs::create_directories(race / L"Stable-Base");
        std::string racedA, racedB, errorA, errorB;
        bool resultA = false, resultB = false;
        std::thread launchA([&]() { resultA = StandaloneProfile::LoadOrCreate(race / L"Portable-Package", racedA, errorA); });
        std::thread launchB([&]() { resultB = StandaloneProfile::LoadOrCreate(race / L"Stable-Base", racedB, errorB); });
        launchA.join(); launchB.join();
        Require(resultA && resultB && racedA == racedB, "Concurrent version launches split identities");
        // Keep synthetic fixtures for failure investigation; never touch game profiles.
        std::cout << "PASS: " << checks << " standalone profile checks\n";
        return 0;
    }
    catch (const std::exception& exception)
    {
        std::cerr << "FAIL: " << exception.what() << '\n';
        return 1;
    }
}
