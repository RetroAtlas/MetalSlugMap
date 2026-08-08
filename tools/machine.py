"""A Metal Slug X machine: the game's code in memory, with the disc stubbed out.

The point of this is to let the game place its own objects. Everything that
moves in a stage is created by executable code rather than described by a table,
so the only faithful way to read placements back is to run that code — this sets
up enough of a console for it to run in.

The disc is the one piece the game cannot do without, and it asks for files in a
way that is easy to answer: its loader takes an entry from the asset manifest in
the executable, so the trap here reads the path out of memory, finds that file,
and drops it at the load address the entry names. The game therefore tells us
what to load and where, which is also the only way to know which overlay is
resident in an arena several files share.
"""
import struct

from cpu import Cpu
from manifest import COUNT, TABLE, entries

EXE = "SLUS_012.12"
CD_LOAD = 0x8001db64        # takes a manifest entry, streams the file to its address
ACTOR_NEW = 0x80014f24      # allocates an actor: flags, parent, required free slots
CURRENT_ACTOR = 0x800c9a98
FREE_LIST = 0x800c9a94
FREE_COUNT = 0x800d41fc
ACTOR_SIZE = 332

# The game reaches the kernel the way every PlayStation title does, by jumping to
# a vector with the function number in $t1. Only the memory and string calls have
# to do anything real; the rest exist so the caller gets an answer and continues.
BIOS_VECTORS = (0xA0, 0xB0, 0xC0)


def _bios_a(cpu, fn):
    r = cpu.r
    dst, src, n = r[4], r[5], r[6]
    if fn in (0x2a, 0x2c, 0x27):                       # memcpy, memmove, bcopy
        if fn == 0x27:
            dst, src, n = r[5], r[4], r[6]
        cpu.load(dst, bytes(cpu.read(src + i, 1) for i in range(n)))
        return dst
    if fn == 0x2b:                                     # memset
        cpu.load(dst, bytes([src & 0xFF]) * n)
        return dst
    if fn == 0x28:                                     # bzero
        cpu.load(dst, bytes(src))
        return dst
    if fn in (0x2d, 0x29):                             # memcmp, bcmp
        for i in range(n):
            a, b = cpu.read(dst + i, 1), cpu.read(src + i, 1)
            if a != b:
                return (a - b) & 0xFFFFFFFF
        return 0
    if fn == 0x1b:                                     # strlen
        return len(cpu.cstring(r[4], 1024))
    if fn == 0x19:                                     # strcpy
        cpu.load(dst, cpu.cstring(src, 1024).encode() + b"\0")
        return dst
    if fn == 0x2f:                                     # rand
        return 0
    return 0


class Machine:
    def __init__(self, disc):
        self.disc = disc
        exe = disc.read_file(EXE)
        pc0, gp, taddr, tsize = struct.unpack_from("<IIII", exe, 0x10)
        sp = struct.unpack_from("<I", exe, 0x30)[0]
        self.entry = pc0
        self.cpu = Cpu()
        self.cpu.load(taddr, exe[0x800:0x800 + tsize])
        self.cpu.r[28] = gp
        self.cpu.r[29] = self.cpu.r[30] = sp or 0x801FFFF0
        self.manifest = {i: e for i, e in enumerate(entries(exe))}
        self.loaded = []
        self.spawned = []
        self.kernel = {}        # (vector, fn) -> times called, so gaps are visible
        self.cpu.traps[CD_LOAD] = self._cd_load
        for vector in BIOS_VECTORS:
            self.cpu.traps[vector] = self._bios

    # ---- traps ----------------------------------------------------------
    def _bios(self, cpu):
        vector = cpu.pc_trap
        fn = cpu.r[9]
        self.kernel[(vector, fn)] = self.kernel.get((vector, fn), 0) + 1
        cpu.r[2] = _bios_a(cpu, fn) if vector == 0xA0 else 0

    def _cd_load(self, cpu):
        entry = cpu.r[4]
        path = cpu.cstring(cpu.read(entry, 4), 64)
        name = path.split("\\")[-1].split(";")[0]
        dest = cpu.read(entry + 4, 4)
        if name in self.disc.files:
            lba, size = self.disc.files[name]
            cpu.load(dest, self.disc.read_file(name))
            cpu.write(entry + 8, 4, lba)
            cpu.write(entry + 12, 4, size)
            self.loaded.append((name, dest))
        cpu.r[2] = 1        # non-zero tells the caller the load finished

    def watch_spawns(self):
        """Log every actor the game allocates, letting the real routine run."""
        def trap(cpu):
            ra = cpu.r[31]
            args = (cpu.r[4], cpu.r[5], cpu.r[6])
            del cpu.traps[ACTOR_NEW]
            got = cpu.call(ACTOR_NEW, args, ra=0xDEAD1000)
            cpu.traps[ACTOR_NEW] = trap
            self.spawned.append({"actor": got, "flags": args[0], "parent": args[1],
                                 "at": cpu.steps})
            cpu.r[2] = got
            cpu.r[31] = ra
        self.cpu.traps[ACTOR_NEW] = trap

    def index_of(self, name):
        for i, e in self.manifest.items():
            if e[1].split("\\")[-1].split(";")[0] == name:
                return i
        return None

    def load(self, name):
        """Load a file the way the game would, through its own manifest entry."""
        i = self.index_of(name)
        if i is None:
            raise KeyError(name)
        self.cpu.call(CD_LOAD, (TABLE + i * 16,))
        return self.manifest[i][2]
