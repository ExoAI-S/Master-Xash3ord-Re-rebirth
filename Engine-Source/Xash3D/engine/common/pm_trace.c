/*
pm_trace.c - pmove player trace code
Copyright (C) 2010 Uncle Mike

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.
*/

#include <float.h>

#include "common.h"
#include "xash3d_mathlib.h"
#include "mod_local.h"
#include "pm_local.h"
#include "enginefeatures.h"
#include "studio.h"
#include "world.h"

#define PM_AllowHitBoxTrace( model, hull ) ( model && model->type == mod_studio && ( FBitSet( model->flags, STUDIO_TRACE_HITBOX ) || hull == 2 ))

static mplane_t	pm_boxplanes[6];
static hull_t pm_boxhull;

// default hullmins
static const vec3_t pm_hullmins[MAX_MAP_HULLS] =
{
{ -16, -16, -36 },
{ -16, -16, -18 },
{   0,   0,   0 },
{ -32, -32, -32 },
};

// defualt hullmaxs
static const vec3_t pm_hullmaxs[MAX_MAP_HULLS] =
{
{  16,  16,  36 },
{  16,  16,  18 },
{   0,   0,   0 },
{  32,  32,  32 },
};

void Pmove_Init( void )
{
	PM_InitBoxHull ();

	// init default hull sizes
	memcpy( host.player_mins, pm_hullmins, sizeof( pm_hullmins ));
	memcpy( host.player_maxs, pm_hullmaxs, sizeof( pm_hullmaxs ));
}

/*
===================
PM_InitBoxHull

Set up the planes and clipnodes so that the six floats of a bounding box
can just be stored out and get a proper hull_t structure.
===================
*/
void PM_InitBoxHull( void )
{
	pm_boxhull.clipnodes16 = (mclipnode16_t *)box_clipnodes16;
	pm_boxhull.planes = pm_boxplanes;
	pm_boxhull.firstclipnode = 0;
	pm_boxhull.lastclipnode = 5;

	for( int i = 0; i < 6; i++ )
	{
		pm_boxplanes[i].type = i>>1;
		pm_boxplanes[i].normal[i>>1] = 1.0f;
		pm_boxplanes[i].signbits = 0;
	}

}

/*
===================
PM_HullForBox

To keep everything totally uniform, bounding boxes are turned into small
BSP trees instead of being compared directly.
===================
*/
static hull_t *PM_HullForBox( const vec3_t mins, const vec3_t maxs )
{
	pm_boxplanes[0].dist = maxs[0];
	pm_boxplanes[1].dist = mins[0];
	pm_boxplanes[2].dist = maxs[1];
	pm_boxplanes[3].dist = mins[1];
	pm_boxplanes[4].dist = maxs[2];
	pm_boxplanes[5].dist = mins[2];

	if( world.version == QBSP2_VERSION )
		pm_boxhull.clipnodes32 = (mclipnode32_t *)box_clipnodes32;
	else
		pm_boxhull.clipnodes16 = (mclipnode16_t *)box_clipnodes16;

	return &pm_boxhull;
}

/*
==================
PM_HullPointContents

==================
*/
int GAME_EXPORT PM_HullPointContents( hull_t *hull, int num, const vec3_t p )
{
	if( !hull || !hull->planes )	// fantom bmodels?
		return CONTENTS_NONE;

	if( world.version == QBSP2_VERSION )
	{
		while( num >= 0 )
		{
			mplane_t *plane = &hull->planes[hull->clipnodes32[num].planenum];
			num = hull->clipnodes32[num].children[PlaneDiff( p, plane ) < 0];
		}
	}
	else
	{
		while( num >= 0 )
		{
			mplane_t *plane = &hull->planes[hull->clipnodes16[num].planenum];
			num = hull->clipnodes16[num].children[PlaneDiff( p, plane ) < 0];
		}
	}
	return num;
}

