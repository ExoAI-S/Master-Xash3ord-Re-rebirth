#pragma once
#include <cstring>

namespace MSRNativePilot
{
using Handler = bool(CScript::*)(SCRIPT_EVENT&, scriptcmd_t&, msstringlist&);

template<Handler Function>
bool MatchCommand(scriptcmd_t& cmd, const char* name, unsigned count,
                  bool conditional, bool newConditional, unsigned elseCount)
{
    if (cmd.m_Params.size()!=count || std::strcmp(cmd.Name().c_str(),name) ||
        cmd.m_Conditional!=conditional || cmd.m_NewConditional!=newConditional ||
        cmd.m_ElseCmds.size()!=elseCount) return false;
    const auto found = CScript::m_GlobalCmdHash.find(cmd.Name());
    if constexpr (Function == nullptr) return found == CScript::m_GlobalCmdHash.end();
    return found != CScript::m_GlobalCmdHash.end() && found->second.GetFunc()==Function;
}

template<Handler Function>
bool Invoke(CScript& script, SCRIPT_EVENT& event, scriptcmd_t& cmd)
{
    msstringlist parameters;
    for (unsigned i=1;i<cmd.m_Params.size();++i)
        parameters.add(script.GetVar(event.GetLocal(cmd.m_Params[i])));
    bool parentSuccess=false;
    if (script.m.pScriptedEnt)
        parentSuccess=script.m.pScriptedInterface->Script_ExecuteCmd(&script,event,cmd,parameters);
    if (parentSuccess || event.bFullStop) return parentSuccess;
    if constexpr (Function != nullptr) return (script.*Function)(event,cmd,parameters);
    return true;
}
}
