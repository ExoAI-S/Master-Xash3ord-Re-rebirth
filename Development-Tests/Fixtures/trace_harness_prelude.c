/* Minimal isolated x86 Debug harness around the actual engine C functions. */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <stdarg.h>
#include <float.h>
#include <windows.h>
typedef int qboolean;
typedef float vec3_t[3];
#define true 1
#define false 0
#define GAME_EXPORT
#define QBSP2_VERSION 844124994
#define CONTENTS_NONE 0
#define CONTENTS_EMPTY -1
#define CONTENTS_SOLID -2
#define CONTENTS_WATER -3
#define DIST_EPSILON (1.0f/32.0f)
#define S_WARN ""
#define DotProduct(x,y) ((x)[0]*(y)[0]+(x)[1]*(y)[1]+(x)[2]*(y)[2])
#define PlaneDiff(point,plane) (((plane)->type<3?(point)[(plane)->type]:DotProduct((point),(plane)->normal))-(plane)->dist)
#define VectorCopy(a,b) ((b)[0]=(a)[0],(b)[1]=(a)[1],(b)[2]=(a)[2])
#define VectorNegate(a,b) ((b)[0]=-(a)[0],(b)[1]=-(a)[1],(b)[2]=-(a)[2])
#define VectorLerp(a,t,b,c) ((c)[0]=(a)[0]+(t)*((b)[0]-(a)[0]),(c)[1]=(a)[1]+(t)*((b)[1]-(a)[1]),(c)[2]=(a)[2]+(t)*((b)[2]-(a)[2]))
typedef struct{float normal[3],dist;uint8_t type,signbits,pad[2];}mplane_t;
typedef struct{int32_t planenum;int16_t children[2];}mclipnode16_t;
typedef struct{int32_t planenum;int32_t children[2];}mclipnode32_t;
typedef struct{union{mclipnode16_t*clipnodes16;mclipnode32_t*clipnodes32;};mplane_t*planes;int firstclipnode,lastclipnode;vec3_t clip_mins,clip_maxs;}hull_t;
typedef struct{vec3_t normal;float dist;}pmplane_t;
typedef struct{qboolean allsolid,startsolid,inopen,inwater;float fraction;vec3_t endpos;pmplane_t plane;int ent;vec3_t deltavelocity;int hitgroup;}pmtrace_t;
struct{int version;}world;
static unsigned long long profile_nodes,profile_recursions,profile_pointqueries;
void Host_Error(const char*fmt,...){va_list v;va_start(v,fmt);vfprintf(stderr,fmt,v);va_end(v);exit(9);}
void Con_Reportf(const char*fmt,...){(void)fmt;}