/*
==================
PM_HullForBsp

assume physent is valid
==================
*/
hull_t *PM_HullForBsp( physent_t *pe, playermove_t *pmove, float *offset )
{
	Assert( pe != NULL );
	Assert( pe->model != NULL );

	hull_t *hull;
	switch( pmove->usehull )
	{
	case 1:
		hull = &pe->model->hulls[3];
		break;
	case 2:
		hull = &pe->model->hulls[0];
		break;
	case 3:
		hull = &pe->model->hulls[2];
		break;
	default:
		hull = &pe->model->hulls[1];
		break;
	}

	Assert( hull != NULL );

	// calculate an offset value to center the origin
	VectorSubtract( hull->clip_mins, host.player_mins[pmove->usehull], offset );
	VectorAdd( offset, pe->origin, offset );

	return hull;
}

/*
==================
PM_HullForStudio

generate multiple hulls as hitboxes
==================
*/
static hull_t *PM_HullForStudio( physent_t *pe, playermove_t *pmove, int *numhitboxes )
{
	vec3_t size;
	VectorSubtract( host.player_maxs[pmove->usehull], host.player_mins[pmove->usehull], size );
	VectorScale( size, 0.5f, size );

	return Mod_HullForStudio( pe->studiomodel, pe->frame, pe->sequence, pe->angles, pe->origin, size, pe->controller, pe->blending, numhitboxes, NULL );
}

/*
==================
PM_RecursiveHullCheck
==================
*/
// Split the physical segment without an epsilon bias. Applying the contact
// epsilon to a BSP split can put the far traversal outside that child's space
// and report an internal terrain plane as a ceiling in otherwise empty space.
typedef struct pm_hullinterval_s
{
	hull_t *hull;
	pmtrace_t *trace;
	double start[3], delta[3];
	double entry;
	const mplane_t *impactplane;
	int impactside;
	size_t remaining;
} pm_hullinterval_t;

static qboolean PM_TraceHullInterval( pm_hullinterval_t *ctx, int num,
	double begin, double end, const mplane_t *enterplane, int enterside, int depth )
{
	while( num >= 0 )
	{
		int children[2], side;
		const mplane_t *plane;
		double d1, d2, split, dotstart, dotdelta;

		if( depth > 1024 || ctx->remaining-- == 0 )
			Host_Error( "%s: invalid or cyclic clipping hull\n", __func__ );
		if( num < ctx->hull->firstclipnode || num > ctx->hull->lastclipnode )
			Host_Error( "%s: bad node number %i\n", __func__, num );

		if( world.version == QBSP2_VERSION )
		{
			children[0] = ctx->hull->clipnodes32[num].children[0];
			children[1] = ctx->hull->clipnodes32[num].children[1];
			plane = ctx->hull->planes + ctx->hull->clipnodes32[num].planenum;
		}
		else
		{
			children[0] = ctx->hull->clipnodes16[num].children[0];
			children[1] = ctx->hull->clipnodes16[num].children[1];
			plane = ctx->hull->planes + ctx->hull->clipnodes16[num].planenum;
		}

		if( plane->type < 3 )
		{
			dotstart = ctx->start[plane->type];
			dotdelta = ctx->delta[plane->type];
		}
		else
		{
			dotstart = ctx->start[0] * plane->normal[0]
				+ ctx->start[1] * plane->normal[1] + ctx->start[2] * plane->normal[2];
			dotdelta = ctx->delta[0] * plane->normal[0]
				+ ctx->delta[1] * plane->normal[1] + ctx->delta[2] * plane->normal[2];
		}
		d1 = dotstart + begin * dotdelta - plane->dist;
		d2 = dotstart + end * dotdelta - plane->dist;

		// Inverted tests reject a malformed non-finite plane as well as NaN.
		if( !( d1 >= -DBL_MAX && d1 <= DBL_MAX && d2 >= -DBL_MAX && d2 <= DBL_MAX ))
			Host_Error( "%s: non-finite clipping plane\n", __func__ );

		if( d1 >= 0.0 && d2 >= 0.0 )
		{
			num = children[0];
			continue;
		}
		if( d1 < 0.0 && d2 < 0.0 )
		{
			num = children[1];
			continue;
		}

		side = d1 < 0.0;
		split = begin + ( end - begin ) * ( d1 / ( d1 - d2 ));
		if( split < begin ) split = begin;
		if( split > end ) split = end;

		if( !PM_TraceHullInterval( ctx, children[side], begin, split, enterplane, enterside, depth + 1 ))
			return false;
		// Use the actual crosspoint for the far interval too. A biased near
		// point must never be reused as an initial point in the far child.
		begin = split;
		num = children[side ^ 1];
		enterplane = plane;
		enterside = side;
	}

	if( num != CONTENTS_SOLID )
	{
		ctx->trace->allsolid = false;
		if( num == CONTENTS_EMPTY ) ctx->trace->inopen = true;
		else ctx->trace->inwater = true;
		return true;
	}
	if( ctx->trace->allsolid )
	{
		// Preserve the native start-solid contract: continue until there is
		// empty/water space, leaving fraction/endpos alone if no impact follows.
		ctx->trace->startsolid = true;
		return true;
	}
	ctx->entry = begin;
	ctx->impactplane = enterplane;
	ctx->impactside = enterside;
	return false;
}

