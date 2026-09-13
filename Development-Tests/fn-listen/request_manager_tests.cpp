#include <algorithm>
#include <cassert>
#include <cstdarg>
#include <cstdio>
#include <deque>
#include <string>
#include <vector>

// The manager and load/rollback bodies below are extracted unchanged. Only
// curl/engine/HTTP transport boundaries are inert; this performs no network IO.
struct HTTPRequest;
struct CURL { HTTPRequest* owner=nullptr; bool attached=false, announced=false; };
struct CURLSH {};
using CURLcode=int;
struct CURLMsg { int msg; CURL* easy_handle; struct { CURLcode result; } data; };
struct CURLM { std::vector<CURL*> handles; std::deque<CURLMsg> messages; };
enum { CURLSHOPT_SHARE, CURL_LOCK_DATA_CONNECT, CURL_LOCK_DATA_DNS, CURLMOPT_PIPELINING,
    CURLPIPE_MULTIPLEX, CURLMOPT_MAXCONNECTS, CURLMOPT_MAX_HOST_CONNECTIONS,
    CURLM_OK, CURLMSG_DONE, CURLINFO_PRIVATE };
static bool dedicated=false, failShare=false, failMulti=false, failAdd=false, failPrepare=false, completeTransfers=true;
static int shares=0,multis=0,liveRequests=0,started=0,completed=0,aborted=0,loads=0,waitCalls=0,assertions=0;
static bool IS_DEDICATED_SERVER(){ return dedicated; }
static const char* UTIL_VarArgs(const char* format,...){static char text[1024];va_list a;va_start(a,format);vsnprintf(text,sizeof(text),format,a);va_end(a);return text;}
static void print(const char* text){std::fputs(text,stdout);}
static struct {void (*pfnServerPrint)(const char*)=print;} g_engfuncs;
static CURLSH* curl_share_init(){if(failShare)return nullptr;++shares;return new CURLSH;}
static void curl_share_setopt(CURLSH*,int,int){}
static void curl_share_cleanup(CURLSH* p){--shares;delete p;}
static CURLM* curl_multi_init(){if(failMulti)return nullptr;++multis;return new CURLM;}
static void curl_multi_setopt(CURLM*,int,long){}
static void curl_multi_cleanup(CURLM* p){assert(p->handles.empty());--multis;delete p;}
static int curl_multi_add_handle(CURLM* m,CURL* h){if(failAdd)return -1;m->handles.push_back(h);h->attached=true;return CURLM_OK;}
static void curl_multi_remove_handle(CURLM* m,CURL* h){m->handles.erase(std::remove(m->handles.begin(),m->handles.end(),h),m->handles.end());h->attached=false;}
static void curl_multi_perform(CURLM* m,int* running){*running=0;for(auto h:m->handles){if(!completeTransfers){++*running;continue;}if(!h->announced){h->announced=true;m->messages.push_back({CURLMSG_DONE,h,{0}});}}}
static CURLMsg* curl_multi_info_read(CURLM* m,int* remaining){static CURLMsg msg;if(m->messages.empty())return nullptr;msg=m->messages.front();m->messages.pop_front();*remaining=(int)m->messages.size();return &msg;}
static void curl_easy_getinfo(CURL* h,int,HTTPRequest** r){*r=h->owner;}
static void curl_easy_cleanup(CURL* h){assert(!h->attached);delete h;}
void wait(unsigned long){++waitCalls;}
struct HTTPRequest {
    enum RequestState {QUEUED,EXECUTED,FINISHED};
    int m_iRequestState=QUEUED; CURL* handle=nullptr;
    HTTPRequest(){++liveRequests;}
    virtual ~HTTPRequest(){if(handle)curl_easy_cleanup(handle);--liveRequests;}
    CURL* PrepareForMulti(){if(failPrepare)return nullptr;handle=new CURL{this};m_iRequestState=EXECUTED;++started;return handle;}
    void OnMultiComplete(CURLcode){m_iRequestState=FINISHED;++completed;}
    void AbortTransfer(CURLM* m){curl_multi_remove_handle(m,handle);++aborted;}
};
#include "build/manager_declaration.inc"
#ifdef TEST_BASELINE
#include "build/baseline_manager.inc"
#else
#include "build/candidate_manager.inc"
#endif
CRequestManager g_FNRequestManager;
enum {CDS_UNLOADED,CDS_LOADING,CDS_NOTFOUND};
struct charinfo_t {int Status=CDS_NOTFOUND,m_CachedStatus=CDS_NOTFOUND;};
constexpr unsigned MAX_CHARSLOTS=3;
struct CBasePlayer {unsigned long long steamID64=123;charinfo_t m_CharInfo[MAX_CHARSLOTS];};
struct LoadCharacterRequest:HTTPRequest {LoadCharacterRequest(unsigned long long,unsigned,const char*){++loads;}};
namespace FNShared {void LoadCharacter(CBasePlayer*);void Print(const char*,...){};}
#include "build/load_paths.inc"
static void check(bool ok){++assertions;if(!ok){std::fprintf(stderr,"assertion %d failed\n",assertions);std::abort();}}
static void clean(){g_FNRequestManager.Shutdown();check(liveRequests==0);check(shares==0);check(multis==0);}
static void scenario(bool isDedicated){
    dedicated=isDedicated;
#if defined(MSR_STANDALONE) && !defined(TEST_BASELINE)
    const bool allowed=true;
#else
    const bool allowed=isDedicated;
#endif
    g_FNRequestManager.Init();check((g_FNRequestManager.GetShareHandle()!=nullptr)==allowed);
    check(!g_FNRequestManager.QueueRequest(nullptr));
    CBasePlayer p;
    int beforeLoads=loads,beforeStarted=started,beforeCompleted=completed;
    FNShared::LoadCharacter(nullptr);p.steamID64=0;FNShared::LoadCharacter(&p);check(loads==beforeLoads);p.steamID64=123;
    FNShared::LoadCharacter(&p);
    if(!allowed){check(loads==beforeLoads+1);check(liveRequests==0);for(auto c:p.m_CharInfo)check(c.Status==CDS_NOTFOUND);}
    else {
        check(loads==beforeLoads+3);check(liveRequests==3);for(auto c:p.m_CharInfo)check(c.Status==CDS_LOADING);
        FNShared::LoadCharacter(&p);check(loads==beforeLoads+3); // no duplicate loading slots
        g_FNRequestManager.Think();check(started==beforeStarted+3);check(completed==beforeCompleted+3);check(liveRequests==0);
        // A generic update request uses this identical queue and transport path.
        check(g_FNRequestManager.QueueRequest(new HTTPRequest));g_FNRequestManager.Think();check(completed==beforeCompleted+4);
        // Clear queued and in-flight requests, and bounded shutdown abort.
        check(g_FNRequestManager.QueueRequest(new HTTPRequest));g_FNRequestManager.Clear();check(liveRequests==0);
        completeTransfers=false;check(g_FNRequestManager.QueueRequest(new HTTPRequest));g_FNRequestManager.Think();
        int beforeAbort=aborted;g_FNRequestManager.Clear();check(aborted==beforeAbort+1);check(liveRequests==0);
        check(g_FNRequestManager.QueueRequest(new HTTPRequest));g_FNRequestManager.Think();beforeAbort=aborted;
        g_FNRequestManager.Shutdown();check(aborted==beforeAbort+1);check(waitCalls>=100);completeTransfers=true;
        g_FNRequestManager.Init();check(shares==1 && multis==1);g_FNRequestManager.Init();check(shares==1 && multis==1);
        failPrepare=true;check(g_FNRequestManager.QueueRequest(new HTTPRequest));g_FNRequestManager.Think();check(liveRequests==0);failPrepare=false;
        failAdd=true;check(g_FNRequestManager.QueueRequest(new HTTPRequest));g_FNRequestManager.Think();check(liveRequests==0);failAdd=false;
    }
    clean();check(!g_FNRequestManager.QueueRequest(new HTTPRequest));check(liveRequests==0);
    if(allowed){
        failMulti=true;g_FNRequestManager.Init();check(shares==0 && multis==0);check(!g_FNRequestManager.QueueRequest(new HTTPRequest));failMulti=false;clean();
        failShare=true;g_FNRequestManager.Init();check(shares==0 && multis==1);check(g_FNRequestManager.QueueRequest(new HTTPRequest));g_FNRequestManager.Think();failShare=false;clean();
    }
    std::printf("CASE dedicated=%d initialized=%d character_queue=%s ownership_clean=1\n",isDedicated,allowed,allowed?"accepted":"rejected");
}
int main(){scenario(false);scenario(true);std::printf("PASS %d manager/load-path assertions; inert curl/HTTP boundary, no engine or network run.\n",assertions);}
