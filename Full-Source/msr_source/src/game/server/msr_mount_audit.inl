// Native Debug-only audit commands. They exercise the real entities and hulls.
// Use an isolated realm with synthetic characters; death/spawn alter that realm.
#if !defined(NDEBUG)
void AuditCheck(const char *name, bool passed)
{
    ALERT(at_console, "Stable audit: %s %s.\n", name, passed ? "PASS" : "FAIL");
}
CMSRHorse *AuditLoan(CBasePlayer *player)
{
    for (int i = gpGlobals->maxClients + 1; i < gpGlobals->maxEntities; ++i)
    {
        edict_t *ed = INDEXENT(i);
        if (!UTIL_IsValidEntity(ed) || !ed->pvPrivateData) continue;
        CMSRHorse *horse = Horse(CBaseEntity::Instance(ed));
        if (horse && horse->m_Assigned && horse->GetCustomer() == player) return horse;
    }
    return NULL;
}
int AuditLoanCount(CBasePlayer *player)
{
    int count = 0;
    for (int i = gpGlobals->maxClients + 1; i < gpGlobals->maxEntities; ++i)
    {
        edict_t *ed = INDEXENT(i);
        if (!UTIL_IsValidEntity(ed) || !ed->pvPrivateData) continue;
        CMSRHorse *horse = Horse(CBaseEntity::Instance(ed));
        if (horse && horse->m_Assigned && horse->GetCustomer() == player) ++count;
    }
    return count;
}
void AuditRemove(CBaseEntity *entity)
{
    if (!entity) return;
    entity->Deactivate();
    UTIL_Remove(entity);
    REMOVE_ENTITY(entity->edict());
}
bool AuditRide(CBasePlayer *player, CMSRHorse *horse)
{
    if (!horse) return false;
    const Vector wanted = horse->pev->origin + Vector(-48,0,-player->pev->mins.z);
    TraceResult clear;
    UTIL_TraceHull(wanted,wanted,dont_ignore_monsters,human_hull,player->edict(),&clear);
    if (clear.fStartSolid || clear.fAllSolid) return false;
    UTIL_SetOrigin(player->pev,wanted);
    SetBits(player->pev->flags,FL_ONGROUND);
    return horse->TryMount(player,true);
}
void StableAuditCommand()
{
    if (!Cheats()) return;
    CBasePlayer *player = SlotPlayer();
    const char *phase = CMD_ARGC() > 2 ? CMD_ARGV(2) : "state";
    if (!player) return;
    if (!strcmp(phase,"quit"))
    {
        CLIENT_COMMAND(player->edict(),"disconnect\nwait 60\nquit\n");
        return;
    }
    if (!strcmp(phase,"state"))
    {
        ALERT(at_console,"Stable audit state: player=%d alive=%d loaded=%d in-server=%d mount=%d loans=%d status=%d physics=%d view=%.1f xyz=%.1f,%.1f,%.1f\n",
            player->entindex(),player->IsAlive()!=0,player->m_CharacterState==CHARSTATE_LOADED,
            player->m_fInServer,(int)player->m_hMount,AuditLoanCount(player),player->m_StatusFlags,
            player->pev->iuser3,player->pev->view_ofs.z,player->pev->origin.x,player->pev->origin.y,player->pev->origin.z);
        return;
    }
    if (!strcmp(phase,"respawn"))
    {
        player->Spawn();
        AuditCheck("respawn after death",player->IsAlive() && !(int)player->m_hMount && AuditLoanCount(player)==0);
        return;
    }
    if (!Enabled() || !TestPlayer() || !player->IsAlive() || (int)player->m_hMount)
    {
        // Death/spawn intentionally accepts a mounted loaded player below.
        if (strcmp(phase,"death") && strcmp(phase,"spawn"))
        {
            g_engfuncs.pfnServerPrint("Stable audit needs an enabled, loaded, unmounted character.\n");
            return;
        }
    }
    if (!strcmp(phase,"death") || !strcmp(phase,"spawn"))
    {
        CMSRHorse *loan = AuditLoan(player);
        EHANDLE oldLoan;
        oldLoan = loan;
        if (!loan || MountedHorse(player) != loan)
        {
            AuditCheck("lifecycle admission",false);
            return;
        }
        if (!strcmp(phase,"death")) player->Killed(player->pev,GIB_NEVER);
        else player->Spawn();
        CBaseEntity *remaining = oldLoan;
        AuditCheck(phase,!(int)player->m_hMount && AuditLoanCount(player)==0 &&
            (!remaining || FBitSet(remaining->pev->flags,FL_KILLME)) &&
            !FBitSet(player->m_StatusFlags,PLAYER_MOVE_MOUNTED));
        return;
    }
    const Vector initialOrigin = player->pev->origin, initialView = player->pev->view_ofs;
    const int initialStatus = player->m_StatusFlags, initialPhysics = player->pev->iuser3;
    if (!strcmp(phase,"restore") || !strcmp(phase,"remove") || !strcmp(phase,"destroy"))
    {
        CMSRHorse *horse = Horse(CBaseEntity::Create("ms_horse",
            initialOrigin+Vector(0,0,player->pev->mins.z),g_vecZero));
        if (!horse || !horse->TryMount(player,true))
        {
            AuditCheck("mount admission",false);
            AuditRemove(horse);
            return;
        }
        if (!strcmp(phase,"destroy"))
        {
            REMOVE_ENTITY(horse->edict());
            AuditCheck("direct engine removal restores rider",!(int)player->m_hMount &&
                player->pev->view_ofs==initialView && player->pev->iuser3==initialPhysics &&
                (player->m_StatusFlags & kRestrictions)==(initialStatus & kRestrictions));
            UTIL_SetOrigin(player->pev,initialOrigin);
            return;
        }
        if (!strcmp(phase,"remove")) UTIL_Remove(horse);
        else horse->EndRide(true,"audit restore",true);
        AuditCheck(phase,!(int)player->m_hMount && !horse->GetRider() && !horse->pev->owner &&
            player->pev->view_ofs==initialView && player->pev->iuser3==initialPhysics &&
            (player->m_StatusFlags & kRestrictions)==(initialStatus & kRestrictions));
        if (!strcmp(phase,"remove")) AuditCheck("removed horse rejects remount",!horse->TryMount(player,true));
        AuditRemove(horse);
        UTIL_SetOrigin(player->pev,initialOrigin);
        player->pev->view_ofs=initialView;
        player->pev->iuser3=initialPhysics;
        player->m_StatusFlags=initialStatus;
        return;
    }
    if (!strcmp(phase,"effects"))
    {
        if (!player->m_Scripts.size()) { AuditCheck("effect script admission",false); return; }
        CScript *script=player->m_Scripts[0];
        const std::string oldJump=script->GetVar("game.effect.canjump");
        const std::string oldAttack=script->GetVar("game.effect.canattack");
        script->SetVar("game.effect.canjump",0);
        player->UpdateClientData();
        CMSRHorse *horse=Horse(CBaseEntity::Create("ms_horse",
            initialOrigin+Vector(0,0,player->pev->mins.z),g_vecZero));
        if (horse && horse->TryMount(player,true))
        {
            script->SetVar("game.effect.canjump",1);
            script->SetVar("game.effect.canattack",0);
            player->UpdateClientData();
            horse->EndRide(true,"audit effects",true);
            AuditCheck("expired jump effect cleared and new attack effect preserved",
                (player->m_StatusFlags & kRestrictions)==PLAYER_MOVE_NOATTACK);
        }
        else AuditCheck("effect mount admission",false);
        script->SetVar("game.effect.canjump",oldJump.c_str());
        script->SetVar("game.effect.canattack",oldAttack.c_str());
        AuditRemove(horse);
        player->UpdateClientData();
        UTIL_SetOrigin(player->pev,initialOrigin);
        AuditCheck("effect fixture restored",(player->m_StatusFlags & kRestrictions)==(initialStatus & kRestrictions));
        return;
    }
    CMSRStablemaster *stable = (CMSRStablemaster *)UTIL_FindEntityByClassname(NULL,"ms_stablemaster");
    if (!stable) { AuditCheck("stable admission",false); return; }
    if (!strcmp(phase,"pads"))
    {
        if (AuditLoan(player)) { AuditCheck("empty customer admission",false); return; }
        CBaseEntity *blocks[8] = {};
        for (int pad=0; pad<8; ++pad)
        {
            Vector feet=stable->pev->origin+Vector(180+(pad%4)*220,140+(pad/4)*180,0);
            blocks[pad]=CBaseEntity::Create("info_target",feet,g_vecZero);
            if (!blocks[pad]) break;
            blocks[pad]->pev->movetype=MOVETYPE_NONE;
            blocks[pad]->pev->solid=SOLID_BBOX;
            UTIL_SetSize(blocks[pad]->pev,Vector(-72,-72,0),Vector(72,72,150));
            UTIL_SetOrigin(blocks[pad]->pev,feet);
        }
        AuditCheck("all blocked pads refuse without loan",blocks[7] && !stable->Request(player) && AuditLoanCount(player)==0);
        for (int pad=1; pad<8; ++pad) AuditRemove(blocks[pad]);
        CMSRHorse *loan=stable->Request(player);
        const Vector firstPad=stable->pev->origin+Vector(180,140,0);
        AuditCheck("blocked first and occupied second pad skipped",loan &&
            (loan->pev->origin-firstPad).Length2D() > 300 && AuditLoanCount(player)==1);
        AuditRemove(blocks[0]);
        AuditRemove(loan);
        AuditCheck("pad audit leaves no loan",AuditLoanCount(player)==0);
    }
    else if (!strcmp(phase,"requests"))
    {
        CMSRHorse *loan=stable->Request(player);
        CBasePlayer *other=TestPlayer(3);
        AuditCheck("repeat unmounted reuse",loan && stable->Request(player)==loan && AuditLoanCount(player)==1);
        AuditCheck("other player cannot take or move loan",loan && other && !loan->TryMount(other,true) && !loan->GetRider());
        if (AuditRide(player,loan))
        {
            UTIL_SetOrigin(player->pev,initialOrigin);
            loan->Follow(player);
            AuditCheck("repeat mounted reuse",stable->Request(player)==loan && AuditLoanCount(player)==1 && loan->GetRider()==player);
            loan->EndRide(true,"audit requests",true);
            UTIL_SetOrigin(player->pev,initialOrigin);
            UTIL_SetOrigin(loan->pev,initialOrigin+Vector(800,120,0));
            const Vector away=loan->pev->origin;
            AuditCheck("moved unmounted loan reuse",stable->Request(player)==loan && loan->pev->origin==away && AuditLoanCount(player)==1);
            UTIL_SetOrigin(loan->pev,loan->m_HomeOrigin);
        }
        else AuditCheck("mounted request admission",false);
    }
    else if (!strcmp(phase,"ride"))
        AuditCheck("ride",AuditRide(player,stable->Request(player)));
    else if (!strcmp(phase,"clear"))
    {
        MSRMounts::Release(player,"spawn");
        AuditCheck("loan clear",AuditLoanCount(player)==0);
    }
    else g_engfuncs.pfnServerPrint("Stable audit phases: state restore remove pads requests ride death spawn clear quit.\n");
}
#endif