qboolean PM_RecursiveHullCheck( hull_t *hull, int num, float p1f, float p2f, vec3_t p1, vec3_t p2, pmtrace_t *trace )
{
	pm_hullinterval_t ctx;
	double safe, approach;
	vec3_t mid;

	// Terminal contents need no hull or plane data, including null hulls.
	if( num < 0 )
	{
		if( num != CONTENTS_SOLID )
		{
			trace->allsolid = false;
			if( num == CONTENTS_EMPTY ) trace->inopen = true;
			else trace->inwater = true;
		}
		else trace->startsolid = true;
		return true;
	}

	// Invalid game-DLL vectors must not create NaN splits or an infinite loop.
	for( int i = 0; i < 3; i++ )
	{
		if( !( p1[i] >= -FLT_MAX && p1[i] <= FLT_MAX && p2[i] >= -FLT_MAX && p2[i] <= FLT_MAX ))
		{
			trace->allsolid = trace->startsolid = true;
			trace->fraction = 0.0f;
			VectorCopy( p1, trace->endpos );
			return false;
		}
	}
	if( !( p1f >= -FLT_MAX && p1f <= FLT_MAX && p2f >= -FLT_MAX && p2f <= FLT_MAX ) || !hull )
	{
		trace->allsolid = trace->startsolid = true;
		trace->fraction = 0.0f;
		VectorCopy( p1, trace->endpos );
		return false;
	}
	if( hull->firstclipnode >= hull->lastclipnode )
	{
		trace->allsolid = false;
		trace->inopen = true;
		return true;
	}

	if( !hull->planes || !hull->clipnodes16 )
	{
		trace->allsolid = trace->startsolid = true;
		trace->fraction = 0.0f;
		VectorCopy( p1, trace->endpos );
		return false;
	}

	memset( &ctx, 0, sizeof( ctx ));
	ctx.hull = hull;
	ctx.trace = trace;
	ctx.remaining = ((size_t)hull->lastclipnode - hull->firstclipnode + 1 ) * 16 + 64;
	for( int i = 0; i < 3; i++ )
	{
		ctx.start[i] = p1[i];
		ctx.delta[i] = (double)p2[i] - p1[i];
	}
	if( PM_TraceHullInterval( &ctx, num, 0.0, 1.0, NULL, 0, 0 ))
		return true;

	if( !ctx.impactplane )
	{
		trace->fraction = p1f;
		VectorCopy( p1, trace->endpos );
		return false;
	}
	if( ctx.impactside )
	{
		VectorNegate( ctx.impactplane->normal, trace->plane.normal );
		trace->plane.dist = -ctx.impactplane->dist;
	}
	else
	{
		VectorCopy( ctx.impactplane->normal, trace->plane.normal );
		trace->plane.dist = ctx.impactplane->dist;
	}

	// Back off from a genuine first solid entry, retaining the existing normal
	// contact epsilon without moving a traversal point across a BSP partition.
	approach = -( ctx.delta[0] * trace->plane.normal[0]
		+ ctx.delta[1] * trace->plane.normal[1] + ctx.delta[2] * trace->plane.normal[2] );
	safe = ctx.entry;
	if( approach > 0.0 ) safe -= DIST_EPSILON / approach;
	if( safe < 0.0 ) safe = 0.0;
	for( int i = 0; i < 3; i++ ) mid[i] = (float)( ctx.start[i] + safe * ctx.delta[i] );

	// Quantizing the safe point back to float can put it just inside a nearby
	// plane. Retreat only; never advance past the first solid interval.
	for( int attempt = 0; attempt < 32 && PM_HullPointContents( hull, hull->firstclipnode, mid ) == CONTENTS_SOLID; attempt++ )
	{
		if( safe == 0.0 ) break;
		safe -= approach > 0.0 ? DIST_EPSILON / approach : 0.1;
		if( safe < 0.0 ) safe = 0.0;
		for( int i = 0; i < 3; i++ ) mid[i] = (float)( ctx.start[i] + safe * ctx.delta[i] );
	}
	trace->fraction = (float)( p1f + ((double)p2f - p1f ) * safe );
	VectorCopy( mid, trace->endpos );
	return false;
}

