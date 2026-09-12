#pragma once

class CBasePlayer;
void EncounterDirector_Init();
void EncounterDirector_MapStart();
void EncounterDirector_Frame();
void EncounterDirector_Disconnect(CBasePlayer *player);
bool EncounterDirector_Command(CBasePlayer *player, const char *command);
