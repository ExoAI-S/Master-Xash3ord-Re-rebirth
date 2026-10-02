"""Read only the known client KB_Find list; never write or control the game."""
import ctypes as c
from ctypes import wintypes as w
import json, struct, sys
from pathlib import Path

K = c.WinDLL('kernel32', use_last_error=True)
class Module(c.Structure):
    _fields_=[('dwSize',w.DWORD),('th32ModuleID',w.DWORD),('th32ProcessID',w.DWORD),
              ('GlblcntUsage',w.DWORD),('ProccntUsage',w.DWORD),('modBaseAddr',c.c_void_p),
              ('modBaseSize',w.DWORD),('hModule',c.c_void_p),('szModule',w.WCHAR*256),
              ('szExePath',w.WCHAR*260)]
K.CreateToolhelp32Snapshot.argtypes=[w.DWORD,w.DWORD]; K.CreateToolhelp32Snapshot.restype=c.c_void_p
K.Module32FirstW.argtypes=[c.c_void_p,c.POINTER(Module)]
K.Module32NextW.argtypes=[c.c_void_p,c.POINTER(Module)]
K.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD]; K.OpenProcess.restype=c.c_void_p
K.ReadProcessMemory.argtypes=[c.c_void_p,c.c_void_p,c.c_void_p,c.c_size_t,c.POINTER(c.c_size_t)]
K.CloseHandle.argtypes=[c.c_void_p]

def snapshot(pid):
    handle=K.CreateToolhelp32Snapshot(0x18,pid)
    entry=Module(); entry.dwSize=c.sizeof(entry)
    try:
        ok=K.Module32FirstW(handle,c.byref(entry))
        while ok:
            if entry.szModule.lower()=='client.dll':
                base=entry.modBaseAddr; size=entry.modBaseSize; path=Path(entry.szExePath)
                break
            ok=K.Module32NextW(handle,c.byref(entry))
        else: raise RuntimeError('Client DLL not loaded')
    finally: K.CloseHandle(handle)
    process=K.OpenProcess(0x410,False,pid)
    if not process: raise c.WinError(c.get_last_error())
    def read(address,length):
        buffer=c.create_string_buffer(length); count=c.c_size_t()
        if not K.ReadProcessMemory(process,address,buffer,length,c.byref(count)) or count.value!=length:
            raise c.WinError(c.get_last_error())
        return buffer.raw
    def u32(address): return struct.unpack('<I',read(address,4))[0]
    try:
        pe=base+u32(base+0x3c)
        if read(pe,4)!=b'PE\0\0' or read(pe+24,2)!=b'\x0b\x01': raise RuntimeError('Expected Win32 PE')
        export=base+u32(pe+24+96)
        values=struct.unpack('<10I',read(export,40))
        functions,names,ordinals=(base+values[i] for i in (7,8,9))
        for index in range(values[6]):
            name=read(base+u32(names+4*index),64).split(b'\0')[0]
            if name==b'KB_Find':
                ordinal=struct.unpack('<H',read(ordinals+2*index,2))[0]
                function=base+u32(functions+4*ordinal); break
        else: raise RuntimeError('KB_Find export absent')
        code=read(function,64)
        # MSVC /Od Win32 KB_Find loads g_kbkeys with MOV EAX, moffs32.
        candidates=[struct.unpack('<I',code[i+1:i+5])[0] for i in range(60)
                    if code[i]==0xa1 and base<=struct.unpack('<I',code[i+1:i+5])[0]<base+size]
        for candidate in candidates:
            p=u32(candidate); result={}
            for _ in range(64):
                if not p: break
                item=read(p,40); nxt,key=struct.unpack('<II',item[:8])
                name=item[8:].split(b'\0')[0].decode('ascii')
                if name in ('in_mlook','in_jlook','in_graph'):
                    result[name]=dict(zip(('down0','down1','state'),struct.unpack('<iii',read(key,12))))
                p=nxt
            if 'in_mlook' in result: return {'pid':pid,'client':str(path),'buttons':result}
        raise RuntimeError('Unrecognized KB_Find code; no state returned')
    finally: K.CloseHandle(process)

if __name__=='__main__':
    print(json.dumps(snapshot(int(sys.argv[1])),indent=2))