pmtrace_t PM_PlayerTraceExt( playermove_t *pmove, vec3_t start, vec3_t end, int flags, int numents, physent_t *ents, int ignore_pe, pfnIgnore pmFilter )
{
	pmtrace_t trace_total;

	memset( &trace_total, 0, sizeof( trace_total ));
	VectorCopy( end, trace_total.endpos );
	trace_total.fraction = 1.0f;
	trace_total.ent = -1;

	for( int i = 0; i < numents; i++ )
	{
		physent_t *pe = &ents[i];
		matrix4x4 matrix;
		vec3_t offset, start_l, end_l;
		vec3_t mins, maxs;
		int hullcount;
		qboolean rotated, transform_bbox;
		hull_t *hull = NULL;

		if( i != 0 && ( flags & PM_WORLD_ONLY ))
			break;

		// run custom user filter
		if( pmFilter != NULL )
		{
			if( pmFilter( pe ))
				continue;
		}
		else if( ignore_pe != -1 )
		{
			if( i == ignore_pe )
				continue;
		}

		if( pe->model != NULL && pe->solid == SOLID_NOT && pe->skin != CONTENTS_NONE )
			continue;

		if(( flags & PM_GLASS_IGNORE ) && pe->rendermode != kRenderNormal )
			continue;

		if(( flags & PM_CUSTOM_IGNORE ) && pe->solid == SOLID_CUSTOM )
			continue;

		hullcount = 1;

		if( pe->solid == SOLID_CUSTOM )
		{
			VectorCopy( host.player_mins[pmove->usehull], mins );
			VectorCopy( host.player_maxs[pmove->usehull], maxs );
			VectorClear( offset );
		}
		else if( pe->model )
		{
			hull = PM_HullForBsp( pe, pmove, offset );
		}
		else
		{
			if( pe->studiomodel )
			{
				if( FBitSet( flags, PM_STUDIO_IGNORE ))
					continue;

				if( PM_AllowHitBoxTrace( pe->studiomodel, pmove->usehull ) && !FBitSet( flags, PM_STUDIO_BOX ))
				{
					hull = PM_HullForStudio( pe, pmove, &hullcount );
					VectorClear( offset );
				}
				else
				{
					VectorSubtract( pe->mins, host.player_maxs[pmove->usehull], mins );
					VectorSubtract( pe->maxs, host.player_mins[pmove->usehull], maxs );

					hull = PM_HullForBox( mins, maxs );
					VectorCopy( pe->origin, offset );
				}
			}
			else
			{
				VectorSubtract( pe->mins, host.player_maxs[pmove->usehull], mins );
				VectorSubtract( pe->maxs, host.player_mins[pmove->usehull], maxs );

				hull = PM_HullForBox( mins, maxs );
				VectorCopy( pe->origin, offset );
			}

		}

		if( pe->solid == SOLID_BSP && !VectorIsNull( pe->angles ))
			rotated = true;
		else rotated = false;

		if( FBitSet( host.features, ENGINE_PHYSICS_PUSHER_EXT ))
		{
			if(( check_angles( pe->angles[0] ) || check_angles( pe->angles[2] )) && pmove->usehull != 2 )
				transform_bbox = true;
			else transform_bbox = false;
		}
		else transform_bbox = false;

		if( rotated )
		{
			if( transform_bbox )
				Matrix4x4_CreateFromEntity( matrix, pe->angles, pe->origin, 1.0f );
			else Matrix4x4_CreateFromEntity( matrix, pe->angles, offset, 1.0f );

			Matrix4x4_VectorITransform( matrix, start, start_l );
			Matrix4x4_VectorITransform( matrix, end, end_l );

			if( transform_bbox )
			{
				World_TransformAABB( matrix, host.player_mins[pmove->usehull], host.player_maxs[pmove->usehull], mins, maxs );
				VectorSubtract( hull->clip_mins, mins, offset );	// calc new local offset

				for( int j = 0; j < 3; j++ )
				{
					if( start_l[j] >= 0.0f )
						start_l[j] -= offset[j];
					else start_l[j] += offset[j];
					if( end_l[j] >= 0.0f )
						end_l[j] -= offset[j];
					else end_l[j] += offset[j];
				}
			}
		}
		else
		{
			VectorSubtract( start, offset, start_l );
			VectorSubtract( end, offset, end_l );
		}

		pmtrace_t trace_bbox;
		PM_InitPMTrace( &trace_bbox, end );

		if( hullcount < 1 )
		{
			// g-cont. probably this never happens
			trace_bbox.allsolid = false;
		}
		else if( pe->solid == SOLID_CUSTOM )
		{
			// run custom sweep callback
			if( pmove->server || Host_IsLocalClient( ))
				SV_ClipPMoveToEntity( pe, start, mins, maxs, end, &trace_bbox );
#if !XASH_DEDICATED
			else CL_ClipPMoveToEntity( pe, start, mins, maxs, end, &trace_bbox );
#endif
		}
		else if( hullcount == 1 )
		{
			PM_RecursiveHullCheck( hull, hull->firstclipnode, 0, 1, start_l, end_l, &trace_bbox );
		}
		else
		{
			int last_hitgroup = 0;

			for( int j = 0; j < hullcount; j++ )
			{
				pmtrace_t trace_hitbox;
				PM_InitPMTrace( &trace_hitbox, end );

				PM_RecursiveHullCheck( &hull[j], hull[j].firstclipnode, 0, 1, start_l, end_l, &trace_hitbox );

				if( j == 0 || trace_hitbox.allsolid || trace_hitbox.startsolid || trace_hitbox.fraction < trace_bbox.fraction )
				{
					if( trace_bbox.startsolid )
					{
						trace_bbox = trace_hitbox;
						trace_bbox.startsolid = true;
					}
					else trace_bbox = trace_hitbox;

					last_hitgroup = j;
				}
			}

			trace_bbox.hitgroup = Mod_HitgroupForStudioHull( last_hitgroup );
		}

		if( trace_bbox.allsolid )
			trace_bbox.startsolid = true;

		if( trace_bbox.startsolid )
			trace_bbox.fraction = 0.0f;

		if( !trace_bbox.startsolid )
		{
			VectorLerp( start, trace_bbox.fraction, end, trace_bbox.endpos );

			if( rotated )
			{
				vec3_t temp = Vec3( trace_bbox.plane.normal );
				Matrix4x4_TransformPositivePlane( matrix, temp, trace_bbox.plane.dist, trace_bbox.plane.normal, &trace_bbox.plane.dist );
			}
			else
			{
				trace_bbox.plane.dist = DotProduct( trace_bbox.endpos, trace_bbox.plane.normal );
			}
		}

		if( trace_bbox.fraction < trace_total.fraction )
		{
			trace_total = trace_bbox;
			trace_total.ent = i;
		}
	}

	return trace_total;
}

