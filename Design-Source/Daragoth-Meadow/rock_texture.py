"""Original tileable weathered stone, without the former broad sine checker."""
from functools import lru_cache
import math
import random


@lru_cache(maxsize=1)
def rock_texture():
    rng=random.Random(930971);size=256
    low,high=(57,58,35),(100,91,57)
    palette=bytes(max(0,min(255,round((low[c]+(high[c]-low[c])*hue/15)*(.60+shade/15*.75))))
        for hue in range(16)for shade in range(16)for c in range(3))
    grids=[(n,[rng.uniform(-1,1)for _ in range(n*n)],weight)
        for n,weight in((4,.32),(8,.30),(16,.24),(32,.14))]
    pixels=bytearray()
    for y in range(size):
        for x in range(size):
            value=0
            for n,grid,weight in grids:
                xx=x*n/size;yy=y*n/size;ix=int(xx);iy=int(yy)
                tx=xx-ix;ty=yy-iy;tx=tx*tx*(3-2*tx);ty=ty*ty*(3-2*ty)
                a=grid[iy*n+ix];b=grid[iy*n+(ix+1)%n]
                c=grid[((iy+1)%n)*n+ix];d=grid[((iy+1)%n)*n+(ix+1)%n]
                value+=weight*((a+(b-a)*tx)*(1-ty)+(c+(d-c)*tx)*ty)
            xx=x*math.tau/size;yy=y*math.tau/size
            vein=math.sin(6*yy+.8*math.sin(3*xx)+value*2)
            fissure=2.3 if abs(vein)<.09 else 0
            hue=round(7.5+value*5+rng.uniform(-.7,.7))
            shade=round(8+value*4+rng.uniform(-1.4,1.4)-fissure)
            pixels.append(max(0,min(15,hue))*16+max(0,min(15,shade)))
    return size,size,pixels,palette
