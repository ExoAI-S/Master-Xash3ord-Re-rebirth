// Generated native CONTROL FLOW. Loader/arguments/scheduler remain legacy.
namespace MSRNativePilot {
static bool MatchBlock0(scriptcmd_list& list)
{
    if (list.m_Cmds.size() != 21) return false;
    { auto& cmd = list.m_Cmds[0];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "setvar", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    { auto& cmd = list.m_Cmds[1];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "setvar", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    { auto& cmd = list.m_Cmds[2];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "setvar", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    { auto& cmd = list.m_Cmds[3];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "setvar", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    { auto& cmd = list.m_Cmds[4];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "setvar", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    { auto& cmd = list.m_Cmds[5];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "setvar", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    { auto& cmd = list.m_Cmds[6];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "setvar", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    { auto& cmd = list.m_Cmds[7];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "setvar", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    { auto& cmd = list.m_Cmds[8];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "setvar", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    { auto& cmd = list.m_Cmds[9];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "setvar", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    { auto& cmd = list.m_Cmds[10];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "setvar", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    { auto& cmd = list.m_Cmds[11];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "setvar", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    { auto& cmd = list.m_Cmds[12];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "setvar", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    { auto& cmd = list.m_Cmds[13];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "setvar", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    { auto& cmd = list.m_Cmds[14];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "setvar", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    { auto& cmd = list.m_Cmds[15];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "setvar", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    { auto& cmd = list.m_Cmds[16];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "setvar", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    { auto& cmd = list.m_Cmds[17];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "setvar", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    { auto& cmd = list.m_Cmds[18];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "setvar", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    { auto& cmd = list.m_Cmds[19];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "setvar", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    { auto& cmd = list.m_Cmds[20];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "setvar", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    return true;
}
static bool RunBlock0(CScript& script, SCRIPT_EVENT& event, scriptcmd_list& list)
{
    // monsters/rat.script:3
    { auto& cmd = list.m_Cmds[0];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    // monsters/rat.script:4
    { auto& cmd = list.m_Cmds[1];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    // monsters/rat.script:5
    { auto& cmd = list.m_Cmds[2];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    // monsters/rat.script:6
    { auto& cmd = list.m_Cmds[3];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    // monsters/rat.script:7
    { auto& cmd = list.m_Cmds[4];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    // monsters/rat.script:8
    { auto& cmd = list.m_Cmds[5];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    // monsters/rat.script:9
    { auto& cmd = list.m_Cmds[6];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    // monsters/rat.script:10
    { auto& cmd = list.m_Cmds[7];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    // monsters/rat.script:11
    { auto& cmd = list.m_Cmds[8];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    // monsters/rat.script:12
    { auto& cmd = list.m_Cmds[9];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    // monsters/rat.script:13
    { auto& cmd = list.m_Cmds[10];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    // monsters/rat.script:14
    { auto& cmd = list.m_Cmds[11];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    // monsters/rat.script:15
    { auto& cmd = list.m_Cmds[12];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    // monsters/rat.script:16
    { auto& cmd = list.m_Cmds[13];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    // monsters/rat.script:17
    { auto& cmd = list.m_Cmds[14];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    // monsters/rat.script:18
    { auto& cmd = list.m_Cmds[15];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    // monsters/rat.script:20
    { auto& cmd = list.m_Cmds[16];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    // monsters/rat.script:21
    { auto& cmd = list.m_Cmds[17];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    // monsters/rat.script:22
    { auto& cmd = list.m_Cmds[18];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    // monsters/rat.script:23
    { auto& cmd = list.m_Cmds[19];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    // monsters/rat.script:24
    { auto& cmd = list.m_Cmds[20];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    return true;
}
static bool MatchBlock1(scriptcmd_list& list)
{
    if (list.m_Cmds.size() != 12) return false;
    { auto& cmd = list.m_Cmds[0];
      if (!MatchCommand<nullptr>(cmd, "hp", 2, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    { auto& cmd = list.m_Cmds[1];
      if (!MatchCommand<nullptr>(cmd, "width", 2, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    { auto& cmd = list.m_Cmds[2];
      if (!MatchCommand<nullptr>(cmd, "height", 2, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    { auto& cmd = list.m_Cmds[3];
      if (!MatchCommand<&CScript::ScriptCmd_Name>(cmd, "name", 2, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    { auto& cmd = list.m_Cmds[4];
      if (!MatchCommand<nullptr>(cmd, "roam", 2, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    { auto& cmd = list.m_Cmds[5];
      if (!MatchCommand<nullptr>(cmd, "hearingsensitivity", 2, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    { auto& cmd = list.m_Cmds[6];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "setvar", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    { auto& cmd = list.m_Cmds[7];
      if (!MatchCommand<nullptr>(cmd, "race", 2, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    { auto& cmd = list.m_Cmds[8];
      if (!MatchCommand<&CScript::ScriptCmd_SetModel>(cmd, "setmodel", 2, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    { auto& cmd = list.m_Cmds[9];
      if (!MatchCommand<&CScript::ScriptCmd_SetModelBody>(cmd, "setmodelbody", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    { auto& cmd = list.m_Cmds[10];
      if (!MatchCommand<nullptr>(cmd, "setidleanim", 2, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    { auto& cmd = list.m_Cmds[11];
      if (!MatchCommand<nullptr>(cmd, "setmoveanim", 2, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    return true;
}
static bool RunBlock1(CScript& script, SCRIPT_EVENT& event, scriptcmd_list& list)
{
    // monsters/rat.script:28
    { auto& cmd = list.m_Cmds[0];
      const bool ok = Invoke<nullptr>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    // monsters/rat.script:29
    { auto& cmd = list.m_Cmds[1];
      const bool ok = Invoke<nullptr>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    // monsters/rat.script:30
    { auto& cmd = list.m_Cmds[2];
      const bool ok = Invoke<nullptr>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    // monsters/rat.script:31
    { auto& cmd = list.m_Cmds[3];
      const bool ok = Invoke<&CScript::ScriptCmd_Name>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    // monsters/rat.script:32
    { auto& cmd = list.m_Cmds[4];
      const bool ok = Invoke<nullptr>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    // monsters/rat.script:33
    { auto& cmd = list.m_Cmds[5];
      const bool ok = Invoke<nullptr>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    // monsters/rat.script:34
    { auto& cmd = list.m_Cmds[6];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    // monsters/rat.script:35
    { auto& cmd = list.m_Cmds[7];
      const bool ok = Invoke<nullptr>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    // monsters/rat.script:36
    { auto& cmd = list.m_Cmds[8];
      const bool ok = Invoke<&CScript::ScriptCmd_SetModel>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    // monsters/rat.script:37
    { auto& cmd = list.m_Cmds[9];
      const bool ok = Invoke<&CScript::ScriptCmd_SetModelBody>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    // monsters/rat.script:38
    { auto& cmd = list.m_Cmds[10];
      const bool ok = Invoke<nullptr>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    // monsters/rat.script:39
    { auto& cmd = list.m_Cmds[11];
      const bool ok = Invoke<nullptr>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    return true;
}
static bool MatchBlock3(scriptcmd_list& list)
{
    if (list.m_Cmds.size() != 0) return false;
    return true;
}
static bool RunBlock3(CScript& script, SCRIPT_EVENT& event, scriptcmd_list& list)
{
    return true;
}
static bool MatchBlock4(scriptcmd_list& list)
{
    if (list.m_Cmds.size() != 0) return false;
    return true;
}
static bool RunBlock4(CScript& script, SCRIPT_EVENT& event, scriptcmd_list& list)
{
    return true;
}
static bool MatchBlock2(scriptcmd_list& list)
{
    if (list.m_Cmds.size() != 4) return false;
    { auto& cmd = list.m_Cmds[0];
      if (!MatchCommand<&CScript::ScriptCmd_RepeatDelay>(cmd, "repeatdelay", 2, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    { auto& cmd = list.m_Cmds[1];
      if (!MatchCommand<&CScript::ScriptCmd_If>(cmd, "if", 2, true, false, 0)) return false;
      if (!MatchBlock3(cmd.m_IfCmds)) return false;
    }
    { auto& cmd = list.m_Cmds[2];
      if (!MatchCommand<&CScript::ScriptCmd_If>(cmd, "if", 2, true, false, 0)) return false;
      if (!MatchBlock4(cmd.m_IfCmds)) return false;
    }
    { auto& cmd = list.m_Cmds[3];
      if (!MatchCommand<nullptr>(cmd, "playanim", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    return true;
}
static bool RunBlock2(CScript& script, SCRIPT_EVENT& event, scriptcmd_list& list)
{
    // monsters/rat.script:42
    { auto& cmd = list.m_Cmds[0];
      const bool ok = Invoke<&CScript::ScriptCmd_RepeatDelay>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    // monsters/rat.script:43
    { auto& cmd = list.m_Cmds[1];
      const bool ok = Invoke<&CScript::ScriptCmd_If>(script, event, cmd);
      if (ok) RunBlock3(script, event, cmd.m_IfCmds);
      else {
          return true; // Original failed guard breaks this list, whose return is true.
      }
      if (event.bFullStop) return false;
    }
    // monsters/rat.script:44
    { auto& cmd = list.m_Cmds[2];
      const bool ok = Invoke<&CScript::ScriptCmd_If>(script, event, cmd);
      if (ok) RunBlock4(script, event, cmd.m_IfCmds);
      else {
          return true; // Original failed guard breaks this list, whose return is true.
      }
      if (event.bFullStop) return false;
    }
    // monsters/rat.script:45
    { auto& cmd = list.m_Cmds[3];
      const bool ok = Invoke<nullptr>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    return true;
}
static bool MatchBlock5(scriptcmd_list& list)
{
    if (list.m_Cmds.size() != 2) return false;
    { auto& cmd = list.m_Cmds[0];
      if (!MatchCommand<&CScript::ScriptCmd_PlaySound>(cmd, "playrandomsound", 4, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    { auto& cmd = list.m_Cmds[1];
      if (!MatchCommand<nullptr>(cmd, "dodamage", 5, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    return true;
}
static bool RunBlock5(CScript& script, SCRIPT_EVENT& event, scriptcmd_list& list)
{
    // monsters/rat.script:49
    { auto& cmd = list.m_Cmds[0];
      const bool ok = Invoke<&CScript::ScriptCmd_PlaySound>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    // monsters/rat.script:50
    { auto& cmd = list.m_Cmds[1];
      const bool ok = Invoke<nullptr>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    return true;
}
static bool MatchBlock6(scriptcmd_list& list)
{
    if (list.m_Cmds.size() != 2) return false;
    { auto& cmd = list.m_Cmds[0];
      if (!MatchCommand<&CScript::ScriptCmd_Volume>(cmd, "volume", 2, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    { auto& cmd = list.m_Cmds[1];
      if (!MatchCommand<&CScript::ScriptCmd_PlaySound>(cmd, "playrandomsound", 7, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    return true;
}
static bool RunBlock6(CScript& script, SCRIPT_EVENT& event, scriptcmd_list& list)
{
    // monsters/rat.script:54
    { auto& cmd = list.m_Cmds[0];
      const bool ok = Invoke<&CScript::ScriptCmd_Volume>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    // monsters/rat.script:55
    { auto& cmd = list.m_Cmds[1];
      const bool ok = Invoke<&CScript::ScriptCmd_PlaySound>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    return true;
}
static bool MatchBlock7(scriptcmd_list& list)
{
    if (list.m_Cmds.size() != 6) return false;
    { auto& cmd = list.m_Cmds[0];
      if (!MatchCommand<&CScript::ScriptCmd_Name>(cmd, "name", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    { auto& cmd = list.m_Cmds[1];
      if (!MatchCommand<&CScript::ScriptCmd_Desc>(cmd, "desc", 5, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    { auto& cmd = list.m_Cmds[2];
      if (!MatchCommand<&CScript::ScriptCmd_Weight>(cmd, "weight", 2, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    { auto& cmd = list.m_Cmds[3];
      if (!MatchCommand<nullptr>(cmd, "size", 2, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    { auto& cmd = list.m_Cmds[4];
      if (!MatchCommand<nullptr>(cmd, "value", 2, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    { auto& cmd = list.m_Cmds[5];
      if (!MatchCommand<nullptr>(cmd, "sethudsprite", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    return true;
}
static bool RunBlock7(CScript& script, SCRIPT_EVENT& event, scriptcmd_list& list)
{
    // items/swords_shortsword.script:36
    { auto& cmd = list.m_Cmds[0];
      const bool ok = Invoke<&CScript::ScriptCmd_Name>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    // items/swords_shortsword.script:37
    { auto& cmd = list.m_Cmds[1];
      const bool ok = Invoke<&CScript::ScriptCmd_Desc>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    // items/swords_shortsword.script:38
    { auto& cmd = list.m_Cmds[2];
      const bool ok = Invoke<&CScript::ScriptCmd_Weight>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    // items/swords_shortsword.script:39
    { auto& cmd = list.m_Cmds[3];
      const bool ok = Invoke<nullptr>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    // items/swords_shortsword.script:40
    { auto& cmd = list.m_Cmds[4];
      const bool ok = Invoke<nullptr>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    // items/swords_shortsword.script:41
    { auto& cmd = list.m_Cmds[5];
      const bool ok = Invoke<nullptr>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    return true;
}
static bool MatchBlock8(scriptcmd_list& list)
{
    if (list.m_Cmds.size() != 3) return false;
    { auto& cmd = list.m_Cmds[0];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "setvar", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    { auto& cmd = list.m_Cmds[1];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "setvar", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    { auto& cmd = list.m_Cmds[2];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "setvar", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    return true;
}
static bool RunBlock8(CScript& script, SCRIPT_EVENT& event, scriptcmd_list& list)
{
    // monsters/base_script_skills.script:18
    { auto& cmd = list.m_Cmds[0];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:19
    { auto& cmd = list.m_Cmds[1];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:20
    { auto& cmd = list.m_Cmds[2];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    return true;
}
static bool MatchBlock10(scriptcmd_list& list)
{
    if (list.m_Cmds.size() != 0) return false;
    return true;
}
static bool RunBlock10(CScript& script, SCRIPT_EVENT& event, scriptcmd_list& list)
{
    return true;
}
static bool MatchBlock11(scriptcmd_list& list)
{
    if (list.m_Cmds.size() != 0) return false;
    return true;
}
static bool RunBlock11(CScript& script, SCRIPT_EVENT& event, scriptcmd_list& list)
{
    return true;
}
static bool MatchBlock12(scriptcmd_list& list)
{
    if (list.m_Cmds.size() != 0) return false;
    return true;
}
static bool RunBlock12(CScript& script, SCRIPT_EVENT& event, scriptcmd_list& list)
{
    return true;
}
static bool MatchBlock14(scriptcmd_list& list)
{
    if (list.m_Cmds.size() != 3) return false;
    { auto& cmd = list.m_Cmds[0];
      if (!MatchCommand<&CScript::ScriptCmd_CallEvent>(cmd, "calleventloop", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    { auto& cmd = list.m_Cmds[1];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "setvar", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    { auto& cmd = list.m_Cmds[2];
      if (!MatchCommand<&CScript::ScriptCmd_CallEvent>(cmd, "calleventloop", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    return true;
}
static bool RunBlock14(CScript& script, SCRIPT_EVENT& event, scriptcmd_list& list)
{
    // monsters/base_script_skills.script:40
    { auto& cmd = list.m_Cmds[0];
      const bool ok = Invoke<&CScript::ScriptCmd_CallEvent>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:41
    { auto& cmd = list.m_Cmds[1];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:42
    { auto& cmd = list.m_Cmds[2];
      const bool ok = Invoke<&CScript::ScriptCmd_CallEvent>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    return true;
}
static bool MatchBlock15(scriptcmd_list& list)
{
    if (list.m_Cmds.size() != 1) return false;
    { auto& cmd = list.m_Cmds[0];
      if (!MatchCommand<&CScript::ScriptCmd_Message>(cmd, "playermessage", 9, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    return true;
}
static bool RunBlock15(CScript& script, SCRIPT_EVENT& event, scriptcmd_list& list)
{
    // monsters/base_script_skills.script:44
    { auto& cmd = list.m_Cmds[0];
      const bool ok = Invoke<&CScript::ScriptCmd_Message>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    return true;
}
static bool MatchBlock16(scriptcmd_list& list)
{
    if (list.m_Cmds.size() != 0) return false;
    return true;
}
static bool RunBlock16(CScript& script, SCRIPT_EVENT& event, scriptcmd_list& list)
{
    return true;
}
static bool MatchBlock13(scriptcmd_list& list)
{
    if (list.m_Cmds.size() != 5) return false;
    { auto& cmd = list.m_Cmds[0];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "local", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    { auto& cmd = list.m_Cmds[1];
      if (!MatchCommand<&CScript::ScriptCmd_If>(cmd, "if()", 4, true, true, 0)) return false;
      if (!MatchBlock14(cmd.m_IfCmds)) return false;
    }
    { auto& cmd = list.m_Cmds[2];
      if (!MatchCommand<&CScript::ScriptCmd_If>(cmd, "if()", 4, true, true, 0)) return false;
      if (!MatchBlock15(cmd.m_IfCmds)) return false;
    }
    { auto& cmd = list.m_Cmds[3];
      if (!MatchCommand<&CScript::ScriptCmd_If>(cmd, "if", 4, true, false, 0)) return false;
      if (!MatchBlock16(cmd.m_IfCmds)) return false;
    }
    { auto& cmd = list.m_Cmds[4];
      if (!MatchCommand<&CScript::ScriptCmd_TokenAdd>(cmd, "token.add", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    return true;
}
static bool RunBlock13(CScript& script, SCRIPT_EVENT& event, scriptcmd_list& list)
{
    // monsters/base_script_skills.script:37
    { auto& cmd = list.m_Cmds[0];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:38
    { auto& cmd = list.m_Cmds[1];
      const bool ok = Invoke<&CScript::ScriptCmd_If>(script, event, cmd);
      if (ok) RunBlock14(script, event, cmd.m_IfCmds);
      else {
      }
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:44
    { auto& cmd = list.m_Cmds[2];
      const bool ok = Invoke<&CScript::ScriptCmd_If>(script, event, cmd);
      if (ok) RunBlock15(script, event, cmd.m_IfCmds);
      else {
      }
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:45
    { auto& cmd = list.m_Cmds[3];
      const bool ok = Invoke<&CScript::ScriptCmd_If>(script, event, cmd);
      if (ok) RunBlock16(script, event, cmd.m_IfCmds);
      else {
          return true; // Original failed guard breaks this list, whose return is true.
      }
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:46
    { auto& cmd = list.m_Cmds[4];
      const bool ok = Invoke<&CScript::ScriptCmd_TokenAdd>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    return true;
}
static bool MatchBlock17(scriptcmd_list& list)
{
    if (list.m_Cmds.size() != 1) return false;
    { auto& cmd = list.m_Cmds[0];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "local", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    return true;
}
static bool RunBlock17(CScript& script, SCRIPT_EVENT& event, scriptcmd_list& list)
{
    // monsters/base_script_skills.script:49
    { auto& cmd = list.m_Cmds[0];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    return true;
}
static bool MatchBlock18(scriptcmd_list& list)
{
    if (list.m_Cmds.size() != 1) return false;
    { auto& cmd = list.m_Cmds[0];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "local", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    return true;
}
static bool RunBlock18(CScript& script, SCRIPT_EVENT& event, scriptcmd_list& list)
{
    // monsters/base_script_skills.script:50
    { auto& cmd = list.m_Cmds[0];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    return true;
}
static bool MatchBlock19(scriptcmd_list& list)
{
    if (list.m_Cmds.size() != 1) return false;
    { auto& cmd = list.m_Cmds[0];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "local", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    return true;
}
static bool RunBlock19(CScript& script, SCRIPT_EVENT& event, scriptcmd_list& list)
{
    // monsters/base_script_skills.script:51
    { auto& cmd = list.m_Cmds[0];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    return true;
}
static bool MatchBlock20(scriptcmd_list& list)
{
    if (list.m_Cmds.size() != 1) return false;
    { auto& cmd = list.m_Cmds[0];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "local", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    return true;
}
static bool RunBlock20(CScript& script, SCRIPT_EVENT& event, scriptcmd_list& list)
{
    // monsters/base_script_skills.script:52
    { auto& cmd = list.m_Cmds[0];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    return true;
}
static bool MatchBlock21(scriptcmd_list& list)
{
    if (list.m_Cmds.size() != 1) return false;
    { auto& cmd = list.m_Cmds[0];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "local", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    return true;
}
static bool RunBlock21(CScript& script, SCRIPT_EVENT& event, scriptcmd_list& list)
{
    // monsters/base_script_skills.script:53
    { auto& cmd = list.m_Cmds[0];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    return true;
}
static bool MatchBlock22(scriptcmd_list& list)
{
    if (list.m_Cmds.size() != 1) return false;
    { auto& cmd = list.m_Cmds[0];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "local", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    return true;
}
static bool RunBlock22(CScript& script, SCRIPT_EVENT& event, scriptcmd_list& list)
{
    // monsters/base_script_skills.script:54
    { auto& cmd = list.m_Cmds[0];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    return true;
}
static bool MatchBlock23(scriptcmd_list& list)
{
    if (list.m_Cmds.size() != 1) return false;
    { auto& cmd = list.m_Cmds[0];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "local", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    return true;
}
static bool RunBlock23(CScript& script, SCRIPT_EVENT& event, scriptcmd_list& list)
{
    // monsters/base_script_skills.script:55
    { auto& cmd = list.m_Cmds[0];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    return true;
}
static bool MatchBlock24(scriptcmd_list& list)
{
    if (list.m_Cmds.size() != 1) return false;
    { auto& cmd = list.m_Cmds[0];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "local", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    return true;
}
static bool RunBlock24(CScript& script, SCRIPT_EVENT& event, scriptcmd_list& list)
{
    // monsters/base_script_skills.script:56
    { auto& cmd = list.m_Cmds[0];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    return true;
}
static bool MatchBlock25(scriptcmd_list& list)
{
    if (list.m_Cmds.size() != 1) return false;
    { auto& cmd = list.m_Cmds[0];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "local", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    return true;
}
static bool RunBlock25(CScript& script, SCRIPT_EVENT& event, scriptcmd_list& list)
{
    // monsters/base_script_skills.script:57
    { auto& cmd = list.m_Cmds[0];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    return true;
}
static bool MatchBlock26(scriptcmd_list& list)
{
    if (list.m_Cmds.size() != 1) return false;
    { auto& cmd = list.m_Cmds[0];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "local", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    return true;
}
static bool RunBlock26(CScript& script, SCRIPT_EVENT& event, scriptcmd_list& list)
{
    // monsters/base_script_skills.script:58
    { auto& cmd = list.m_Cmds[0];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    return true;
}
static bool MatchBlock27(scriptcmd_list& list)
{
    if (list.m_Cmds.size() != 1) return false;
    { auto& cmd = list.m_Cmds[0];
      if (!MatchCommand<&CScript::ScriptCmd_TokenSet>(cmd, "token.set", 4, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    return true;
}
static bool RunBlock27(CScript& script, SCRIPT_EVENT& event, scriptcmd_list& list)
{
    // monsters/base_script_skills.script:60
    { auto& cmd = list.m_Cmds[0];
      const bool ok = Invoke<&CScript::ScriptCmd_TokenSet>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    return true;
}
static bool MatchBlock28(scriptcmd_list& list)
{
    if (list.m_Cmds.size() != 1) return false;
    { auto& cmd = list.m_Cmds[0];
      if (!MatchCommand<&CScript::ScriptCmd_TokenSet>(cmd, "token.set", 4, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    return true;
}
static bool RunBlock28(CScript& script, SCRIPT_EVENT& event, scriptcmd_list& list)
{
    // monsters/base_script_skills.script:61
    { auto& cmd = list.m_Cmds[0];
      const bool ok = Invoke<&CScript::ScriptCmd_TokenSet>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    return true;
}
static bool MatchBlock29(scriptcmd_list& list)
{
    if (list.m_Cmds.size() != 1) return false;
    { auto& cmd = list.m_Cmds[0];
      if (!MatchCommand<&CScript::ScriptCmd_TokenSet>(cmd, "token.set", 4, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    return true;
}
static bool RunBlock29(CScript& script, SCRIPT_EVENT& event, scriptcmd_list& list)
{
    // monsters/base_script_skills.script:62
    { auto& cmd = list.m_Cmds[0];
      const bool ok = Invoke<&CScript::ScriptCmd_TokenSet>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    return true;
}
static bool MatchBlock30(scriptcmd_list& list)
{
    if (list.m_Cmds.size() != 1) return false;
    { auto& cmd = list.m_Cmds[0];
      if (!MatchCommand<&CScript::ScriptCmd_TokenSet>(cmd, "token.set", 4, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    return true;
}
static bool RunBlock30(CScript& script, SCRIPT_EVENT& event, scriptcmd_list& list)
{
    // monsters/base_script_skills.script:63
    { auto& cmd = list.m_Cmds[0];
      const bool ok = Invoke<&CScript::ScriptCmd_TokenSet>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    return true;
}
static bool MatchBlock31(scriptcmd_list& list)
{
    if (list.m_Cmds.size() != 1) return false;
    { auto& cmd = list.m_Cmds[0];
      if (!MatchCommand<&CScript::ScriptCmd_TokenSet>(cmd, "token.set", 4, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    return true;
}
static bool RunBlock31(CScript& script, SCRIPT_EVENT& event, scriptcmd_list& list)
{
    // monsters/base_script_skills.script:64
    { auto& cmd = list.m_Cmds[0];
      const bool ok = Invoke<&CScript::ScriptCmd_TokenSet>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    return true;
}
static bool MatchBlock32(scriptcmd_list& list)
{
    if (list.m_Cmds.size() != 1) return false;
    { auto& cmd = list.m_Cmds[0];
      if (!MatchCommand<&CScript::ScriptCmd_TokenSet>(cmd, "token.set", 4, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    return true;
}
static bool RunBlock32(CScript& script, SCRIPT_EVENT& event, scriptcmd_list& list)
{
    // monsters/base_script_skills.script:65
    { auto& cmd = list.m_Cmds[0];
      const bool ok = Invoke<&CScript::ScriptCmd_TokenSet>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    return true;
}
static bool MatchBlock33(scriptcmd_list& list)
{
    if (list.m_Cmds.size() != 1) return false;
    { auto& cmd = list.m_Cmds[0];
      if (!MatchCommand<&CScript::ScriptCmd_TokenSet>(cmd, "token.set", 4, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    return true;
}
static bool RunBlock33(CScript& script, SCRIPT_EVENT& event, scriptcmd_list& list)
{
    // monsters/base_script_skills.script:66
    { auto& cmd = list.m_Cmds[0];
      const bool ok = Invoke<&CScript::ScriptCmd_TokenSet>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    return true;
}
static bool MatchBlock34(scriptcmd_list& list)
{
    if (list.m_Cmds.size() != 1) return false;
    { auto& cmd = list.m_Cmds[0];
      if (!MatchCommand<&CScript::ScriptCmd_TokenSet>(cmd, "token.set", 4, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    return true;
}
static bool RunBlock34(CScript& script, SCRIPT_EVENT& event, scriptcmd_list& list)
{
    // monsters/base_script_skills.script:67
    { auto& cmd = list.m_Cmds[0];
      const bool ok = Invoke<&CScript::ScriptCmd_TokenSet>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    return true;
}
static bool MatchBlock35(scriptcmd_list& list)
{
    if (list.m_Cmds.size() != 1) return false;
    { auto& cmd = list.m_Cmds[0];
      if (!MatchCommand<&CScript::ScriptCmd_TokenSet>(cmd, "token.set", 4, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    return true;
}
static bool RunBlock35(CScript& script, SCRIPT_EVENT& event, scriptcmd_list& list)
{
    // monsters/base_script_skills.script:68
    { auto& cmd = list.m_Cmds[0];
      const bool ok = Invoke<&CScript::ScriptCmd_TokenSet>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    return true;
}
static bool MatchBlock36(scriptcmd_list& list)
{
    if (list.m_Cmds.size() != 1) return false;
    { auto& cmd = list.m_Cmds[0];
      if (!MatchCommand<&CScript::ScriptCmd_TokenSet>(cmd, "token.set", 4, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    return true;
}
static bool RunBlock36(CScript& script, SCRIPT_EVENT& event, scriptcmd_list& list)
{
    // monsters/base_script_skills.script:69
    { auto& cmd = list.m_Cmds[0];
      const bool ok = Invoke<&CScript::ScriptCmd_TokenSet>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    return true;
}
static bool MatchBlock9(scriptcmd_list& list)
{
    if (list.m_Cmds.size() != 38) return false;
    { auto& cmd = list.m_Cmds[0];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "local", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    { auto& cmd = list.m_Cmds[1];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "local", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    { auto& cmd = list.m_Cmds[2];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "local", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    { auto& cmd = list.m_Cmds[3];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "local", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    { auto& cmd = list.m_Cmds[4];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "local", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    { auto& cmd = list.m_Cmds[5];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "setvar", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    { auto& cmd = list.m_Cmds[6];
      if (!MatchCommand<&CScript::ScriptCmd_CallEvent>(cmd, "callevent", 5, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    { auto& cmd = list.m_Cmds[7];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "local", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    { auto& cmd = list.m_Cmds[8];
      if (!MatchCommand<&CScript::ScriptCmd_If>(cmd, "if", 4, true, false, 0)) return false;
      if (!MatchBlock10(cmd.m_IfCmds)) return false;
    }
    { auto& cmd = list.m_Cmds[9];
      if (!MatchCommand<&CScript::ScriptCmd_If>(cmd, "if", 4, true, false, 0)) return false;
      if (!MatchBlock11(cmd.m_IfCmds)) return false;
    }
    { auto& cmd = list.m_Cmds[10];
      if (!MatchCommand<&CScript::ScriptCmd_If>(cmd, "if", 2, true, false, 0)) return false;
      if (!MatchBlock12(cmd.m_IfCmds)) return false;
    }
    { auto& cmd = list.m_Cmds[11];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "local", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    { auto& cmd = list.m_Cmds[12];
      if (!MatchCommand<&CScript::ScriptCmd_If>(cmd, "if()", 4, true, true, 0)) return false;
      if (!MatchBlock13(cmd.m_IfCmds)) return false;
    }
    { auto& cmd = list.m_Cmds[13];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "local", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    { auto& cmd = list.m_Cmds[14];
      if (!MatchCommand<&CScript::ScriptCmd_If>(cmd, "if()", 4, true, true, 0)) return false;
      if (!MatchBlock17(cmd.m_IfCmds)) return false;
    }
    { auto& cmd = list.m_Cmds[15];
      if (!MatchCommand<&CScript::ScriptCmd_If>(cmd, "if()", 4, true, true, 0)) return false;
      if (!MatchBlock18(cmd.m_IfCmds)) return false;
    }
    { auto& cmd = list.m_Cmds[16];
      if (!MatchCommand<&CScript::ScriptCmd_If>(cmd, "if()", 4, true, true, 0)) return false;
      if (!MatchBlock19(cmd.m_IfCmds)) return false;
    }
    { auto& cmd = list.m_Cmds[17];
      if (!MatchCommand<&CScript::ScriptCmd_If>(cmd, "if()", 4, true, true, 0)) return false;
      if (!MatchBlock20(cmd.m_IfCmds)) return false;
    }
    { auto& cmd = list.m_Cmds[18];
      if (!MatchCommand<&CScript::ScriptCmd_If>(cmd, "if()", 4, true, true, 0)) return false;
      if (!MatchBlock21(cmd.m_IfCmds)) return false;
    }
    { auto& cmd = list.m_Cmds[19];
      if (!MatchCommand<&CScript::ScriptCmd_If>(cmd, "if()", 4, true, true, 0)) return false;
      if (!MatchBlock22(cmd.m_IfCmds)) return false;
    }
    { auto& cmd = list.m_Cmds[20];
      if (!MatchCommand<&CScript::ScriptCmd_If>(cmd, "if()", 4, true, true, 0)) return false;
      if (!MatchBlock23(cmd.m_IfCmds)) return false;
    }
    { auto& cmd = list.m_Cmds[21];
      if (!MatchCommand<&CScript::ScriptCmd_If>(cmd, "if()", 4, true, true, 0)) return false;
      if (!MatchBlock24(cmd.m_IfCmds)) return false;
    }
    { auto& cmd = list.m_Cmds[22];
      if (!MatchCommand<&CScript::ScriptCmd_If>(cmd, "if()", 4, true, true, 0)) return false;
      if (!MatchBlock25(cmd.m_IfCmds)) return false;
    }
    { auto& cmd = list.m_Cmds[23];
      if (!MatchCommand<&CScript::ScriptCmd_If>(cmd, "if()", 4, true, true, 0)) return false;
      if (!MatchBlock26(cmd.m_IfCmds)) return false;
    }
    { auto& cmd = list.m_Cmds[24];
      if (!MatchCommand<&CScript::ScriptCmd_MathSet>(cmd, "add", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    { auto& cmd = list.m_Cmds[25];
      if (!MatchCommand<&CScript::ScriptCmd_If>(cmd, "if()", 4, true, true, 0)) return false;
      if (!MatchBlock27(cmd.m_IfCmds)) return false;
    }
    { auto& cmd = list.m_Cmds[26];
      if (!MatchCommand<&CScript::ScriptCmd_If>(cmd, "if()", 4, true, true, 0)) return false;
      if (!MatchBlock28(cmd.m_IfCmds)) return false;
    }
    { auto& cmd = list.m_Cmds[27];
      if (!MatchCommand<&CScript::ScriptCmd_If>(cmd, "if()", 4, true, true, 0)) return false;
      if (!MatchBlock29(cmd.m_IfCmds)) return false;
    }
    { auto& cmd = list.m_Cmds[28];
      if (!MatchCommand<&CScript::ScriptCmd_If>(cmd, "if()", 4, true, true, 0)) return false;
      if (!MatchBlock30(cmd.m_IfCmds)) return false;
    }
    { auto& cmd = list.m_Cmds[29];
      if (!MatchCommand<&CScript::ScriptCmd_If>(cmd, "if()", 4, true, true, 0)) return false;
      if (!MatchBlock31(cmd.m_IfCmds)) return false;
    }
    { auto& cmd = list.m_Cmds[30];
      if (!MatchCommand<&CScript::ScriptCmd_If>(cmd, "if()", 4, true, true, 0)) return false;
      if (!MatchBlock32(cmd.m_IfCmds)) return false;
    }
    { auto& cmd = list.m_Cmds[31];
      if (!MatchCommand<&CScript::ScriptCmd_If>(cmd, "if()", 4, true, true, 0)) return false;
      if (!MatchBlock33(cmd.m_IfCmds)) return false;
    }
    { auto& cmd = list.m_Cmds[32];
      if (!MatchCommand<&CScript::ScriptCmd_If>(cmd, "if()", 4, true, true, 0)) return false;
      if (!MatchBlock34(cmd.m_IfCmds)) return false;
    }
    { auto& cmd = list.m_Cmds[33];
      if (!MatchCommand<&CScript::ScriptCmd_If>(cmd, "if()", 4, true, true, 0)) return false;
      if (!MatchBlock35(cmd.m_IfCmds)) return false;
    }
    { auto& cmd = list.m_Cmds[34];
      if (!MatchCommand<&CScript::ScriptCmd_If>(cmd, "if()", 4, true, true, 0)) return false;
      if (!MatchBlock36(cmd.m_IfCmds)) return false;
    }
    { auto& cmd = list.m_Cmds[35];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "local", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    { auto& cmd = list.m_Cmds[36];
      if (!MatchCommand<&CScript::ScriptCmd_MathSet>(cmd, "add", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    { auto& cmd = list.m_Cmds[37];
      if (!MatchCommand<&CScript::ScriptCmd_TokenSet>(cmd, "token.set", 4, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    return true;
}
static bool RunBlock9(CScript& script, SCRIPT_EVENT& event, scriptcmd_list& list)
{
    // monsters/base_script_skills.script:23
    { auto& cmd = list.m_Cmds[0];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:24
    { auto& cmd = list.m_Cmds[1];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:25
    { auto& cmd = list.m_Cmds[2];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:26
    { auto& cmd = list.m_Cmds[3];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:27
    { auto& cmd = list.m_Cmds[4];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:28
    { auto& cmd = list.m_Cmds[5];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:29
    { auto& cmd = list.m_Cmds[6];
      const bool ok = Invoke<&CScript::ScriptCmd_CallEvent>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:30
    { auto& cmd = list.m_Cmds[7];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:31
    { auto& cmd = list.m_Cmds[8];
      const bool ok = Invoke<&CScript::ScriptCmd_If>(script, event, cmd);
      if (ok) RunBlock10(script, event, cmd.m_IfCmds);
      else {
          return true; // Original failed guard breaks this list, whose return is true.
      }
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:32
    { auto& cmd = list.m_Cmds[9];
      const bool ok = Invoke<&CScript::ScriptCmd_If>(script, event, cmd);
      if (ok) RunBlock11(script, event, cmd.m_IfCmds);
      else {
          return true; // Original failed guard breaks this list, whose return is true.
      }
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:33
    { auto& cmd = list.m_Cmds[10];
      const bool ok = Invoke<&CScript::ScriptCmd_If>(script, event, cmd);
      if (ok) RunBlock12(script, event, cmd.m_IfCmds);
      else {
          return true; // Original failed guard breaks this list, whose return is true.
      }
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:34
    { auto& cmd = list.m_Cmds[11];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:35
    { auto& cmd = list.m_Cmds[12];
      const bool ok = Invoke<&CScript::ScriptCmd_If>(script, event, cmd);
      if (ok) RunBlock13(script, event, cmd.m_IfCmds);
      else {
      }
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:48
    { auto& cmd = list.m_Cmds[13];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:49
    { auto& cmd = list.m_Cmds[14];
      const bool ok = Invoke<&CScript::ScriptCmd_If>(script, event, cmd);
      if (ok) RunBlock17(script, event, cmd.m_IfCmds);
      else {
      }
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:50
    { auto& cmd = list.m_Cmds[15];
      const bool ok = Invoke<&CScript::ScriptCmd_If>(script, event, cmd);
      if (ok) RunBlock18(script, event, cmd.m_IfCmds);
      else {
      }
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:51
    { auto& cmd = list.m_Cmds[16];
      const bool ok = Invoke<&CScript::ScriptCmd_If>(script, event, cmd);
      if (ok) RunBlock19(script, event, cmd.m_IfCmds);
      else {
      }
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:52
    { auto& cmd = list.m_Cmds[17];
      const bool ok = Invoke<&CScript::ScriptCmd_If>(script, event, cmd);
      if (ok) RunBlock20(script, event, cmd.m_IfCmds);
      else {
      }
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:53
    { auto& cmd = list.m_Cmds[18];
      const bool ok = Invoke<&CScript::ScriptCmd_If>(script, event, cmd);
      if (ok) RunBlock21(script, event, cmd.m_IfCmds);
      else {
      }
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:54
    { auto& cmd = list.m_Cmds[19];
      const bool ok = Invoke<&CScript::ScriptCmd_If>(script, event, cmd);
      if (ok) RunBlock22(script, event, cmd.m_IfCmds);
      else {
      }
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:55
    { auto& cmd = list.m_Cmds[20];
      const bool ok = Invoke<&CScript::ScriptCmd_If>(script, event, cmd);
      if (ok) RunBlock23(script, event, cmd.m_IfCmds);
      else {
      }
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:56
    { auto& cmd = list.m_Cmds[21];
      const bool ok = Invoke<&CScript::ScriptCmd_If>(script, event, cmd);
      if (ok) RunBlock24(script, event, cmd.m_IfCmds);
      else {
      }
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:57
    { auto& cmd = list.m_Cmds[22];
      const bool ok = Invoke<&CScript::ScriptCmd_If>(script, event, cmd);
      if (ok) RunBlock25(script, event, cmd.m_IfCmds);
      else {
      }
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:58
    { auto& cmd = list.m_Cmds[23];
      const bool ok = Invoke<&CScript::ScriptCmd_If>(script, event, cmd);
      if (ok) RunBlock26(script, event, cmd.m_IfCmds);
      else {
      }
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:59
    { auto& cmd = list.m_Cmds[24];
      const bool ok = Invoke<&CScript::ScriptCmd_MathSet>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:60
    { auto& cmd = list.m_Cmds[25];
      const bool ok = Invoke<&CScript::ScriptCmd_If>(script, event, cmd);
      if (ok) RunBlock27(script, event, cmd.m_IfCmds);
      else {
      }
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:61
    { auto& cmd = list.m_Cmds[26];
      const bool ok = Invoke<&CScript::ScriptCmd_If>(script, event, cmd);
      if (ok) RunBlock28(script, event, cmd.m_IfCmds);
      else {
      }
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:62
    { auto& cmd = list.m_Cmds[27];
      const bool ok = Invoke<&CScript::ScriptCmd_If>(script, event, cmd);
      if (ok) RunBlock29(script, event, cmd.m_IfCmds);
      else {
      }
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:63
    { auto& cmd = list.m_Cmds[28];
      const bool ok = Invoke<&CScript::ScriptCmd_If>(script, event, cmd);
      if (ok) RunBlock30(script, event, cmd.m_IfCmds);
      else {
      }
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:64
    { auto& cmd = list.m_Cmds[29];
      const bool ok = Invoke<&CScript::ScriptCmd_If>(script, event, cmd);
      if (ok) RunBlock31(script, event, cmd.m_IfCmds);
      else {
      }
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:65
    { auto& cmd = list.m_Cmds[30];
      const bool ok = Invoke<&CScript::ScriptCmd_If>(script, event, cmd);
      if (ok) RunBlock32(script, event, cmd.m_IfCmds);
      else {
      }
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:66
    { auto& cmd = list.m_Cmds[31];
      const bool ok = Invoke<&CScript::ScriptCmd_If>(script, event, cmd);
      if (ok) RunBlock33(script, event, cmd.m_IfCmds);
      else {
      }
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:67
    { auto& cmd = list.m_Cmds[32];
      const bool ok = Invoke<&CScript::ScriptCmd_If>(script, event, cmd);
      if (ok) RunBlock34(script, event, cmd.m_IfCmds);
      else {
      }
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:68
    { auto& cmd = list.m_Cmds[33];
      const bool ok = Invoke<&CScript::ScriptCmd_If>(script, event, cmd);
      if (ok) RunBlock35(script, event, cmd.m_IfCmds);
      else {
      }
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:69
    { auto& cmd = list.m_Cmds[34];
      const bool ok = Invoke<&CScript::ScriptCmd_If>(script, event, cmd);
      if (ok) RunBlock36(script, event, cmd.m_IfCmds);
      else {
      }
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:70
    { auto& cmd = list.m_Cmds[35];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:71
    { auto& cmd = list.m_Cmds[36];
      const bool ok = Invoke<&CScript::ScriptCmd_MathSet>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:72
    { auto& cmd = list.m_Cmds[37];
      const bool ok = Invoke<&CScript::ScriptCmd_TokenSet>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    return true;
}
static bool MatchBlock38(scriptcmd_list& list)
{
    if (list.m_Cmds.size() != 1) return false;
    { auto& cmd = list.m_Cmds[0];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "local", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    return true;
}
static bool RunBlock38(CScript& script, SCRIPT_EVENT& event, scriptcmd_list& list)
{
    // monsters/base_script_skills.script:77
    { auto& cmd = list.m_Cmds[0];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    return true;
}
static bool MatchBlock39(scriptcmd_list& list)
{
    if (list.m_Cmds.size() != 1) return false;
    { auto& cmd = list.m_Cmds[0];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "local", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    return true;
}
static bool RunBlock39(CScript& script, SCRIPT_EVENT& event, scriptcmd_list& list)
{
    // monsters/base_script_skills.script:78
    { auto& cmd = list.m_Cmds[0];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    return true;
}
static bool MatchBlock40(scriptcmd_list& list)
{
    if (list.m_Cmds.size() != 0) return false;
    return true;
}
static bool RunBlock40(CScript& script, SCRIPT_EVENT& event, scriptcmd_list& list)
{
    return true;
}
static bool MatchBlock37(scriptcmd_list& list)
{
    if (list.m_Cmds.size() != 6) return false;
    { auto& cmd = list.m_Cmds[0];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "local", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    { auto& cmd = list.m_Cmds[1];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "local", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    { auto& cmd = list.m_Cmds[2];
      if (!MatchCommand<&CScript::ScriptCmd_If>(cmd, "if()", 2, true, true, 0)) return false;
      if (!MatchBlock38(cmd.m_IfCmds)) return false;
    }
    { auto& cmd = list.m_Cmds[3];
      if (!MatchCommand<&CScript::ScriptCmd_If>(cmd, "if()", 2, true, true, 0)) return false;
      if (!MatchBlock39(cmd.m_IfCmds)) return false;
    }
    { auto& cmd = list.m_Cmds[4];
      if (!MatchCommand<&CScript::ScriptCmd_If>(cmd, "if", 2, true, false, 0)) return false;
      if (!MatchBlock40(cmd.m_IfCmds)) return false;
    }
    { auto& cmd = list.m_Cmds[5];
      if (!MatchCommand<&CScript::ScriptCmd_CallEvent>(cmd, "callevent", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    return true;
}
static bool RunBlock37(CScript& script, SCRIPT_EVENT& event, scriptcmd_list& list)
{
    // monsters/base_script_skills.script:75
    { auto& cmd = list.m_Cmds[0];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:76
    { auto& cmd = list.m_Cmds[1];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:77
    { auto& cmd = list.m_Cmds[2];
      const bool ok = Invoke<&CScript::ScriptCmd_If>(script, event, cmd);
      if (ok) RunBlock38(script, event, cmd.m_IfCmds);
      else {
      }
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:78
    { auto& cmd = list.m_Cmds[3];
      const bool ok = Invoke<&CScript::ScriptCmd_If>(script, event, cmd);
      if (ok) RunBlock39(script, event, cmd.m_IfCmds);
      else {
      }
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:79
    { auto& cmd = list.m_Cmds[4];
      const bool ok = Invoke<&CScript::ScriptCmd_If>(script, event, cmd);
      if (ok) RunBlock40(script, event, cmd.m_IfCmds);
      else {
          return true; // Original failed guard breaks this list, whose return is true.
      }
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:80
    { auto& cmd = list.m_Cmds[5];
      const bool ok = Invoke<&CScript::ScriptCmd_CallEvent>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    return true;
}
static bool MatchBlock42(scriptcmd_list& list)
{
    if (list.m_Cmds.size() != 0) return false;
    return true;
}
static bool RunBlock42(CScript& script, SCRIPT_EVENT& event, scriptcmd_list& list)
{
    return true;
}
static bool MatchBlock43(scriptcmd_list& list)
{
    if (list.m_Cmds.size() != 1) return false;
    { auto& cmd = list.m_Cmds[0];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "setvar", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    return true;
}
static bool RunBlock43(CScript& script, SCRIPT_EVENT& event, scriptcmd_list& list)
{
    // monsters/base_script_skills.script:85
    { auto& cmd = list.m_Cmds[0];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    return true;
}
static bool MatchBlock41(scriptcmd_list& list)
{
    if (list.m_Cmds.size() != 3) return false;
    { auto& cmd = list.m_Cmds[0];
      if (!MatchCommand<&CScript::ScriptCmd_If>(cmd, "if", 4, true, false, 0)) return false;
      if (!MatchBlock42(cmd.m_IfCmds)) return false;
    }
    { auto& cmd = list.m_Cmds[1];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "local", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    { auto& cmd = list.m_Cmds[2];
      if (!MatchCommand<&CScript::ScriptCmd_If>(cmd, "if()", 4, true, true, 0)) return false;
      if (!MatchBlock43(cmd.m_IfCmds)) return false;
    }
    return true;
}
static bool RunBlock41(CScript& script, SCRIPT_EVENT& event, scriptcmd_list& list)
{
    // monsters/base_script_skills.script:83
    { auto& cmd = list.m_Cmds[0];
      const bool ok = Invoke<&CScript::ScriptCmd_If>(script, event, cmd);
      if (ok) RunBlock42(script, event, cmd.m_IfCmds);
      else {
          return true; // Original failed guard breaks this list, whose return is true.
      }
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:84
    { auto& cmd = list.m_Cmds[1];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:85
    { auto& cmd = list.m_Cmds[2];
      const bool ok = Invoke<&CScript::ScriptCmd_If>(script, event, cmd);
      if (ok) RunBlock43(script, event, cmd.m_IfCmds);
      else {
      }
      if (event.bFullStop) return false;
    }
    return true;
}
static bool MatchBlock45(scriptcmd_list& list)
{
    if (list.m_Cmds.size() != 0) return false;
    return true;
}
static bool RunBlock45(CScript& script, SCRIPT_EVENT& event, scriptcmd_list& list)
{
    return true;
}
static bool MatchBlock44(scriptcmd_list& list)
{
    if (list.m_Cmds.size() != 3) return false;
    { auto& cmd = list.m_Cmds[0];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "local", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    { auto& cmd = list.m_Cmds[1];
      if (!MatchCommand<&CScript::ScriptCmd_If>(cmd, "if", 4, true, false, 0)) return false;
      if (!MatchBlock45(cmd.m_IfCmds)) return false;
    }
    { auto& cmd = list.m_Cmds[2];
      if (!MatchCommand<&CScript::ScriptCmd_CallEvent>(cmd, "callevent", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    return true;
}
static bool RunBlock44(CScript& script, SCRIPT_EVENT& event, scriptcmd_list& list)
{
    // monsters/base_script_skills.script:88
    { auto& cmd = list.m_Cmds[0];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:89
    { auto& cmd = list.m_Cmds[1];
      const bool ok = Invoke<&CScript::ScriptCmd_If>(script, event, cmd);
      if (ok) RunBlock45(script, event, cmd.m_IfCmds);
      else {
          return true; // Original failed guard breaks this list, whose return is true.
      }
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:90
    { auto& cmd = list.m_Cmds[2];
      const bool ok = Invoke<&CScript::ScriptCmd_CallEvent>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    return true;
}
static bool MatchBlock47(scriptcmd_list& list)
{
    if (list.m_Cmds.size() != 1) return false;
    { auto& cmd = list.m_Cmds[0];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "setvar", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    return true;
}
static bool RunBlock47(CScript& script, SCRIPT_EVENT& event, scriptcmd_list& list)
{
    // monsters/base_script_skills.script:95
    { auto& cmd = list.m_Cmds[0];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    return true;
}
static bool MatchBlock48(scriptcmd_list& list)
{
    if (list.m_Cmds.size() != 1) return false;
    { auto& cmd = list.m_Cmds[0];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "setvar", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    return true;
}
static bool RunBlock48(CScript& script, SCRIPT_EVENT& event, scriptcmd_list& list)
{
    // monsters/base_script_skills.script:96
    { auto& cmd = list.m_Cmds[0];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    return true;
}
static bool MatchBlock49(scriptcmd_list& list)
{
    if (list.m_Cmds.size() != 1) return false;
    { auto& cmd = list.m_Cmds[0];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "setvar", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    return true;
}
static bool RunBlock49(CScript& script, SCRIPT_EVENT& event, scriptcmd_list& list)
{
    // monsters/base_script_skills.script:97
    { auto& cmd = list.m_Cmds[0];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    return true;
}
static bool MatchBlock50(scriptcmd_list& list)
{
    if (list.m_Cmds.size() != 1) return false;
    { auto& cmd = list.m_Cmds[0];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "setvar", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    return true;
}
static bool RunBlock50(CScript& script, SCRIPT_EVENT& event, scriptcmd_list& list)
{
    // monsters/base_script_skills.script:98
    { auto& cmd = list.m_Cmds[0];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    return true;
}
static bool MatchBlock51(scriptcmd_list& list)
{
    if (list.m_Cmds.size() != 1) return false;
    { auto& cmd = list.m_Cmds[0];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "setvar", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    return true;
}
static bool RunBlock51(CScript& script, SCRIPT_EVENT& event, scriptcmd_list& list)
{
    // monsters/base_script_skills.script:99
    { auto& cmd = list.m_Cmds[0];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    return true;
}
static bool MatchBlock52(scriptcmd_list& list)
{
    if (list.m_Cmds.size() != 1) return false;
    { auto& cmd = list.m_Cmds[0];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "setvar", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    return true;
}
static bool RunBlock52(CScript& script, SCRIPT_EVENT& event, scriptcmd_list& list)
{
    // monsters/base_script_skills.script:100
    { auto& cmd = list.m_Cmds[0];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    return true;
}
static bool MatchBlock53(scriptcmd_list& list)
{
    if (list.m_Cmds.size() != 1) return false;
    { auto& cmd = list.m_Cmds[0];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "setvar", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    return true;
}
static bool RunBlock53(CScript& script, SCRIPT_EVENT& event, scriptcmd_list& list)
{
    // monsters/base_script_skills.script:101
    { auto& cmd = list.m_Cmds[0];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    return true;
}
static bool MatchBlock54(scriptcmd_list& list)
{
    if (list.m_Cmds.size() != 1) return false;
    { auto& cmd = list.m_Cmds[0];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "setvar", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    return true;
}
static bool RunBlock54(CScript& script, SCRIPT_EVENT& event, scriptcmd_list& list)
{
    // monsters/base_script_skills.script:102
    { auto& cmd = list.m_Cmds[0];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    return true;
}
static bool MatchBlock55(scriptcmd_list& list)
{
    if (list.m_Cmds.size() != 1) return false;
    { auto& cmd = list.m_Cmds[0];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "setvar", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    return true;
}
static bool RunBlock55(CScript& script, SCRIPT_EVENT& event, scriptcmd_list& list)
{
    // monsters/base_script_skills.script:103
    { auto& cmd = list.m_Cmds[0];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    return true;
}
static bool MatchBlock56(scriptcmd_list& list)
{
    if (list.m_Cmds.size() != 1) return false;
    { auto& cmd = list.m_Cmds[0];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "setvar", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    return true;
}
static bool RunBlock56(CScript& script, SCRIPT_EVENT& event, scriptcmd_list& list)
{
    // monsters/base_script_skills.script:104
    { auto& cmd = list.m_Cmds[0];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    return true;
}
static bool MatchBlock46(scriptcmd_list& list)
{
    if (list.m_Cmds.size() != 12) return false;
    { auto& cmd = list.m_Cmds[0];
      if (!MatchCommand<&CScript::ScriptCmd_TokenSet>(cmd, "token.set", 4, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    { auto& cmd = list.m_Cmds[1];
      if (!MatchCommand<&CScript::ScriptCmd_TokenSet>(cmd, "token.set", 4, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    { auto& cmd = list.m_Cmds[2];
      if (!MatchCommand<&CScript::ScriptCmd_If>(cmd, "if()", 4, true, true, 0)) return false;
      if (!MatchBlock47(cmd.m_IfCmds)) return false;
    }
    { auto& cmd = list.m_Cmds[3];
      if (!MatchCommand<&CScript::ScriptCmd_If>(cmd, "if()", 4, true, true, 0)) return false;
      if (!MatchBlock48(cmd.m_IfCmds)) return false;
    }
    { auto& cmd = list.m_Cmds[4];
      if (!MatchCommand<&CScript::ScriptCmd_If>(cmd, "if()", 4, true, true, 0)) return false;
      if (!MatchBlock49(cmd.m_IfCmds)) return false;
    }
    { auto& cmd = list.m_Cmds[5];
      if (!MatchCommand<&CScript::ScriptCmd_If>(cmd, "if()", 4, true, true, 0)) return false;
      if (!MatchBlock50(cmd.m_IfCmds)) return false;
    }
    { auto& cmd = list.m_Cmds[6];
      if (!MatchCommand<&CScript::ScriptCmd_If>(cmd, "if()", 4, true, true, 0)) return false;
      if (!MatchBlock51(cmd.m_IfCmds)) return false;
    }
    { auto& cmd = list.m_Cmds[7];
      if (!MatchCommand<&CScript::ScriptCmd_If>(cmd, "if()", 4, true, true, 0)) return false;
      if (!MatchBlock52(cmd.m_IfCmds)) return false;
    }
    { auto& cmd = list.m_Cmds[8];
      if (!MatchCommand<&CScript::ScriptCmd_If>(cmd, "if()", 4, true, true, 0)) return false;
      if (!MatchBlock53(cmd.m_IfCmds)) return false;
    }
    { auto& cmd = list.m_Cmds[9];
      if (!MatchCommand<&CScript::ScriptCmd_If>(cmd, "if()", 4, true, true, 0)) return false;
      if (!MatchBlock54(cmd.m_IfCmds)) return false;
    }
    { auto& cmd = list.m_Cmds[10];
      if (!MatchCommand<&CScript::ScriptCmd_If>(cmd, "if()", 4, true, true, 0)) return false;
      if (!MatchBlock55(cmd.m_IfCmds)) return false;
    }
    { auto& cmd = list.m_Cmds[11];
      if (!MatchCommand<&CScript::ScriptCmd_If>(cmd, "if()", 4, true, true, 0)) return false;
      if (!MatchBlock56(cmd.m_IfCmds)) return false;
    }
    return true;
}
static bool RunBlock46(CScript& script, SCRIPT_EVENT& event, scriptcmd_list& list)
{
    // monsters/base_script_skills.script:93
    { auto& cmd = list.m_Cmds[0];
      const bool ok = Invoke<&CScript::ScriptCmd_TokenSet>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:94
    { auto& cmd = list.m_Cmds[1];
      const bool ok = Invoke<&CScript::ScriptCmd_TokenSet>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:95
    { auto& cmd = list.m_Cmds[2];
      const bool ok = Invoke<&CScript::ScriptCmd_If>(script, event, cmd);
      if (ok) RunBlock47(script, event, cmd.m_IfCmds);
      else {
      }
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:96
    { auto& cmd = list.m_Cmds[3];
      const bool ok = Invoke<&CScript::ScriptCmd_If>(script, event, cmd);
      if (ok) RunBlock48(script, event, cmd.m_IfCmds);
      else {
      }
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:97
    { auto& cmd = list.m_Cmds[4];
      const bool ok = Invoke<&CScript::ScriptCmd_If>(script, event, cmd);
      if (ok) RunBlock49(script, event, cmd.m_IfCmds);
      else {
      }
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:98
    { auto& cmd = list.m_Cmds[5];
      const bool ok = Invoke<&CScript::ScriptCmd_If>(script, event, cmd);
      if (ok) RunBlock50(script, event, cmd.m_IfCmds);
      else {
      }
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:99
    { auto& cmd = list.m_Cmds[6];
      const bool ok = Invoke<&CScript::ScriptCmd_If>(script, event, cmd);
      if (ok) RunBlock51(script, event, cmd.m_IfCmds);
      else {
      }
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:100
    { auto& cmd = list.m_Cmds[7];
      const bool ok = Invoke<&CScript::ScriptCmd_If>(script, event, cmd);
      if (ok) RunBlock52(script, event, cmd.m_IfCmds);
      else {
      }
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:101
    { auto& cmd = list.m_Cmds[8];
      const bool ok = Invoke<&CScript::ScriptCmd_If>(script, event, cmd);
      if (ok) RunBlock53(script, event, cmd.m_IfCmds);
      else {
      }
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:102
    { auto& cmd = list.m_Cmds[9];
      const bool ok = Invoke<&CScript::ScriptCmd_If>(script, event, cmd);
      if (ok) RunBlock54(script, event, cmd.m_IfCmds);
      else {
      }
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:103
    { auto& cmd = list.m_Cmds[10];
      const bool ok = Invoke<&CScript::ScriptCmd_If>(script, event, cmd);
      if (ok) RunBlock55(script, event, cmd.m_IfCmds);
      else {
      }
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:104
    { auto& cmd = list.m_Cmds[11];
      const bool ok = Invoke<&CScript::ScriptCmd_If>(script, event, cmd);
      if (ok) RunBlock56(script, event, cmd.m_IfCmds);
      else {
      }
      if (event.bFullStop) return false;
    }
    return true;
}
static bool MatchBlock58(scriptcmd_list& list)
{
    if (list.m_Cmds.size() != 0) return false;
    return true;
}
static bool RunBlock58(CScript& script, SCRIPT_EVENT& event, scriptcmd_list& list)
{
    return true;
}
static bool MatchBlock57(scriptcmd_list& list)
{
    if (list.m_Cmds.size() != 2) return false;
    { auto& cmd = list.m_Cmds[0];
      if (!MatchCommand<&CScript::ScriptCmd_If>(cmd, "if", 4, true, false, 0)) return false;
      if (!MatchBlock58(cmd.m_IfCmds)) return false;
    }
    { auto& cmd = list.m_Cmds[1];
      if (!MatchCommand<&CScript::ScriptCmd_CallEvent>(cmd, "calleventloop", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    return true;
}
static bool RunBlock57(CScript& script, SCRIPT_EVENT& event, scriptcmd_list& list)
{
    // monsters/base_script_skills.script:107
    { auto& cmd = list.m_Cmds[0];
      const bool ok = Invoke<&CScript::ScriptCmd_If>(script, event, cmd);
      if (ok) RunBlock58(script, event, cmd.m_IfCmds);
      else {
          return true; // Original failed guard breaks this list, whose return is true.
      }
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:108
    { auto& cmd = list.m_Cmds[1];
      const bool ok = Invoke<&CScript::ScriptCmd_CallEvent>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    return true;
}
static bool MatchBlock60(scriptcmd_list& list)
{
    if (list.m_Cmds.size() != 1) return false;
    { auto& cmd = list.m_Cmds[0];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "setvar", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    return true;
}
static bool RunBlock60(CScript& script, SCRIPT_EVENT& event, scriptcmd_list& list)
{
    // monsters/base_script_skills.script:114
    { auto& cmd = list.m_Cmds[0];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    return true;
}
static bool MatchBlock61(scriptcmd_list& list)
{
    if (list.m_Cmds.size() != 1) return false;
    { auto& cmd = list.m_Cmds[0];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "setvar", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    return true;
}
static bool RunBlock61(CScript& script, SCRIPT_EVENT& event, scriptcmd_list& list)
{
    // monsters/base_script_skills.script:115
    { auto& cmd = list.m_Cmds[0];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    return true;
}
static bool MatchBlock62(scriptcmd_list& list)
{
    if (list.m_Cmds.size() != 1) return false;
    { auto& cmd = list.m_Cmds[0];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "setvar", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    return true;
}
static bool RunBlock62(CScript& script, SCRIPT_EVENT& event, scriptcmd_list& list)
{
    // monsters/base_script_skills.script:116
    { auto& cmd = list.m_Cmds[0];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    return true;
}
static bool MatchBlock63(scriptcmd_list& list)
{
    if (list.m_Cmds.size() != 1) return false;
    { auto& cmd = list.m_Cmds[0];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "setvar", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    return true;
}
static bool RunBlock63(CScript& script, SCRIPT_EVENT& event, scriptcmd_list& list)
{
    // monsters/base_script_skills.script:117
    { auto& cmd = list.m_Cmds[0];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    return true;
}
static bool MatchBlock64(scriptcmd_list& list)
{
    if (list.m_Cmds.size() != 1) return false;
    { auto& cmd = list.m_Cmds[0];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "setvar", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    return true;
}
static bool RunBlock64(CScript& script, SCRIPT_EVENT& event, scriptcmd_list& list)
{
    // monsters/base_script_skills.script:118
    { auto& cmd = list.m_Cmds[0];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    return true;
}
static bool MatchBlock65(scriptcmd_list& list)
{
    if (list.m_Cmds.size() != 1) return false;
    { auto& cmd = list.m_Cmds[0];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "setvar", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    return true;
}
static bool RunBlock65(CScript& script, SCRIPT_EVENT& event, scriptcmd_list& list)
{
    // monsters/base_script_skills.script:119
    { auto& cmd = list.m_Cmds[0];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    return true;
}
static bool MatchBlock66(scriptcmd_list& list)
{
    if (list.m_Cmds.size() != 1) return false;
    { auto& cmd = list.m_Cmds[0];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "setvar", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    return true;
}
static bool RunBlock66(CScript& script, SCRIPT_EVENT& event, scriptcmd_list& list)
{
    // monsters/base_script_skills.script:120
    { auto& cmd = list.m_Cmds[0];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    return true;
}
static bool MatchBlock67(scriptcmd_list& list)
{
    if (list.m_Cmds.size() != 1) return false;
    { auto& cmd = list.m_Cmds[0];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "setvar", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    return true;
}
static bool RunBlock67(CScript& script, SCRIPT_EVENT& event, scriptcmd_list& list)
{
    // monsters/base_script_skills.script:121
    { auto& cmd = list.m_Cmds[0];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    return true;
}
static bool MatchBlock68(scriptcmd_list& list)
{
    if (list.m_Cmds.size() != 1) return false;
    { auto& cmd = list.m_Cmds[0];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "setvar", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    return true;
}
static bool RunBlock68(CScript& script, SCRIPT_EVENT& event, scriptcmd_list& list)
{
    // monsters/base_script_skills.script:122
    { auto& cmd = list.m_Cmds[0];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    return true;
}
static bool MatchBlock69(scriptcmd_list& list)
{
    if (list.m_Cmds.size() != 1) return false;
    { auto& cmd = list.m_Cmds[0];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "setvar", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    return true;
}
static bool RunBlock69(CScript& script, SCRIPT_EVENT& event, scriptcmd_list& list)
{
    // monsters/base_script_skills.script:123
    { auto& cmd = list.m_Cmds[0];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    return true;
}
static bool MatchBlock70(scriptcmd_list& list)
{
    if (list.m_Cmds.size() != 2) return false;
    { auto& cmd = list.m_Cmds[0];
      if (!MatchCommand<&CScript::ScriptCmd_MathSet>(cmd, "divide", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    { auto& cmd = list.m_Cmds[1];
      if (!MatchCommand<&CScript::ScriptCmd_MathSet>(cmd, "multiply", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    return true;
}
static bool RunBlock70(CScript& script, SCRIPT_EVENT& event, scriptcmd_list& list)
{
    // monsters/base_script_skills.script:128
    { auto& cmd = list.m_Cmds[0];
      const bool ok = Invoke<&CScript::ScriptCmd_MathSet>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:129
    { auto& cmd = list.m_Cmds[1];
      const bool ok = Invoke<&CScript::ScriptCmd_MathSet>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    return true;
}
static bool MatchBlock71(scriptcmd_list& list)
{
    if (list.m_Cmds.size() != 1) return false;
    { auto& cmd = list.m_Cmds[0];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "setvar", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    return true;
}
static bool RunBlock71(CScript& script, SCRIPT_EVENT& event, scriptcmd_list& list)
{
    // monsters/base_script_skills.script:133
    { auto& cmd = list.m_Cmds[0];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    return true;
}
static bool MatchBlock59(scriptcmd_list& list)
{
    if (list.m_Cmds.size() != 19) return false;
    { auto& cmd = list.m_Cmds[0];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "local", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    { auto& cmd = list.m_Cmds[1];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "local", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    { auto& cmd = list.m_Cmds[2];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "local", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    { auto& cmd = list.m_Cmds[3];
      if (!MatchCommand<&CScript::ScriptCmd_If>(cmd, "if()", 4, true, true, 0)) return false;
      if (!MatchBlock60(cmd.m_IfCmds)) return false;
    }
    { auto& cmd = list.m_Cmds[4];
      if (!MatchCommand<&CScript::ScriptCmd_If>(cmd, "if()", 4, true, true, 0)) return false;
      if (!MatchBlock61(cmd.m_IfCmds)) return false;
    }
    { auto& cmd = list.m_Cmds[5];
      if (!MatchCommand<&CScript::ScriptCmd_If>(cmd, "if()", 4, true, true, 0)) return false;
      if (!MatchBlock62(cmd.m_IfCmds)) return false;
    }
    { auto& cmd = list.m_Cmds[6];
      if (!MatchCommand<&CScript::ScriptCmd_If>(cmd, "if()", 4, true, true, 0)) return false;
      if (!MatchBlock63(cmd.m_IfCmds)) return false;
    }
    { auto& cmd = list.m_Cmds[7];
      if (!MatchCommand<&CScript::ScriptCmd_If>(cmd, "if()", 4, true, true, 0)) return false;
      if (!MatchBlock64(cmd.m_IfCmds)) return false;
    }
    { auto& cmd = list.m_Cmds[8];
      if (!MatchCommand<&CScript::ScriptCmd_If>(cmd, "if()", 4, true, true, 0)) return false;
      if (!MatchBlock65(cmd.m_IfCmds)) return false;
    }
    { auto& cmd = list.m_Cmds[9];
      if (!MatchCommand<&CScript::ScriptCmd_If>(cmd, "if()", 4, true, true, 0)) return false;
      if (!MatchBlock66(cmd.m_IfCmds)) return false;
    }
    { auto& cmd = list.m_Cmds[10];
      if (!MatchCommand<&CScript::ScriptCmd_If>(cmd, "if()", 4, true, true, 0)) return false;
      if (!MatchBlock67(cmd.m_IfCmds)) return false;
    }
    { auto& cmd = list.m_Cmds[11];
      if (!MatchCommand<&CScript::ScriptCmd_If>(cmd, "if()", 4, true, true, 0)) return false;
      if (!MatchBlock68(cmd.m_IfCmds)) return false;
    }
    { auto& cmd = list.m_Cmds[12];
      if (!MatchCommand<&CScript::ScriptCmd_If>(cmd, "if()", 4, true, true, 0)) return false;
      if (!MatchBlock69(cmd.m_IfCmds)) return false;
    }
    { auto& cmd = list.m_Cmds[13];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "setvar", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    { auto& cmd = list.m_Cmds[14];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "local", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    { auto& cmd = list.m_Cmds[15];
      if (!MatchCommand<&CScript::ScriptCmd_If>(cmd, "if()", 4, true, true, 0)) return false;
      if (!MatchBlock70(cmd.m_IfCmds)) return false;
    }
    { auto& cmd = list.m_Cmds[16];
      if (!MatchCommand<&CScript::ScriptCmd_If>(cmd, "if()", 4, true, true, 0)) return false;
      if (!MatchBlock71(cmd.m_IfCmds)) return false;
    }
    { auto& cmd = list.m_Cmds[17];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "setvar", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    { auto& cmd = list.m_Cmds[18];
      if (!MatchCommand<&CScript::ScriptCmd_CallEvent>(cmd, "calleventloop", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    return true;
}
static bool RunBlock59(CScript& script, SCRIPT_EVENT& event, scriptcmd_list& list)
{
    // monsters/base_script_skills.script:111
    { auto& cmd = list.m_Cmds[0];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:112
    { auto& cmd = list.m_Cmds[1];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:113
    { auto& cmd = list.m_Cmds[2];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:114
    { auto& cmd = list.m_Cmds[3];
      const bool ok = Invoke<&CScript::ScriptCmd_If>(script, event, cmd);
      if (ok) RunBlock60(script, event, cmd.m_IfCmds);
      else {
      }
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:115
    { auto& cmd = list.m_Cmds[4];
      const bool ok = Invoke<&CScript::ScriptCmd_If>(script, event, cmd);
      if (ok) RunBlock61(script, event, cmd.m_IfCmds);
      else {
      }
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:116
    { auto& cmd = list.m_Cmds[5];
      const bool ok = Invoke<&CScript::ScriptCmd_If>(script, event, cmd);
      if (ok) RunBlock62(script, event, cmd.m_IfCmds);
      else {
      }
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:117
    { auto& cmd = list.m_Cmds[6];
      const bool ok = Invoke<&CScript::ScriptCmd_If>(script, event, cmd);
      if (ok) RunBlock63(script, event, cmd.m_IfCmds);
      else {
      }
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:118
    { auto& cmd = list.m_Cmds[7];
      const bool ok = Invoke<&CScript::ScriptCmd_If>(script, event, cmd);
      if (ok) RunBlock64(script, event, cmd.m_IfCmds);
      else {
      }
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:119
    { auto& cmd = list.m_Cmds[8];
      const bool ok = Invoke<&CScript::ScriptCmd_If>(script, event, cmd);
      if (ok) RunBlock65(script, event, cmd.m_IfCmds);
      else {
      }
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:120
    { auto& cmd = list.m_Cmds[9];
      const bool ok = Invoke<&CScript::ScriptCmd_If>(script, event, cmd);
      if (ok) RunBlock66(script, event, cmd.m_IfCmds);
      else {
      }
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:121
    { auto& cmd = list.m_Cmds[10];
      const bool ok = Invoke<&CScript::ScriptCmd_If>(script, event, cmd);
      if (ok) RunBlock67(script, event, cmd.m_IfCmds);
      else {
      }
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:122
    { auto& cmd = list.m_Cmds[11];
      const bool ok = Invoke<&CScript::ScriptCmd_If>(script, event, cmd);
      if (ok) RunBlock68(script, event, cmd.m_IfCmds);
      else {
      }
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:123
    { auto& cmd = list.m_Cmds[12];
      const bool ok = Invoke<&CScript::ScriptCmd_If>(script, event, cmd);
      if (ok) RunBlock69(script, event, cmd.m_IfCmds);
      else {
      }
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:124
    { auto& cmd = list.m_Cmds[13];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:125
    { auto& cmd = list.m_Cmds[14];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:126
    { auto& cmd = list.m_Cmds[15];
      const bool ok = Invoke<&CScript::ScriptCmd_If>(script, event, cmd);
      if (ok) RunBlock70(script, event, cmd.m_IfCmds);
      else {
      }
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:131
    { auto& cmd = list.m_Cmds[16];
      const bool ok = Invoke<&CScript::ScriptCmd_If>(script, event, cmd);
      if (ok) RunBlock71(script, event, cmd.m_IfCmds);
      else {
      }
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:135
    { auto& cmd = list.m_Cmds[17];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:136
    { auto& cmd = list.m_Cmds[18];
      const bool ok = Invoke<&CScript::ScriptCmd_CallEvent>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    return true;
}
static bool MatchBlock72(scriptcmd_list& list)
{
    if (list.m_Cmds.size() != 9) return false;
    { auto& cmd = list.m_Cmds[0];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "local", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    { auto& cmd = list.m_Cmds[1];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "local", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    { auto& cmd = list.m_Cmds[2];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "local", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    { auto& cmd = list.m_Cmds[3];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "local", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    { auto& cmd = list.m_Cmds[4];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "local", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    { auto& cmd = list.m_Cmds[5];
      if (!MatchCommand<&CScript::ScriptCmd_MathSet>(cmd, "divide", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    { auto& cmd = list.m_Cmds[6];
      if (!MatchCommand<&CScript::ScriptCmd_SetVar>(cmd, "local", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    { auto& cmd = list.m_Cmds[7];
      if (!MatchCommand<&CScript::ScriptCmd_MathSet>(cmd, "multiply", 3, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    { auto& cmd = list.m_Cmds[8];
      if (!MatchCommand<nullptr>(cmd, "learnskill", 4, false, false, 0)) return false;
      if (cmd.m_IfCmds.m_Cmds.size()) return false;
    }
    return true;
}
static bool RunBlock72(CScript& script, SCRIPT_EVENT& event, scriptcmd_list& list)
{
    // monsters/base_script_skills.script:139
    { auto& cmd = list.m_Cmds[0];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:140
    { auto& cmd = list.m_Cmds[1];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:141
    { auto& cmd = list.m_Cmds[2];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:142
    { auto& cmd = list.m_Cmds[3];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:143
    { auto& cmd = list.m_Cmds[4];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:144
    { auto& cmd = list.m_Cmds[5];
      const bool ok = Invoke<&CScript::ScriptCmd_MathSet>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:145
    { auto& cmd = list.m_Cmds[6];
      const bool ok = Invoke<&CScript::ScriptCmd_SetVar>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:146
    { auto& cmd = list.m_Cmds[7];
      const bool ok = Invoke<&CScript::ScriptCmd_MathSet>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    // monsters/base_script_skills.script:147
    { auto& cmd = list.m_Cmds[8];
      const bool ok = Invoke<nullptr>(script, event, cmd);
      (void)ok; // Ordinary handler failure does not terminate the list.
      if (event.bFullStop) return false;
    }
    return true;
}
static bool TryEvent(CScript& script, SCRIPT_EVENT& event, bool& result)
{
    if (MatchBlock0(event.Commands)) { result = RunBlock0(script, event, event.Commands); return true; }
    if (MatchBlock1(event.Commands)) { result = RunBlock1(script, event, event.Commands); return true; }
    if (MatchBlock2(event.Commands)) { result = RunBlock2(script, event, event.Commands); return true; }
    if (MatchBlock5(event.Commands)) { result = RunBlock5(script, event, event.Commands); return true; }
    if (MatchBlock6(event.Commands)) { result = RunBlock6(script, event, event.Commands); return true; }
    if (MatchBlock7(event.Commands)) { result = RunBlock7(script, event, event.Commands); return true; }
    if (MatchBlock8(event.Commands)) { result = RunBlock8(script, event, event.Commands); return true; }
    if (MatchBlock9(event.Commands)) { result = RunBlock9(script, event, event.Commands); return true; }
    if (MatchBlock37(event.Commands)) { result = RunBlock37(script, event, event.Commands); return true; }
    if (MatchBlock41(event.Commands)) { result = RunBlock41(script, event, event.Commands); return true; }
    if (MatchBlock44(event.Commands)) { result = RunBlock44(script, event, event.Commands); return true; }
    if (MatchBlock46(event.Commands)) { result = RunBlock46(script, event, event.Commands); return true; }
    if (MatchBlock57(event.Commands)) { result = RunBlock57(script, event, event.Commands); return true; }
    if (MatchBlock59(event.Commands)) { result = RunBlock59(script, event, event.Commands); return true; }
    if (MatchBlock72(event.Commands)) { result = RunBlock72(script, event, event.Commands); return true; }
    return false;
}
}
