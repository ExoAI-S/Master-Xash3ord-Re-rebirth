#include "scenery_distance_policy.h"
#include "hud.h"
#include "cl_util.h"
#include "const.h"
#include "com_model.h"
#include "studio.h"
#include "cl_entity.h"
#include "r_studioint.h"
#include "studio_util.h"
#include "scenery_distance.h"
#ifdef _WIN32
#include <windows.h>
#endif
#include <GL/gl.h>

extern engine_studio_api_t IEngineStudio;

namespace
{
namespace P = MSRSceneryPolicy;
cvar_t* distanceScale = nullptr;
struct Counts { int tested = 0, full = 0, fading = 0, culled = 0; };
Counts counts[6];
int counterFrame = -1;

void Stats()
{
    const char* names[] = {"other", "grass", "bush", "rock", "tree", "detail"};
    gEngfuncs.Con_Printf("MS_SCENERY distance=%.2f frame=%d (studio submissions, including extra views)\n",
        distanceScale ? distanceScale->value : 0, counterFrame);
    for (int i = 1; i < 6; ++i)
        gEngfuncs.Con_Printf("MS_SCENERY %s tested=%d full=%d fading=%d culled=%d\n",
            names[i], counts[i].tested, counts[i].full, counts[i].fading, counts[i].culled);
}

bool WorldBounds(const cl_entity_t& entity, float mins[3], float maxs[3])
{
    // These exact assets contain static decoration with conservative model
    // bounds. Include sequence bounds too, so wind animation stays inside.
    float localMin[3], localMax[3];
    for (int axis = 0; axis < 3; ++axis)
    {
        localMin[axis] = entity.model->mins[axis];
        localMax[axis] = entity.model->maxs[axis];
    }
    auto* header = static_cast<studiohdr_t*>(IEngineStudio.Mod_Extradata(entity.model));
    if (!header || entity.curstate.sequence < 0 || entity.curstate.sequence >= header->numseq)
        return false;
    auto* sequence = reinterpret_cast<mstudioseqdesc_t*>(reinterpret_cast<byte*>(header) + header->seqindex)
        + entity.curstate.sequence;
    for (int axis = 0; axis < 3; ++axis)
    {
        if (sequence->bbmin[axis] < localMin[axis]) localMin[axis] = sequence->bbmin[axis];
        if (sequence->bbmax[axis] > localMax[axis]) localMax[axis] = sequence->bbmax[axis];
        if (!std::isfinite(localMin[axis]) || !std::isfinite(localMax[axis]) || localMin[axis] > localMax[axis]
            || !std::isfinite(entity.origin[axis]) || !std::isfinite(entity.angles[axis])) return false;
    }
    const float scale = entity.curstate.scale == 0 ? 1.0f : entity.curstate.scale;
    if (!std::isfinite(scale) || scale <= 0) return false;
    Vector angles = entity.angles;
    angles.x = -angles.x; // Same convention as StudioSetUpTransform.
    float matrix[3][4];
    AngleMatrix(angles, matrix);
    for (int corner = 0; corner < 8; ++corner)
    {
        float point[3];
        for (int axis = 0; axis < 3; ++axis)
            point[axis] = ((corner & (1 << axis)) ? localMax[axis] : localMin[axis]) * scale;
        for (int axis = 0; axis < 3; ++axis)
        {
            const float transformed = entity.origin[axis] + matrix[axis][0] * point[0]
                + matrix[axis][1] * point[1] + matrix[axis][2] * point[2];
            if (!std::isfinite(transformed)) return false;
            if (corner == 0 || transformed < mins[axis]) mins[axis] = transformed;
            if (corner == 0 || transformed > maxs[axis]) maxs[axis] = transformed;
        }
    }
    return true;
}
}

void MSRSceneryDistanceInit()
{
    distanceScale = gEngfuncs.pfnRegisterVariable("ms_scenery_distance", "1", FCVAR_ARCHIVE);
    gEngfuncs.pfnAddCommand("ms_scenery_stats", Stats);
}

MSRSceneryDrawScope::MSRSceneryDrawScope(const cl_entity_t* entity, int flags)
{
    if (!(flags & STUDIO_RENDER) || !entity || !entity->model || entity->player
        || entity->model->type != mod_studio || entity->curstate.movetype != MOVETYPE_NONE
        || entity->curstate.solid != SOLID_NOT || entity->curstate.owner != 0
        || entity->curstate.aiment != 0 || entity->curstate.rendermode != kRenderNormal) return;
    const P::Kind kind = P::Classify(entity->model->name);
    if (kind == P::Kind::None) return;

    int frame = 0;
    double current = 0, previous = 0;
    IEngineStudio.GetTimes(&frame, &current, &previous);
    if (frame != counterFrame)
    {
        for (auto& count : counts) count = Counts{};
        counterFrame = frame;
    }
    Counts& count = counts[static_cast<int>(kind)];
    ++count.tested;
    const float scale = P::DistanceScale(distanceScale ? distanceScale->value : 0);
    float mins[3], maxs[3], origin[3], up[3], right[3], forward[3];
    if (scale <= 0 || !WorldBounds(*entity, mins, maxs)) { ++count.full; return; }
    // Query the active render view here. HUD_AddEntity runs before the current
    // camera is computed, so filtering there can pop near scenery on turns.
    IEngineStudio.GetViewInfo(origin, up, right, forward);
    const float alpha = P::VisibilityAlpha(kind, origin, mins, maxs, scale);
    if (alpha <= 0) { culled = true; ++count.culled; return; }
    if (alpha >= 1 || !IEngineStudio.IsHardware()) { ++count.full; return; }
    ++count.fading;
    unsigned char mask[128];
    P::BuildStippleMask(alpha, mask);
    // Coverage fading keeps the normal opaque/masked material and depth path,
    // rather than making large grass sectors translucent sorting problems.
    glPushAttrib(GL_ENABLE_BIT | GL_POLYGON_STIPPLE_BIT);
    glPushClientAttrib(GL_CLIENT_PIXEL_STORE_BIT);
    glPixelStorei(GL_UNPACK_ALIGNMENT, 1);
    glPixelStorei(GL_UNPACK_LSB_FIRST, GL_FALSE);
    glPixelStorei(GL_UNPACK_SWAP_BYTES, GL_FALSE);
    glPixelStorei(GL_UNPACK_ROW_LENGTH, 0);
    glPixelStorei(GL_UNPACK_SKIP_ROWS, 0);
    glPixelStorei(GL_UNPACK_SKIP_PIXELS, 0);
    glPolygonStipple(mask);
    glPopClientAttrib();
    glEnable(GL_POLYGON_STIPPLE);
    stippled = true;
}

MSRSceneryDrawScope::~MSRSceneryDrawScope()
{
    if (stippled) glPopAttrib();
}
