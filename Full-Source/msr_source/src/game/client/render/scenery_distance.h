#pragma once

struct cl_entity_s;
void MSRSceneryDistanceInit();

// Draw-only state: no entity, networking, collision or animation mutation.
class MSRSceneryDrawScope
{
public:
    MSRSceneryDrawScope(const cl_entity_s* entity, int flags);
    ~MSRSceneryDrawScope();
    bool Culled() const { return culled; }
    MSRSceneryDrawScope(const MSRSceneryDrawScope&) = delete;
    MSRSceneryDrawScope& operator=(const MSRSceneryDrawScope&) = delete;
private:
    bool culled = false;
    bool stippled = false;
};
