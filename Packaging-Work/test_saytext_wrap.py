"""Compile and exercise the production chat wrapper with a deterministic font."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
source = (root/'Full-Source/msr_source/src/game/client/saytext.cpp').read_text()

def function(signature):
    start = source.index(signature)
    body = source.index('{', start)
    depth = 1
    end = body + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]

harness = r'''
#include <cstring>
#include <cassert>
#include <string>
#include <iostream>
constexpr int MAX_LINES = 5, MAX_CHARS_PER_LINE = 256, LINE_START = 10;
static char g_szLineBuffer[MAX_LINES+1][MAX_CHARS_PER_LINE];
static float *g_pflNameColors[MAX_LINES+1];
static int g_iNameLengths[MAX_LINES+1], line_height, screenWidth;
int ScreenWidth() { return screenWidth; }
void GetConsoleStringSize(const char *text, int *w, int *h) {
    *w = int(strlen(text))*8; *h = 12;
}
class CHudSayText { public: void EnsureTextFitsInOneLineAndWrapIfHaveTo(int); };
''' + function('int ScrollTextUp( void )') + '\n' + function('void CHudSayText :: EnsureTextFitsInOneLineAndWrapIfHaveTo( int line )') + r'''
void reset(const std::string &text, int width) {
    memset(g_szLineBuffer, 0, sizeof(g_szLineBuffer));
    strncpy(g_szLineBuffer[0], text.c_str(), MAX_CHARS_PER_LINE-1);
    screenWidth=width;
}
int main() {
    CHudSayText hud;
    const char *status="Dungeon Master: the host must grant you control with the Dungeon Master host tool.";
    reset(status,0);
    hud.EnsureTextFitsInOneLineAndWrapIfHaveTo(0);
    assert(std::string(g_szLineBuffer[0])==status);
    screenWidth=1280;
    hud.EnsureTextFitsInOneLineAndWrapIfHaveTo(0);
    assert(std::string(g_szLineBuffer[0])==status);
    reset("one two three four five six",120);
    hud.EnsureTextFitsInOneLineAndWrapIfHaveTo(0);
    std::string joined;
    for(int i=0;i<MAX_LINES;i++) {
        assert(strlen(g_szLineBuffer[i])*8+LINE_START<=80);
        if(g_szLineBuffer[i][0]) { if(!joined.empty()) joined+=' '; joined+=g_szLineBuffer[i]; }
    }
    assert(joined=="one two three four five six");
    reset("abcdefghijklmnopqrstuvwx",100);
    hud.EnsureTextFitsInOneLineAndWrapIfHaveTo(0);
    joined.clear();
    for(int i=0;i<MAX_LINES;i++) joined+=g_szLineBuffer[i];
    assert(joined=="abcdefghijklmnopqrstuvwx");
    for(int width: {0,1,40,50,51,52,58,64,100,320,1280,3840}) {
        reset(std::string(255,'W'),width);
        for(int i=1;i<MAX_LINES;i++) strcpy(g_szLineBuffer[i],"occupied");
        hud.EnsureTextFitsInOneLineAndWrapIfHaveTo(0);
        for(auto &row:g_szLineBuffer) assert(memchr(row,0,sizeof(row)));
        reset("/(unterminated",width);
        hud.EnsureTextFitsInOneLineAndWrapIfHaveTo(0);
    }
    hud.EnsureTextFitsInOneLineAndWrapIfHaveTo(-1);
    hud.EnsureTextFitsInOneLineAndWrapIfHaveTo(MAX_LINES);
    std::cout<<"PASS: startup, resizing, status, word wrapping, long words, tiny widths, full buffer, malformed color, bounds\n";
}
'''
with tempfile.TemporaryDirectory(prefix='msr-chat-test-') as folder:
    work = Path(folder)
    cpp = work/'chat_wrap_test.cpp'
    cpp.write_text(harness)
    subprocess.run(['cl.exe','/nologo','/EHsc','/std:c++20',str(cpp),'/Fe:'+str(work/'chat_wrap_test.exe')], cwd=work,check=True)
    subprocess.run([str(work/'chat_wrap_test.exe')],check=True,timeout=10)
