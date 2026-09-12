// The runner extracts the real light/frameent branches from client/entity.cpp.
// Bounds-checked script parameters and the real Xash enqueue precondition make
// these tests fail on the original out-of-range read and missing-model enqueue.
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

struct msstring : std::string {
    using std::string::string;
    operator const char*() const { return c_str(); }
    bool contains(const char* value) const { return find(value) != npos; }
};
template<class T> struct mslist {
    std::vector<T> values;
    T& operator[](size_t index) { return values.at(index); }
    size_t size() const { return values.size(); }
    T& add(const T& value) { values.push_back(value); return values.back(); }
    void clearitems() { values.clear(); }
    void erase(size_t index) { values.erase(values.begin() + index); }
};
using msstringlist = mslist<msstring>;
struct Vector { float x, y, z; };
struct Color { unsigned char r, g, b; };
struct dlight_t { Vector origin; float radius; Color color; float die; bool dark; };
struct model_s { int marker; };
struct entity_state { int rendermode; Color rendercolor; int renderamt; int modelindex; float starttime; };
struct cl_entity_t { entity_state curstate; model_s* model; Vector origin; };
static const int ET_NORMAL = 0, kRenderTransAdd = 5;
template<class T> void clrmem(T& item) { std::memset(&item, 0, sizeof(item)); }
Vector StringToVec(const msstring& value) {
    Vector result{};
    if (std::sscanf(value.c_str(), "(%f,%f,%f)", &result.x, &result.y, &result.z) != 3)
        throw std::runtime_error("Invalid test vector");
    return result;
}
msstring GetFullResourceName(const msstring& name) { return name; }
static bool dynamicEnabled = true, modelAvailable = true;
static int dlightCalls, elightCalls, visibleCalls, acceptedCalls, callbackCalls;
static int m_gLastLightID;
static dlight_t allocatedLight;
static cl_entity_t lastVisible;
static model_s spriteModel{7};
static cl_entity_t* g_CurrentEnt;
namespace MSCLGlobals { static mslist<cl_entity_t> m_ClModels; }
namespace EngineFunc { const char* CVAR_GetString(const char*) { return dynamicEnabled ? "1" : "0"; } }
struct MockEffects {
    dlight_t* CL_AllocDlight(int) { ++dlightCalls; return &allocatedLight; }
    dlight_t* CL_AllocElight(int) { ++elightCalls; return &allocatedLight; }
};
static MockEffects effects;
struct MockEngine {
    MockEffects* pEfxAPI = &effects;
    float GetClientTime() { return 10; }
    model_s* CL_LoadModel(const msstring&, int* index) { *index = 42; return modelAvailable ? &spriteModel : nullptr; }
    bool CL_CreateVisibleEntity(int, cl_entity_t* entity) {
        ++visibleCalls;
        if (!entity || !entity->model) return false; // Xash CL_AddVisibleEntity.
        lastVisible = *entity;
        ++acceptedCalls;
        return true;
    }
} gEngfuncs;
void RunScriptEventByName(const msstring&) {
    if (!g_CurrentEnt) throw std::runtime_error("No entity during setup callback");
    ++callbackCalls;
    g_CurrentEnt->curstate.renderamt = 128;
}
void SetClEntityProp(cl_entity_t&, msstring&, mslist<msstring*>&) {}
void Execute(msstringlist& Params) {
    if (!Params.size()) return; // The production function's entry guard.
    if (false) {}
#include "actual_effect_branches.inc"
}
msstringlist Args(std::initializer_list<const char*> values) {
    msstringlist result;
    for (const char* value : values) result.add(msstring(value));
    return result;
}
void Check(bool value, const char* message) { if (!value) throw std::runtime_error(message); }
void Reset() {
    dynamicEnabled = modelAvailable = true;
    dlightCalls = elightCalls = visibleCalls = acceptedCalls = callbackCalls = 0;
    clrmem(allocatedLight); clrmem(lastVisible); g_CurrentEnt = nullptr;
    MSCLGlobals::m_ClModels.clearitems();
}
int main() {
    try {
        Reset();
        auto plain = Args({"light","new","(1,2,3)","128","(100,33,253)","2"});
        Execute(plain);
        Check(dlightCalls == 1 && elightCalls == 0 && allocatedLight.radius == 128 && allocatedLight.die == 12 && allocatedLight.color.b == 253, "Six required light arguments");
        for (const char* flag : {"entity", "dark", "entity dark"}) {
            Reset(); auto params = plain; params.add(msstring(flag)); Execute(params);
            Check(elightCalls == (std::strstr(flag,"entity") ? 1 : 0), "Optional entity flag");
            Check(allocatedLight.dark == (std::strstr(flag,"dark") != nullptr), "Optional dark flag");
        }
        for (size_t count = 0; count < 6; ++count) {
            Reset(); auto params = plain; params.values.resize(count); Execute(params);
            Check(dlightCalls + elightCalls == 0, "Too-few light arguments must be refused");
        }
        Reset(); dynamicEnabled = false; Execute(plain);
        Check(dlightCalls + elightCalls == 0, "Disabled dynamic light");
        Reset(); auto frame = Args({"frameent","sprite","3dmflaora.spr","(1,2,3)","setup_sprite_2"}); Execute(frame);
        Check(acceptedCalls == 1 && callbackCalls == 1 && lastVisible.model == &spriteModel && lastVisible.curstate.modelindex == 42 && lastVisible.curstate.renderamt == 128 && lastVisible.origin.z == 3, "Frame sprite fully initialized before enqueue");
        Reset(); modelAvailable = false; Execute(frame);
        Check(visibleCalls == 0 && callbackCalls == 0, "Missing model is not enqueued");
        Reset(); frame.values[1] = "sprite perm"; Execute(frame);
        Check(visibleCalls == 0 && callbackCalls == 1 && MSCLGlobals::m_ClModels.size() == 1, "Permanent model remains deferred");
        std::cout << "PASS: actual light/frameent production branches; strict parameter bounds; required/optional/short/disabled lights; model and callback initialized before Xash enqueue; missing and permanent models.\n";
        return 0;
    } catch (const std::exception& error) { std::cerr << "FAIL: " << error.what() << '\n'; return 1; }
}
