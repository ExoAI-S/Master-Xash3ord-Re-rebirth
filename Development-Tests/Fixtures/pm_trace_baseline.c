/* Baseline Xash PM_RecursiveHullCheck for regression comparison.
 * Copyright (C) 2010 Uncle Mike. GPL-3.0-or-later, same license as engine source.
 * Frozen immediately before the interval traversal fix. */
qboolean PM_RecursiveHullCheck( hull_t *hull, int num, float p1f, float p2f, vec3_t p1, vec3_t p2, pmtrace_t *trace )
{
	int children[2];
	mplane_t		*plane;
	float		t1, t2;
	float		frac, midf;
	int		side;
	vec3_t		mid;
loc0:
	// check for empty
	if( num < 0 )
	{
		if( num != CONTENTS_SOLID )
		{
			trace->allsolid = false;
			if( num == CONTENTS_EMPTY )
				trace->inopen = true;
			else trace->inwater = true;
		}
		else trace->startsolid = true;
		return true; // empty
	}

	if( hull->firstclipnode >= hull->lastclipnode )
	{
		// empty hull?
		trace->allsolid = false;
		trace->inopen = true;
		return true;
	}

	if( num < hull->firstclipnode || num > hull->lastclipnode )
		Host_Error( "%s: bad node number %i\n", __func__, num );

	// find the point distances
	if( world.version == QBSP2_VERSION )
	{
		children[0] = hull->clipnodes32[num].children[0];
		children[1] = hull->clipnodes32[num].children[1];
		plane = hull->planes + hull->clipnodes32[num].planenum;
	}
	else
	{
		children[0] = hull->clipnodes16[num].children[0];
		children[1] = hull->clipnodes16[num].children[1];
		plane = hull->planes + hull->clipnodes16[num].planenum;
	}

	t1 = PlaneDiff( p1, plane );
	t2 = PlaneDiff( p2, plane );

	if( t1 >= 0.0f && t2 >= 0.0f )
	{
		num = children[0];
		goto loc0;
	}

	if( t1 < 0.0f && t2 < 0.0f )
	{
		num = children[1];
		goto loc0;
	}

	// put the crosspoint DIST_EPSILON pixels on the near side
	side = (t1 < 0.0f);

	if( side ) frac = ( t1 + DIST_EPSILON ) / ( t1 - t2 );
	else frac = ( t1 - DIST_EPSILON ) / ( t1 - t2 );

	// inverted comparison also catches NaN (e.g. from a non-finite trace passed
	// in by the game dll), which otherwise slips through both clamps and turns
	// the backing-up loop below into an infinite loop, hanging the host
	if( !( frac >= 0.0f )) frac = 0.0f;
	if( frac > 1.0f ) frac = 1.0f;

	midf = p1f + ( p2f - p1f ) * frac;
	VectorLerp( p1, frac, p2, mid );

	// move up to the node
	if( !PM_RecursiveHullCheck( hull, children[side], p1f, midf, p1, mid, trace ))
		return false;

	// this recursion can not be optimized because mid would need to be duplicated on a stack
	if( PM_HullPointContents( hull, children[side^1], mid ) != CONTENTS_SOLID )
	{
		// go past the node
		return PM_RecursiveHullCheck( hull, children[side^1], midf, p2f, mid, p2, trace );
	}

	// never got out of the solid area
	if( trace->allsolid )
		return false;

	// the other side of the node is solid, this is the impact point
	if( !side )
	{
		VectorCopy( plane->normal, trace->plane.normal );
		trace->plane.dist = plane->dist;
	}
	else
	{
		VectorNegate( plane->normal, trace->plane.normal );
		trace->plane.dist = -plane->dist;
	}

	while( PM_HullPointContents( hull, hull->firstclipnode, mid ) == CONTENTS_SOLID )
	{
		// shouldn't really happen, but does occasionally
		frac -= 0.1f;

		// inverted comparison also catches NaN, see above
		if( !( frac >= 0.0f ))
		{
			trace->fraction = midf;
			VectorCopy( mid, trace->endpos );
			Con_Reportf( S_WARN "trace backed up past 0.0\n" );
			return false;
		}

		midf = p1f + ( p2f - p1f ) * frac;
		VectorLerp( p1, frac, p2, mid );
	}

	trace->fraction = midf;
	VectorCopy( mid, trace->endpos );

	return false;
}
