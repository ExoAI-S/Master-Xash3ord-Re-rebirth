// Persistent world state. See msr_worldstate.h.

#include "msdllheaders.h"
#include "global.h"
#include "script.h"
#include "svglobals.h"
#include "msr_worldstate.h"
#include "fn/FNSharedDefs.h"
#include "fn/RequestManager.h"
#include "fn/WorldStateReq.h"

#include <rapidjson/document.h>
#include <rapidjson/stringbuffer.h>
#include <rapidjson/writer.h>

#include <algorithm>
#include <cctype>
#include <chrono>
#include <cmath>
#include <cstdarg>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <map>
#include <memory>
#include <string>
#include <utility>
#include <vector>

namespace
{
struct entry_t
{
	std::string value;
	double expires = 0;			// wall clock (epoch seconds); 0 = never
	bool dirty = false;			// changed here since FN last confirmed it
	bool pendingDelete = false;	// unset here; the entry goes once FN confirms
	unsigned long change = 0;	// bumped by every local change: a reply clears only the change it carried
	bool additive = false;		// only "add"s here while FN's copy was not in: the merge adds them to FN's value
	long addDelta = 0;
};
typedef std::map<std::string, entry_t> keymap_t;				  // ordered: listings and prefix dumps come out sorted
typedef std::vector<std::pair<std::string, unsigned long>> sentlist_t; // key, change

keymap_t g_Keys;
unsigned long g_Changes = 0;

std::string g_Realm, g_Map;
bool g_Active = false;	 // a map's world is open (MapStart .. MapEnd); writes outside it are dropped
bool g_FN = false;		 // FN was on when the map started
bool g_Synced = false;	 // FN's keys are in: changes may be sent
bool g_Disabled = false; // no FN sync for this map (old FN, a name FN can't take, load refused)

// Replies carry the generation they were sent in. MapStart and MapEnd bump it, so a reply for
// an older map (the request queue also drains during the next map's load) is ignored.
unsigned int g_Generation = 0;
unsigned int g_Serial = 0;

bool g_WriteInFlight = false;
unsigned int g_WriteSerial = 0;
sentlist_t g_WriteSent;
double g_NextWrite = 0; // steady clock seconds
double g_Backoff = 1;

bool g_LoadInFlight = false;
unsigned int g_LoadSerial = 0;
double g_NextLoad = 0;
double g_MapStartedAt = 0; // steady clock seconds; bounds Pending()

// game_worldstate_loaded also goes to the game master, which ServerActivate only creates after
// the world script got the event.
int g_EventSeq = 0, g_GMEventSeq = 0;
std::string g_EventSource;
double g_GMNextTry = 0, g_GMGiveUp = 0;

double g_NextTick = 0, g_NextPrune = 0;
bool g_Told404 = false;

constexpr size_t kMaxValueBytes = 255;		 // FN's limit, and a script string's
constexpr size_t kMaxKeys = 4096;			 // FN's live keys per world
constexpr size_t kMaxBatchOps = 256;		 // FN's operations per batch
constexpr size_t kMaxBatchBytes = 60 * 1024; // FN takes bodies up to 72 KB
constexpr double kMaxTTL = 30.0 * 24 * 3600; // FN's longest ttl
constexpr double kLoadRetry = 30;			 // seconds between loads after a failed one
constexpr double kMaxBackoff = 60;

// Always printed (dedicated console and -log file), unlike ALERT(at_console).
void Log(const char *fmt, ...)
{
	char text[1024];
	va_list args;
	va_start(args, fmt);
	vsnprintf(text, sizeof(text), fmt, args);
	va_end(args);
	g_engfuncs.pfnServerPrint(text);
}

// Scheduling uses a monotonic clock; expiry uses the wall clock (it must survive restarts).
double Steady()
{
	return std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count();
}

bool Expired(const entry_t &e, double now) { return e.expires > 0 && e.expires <= now; }
bool Live(const entry_t &e, double now) { return !e.pendingDelete && !Expired(e, now); }

// Length of the valid UTF-8 sequence at p, 0 if invalid (FN rejects the whole batch for one bad value)
int Utf8Len(const unsigned char *p)
{
	const unsigned char c = p[0];
	if (c < 0x80)
		return 1;
	int n;
	unsigned char lo = 0x80, hi = 0xBF;
	if (c >= 0xC2 && c <= 0xDF)
		n = 2;
	else if (c >= 0xE0 && c <= 0xEF)
	{
		n = 3;
		if (c == 0xE0) lo = 0xA0;	   // overlong
		else if (c == 0xED) hi = 0x9F; // surrogates
	}
	else if (c >= 0xF0 && c <= 0xF4)
	{
		n = 4;
		if (c == 0xF0) lo = 0x90;
		else if (c == 0xF4) hi = 0x8F;
	}
	else
		return 0;
	if (p[1] < lo || p[1] > hi) // also stops at the terminator
		return 0;
	for (int i = 2; i < n; i++)
		if ((p[i] & 0xC0) != 0x80)
			return 0;
	return n;
}

// At most kMaxValueBytes of valid UTF-8; bad bytes become '?'
std::string CleanValue(const char *text)
{
	std::string out;
	const unsigned char *p = (const unsigned char *)(text ? text : "");
	while (*p)
	{
		const int n = Utf8Len(p);
		if (out.size() + (n ? n : 1) > kMaxValueBytes)
			break;
		if (n)
			out.append((const char *)p, n);
		else
			out += '?';
		p += n ? n : 1;
	}
	return out;
}

// ms_realm, lowercased to [a-z0-9_-] (starting alphanumeric, as FN wants), at most 32 chars.
// Empty: "port<hostport>", so two servers on one FN never share a world by accident.
std::string RealmName()
{
	std::string realm;
	const char *cvar = CVAR_GET_STRING("ms_realm");
	for (const char *c = cvar ? cvar : ""; *c && realm.size() < 32; c++)
	{
		const char ch = (char)tolower((unsigned char)*c);
		if ((ch >= 'a' && ch <= 'z') || (ch >= '0' && ch <= '9') || ((ch == '_' || ch == '-') && !realm.empty()))
			realm += ch;
	}
	if (realm.empty())
	{
		int port = (int)CVAR_GET_FLOAT("hostport");
		if (port <= 0)
			port = 27015;
		realm = "port" + std::to_string(port);
	}
	return realm;
}

// What FN accepts as a map name (it stores it lowercased)
bool ValidMapName(const std::string &map)
{
	if (map.empty() || map.size() > 32)
		return false;
	for (char c : map)
		if (!((c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') || c == '_' || c == '-'))
			return false;
	return true;
}

std::string WorldUrl()
{
	return "/api/v2/internal/world/" + g_Realm + "/" + g_Map;
}

const char *StateName()
{
	if (!g_Active) return "no map";
	if (!g_FN) return "in memory (FN off)";
	if (g_Disabled) return "in memory (no FN world sync)";
	if (!g_Synced) return "in memory (FN unreachable, retrying)";
	return "online";
}

size_t CountDirty()
{
	size_t n = 0;
	for (const auto &kv : g_Keys)
		if (kv.second.dirty)
			n++;
	return n;
}

bool AnyDirty()
{
	for (const auto &kv : g_Keys)
		if (kv.second.dirty)
			return true;
	return false;
}

// FN's error text for the log ({"status":false,"code":400,"error":"..."}), else the start of the body
std::string ReplyError(const std::string &body)
{
	JSONDocument doc = HTTPRequest::ParseJSON(body.c_str());
	if (doc.IsObject())
	{
		auto err = doc.FindMember("error");
		if (err != doc.MemberEnd() && err->value.IsString())
			return std::string(err->value.GetString()).substr(0, 200);
	}
	return body.substr(0, 120);
}

// {"data":{"now":..,"keys":{k:{"value":str,"expires_in":sec|null,"rev":n}}}}
bool ParseKeys(const std::string &body, keymap_t &out)
{
	JSONDocument doc = HTTPRequest::ParseJSON(body.c_str());
	if (!doc.IsObject())
		return false;
	auto data = doc.FindMember("data");
	if (data == doc.MemberEnd() || !data->value.IsObject())
		return false;
	auto keys = data->value.FindMember("keys");
	if (keys == data->value.MemberEnd() || !keys->value.IsObject())
		return false;

	const double now = WorldState::Now();
	for (auto m = keys->value.MemberBegin(); m != keys->value.MemberEnd(); ++m)
	{
		const char *key = m->name.GetString();
		if (!m->value.IsObject() || !WorldState::ValidKey(key, true))
			continue;
		auto value = m->value.FindMember("value");
		if (value == m->value.MemberEnd() || !value->value.IsString())
			continue;
		entry_t e;
		e.value = CleanValue(value->value.GetString());
		auto left = m->value.FindMember("expires_in");
		if (left != m->value.MemberEnd() && left->value.IsNumber())
		{
			if (left->value.GetDouble() <= 0)
				continue;
			e.expires = now + left->value.GetDouble(); // relative on the wire: no clock skew with FN
		}
		out[key] = std::move(e);
	}
	return true;
}

// FN's values replace everything not changed here since; changes made here win and go out next.
void Merge(keymap_t &loaded)
{
	for (auto it = g_Keys.begin(); it != g_Keys.end();)
		if (!it->second.dirty)
			it = g_Keys.erase(it);
		else
			++it;
	for (auto &kv : g_Keys)
		if (kv.second.additive)
		{
			// Counted here before FN's value was known: count on top of it
			auto l = loaded.find(kv.first);
			if (l != loaded.end())
				kv.second.value = std::to_string(atol(l->second.value.c_str()) + kv.second.addDelta);
			kv.second.additive = false;
			kv.second.addDelta = 0;
		}
	for (auto &kv : loaded)
		if (g_Keys.find(kv.first) == g_Keys.end())
			g_Keys.emplace(kv.first, std::move(kv.second));
}

void LoadBlocking(int &code, std::string &body)
{
	std::unique_ptr<WorldStateRequest> req(new WorldStateRequest(WorldUrl().c_str(), NULL, NULL, 0, 0));
	FNShared::SendBlocking(req.get());
	code = req->m_iRespCode;
	body.swap(req->m_sResponseBody);
}

// True when FN's keys are in now. quiet: a repeat attempt, log only what changes.
bool HandleLoad(int code, const std::string &body, bool quiet)
{
	if (code == 200)
	{
		keymap_t loaded;
		if (ParseKeys(body, loaded))
		{
			const unsigned int count = (unsigned int)loaded.size();
			Merge(loaded);
			g_Synced = true;
			g_Backoff = 1;
			g_NextWrite = Steady() + 1;
			Log("MSR: worldstate %s/%s: %u keys loaded from FN\n", g_Realm.c_str(), g_Map.c_str(), count);
			return true;
		}
		if (!quiet)
			Log("MSR: worldstate %s/%s: malformed world from FN; in memory, retrying every %.0f s\n", g_Realm.c_str(), g_Map.c_str(), kLoadRetry);
	}
	else if (code == 404)
	{
		// An fn_server.py from before world state: nothing to retry
		g_Disabled = true;
		if (!g_Told404)
			Log("MSR: worldstate: FN has no world endpoint (older fn_server.py); world state stays in memory per map\n");
		g_Told404 = true;
		return false;
	}
	else if (code >= 400 && code < 500 && code != 401 && code != 403 && code != 408 && code != 429)
	{
		g_Disabled = true;
		Log("MSR: worldstate %s/%s: FN refused the world (HTTP %d: %s); in memory for this map\n", g_Realm.c_str(), g_Map.c_str(), code, ReplyError(body).c_str());
		return false;
	}
	else if (!quiet)
		Log("MSR: worldstate %s/%s: FN load failed (HTTP %d); in memory, retrying every %.0f s\n", g_Realm.c_str(), g_Map.c_str(), code, kLoadRetry);
	g_NextLoad = Steady() + kLoadRetry;
	return false;
}

// Tell the scripts the world's keys are known (source: fn, offline or retry). World script now,
// the game master from Frame once it exists.
void Fire(const char *source)
{
	g_EventSource = source;
	g_EventSeq++;
	g_GMNextTry = g_GMGiveUp = 0;
	if (MSGlobals::GameScript)
	{
		msstringlist params;
		params.add(source);
		MSGlobals::GameScript->CallScriptEvent("game_worldstate_loaded", &params);
	}
}

void NotifyGameMaster(double now)
{
	if (g_GMEventSeq == g_EventSeq || !g_serveractive || now < g_GMNextTry)
		return;
	if (!g_GMGiveUp)
		g_GMGiveUp = now + 60; // maps without a game master (AngelScript setups)
	else if (now > g_GMGiveUp)
	{
		g_GMEventSeq = g_EventSeq;
		return;
	}
	g_GMNextTry = now + 1;
	// Looked up by name each time rather than trusting a cached pointer
	CBaseEntity *pGameMaster = UTIL_FindEntityByString(NULL, "netname", "-game_master");
	IScripted *pScripted = pGameMaster ? pGameMaster->GetScripted() : NULL;
	if (!pScripted)
		return;
	g_GMEventSeq = g_EventSeq;
	msstringlist params;
	params.add(g_EventSource.c_str());
	pScripted->CallScriptEvent("game_worldstate_loaded", &params);
}

// {"set":{k:{"value":v,"ttl":sec|null}},"del":[k,..]} from the dirty keys, within FN's batch limits.
// An entry that expired before FN heard of it goes out as a delete (FN's older copy must not return).
std::string BuildBatch(sentlist_t &sent)
{
	const double now = WorldState::Now();
	rapidjson::StringBuffer buffer;
	rapidjson::Writer<rapidjson::StringBuffer> writer(buffer);
	std::vector<const std::string *> dels;
	size_t bytes = 32;

	writer.StartObject();
	writer.Key("set");
	writer.StartObject();
	for (const auto &kv : g_Keys)
	{
		const entry_t &e = kv.second;
		if (!e.dirty)
			continue;
		const size_t cost = kv.first.size() * 2 + e.value.size() * 6 + 48; // escaped worst case
		if (sent.size() >= kMaxBatchOps || (!sent.empty() && bytes + cost > kMaxBatchBytes))
			break; // the rest go in the next batch
		bytes += cost;
		sent.push_back(std::make_pair(kv.first, e.change));
		if (e.pendingDelete || Expired(e, now))
		{
			dels.push_back(&kv.first);
			continue;
		}
		writer.Key(kv.first.c_str(), (rapidjson::SizeType)kv.first.size());
		writer.StartObject();
		writer.Key("value");
		writer.String(e.value.c_str(), (rapidjson::SizeType)e.value.size());
		writer.Key("ttl");
		if (e.expires > 0)
			writer.Int64((int64_t)std::min(kMaxTTL, std::max(1.0, std::ceil(e.expires - now))));
		else
			writer.Null();
		writer.EndObject();
	}
	writer.EndObject();
	writer.Key("del");
	writer.StartArray();
	for (const std::string *key : dels)
		writer.String(key->c_str(), (rapidjson::SizeType)key->size());
	writer.EndArray();
	writer.EndObject();
	return std::string(buffer.GetString(), buffer.GetSize());
}

// FN has these: dirty no more, unless changed again since the batch left
void ClearSent(const sentlist_t &sent)
{
	const double now = WorldState::Now();
	for (const auto &s : sent)
	{
		auto it = g_Keys.find(s.first);
		if (it == g_Keys.end() || it->second.change != s.second)
			continue;
		if (it->second.pendingDelete || Expired(it->second, now))
			g_Keys.erase(it);
		else
			it->second.dirty = false;
	}
}

// True when the batch left the dirty set (stored, or refused for good)
bool HandleWrite(const sentlist_t &sent, int code, const std::string &body)
{
	if (code >= 200 && code < 300)
	{
		ClearSent(sent);
		if (g_Backoff > 1)
			Log("MSR: worldstate %s/%s: FN writes resumed\n", g_Realm.c_str(), g_Map.c_str());
		g_Backoff = 1;
		return true;
	}
	if (code == 404)
	{
		g_Disabled = true;
		Log("MSR: worldstate %s/%s: FN has no world endpoint any more; changes stay in memory for this map\n", g_Realm.c_str(), g_Map.c_str());
		return false;
	}
	if (code == 400 || code == 413 || code == 422)
	{
		// Retrying the same batch would fail forever
		Log("MSR: worldstate %s/%s: FN refused %u changes (HTTP %d: %s); dropped\n", g_Realm.c_str(), g_Map.c_str(), (unsigned int)sent.size(), code, ReplyError(body).c_str());
		ClearSent(sent);
		return true;
	}
	// Transport failure (0), dropped unsent (-1), 5xx, auth: keep them dirty and back off
	Log("MSR: worldstate %s/%s: FN write failed (HTTP %d); retrying in %.0f s\n", g_Realm.c_str(), g_Map.c_str(), code, g_Backoff);
	g_NextWrite = Steady() + g_Backoff;
	g_Backoff = std::min(g_Backoff * 2, kMaxBackoff);
	return false;
}

void OnWriteReply(unsigned int generation, unsigned int serial, int code, const std::string &body)
{
	if (generation != g_Generation || !g_WriteInFlight || serial != g_WriteSerial)
		return; // an older map's or batch's: MapEnd already flushed those keys itself
	g_WriteInFlight = false;
	sentlist_t sent;
	sent.swap(g_WriteSent);
	HandleWrite(sent, code, body);
}

void SendAsync()
{
	sentlist_t sent;
	const std::string json = BuildBatch(sent);
	if (sent.empty())
		return;
	g_WriteSent.swap(sent);
	g_WriteSerial = ++g_Serial;
	g_WriteInFlight = true;
	g_NextWrite = Steady() + 1; // at most one batch a second
	// A refused request reports back (-1) from its destructor before this returns
	g_FNRequestManager.QueueRequest(new WorldStateRequest(WorldUrl().c_str(), json.c_str(), OnWriteReply, g_Generation, g_WriteSerial));
}

// Every change now, batch after batch, waiting for each reply. False when some stay unsaved.
bool FlushBlocking()
{
	for (int batches = 0; batches < 64 && g_Synced && !g_Disabled; batches++)
	{
		sentlist_t sent;
		const std::string json = BuildBatch(sent);
		if (sent.empty())
			return true;
		std::unique_ptr<WorldStateRequest> req(new WorldStateRequest(WorldUrl().c_str(), json.c_str(), NULL, 0, 0));
		FNShared::SendBlocking(req.get());
		if (!HandleWrite(sent, req->m_iRespCode, req->m_sResponseBody))
			return false;
	}
	return !AnyDirty();
}

void OnLoadReply(unsigned int generation, unsigned int serial, int code, const std::string &body)
{
	if (generation != g_Generation || !g_LoadInFlight || serial != g_LoadSerial)
		return;
	g_LoadInFlight = false;
	if (g_Synced || g_Disabled)
		return;
	if (HandleLoad(code, body, true))
		Fire("retry");
}

void StartLoad()
{
	g_LoadSerial = ++g_Serial;
	g_LoadInFlight = true;
	g_NextLoad = Steady() + kLoadRetry;
	g_FNRequestManager.QueueRequest(new WorldStateRequest(WorldUrl().c_str(), NULL, OnLoadReply, g_Generation, g_LoadSerial));
}

// Expired or deleted keys FN needs no word about (or never will: no sync this map)
void Prune()
{
	const double now = WorldState::Now();
	const bool neverSent = !g_FN || g_Disabled;
	for (auto it = g_Keys.begin(); it != g_Keys.end();)
		if ((!it->second.dirty || neverSent) && !Live(it->second, now))
			it = g_Keys.erase(it);
		else
			++it;
}

void ResetWorld()
{
	g_Keys.clear();
	g_Active = g_FN = g_Synced = g_Disabled = false;
	g_WriteInFlight = g_LoadInFlight = false;
	g_WriteSent.clear();
	g_NextWrite = g_NextLoad = g_NextTick = g_NextPrune = 0;
	g_Backoff = 1;
	g_GMEventSeq = g_EventSeq; // nothing pending for the game master
	g_GMNextTry = g_GMGiveUp = 0;
}

void List(const char *prefix)
{
	const double now = WorldState::Now();
	size_t live = 0;
	for (const auto &kv : g_Keys)
		if (Live(kv.second, now))
			live++;
	Log("MSR: worldstate %s/%s: %s, %u keys, %u unsaved changes\n", g_Realm.empty() ? "-" : g_Realm.c_str(), g_Map.empty() ? "-" : g_Map.c_str(),
		StateName(), (unsigned int)live, (unsigned int)CountDirty());
	const std::string start = prefix ? prefix : "";
	for (auto it = g_Keys.lower_bound(start); it != g_Keys.end() && it->first.compare(0, start.size(), start) == 0; ++it)
	{
		const entry_t &e = it->second;
		const bool gone = !Live(e, now);
		if (gone && (!e.dirty || !g_FN || g_Disabled)) // shown only while FN still has to hear of it
			continue;
		char left[32];
		if (gone)
			snprintf(left, sizeof(left), "deleted");
		else if (e.expires > 0)
			snprintf(left, sizeof(left), "%.0f s left", std::ceil(e.expires - now));
		else
			snprintf(left, sizeof(left), "permanent");
		Log("  %s = \"%s\" (%s)%s\n", it->first.c_str(), gone ? "" : e.value.c_str(), left, e.dirty ? " unsaved" : "");
	}
}

void ReloadCommand()
{
	if (!g_FN || g_Disabled)
	{
		Log("MSR: worldstate %s/%s is %s: nothing to reload\n", g_Realm.c_str(), g_Map.c_str(), StateName());
		return;
	}
	const bool wasSynced = g_Synced;
	g_LoadInFlight = false; // a retry still out is superseded
	int code = 0;
	std::string body;
	LoadBlocking(code, body);
	if (HandleLoad(code, body, false) && !wasSynced)
		Fire("retry");
}

void FlushCommand()
{
	if (!g_FN || g_Disabled || !g_Synced)
	{
		Log("MSR: worldstate %s/%s is %s: nothing sent\n", g_Realm.c_str(), g_Map.c_str(), StateName());
		return;
	}
	// The batch on the wire first, so the flush cannot be overtaken by it
	if (g_WriteInFlight)
		g_FNRequestManager.Drain();
	const size_t before = CountDirty();
	const bool ok = FlushBlocking();
	Log("MSR: worldstate %s/%s: %u of %u changes saved\n", g_Realm.c_str(), g_Map.c_str(), (unsigned int)(before - std::min(before, CountDirty())),
		(unsigned int)before);
	if (!ok)
		Log("MSR: worldstate: the rest stay unsaved (see above) and are retried\n");
}

// "msr_worldstate [list [prefix] | set <key> <value> [ttl] | del <key> | reload | flush]" (admins
// may use the reserved boss./logout./sys. keys)
void Command()
{
	const std::string sub = CMD_ARGC() > 1 ? CMD_ARGV(1) : "list";
	if (sub == "list")
	{
		const std::string prefix = CMD_ARGC() > 2 ? CMD_ARGV(2) : "";
		List(prefix.c_str());
		return;
	}
	if ((sub == "set" && CMD_ARGC() > 3) || ((sub == "del" || sub == "unset") && CMD_ARGC() > 2))
	{
		const std::string key = CMD_ARGV(2);
		if (!g_Active)
			Log("MSR: worldstate: no map is running\n");
		else if (!WorldState::ValidKey(key.c_str(), true))
			Log("MSR: worldstate: bad key '%s' (lowercase a-z 0-9 _ . : -, up to 64, no global./local./game./const.)\n", key.c_str());
		else if (sub == "set")
		{
			const std::string value = CMD_ARGV(3);
			WorldState::Set(key.c_str(), value.c_str(), CMD_ARGC() > 4 ? atof(CMD_ARGV(4)) : -1);
			const double left = WorldState::TimeLeft(key.c_str());
			Log("MSR: worldstate %s = \"%s\" (%s)\n", key.c_str(), value.c_str(), left < 0 ? "permanent" : UTIL_VarArgs("%.0f s", std::ceil(left)));
		}
		else
		{
			WorldState::Unset(key.c_str());
			Log("MSR: worldstate %s unset\n", key.c_str());
		}
		return;
	}
	if (sub == "reload")
		ReloadCommand();
	else if (sub == "flush")
		FlushCommand();
	else
		Log("usage: msr_worldstate [list [prefix] | set <key> <value> [ttl] | del <key> | reload | flush]\n");
}
} // namespace

// "worldstate dump [prefix]" in scripts (scriptcmds.cpp)
void MSR_WorldStateDump(const char *prefix)
{
	List(prefix);
}

namespace WorldState
{
void Init()
{
	g_engfuncs.pfnAddServerCommand((char *)"msr_worldstate", Command);
}

void MapStart()
{
	ResetWorld(); // a world left open (no MapEnd) must not leak into this map
	g_Generation++;
	g_Realm = RealmName();
	g_Map = STRING(gpGlobals->mapname);
	std::transform(g_Map.begin(), g_Map.end(), g_Map.begin(), [](char c) { return (char)tolower((unsigned char)c); });
	g_Active = true;
	g_MapStartedAt = Steady();
	g_FN = FNShared::IsEnabled();
	if (!g_FN)
		Log("MSR: worldstate %s/%s: FN off, kept in memory for this map\n", g_Realm.c_str(), g_Map.c_str());
	else if (!ValidMapName(g_Map))
	{
		g_Disabled = true;
		Log("MSR: worldstate %s/%s: FN can't store a world under this map name; in memory for this map\n", g_Realm.c_str(), g_Map.c_str());
	}
	else
	{
		// Blocking, like the validation just before it: every entity after worldspawn spawns
		// with the world's keys known.
		int code = 0;
		std::string body;
		LoadBlocking(code, body);
		HandleLoad(code, body, false);
	}
	Fire(g_Synced ? "fn" : "offline");
}

void MapEnd()
{
	// Replies still out now belong to the old world: ignored, their keys stay dirty for the flush
	g_Generation++;
	g_WriteInFlight = g_LoadInFlight = false;
	g_WriteSent.clear();

	// Requests already on the wire (a batch, the saves MSGameEnd just queued) finish first,
	// so nothing older can land after the final flush. Their replies run here, while the
	// players they name still exist, instead of during the next map's load.
	FNShared::ThinkSaves();
	g_FNRequestManager.Drain();

	if (!g_Active)
		return;
	const size_t dirty = CountDirty();
	if (dirty && g_FN && !g_Disabled)
	{
		if (!g_Synced)
		{
			// FN was down all along: one last load (changes here win the merge), then send
			int code = 0;
			std::string body;
			LoadBlocking(code, body);
			HandleLoad(code, body, true);
		}
		if (g_Synced && !g_Disabled)
			FlushBlocking();
	}
	const size_t lost = CountDirty();
	if (lost && g_FN) // with FN off that is the plan, not news
		Log("MSR: worldstate %s/%s: %u changes not saved (%s)\n", g_Realm.c_str(), g_Map.c_str(), (unsigned int)lost,
			g_Disabled ? "no FN world sync" : !g_Synced ? "FN unreachable" : "FN write failed");
	else if (dirty && g_FN) // with FN off the changes stay in memory by design
		Log("MSR: worldstate %s/%s: %u changes saved at map end\n", g_Realm.c_str(), g_Map.c_str(), (unsigned int)dirty);
	ResetWorld();
}

void Shutdown()
{
	MapEnd(); // normally ServerDeactivate got there first
	// Saves queued at quit were lost before: send them now
	FNShared::ThinkSaves();
	g_FNRequestManager.Shutdown();
}

void Frame()
{
	if (!g_Active)
		return;
	const double now = Steady();
	if (now < g_NextTick)
		return;
	g_NextTick = now + 0.25;
	NotifyGameMaster(now);
	if (now >= g_NextPrune)
	{
		g_NextPrune = now + 10;
		Prune();
	}
	if (!g_FN || g_Disabled)
		return;
	if (!g_Synced)
	{
		// While FN's copy is unknown nothing is sent; changes stay dirty for the merge
		if (!g_LoadInFlight && now >= g_NextLoad)
			StartLoad();
		return;
	}
	if (!g_WriteInFlight && now >= g_NextWrite && AnyDirty())
		SendAsync();
}

bool Loaded() { return g_Active; }
bool Online() { return g_Active && g_FN && g_Synced && !g_Disabled; }

// FN is on for this map but its keys are not in yet (it was unreachable at map start). Callers may
// wait for them, but only briefly: after 90 s a long outage must not keep content away.
bool Pending() { return g_Active && g_FN && !g_Synced && !g_Disabled && Steady() - g_MapStartedAt < 90.0; }

bool Get(const char *key, std::string &value)
{
	if (!key)
		return false;
	auto it = g_Keys.find(key);
	if (it == g_Keys.end() || !Live(it->second, Now()))
		return false;
	value = it->second.value;
	return true;
}

double TimeLeft(const char *key)
{
	if (!key)
		return 0;
	auto it = g_Keys.find(key);
	const double now = Now();
	if (it == g_Keys.end() || !Live(it->second, now))
		return 0;
	return it->second.expires > 0 ? it->second.expires - now : -1;
}

void Set(const char *key, const char *value, double ttlSeconds)
{
	if (!ValidKey(key, true))
	{
		Log("MSR: worldstate: bad key '%s' not set\n", key ? key : "");
		return;
	}
	if (!g_Active)
	{
		// Between maps (or in world-script init, before the load): it would land in the wrong world
		Log("MSR: worldstate: %s set while no world is open; ignored\n", key);
		return;
	}
	auto it = g_Keys.find(key);
	if (it == g_Keys.end() && g_Keys.size() >= kMaxKeys)
	{
		Log("MSR: worldstate %s/%s: %u keys already, %s not set\n", g_Realm.c_str(), g_Map.c_str(), (unsigned int)kMaxKeys, key);
		return;
	}
	double expires = 0;
	if (ttlSeconds > 0)
	{
		if (ttlSeconds > kMaxTTL)
		{
			Log("MSR: worldstate: %s ttl %.0f s capped to 30 days\n", key, ttlSeconds);
			ttlSeconds = kMaxTTL;
		}
		expires = Now() + ttlSeconds;
	}
	const std::string clean = CleanValue(value);
	if (it != g_Keys.end() && !expires && !it->second.expires && !it->second.pendingDelete && it->second.value == clean)
		return; // same permanent value: no write (scripts may set a flag every think)
	entry_t &e = g_Keys[key];
	e.value = clean;
	e.expires = expires;
	e.pendingDelete = false;
	e.dirty = true;
	e.change = ++g_Changes;
	e.additive = false; // an absolute value wins the merge
	e.addDelta = 0;
}

void Unset(const char *key)
{
	if (!key)
		return;
	auto it = g_Keys.find(key);
	if (it == g_Keys.end() && g_Active && g_FN && !g_Disabled && !g_Synced && ValidKey(key, true))
		it = g_Keys.emplace(key, entry_t()).first; // FN's copy is not in yet and may hold it: the delete must win the merge
	if (it == g_Keys.end() || (it->second.pendingDelete && it->second.dirty))
		return;
	if (!g_FN || g_Disabled)
	{
		g_Keys.erase(it); // never synced this map: nobody to tell
		return;
	}
	// FN may hold an older value: the delete must go out even if the set never did
	it->second.value.clear();
	it->second.expires = 0;
	it->second.pendingDelete = true;
	it->second.dirty = true;
	it->second.change = ++g_Changes;
	it->second.additive = false;
	it->second.addDelta = 0;
}

long Add(const char *key, long delta, double ttlSeconds)
{
	std::string current;
	const bool known = Get(key, current);
	auto before = g_Keys.find(key ? key : "");
	const bool wasAdditive = before != g_Keys.end() && before->second.additive;
	const bool deletedHere = before != g_Keys.end() && before->second.pendingDelete; // unset, then counted from 0
	const long added = wasAdditive ? before->second.addDelta : 0;
	long n = known ? atol(current.c_str()) : 0;
	n += delta;
	Set(key, std::to_string(n).c_str(), ttlSeconds);
	// FN's copy is not in yet (it was unreachable at map start) and may hold this counter: keep
	// what was added, so the merge counts on top of FN's value instead of replacing it
	if (g_Active && g_FN && !g_Disabled && !g_Synced && ((!known && !deletedHere) || wasAdditive))
	{
		auto it = g_Keys.find(key);
		if (it != g_Keys.end() && !it->second.pendingDelete)
		{
			it->second.additive = true;
			it->second.addDelta = added + delta;
		}
	}
	return n;
}

bool ValidKey(const char *key, bool allowReserved)
{
	if (!key || !*key)
		return false;
	const size_t len = strlen(key);
	if (len > 64)
		return false;
	for (size_t i = 0; i < len; i++)
	{
		const char c = key[i];
		const bool alnum = (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9');
		if (!alnum && (i == 0 || (c != '_' && c != '.' && c != ':' && c != '-')))
			return false;
	}
	// Script names: an unquoted key naming a variable or const would be replaced by its value
	static const char *const kNever[] = {"global.", "local.", "game.", "const."};
	for (const char *prefix : kNever)
		if (!strncmp(key, prefix, strlen(prefix)))
			return false;
	// Written by ms.dll itself (boss timers, logout spots, bookkeeping)
	static const char *const kReserved[] = {"boss.", "logout.", "sys."};
	if (!allowReserved)
		for (const char *prefix : kReserved)
			if (!strncmp(key, prefix, strlen(prefix)))
				return false;
	return true;
}

double Now()
{
	return std::chrono::duration<double>(std::chrono::system_clock::now().time_since_epoch()).count();
}
} // namespace WorldState
