#pragma once

class CBaseEntity;
class CBasePlayer;
struct usercmd_s;

namespace MSRMounts
{
void Init();
void Precache();
void PlayerPreThink(CBasePlayer *player);
void PlayerPostThink(CBasePlayer *player);
void ApplyRestrictions(CBasePlayer *player);
void RecordCommand(CBasePlayer *player, const usercmd_s *command);
bool PlayerUse(CBasePlayer *player);
void Release(CBasePlayer *player, const char *reason);
void MapEnd();
bool HasRider(CBaseEntity *entity);
CBasePlayer *Rider(CBaseEntity *entity);
} // namespace MSRMounts