int PM_TestPlayerPosition( playermove_t *pmove, vec3_t pos, pmtrace_t *ptrace, pfnIgnore pmFilter )
{
	pmtrace_t trace = PM_PlayerTraceExt( pmove, pmove->origin, pmove->origin, 0, pmove->numphysent, pmove->physents, -1, pmFilter );
	if( ptrace ) *ptrace = trace;

	for( int i = 0; i < pmove->numphysent; i++ )
	{
		physent_t *pe = &pmove->physents[i];
		vec3_t pos_l, offset;
		vec3_t mins, maxs;
		hull_t *hull = NULL;
		int hullcount;

		// run custom user filter
		if( pmFilter != NULL )
		{
			if( pmFilter( pe ))
				continue;
		}

		if( pe->model != NULL && pe->solid == SOLID_NOT && pe->skin != CONTENTS_NONE )
			continue;

		hullcount = 1;

		if( pe->solid == SOLID_CUSTOM )
		{
			VectorCopy( host.player_mins[pmove->usehull], mins );
			VectorCopy( host.player_maxs[pmove->usehull], maxs );
			VectorClear( offset );
		}
		else if( pe->model )
		{
			hull = PM_HullForBsp( pe, pmove, offset );
		}
		else if( PM_AllowHitBoxTrace( pe->studiomodel, pmove->usehull ))
		{
			hull = PM_HullForStudio( pe, pmove, &hullcount );
			VectorClear( offset );
		}
		else
		{
			VectorSubtract( pe->mins, host.player_maxs[pmove->usehull], mins );
			VectorSubtract( pe->maxs, host.player_mins[pmove->usehull], maxs );

			hull = PM_HullForBox( mins, maxs );
			VectorCopy( pe->origin, offset );
		}

		// CM_TransformedPointContents :-)
		if( pe->solid == SOLID_BSP && !VectorIsNull( pe->angles ))
		{
			qboolean	transform_bbox = false;
			matrix4x4	matrix;

			if( FBitSet( host.features, ENGINE_PHYSICS_PUSHER_EXT ))
			{
				if(( check_angles( pe->angles[0] ) || check_angles( pe->angles[2] )) && pmove->usehull != 2 )
					transform_bbox = true;
			}

			if( transform_bbox )
				Matrix4x4_CreateFromEntity( matrix, pe->angles, pe->origin, 1.0f );
			else Matrix4x4_CreateFromEntity( matrix, pe->angles, offset, 1.0f );

			Matrix4x4_VectorITransform( matrix, pos, pos_l );

			if( transform_bbox )
			{
				World_TransformAABB( matrix, host.player_mins[pmove->usehull], host.player_maxs[pmove->usehull], mins, maxs );
				VectorSubtract( hull->clip_mins, mins, offset );	// calc new local offset

				for( int j = 0; j < 3; j++ )
				{
					if( pos_l[j] >= 0.0f )
						pos_l[j] -= offset[j];
					else pos_l[j] += offset[j];
				}
			}
		}
		else
		{
			// offset the test point appropriately for this hull.
			VectorSubtract( pos, offset, pos_l );
		}

		if( pe->solid == SOLID_CUSTOM )
		{
			pmtrace_t	trace;

			PM_InitPMTrace( &trace, pos );

			// run custom sweep callback
			if( pmove->server || Host_IsLocalClient( ))
				SV_ClipPMoveToEntity( pe, pos, mins, maxs, pos, &trace );
#if !XASH_DEDICATED
			else CL_ClipPMoveToEntity( pe, pos, mins, maxs, pos, &trace );
#endif

			// if we inside the custom hull
			if( trace.allsolid )
				return i;
		}
		else if( hullcount == 1 )
		{
			if( PM_HullPointContents( hull, hull->firstclipnode, pos_l ) == CONTENTS_SOLID )
				return i;
		}
		else
		{
			for( int j = 0; j < hullcount; j++ )
			{
				if( PM_HullPointContents( &hull[j], hull[j].firstclipnode, pos_l ) == CONTENTS_SOLID )
					return i;
			}
		}
	}

	return -1; // didn't hit anything
}

