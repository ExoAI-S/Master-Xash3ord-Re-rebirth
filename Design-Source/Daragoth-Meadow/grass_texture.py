"""Original tileable meadow grain; numeric palette reference, no copied pixels."""
from functools import lru_cache
import math
import random


@lru_cache(maxsize=1)
def grass_texture():
    rng=random.Random(930730);size=256
    low,high=(19,62,0),(104,87,8)
    palette=bytes(max(0,min(255,round((low[c]+(high[c]-low[c])*hue/15)*(.55+shade/15*.77))))
        for hue in range(16) for shade in range(16) for c in range(3))
    grids=[(n,[rng.uniform(-1,1)for _ in range(n*n)],weight)
        for n,weight in ((4,.24),(8,.30),(16,.26),(32,.20))]
    noise=[]
    for y in range(size):
        for x in range(size):
            value=0
            for n,grid,weight in grids:
                xx=x*n/size;yy=y*n/size;ix=int(xx);iy=int(yy)
                tx=xx-ix;ty=yy-iy;tx=tx*tx*(3-2*tx);ty=ty*ty*(3-2*ty)
                a=grid[iy*n+ix];b=grid[iy*n+(ix+1)%n]
                c=grid[((iy+1)%n)*n+ix];d=grid[((iy+1)%n)*n+(ix+1)%n]
                value+=weight*((a+(b-a)*tx)*(1-ty)+(c+(d-c)*tx)*ty)
            noise.append(value)
    mean=sum(noise)/len(noise)
    deviation=math.sqrt(sum((v-mean)**2 for v in noise)/len(noise))
    pixels=bytearray()
    for value in noise:
        value=(value-mean)/deviation
        hue=round(7.5+value*2.4+rng.uniform(-1.2,1.2))
        shade=round(8+value*1.4+rng.uniform(-2.2,2.2))
        pixels.append(max(0,min(15,hue))*16+max(0,min(15,shade)))
    for _ in range(7200):
        x=rng.randrange(size);y=rng.randrange(size);length=rng.randrange(2,7)
        bend=rng.choice((-1,0,1));delta=rng.choice((-2,2,3))
        for i in range(length):
            index=((y+i)%size)*size+(x+bend*i//3)%size
            old=pixels[index];pixels[index]=(old//16)*16+max(0,min(15,old%16+delta))
    return size,size,pixels,palette
