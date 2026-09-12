#pragma once

#include <filesystem>
#include <string>

namespace StandaloneProfile
{
// Reads the launcher-compatible profile, or creates it once. Errors never
// substitute a temporary identity or overwrite a conflicting/invalid profile.
bool LoadOrCreate(const std::filesystem::path& runtime, std::string& key, std::string& error);
bool LoadForThisClient(std::string& key, std::string& error);
}
