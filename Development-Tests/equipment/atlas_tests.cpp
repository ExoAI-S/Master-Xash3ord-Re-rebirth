#include "worldmap_atlas.h"
#include <fstream>
#include <iterator>
#include <iostream>
int main(int argc,char** argv)
{
    if(argc!=2 || !MSRWorldAtlas::SelfTest()) { std::cerr<<"Atlas helper SelfTest failed\n";return 1; }
    for(const auto& tile:MSRWorldChart::tiles)
    {
        std::ifstream input(std::string(argv[1])+"/"+tile.file,std::ios::binary);
        if(!input) {std::cerr<<"Missing tile "<<tile.file<<'\n';return 1;}
        std::vector<unsigned char> bytes((std::istreambuf_iterator<char>(input)),{}),rgba;
        if(!MSRWorldAtlas::DecodeTile(bytes.data(),bytes.size(),rgba)) {std::cerr<<"Rejected tile "<<tile.file<<'\n';return 1;}
    }
    std::cout<<"PASS atlas helper SelfTest and "<<MSRWorldChart::tileCount<<" actual packaged tile decodes. No engine, texture upload or UI run.\n";
}