/*
=============
PM_TruePointContents

=============
*/
int PM_TruePointContents( playermove_t *pmove, const vec3_t p )
{
	hull_t	*hull = &pmove->physents[0].model->hulls[0];

	if( hull )
	{
		return PM_HullPointContents( hull, hull->firstclipnode, p );
	}
	else
	{
		return CONTENTS_EMPTY;
	}
}

/*
=============
PM_PointContents

=============
*/
int PM_PointContents( playermove_t *pmove, const vec3_t p )
{
	// sanity check
	if( !p || !pmove->physents[0].model )
		return CONTENTS_NONE;

	// get base contents from world
	int contents = PM_HullPointContents( &pmove->physents[0].model->hulls[0], 0, p );

	for( int i = 1; i < pmove->numphysent; i++ )
	{
		physent_t *pe = &pmove->physents[i];

		if( pe->solid != SOLID_NOT ) // disabled ?
			continue;

		// only brushes can have special contents
		if( !pe->model ) continue;

		// check water brushes accuracy
		hull_t *hull = &pe->model->hulls[0];
		vec3_t test;

		if( FBitSet( pe->model->flags, MODEL_HAS_ORIGIN ) && !VectorIsNull( pe->angles ))
		{
			matrix4x4 matrix;

			Matrix4x4_CreateFromEntity( matrix, pe->angles, pe->origin, 1.0f );
			Matrix4x4_VectorITransform( matrix, p, test );
		}
		else
		{
			// offset the test point appropriately for this hull.
			VectorSubtract( p, pe->origin, test );
		}

		// test hull for intersection with this model
		if( PM_HullPointContents( hull, hull->firstclipnode, test ) == CONTENTS_EMPTY )
			continue;

		// compare contents ranking
		if( RankForContents( pe->skin ) > RankForContents( contents ))
			contents = pe->skin; // new content has more priority
	}

	return contents;
}

