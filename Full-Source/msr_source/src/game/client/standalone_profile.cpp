#include "standalone_profile.h"

#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#include <bcrypt.h>
#include <json.hpp>
#include <array>
#include <stdexcept>
#include <vector>

namespace StandaloneProfile
{
namespace
{
struct Handle
{
    HANDLE value;
    explicit Handle(HANDLE handle) : value(handle) {}
    ~Handle() { if (value != INVALID_HANDLE_VALUE) CloseHandle(value); }
    Handle(const Handle&) = delete;
    Handle& operator=(const Handle&) = delete;
};

bool Missing(DWORD error)
{
    return error == ERROR_FILE_NOT_FOUND || error == ERROR_PATH_NOT_FOUND;
}

HANDLE OpenRetry(const std::filesystem::path& path, DWORD access, DWORD sharing, DWORD creation)
{
    for (int attempt = 0; ; ++attempt)
    {
        HANDLE result = CreateFileW(path.c_str(), access, sharing, nullptr, creation, FILE_ATTRIBUTE_NORMAL, nullptr);
        if (result != INVALID_HANDLE_VALUE) return result;
        DWORD code = GetLastError();
        if ((code != ERROR_SHARING_VIOLATION && code != ERROR_LOCK_VIOLATION) || attempt >= 100)
        {
            SetLastError(code);
            return INVALID_HANDLE_VALUE;
        }
        Sleep(20);
    }
}

bool ReadKey(const std::filesystem::path& path, std::string& key)
{
    Handle file(OpenRetry(path, GENERIC_READ, FILE_SHARE_READ, OPEN_EXISTING));
    if (file.value == INVALID_HANDLE_VALUE)
    {
        if (Missing(GetLastError())) return false;
        throw std::runtime_error("Cannot read player-profile.json. Close other launchers and check the extracted folder is writable.");
    }
    LARGE_INTEGER size{};
    if (!GetFileSizeEx(file.value, &size) || size.QuadPart < 2 || size.QuadPart > 16384)
        throw std::runtime_error("Invalid player-profile.json size. Restore its backup; the file was not changed.");
    std::string text(static_cast<size_t>(size.QuadPart), '\0');
    DWORD read = 0;
    if (!ReadFile(file.value, text.data(), static_cast<DWORD>(text.size()), &read, nullptr) || read != text.size())
        throw std::runtime_error("Cannot read all of player-profile.json. The file was not changed.");
    try
    {
        // Reject duplicate identity fields rather than silently accepting the last.
        int profileFields = 0;
        auto parsed = nlohmann::json::parse(text, [&profileFields](int depth, nlohmann::json::parse_event_t event, nlohmann::json& value)
        {
            if (depth == 1 && event == nlohmann::json::parse_event_t::key && value == "profile_key") ++profileFields;
            return true;
        });
        if (!parsed.is_object() || profileFields != 1 || !parsed.contains("profile_key") || !parsed["profile_key"].is_string())
            throw std::runtime_error("invalid profile object");
        key = parsed["profile_key"].get<std::string>();
        if (key.size() != 32 || key.find_first_not_of("0123456789abcdef") != std::string::npos)
            throw std::runtime_error("invalid profile key");
    }
    catch (...)
    {
        throw std::runtime_error("Invalid player-profile.json. Restore its backup; the file was not changed.");
    }
    return true;
}

std::string RandomKey()
{
    std::array<unsigned char, 16> bytes{};
    if (BCryptGenRandom(nullptr, bytes.data(), static_cast<ULONG>(bytes.size()), BCRYPT_USE_SYSTEM_PREFERRED_RNG) < 0)
        throw std::runtime_error("Windows could not generate a secure player identity.");
    const char hex[] = "0123456789abcdef";
    std::string key;
    for (auto byte : bytes) { key += hex[byte >> 4]; key += hex[byte & 15]; }
    return key;
}

void CreateProfile(const std::filesystem::path& path, const std::string& key)
{
    Handle file(OpenRetry(path, GENERIC_WRITE, 0, CREATE_NEW));
    if (file.value == INVALID_HANDLE_VALUE)
        throw std::runtime_error("Cannot create player-profile.json. Close other launchers and check the extracted folder is writable.");
    const std::string contents = "{\"profile_key\":\"" + key + "\"}\r\n";
    DWORD written = 0;
    if (!WriteFile(file.value, contents.data(), static_cast<DWORD>(contents.size()), &written, nullptr) ||
        written != contents.size() || !FlushFileBuffers(file.value))
        throw std::runtime_error("Cannot save player-profile.json completely. Check free disk space before starting the game again.");
}
}

bool LoadOrCreate(const std::filesystem::path& runtime, std::string& key, std::string& error)
{
    key.clear();
    error.clear();
    try
    {
        const auto version = runtime.filename().wstring();
        const bool paired = version == L"Portable-Package" || version == L"Stable-Base";
        const auto bundle = paired ? runtime.parent_path() : runtime;
        Handle lock(OpenRetry(bundle / L".player-profile.lock", GENERIC_READ | GENERIC_WRITE, 0, OPEN_ALWAYS));
        if (lock.value == INVALID_HANDLE_VALUE)
            throw std::runtime_error("Cannot lock the player profile. Close other launchers and extract the entire ZIP to a writable folder.");

        std::string currentKey, siblingKey;
        bool currentExists = ReadKey(runtime / L"player-profile.json", currentKey);
        bool siblingExists = paired && ReadKey(bundle / (version == L"Portable-Package" ? L"Stable-Base" : L"Portable-Package") / L"player-profile.json", siblingKey);
        if (currentExists && siblingExists && currentKey != siblingKey)
            throw std::runtime_error("Stable and Enhanced have different player identities. Keep both player-profile.json files and restore the intended identity. Neither file was changed.");
        key = currentExists ? currentKey : (siblingExists ? siblingKey : RandomKey());
        if (!currentExists) CreateProfile(runtime / L"player-profile.json", key);
        return true;
    }
    catch (const std::exception& exception)
    {
        key.clear();
        error = exception.what();
        return false;
    }
}

bool LoadForThisClient(std::string& key, std::string& error)
{
    HMODULE module = nullptr;
    if (!GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
        reinterpret_cast<LPCWSTR>(&LoadForThisClient), &module))
    {
        error = "Cannot locate the MSR client library.";
        return false;
    }
    std::vector<wchar_t> buffer(32768);
    DWORD length = GetModuleFileNameW(module, buffer.data(), static_cast<DWORD>(buffer.size()));
    if (!length || length >= buffer.size())
    {
        error = "Cannot locate the extracted MSR game folder.";
        return false;
    }
    const std::filesystem::path client(std::wstring(buffer.data(), length));
    // <runtime>/game/msr/cl_dlls/client.dll; independent of process working directory.
    const auto clDlls = client.parent_path();
    if (clDlls.filename() != L"cl_dlls" || clDlls.parent_path().filename() != L"msr" || clDlls.parent_path().parent_path().filename() != L"game")
    {
        error = "Unexpected MSR folder layout. Extract the entire package before starting the game.";
        return false;
    }
    return LoadOrCreate(clDlls.parent_path().parent_path().parent_path(), key, error);
}
}
#else
namespace StandaloneProfile
{
bool LoadOrCreate(const std::filesystem::path&, std::string& key, std::string& error)
{
    key.clear();
    error = "Automatic standalone player profile setup is available on Windows only. Use the platform launcher.";
    return false;
}
bool LoadForThisClient(std::string& key, std::string& error) { return LoadOrCreate({}, key, error); }
}
#endif
