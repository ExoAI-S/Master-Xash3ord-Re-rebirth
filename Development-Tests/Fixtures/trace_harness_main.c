int main(int argc,char**argv)
{
    FILE*in,*out;char magic[8];uint32_t header[8];hull_t hull={0};mplane_t*planes;mclipnode16_t*clip16;mclipnode32_t*clip32;LARGE_INTEGER frequency;
    if(argc!=3)return 2;
    in=fopen(argv[1],"rb");out=fopen(argv[2],"wb");if(!in||!out)return 3;
    if(fread(magic,1,8,in)!=8||memcmp(magic,"MSRTRACE",8)||fread(header,4,8,in)!=8)return 4;
    planes=calloc(header[0],sizeof(*planes));clip16=calloc(header[1],sizeof(*clip16));clip32=calloc(header[1],sizeof(*clip32));if((header[0]&&!planes)||(header[1]&&(!clip16||!clip32)))return 5;
    if(fread(planes,sizeof(*planes),header[0],in)!=header[0]||fread(clip32,sizeof(*clip32),header[1],in)!=header[1])return 6;
    for(uint32_t i=0;i<header[1];i++){clip16[i].planenum=clip32[i].planenum;clip16[i].children[0]=(int16_t)clip32[i].children[0];clip16[i].children[1]=(int16_t)clip32[i].children[1];}
    world.version=header[4];hull.planes=planes;hull.firstclipnode=(int)header[2];hull.lastclipnode=(int)header[3];
    if(world.version==QBSP2_VERSION)hull.clipnodes32=clip32;else hull.clipnodes16=clip16;
    if(header[7]&2)hull.clipnodes16=NULL;
    if(header[7]&4)hull.planes=NULL;
    QueryPerformanceFrequency(&frequency);
    for(uint32_t i=0;i<header[6];i++)
    {
        float points[6];pmtrace_t trace={0};LARGE_INTEGER before,after;double elapsed;
        if(fread(points,sizeof(float),6,in)!=6)return 7;
        trace.allsolid=true;trace.fraction=1;VectorCopy(points+3,trace.endpos);profile_nodes=profile_recursions=profile_pointqueries=0;
        QueryPerformanceCounter(&before);
        if(header[5])PM_RecursiveHullCheck_Baseline((header[7]&1)?NULL:&hull,hull.firstclipnode,0,1,points,points+3,&trace);
        else PM_RecursiveHullCheck((header[7]&1)?NULL:&hull,hull.firstclipnode,0,1,points,points+3,&trace);
        QueryPerformanceCounter(&after);elapsed=(double)(after.QuadPart-before.QuadPart)/frequency.QuadPart;
        fwrite(&trace.allsolid,4,1,out);fwrite(&trace.startsolid,4,1,out);fwrite(&trace.inopen,4,1,out);fwrite(&trace.inwater,4,1,out);fwrite(&trace.fraction,4,1,out);fwrite(trace.endpos,4,3,out);fwrite(trace.plane.normal,4,3,out);fwrite(&trace.plane.dist,4,1,out);
        fwrite(&profile_nodes,8,1,out);fwrite(&profile_recursions,8,1,out);fwrite(&profile_pointqueries,8,1,out);fwrite(&elapsed,8,1,out);
    }
    fclose(in);fclose(out);free(planes);free(clip16);free(clip32);return 0;
}