/*
=============
PM_TraceModel

=============
*/
float PM_TraceModel( playermove_t *pmove, physent_t *pe, float *start, float *end, trace_t *trace )
{
	PM_InitTrace( trace, end );

	int old_usehull = pmove->usehull;
	pmove->usehull = 2;

	vec3_t offset;
	hull_t *hull = PM_HullForBsp( pe, pmove, offset );

	pmove->usehull = old_usehull;

	qboolean rotated;
	if( pe->solid == SOLID_BSP && !VectorIsNull( pe->angles ))
		rotated = true;
	else rotated = false;

	vec3_t start_l, end_l;
	matrix4x4 matrix;

	if( rotated )
	{
		Matrix4x4_CreateFromEntity( matrix, pe->angles, offset, 1.0f );
		Matrix4x4_VectorITransform( matrix, start, start_l );
		Matrix4x4_VectorITransform( matrix, end, end_l );
	}
	else
	{
		VectorSubtract( start, offset, start_l );
		VectorSubtract( end, offset, end_l );
	}

	PM_RecursiveHullCheck( hull, hull->firstclipnode, 0, 1, start_l, end_l, (pmtrace_t *)trace );
	trace->ent = NULL;

	if( rotated )
	{
		vec3_t temp = Vec3( trace->plane.normal );
		Matrix4x4_TransformPositivePlane( matrix, temp, trace->plane.dist, trace->plane.normal, &trace->plane.dist );
	}

	VectorLerp( start, trace->fraction, end, trace->endpos );

	return trace->fraction;
}

