#pragma once

#include "msr_encounter_policy.h"

class CMSMonster;
typedef struct KeyValueData_s KeyValueData;

// Server-only opt-in encounter adapter. Legacy actors are never registered here.
namespace MSREncounters
{
void Init();
void ResetMap();
void MapEnd();
void Frame();
void Request(); // Encounter=1 parsed on a controller in this map generation.
bool TemplateKeyValue(CMSMonster* actor, KeyValueData* data);
bool ConsumeDescriptor(CMSMonster* actor, MSREncounterPolicy::Descriptor& descriptor);
void AcceptedDamage(CMSMonster* actor, double amount);
void AcceptedCredit(CMSMonster* actor, double amount);
void InitializeStatsLedger(CMSMonster* actor); // Only newly allocated managed NPC bookkeeping.
void ObservedAttack(CMSMonster* actor);
void OrdinaryDeath(CMSMonster* actor);
enum class Lifecycle { NativeXPDispatch, PredeathDispatch, DeathDispatch, DropAllCall };
void ObserveLifecycle(CMSMonster* actor, Lifecycle event);
bool RetainRegion(int region);
}
