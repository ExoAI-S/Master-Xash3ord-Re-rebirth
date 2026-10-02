"""Road surface clipping and read-only import of the installed Daragoth road."""
import hashlib
import math
import struct


def entry_road_width(y, base):
    # The surveyed original exit road is x1400..1656, centered at1528.
    # Keep its 256-unit physical width so the original stones retain their size.
    return 128


def installed_path_texture(bsp):
    """Return exact source indices/palette; never save extracted assets to source."""
    texture=next(t for t in bsp.textures if t.name.lower()=='deraliaroad_2_0')
    raw=texture.raw
    width,height,*offsets=struct.unpack_from('<6I',raw,16)
    palette_start=offsets[3]+width*height//64
    assert (width,height)==(256,256) and struct.unpack_from('<H',raw,palette_start)[0]==256
    pixels=raw[offsets[0]:offsets[0]+width*height]
    palette=raw[palette_start+2:palette_start+770]
    assert len(pixels)==width*height and len(palette)==768
    return (width,height,pixels,palette),{'texture':texture.name,
        'indexed_pixels_sha256':hashlib.sha256(pixels).hexdigest(),
        'palette_sha256':hashlib.sha256(palette).hexdigest()}


def path_axes(points, road_x, road_width):
    """Affine Valve220 Saxis gives each triangular half-road a shared stripe."""
    values=[128+128*(p[0]-road_x(p[1]))/road_width(p[1]) for p in points]
    return _axes_from_values(points, values)


def _axes_from_values(points, values):
    a,b,c=points
    determinant=(b[0]-a[0])*(c[1]-a[1])-(c[0]-a[0])*(b[1]-a[1])
    if abs(determinant)<1e-6:raise ValueError('Degenerate road face')
    sx=((values[1]-values[0])*(c[1]-a[1])-(values[2]-values[0])*(b[1]-a[1]))/determinant
    sy=((b[0]-a[0])*(values[2]-values[0])-(c[0]-a[0])*(values[1]-values[0]))/determinant
    return sx,sy,values[0]-sx*a[0]-sy*a[1]


def split_road_triangle(points, road_x, desired_width, *, s_values=None):
    """Return ``(center, outer, axes)`` without changing the terrain plane.

    ``center`` and ``outer`` contain XYZ triangles with the input winding.
    Evaluate the desired half-width only at the three original vertices, snap
    values within 0.25 texels of an edge to that edge, then clip their affine S
    coordinate at 0 and 256. The snap avoids tiny brushes at rounded integer
    road columns and changes S by at most 0.25 texels. All center pieces retain
    the returned Valve220 ``(sx, sy, shift)``; do not
    recompute axes at new vertices, where the nonlinear road width can differ.
    Adjacent original triangles therefore agree along their shared edge.

    ``s_values`` optionally supplies three explicit vertex S coordinates.
    Apply this helper only to original main-road triangles; village side paths
    and other dirt faces are outside its scope.
    """
    points=tuple(tuple(float(v) for v in point) for point in points)
    if len(points)!=3 or any(len(point)!=3 for point in points):
        raise ValueError('Expected three XYZ road vertices')
    if not all(math.isfinite(v) for point in points for v in point):
        raise ValueError('Road vertices must be finite')
    if s_values is None:
        widths=tuple(float(desired_width(point[1])) for point in points)
        centers=tuple(float(road_x(point[1])) for point in points)
        if not all(math.isfinite(width) and width>0 for width in widths):
            raise ValueError('Desired road half-width must be positive and finite')
        if not all(math.isfinite(center) for center in centers):
            raise ValueError('Road centers must be finite')
        values=tuple(128+128*(point[0]-center)/width
                     for point,center,width in zip(points,centers,widths))
    else:
        values=tuple(float(value) for value in s_values)
    if len(values)!=3 or not all(math.isfinite(value) for value in values):
        raise ValueError('Expected three finite vertex S coordinates')
    values=tuple(0.0 if abs(value)<=.25 else
                 256.0 if abs(value-256)<=.25 else value for value in values)
    axes=_axes_from_values(points,values)
    polygon=tuple(zip(points,values))

    def clip(vertices, boundary, keep_above):
        if not vertices:return ()
        result=[]
        previous=vertices[-1]
        previous_inside=(previous[1]>=boundary if keep_above else previous[1]<=boundary)
        for current in vertices:
            current_inside=(current[1]>=boundary if keep_above else current[1]<=boundary)
            if current_inside!=previous_inside:
                if previous[1]==boundary:intersection=previous[0]
                elif current[1]==boundary:intersection=current[0]
                else:
                    t=(boundary-previous[1])/(current[1]-previous[1])
                    intersection=tuple(previous[0][i]+t*(current[0][i]-previous[0][i])
                                       for i in range(3))
                result.append((intersection,boundary))
            if current_inside:result.append(current)
            previous=current;previous_inside=current_inside
        return tuple(result)

    def triangles(vertices):
        # Exact boundary vertices can be emitted twice by inclusive clipping.
        clean=[]
        for point,_ in vertices:
            if not clean or max(abs(point[i]-clean[-1][i]) for i in range(3))>1e-8:
                clean.append(point)
        if len(clean)>1 and max(abs(clean[0][i]-clean[-1][i]) for i in range(3))<=1e-8:
            clean.pop()
        result=[]
        for i in range(1,len(clean)-1):
            a,b,c=clean[0],clean[i],clean[i+1]
            area2=(b[0]-a[0])*(c[1]-a[1])-(c[0]-a[0])*(b[1]-a[1])
            if abs(area2)>1e-6:result.append((a,b,c))
        return tuple(result)

    center=triangles(clip(clip(polygon,0,True),256,False))
    outer=triangles(clip(polygon,0,False))+triangles(clip(polygon,256,True))
    return center,outer,axes