pmtrace_t *PM_TraceLine( playermove_t *pmove, float *start, float *end, int flags, int usehull, int ignore_pe )
{
	static pmtrace_t tr;
	int old_usehull = pmove->usehull;
	pmove->usehull = usehull;

	switch( flags )
	{
	case PM_TRACELINE_PHYSENTSONLY:
		tr = PM_PlayerTraceExt( pmove, start, end, 0, pmove->numphysent, pmove->physents, ignore_pe, NULL );
		break;
	case PM_TRACELINE_ANYVISIBLE:
		tr = PM_PlayerTraceExt( pmove, start, end, 0, pmove->numvisent, pmove->visents, ignore_pe, NULL );
		break;
	}

	pmove->usehull = old_usehull;

	return &tr;
}

pmtrace_t *PM_TraceLineEx( playermove_t *pmove, float *start, float *end, int flags, int usehull, pfnIgnore pmFilter )
{
	static pmtrace_t tr;
	int old_usehull = pmove->usehull;
	pmove->usehull = usehull;

	switch( flags )
	{
	case PM_TRACELINE_PHYSENTSONLY:
		tr = PM_PlayerTraceExt( pmove, start, end, 0, pmove->numphysent, pmove->physents, -1, pmFilter );
		break;
	case PM_TRACELINE_ANYVISIBLE:
		tr = PM_PlayerTraceExt( pmove, start, end, 0, pmove->numvisent, pmove->visents, -1, pmFilter );
		break;
	}

	pmove->usehull = old_usehull;

	return &tr;
}

struct msurface_s *PM_TraceSurfacePmove( playermove_t *pmove, int ground, float *vstart, float *vend )
{
	if( ground < 0 || ground >= pmove->numphysent )
		return NULL; // bad ground

	return PM_TraceSurface( &pmove->physents[ground], vstart, vend );
}

const char *PM_TraceTexture( playermove_t *pmove, int ground, float *vstart, float *vend )
{
	if( ground < 0 || ground >= pmove->numphysent )
		return NULL; // bad ground

	msurface_t *surf = PM_TraceSurface( &pmove->physents[ground], vstart, vend );

	if( !surf || !surf->texinfo || !surf->texinfo->texture )
		return NULL;

	return surf->texinfo->texture->name;
}

int PM_PointContentsPmove( playermove_t *pmove, const float *p, int *truecontents )
{
	int truecont, cont;
	truecont = cont = PM_PointContents( pmove, p );
	if( truecontents ) *truecontents = truecont;

	if( cont <= CONTENTS_CURRENT_0 && cont >= CONTENTS_CURRENT_DOWN )
		cont = CONTENTS_WATER;
	return cont;
}

void PM_StuckTouch( playermove_t *pmove, int hitent, pmtrace_t *tr )
{
	for( int i = 0; i < pmove->numtouch; i++ )
	{
		if( pmove->touchindex[i].ent == hitent )
			return;
	}

	if( pmove->numtouch >= MAX_PHYSENTS )
		return;

	VectorCopy( pmove->velocity, tr->deltavelocity );
	tr->ent = hitent;

	pmove->touchindex[pmove->numtouch++] = *tr;
}
