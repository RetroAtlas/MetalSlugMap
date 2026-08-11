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

Not every file is asked for by manifest entry, though: a stage names its own
files by path and has them looked up first, so the lookup is answered from the
disc image too. That is not a convenience — a lookup that fails is retried on
the same file forever, so leaving it unanswered stalls the game outright.
"""
import struct

from cpu import Cpu
from manifest import COUNT, TABLE, entries

EXE = "SLUS_012.12"
CD_LOAD = 0x8001db64        # takes a manifest entry, streams the file to its address
CD_FIND = 0x8006f2c4        # looks a path up on the disc: where it is, and how big
CD_STREAM = 0x80072504      # reads a named file, or the next piece of the last one
ACTOR_NEW = 0x80014f24      # allocates an actor: flags, parent, required free slots
CURRENT_ACTOR = 0x800c9a98
FREE_LIST = 0x800c9a94
FREE_COUNT = 0x800d41fc
ACTOR_SIZE = 332
MAIN = 0x8001255c

# The disc driver polls hardware that is not here and times out, over and over.
# Answering success at the library's own entry points keeps the game moving; the
# file requests it really cares about arrive at CD_LOAD, which is served in full.
CD_STUBS = (0x80061cf8, 0x80071354, 0x800715c4)

STAGE_START = 0x80013280    # sets a stage up; takes its index from PICK_STAGE
PICK_STAGE = 0x800529b0     # trap this to choose one of the sub-stage table's entries
FRAME_LOOP = 0x800152e8     # walks the actor lists and calls each handler
CD_COMMAND = 0x800706e8     # two in to the library's command sender, which the
                            # retry wrapper at 0x80071490 asks up to four times
VSYNC = 0x8006e434          # returns the frame counter, which the game waits on
DRAW_LIST = 0x8007d0ec      # walks the primitive list; drawing, so it can be skipped
BSS, BSS_END = 0x800c9a50, 0x800fa6b0    # the range the start-up code clears

# The game reaches the kernel the way every PlayStation title does, by jumping to
# a vector with the function number in $t1. Only the memory and string calls have
# to do anything real; the rest exist so the caller gets an answer and continues.
BIOS_VECTORS = (0xA0, 0xB0, 0xC0)

GPUSTAT = 0x1F801814
# bits 26-28 are the "ready" flags the drawing code waits on; without them set
# the game spins forever on a graphics chip that is never going to answer
GPU_READY = 0x1C000000


def _basename(path):
    return path.split("\\")[-1].split(";")[0].upper()


def _found_file(lba, size, name):
    """A lookup's answer, laid out the way the disc library hands it back.

    The position is what the drive is asked to seek to, so it is a running time
    from the start of the lead-in rather than a sector number.
    """
    frames = lba + 150
    bcd = lambda v: (v // 10) * 16 + v % 10
    pos = bytes([bcd(frames // 4500), bcd(frames // 75 % 60), bcd(frames % 75), 0])
    return pos + struct.pack("<I", size) + name.encode()[:15].ljust(16, b"\0")


def _bios_b(cpu, fn, events):
    """The kernel's event system, answered as if everything already happened.

    Waiting on the disc or on a frame is how the game paces itself against
    hardware that is not here, so an event that is always ready is what keeps it
    moving. Nothing it waits for can fail in this machine.
    """
    if fn == 0x08:                                     # OpenEvent
        events.append(cpu.r[4])
        return 0xF1000000 + len(events)
    if fn in (0x07, 0x09, 0x0a, 0x0b, 0x0c, 0x0d):     # Deliver/Close/Wait/Test/Enable
        return 1
    return 0


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
        self.searched = []
        self.streamed = []
        self.stream = None
        self.spawned = []
        self.kernel = {}        # (vector, fn) -> times called, so gaps are visible
        self.events = []
        self.frames = 0
        self.cpu.traps[CD_LOAD] = self._cd_load
        self.cpu.traps[CD_FIND] = self._cd_find
        self.cpu.traps[CD_STREAM] = self._cd_stream
        for addr in CD_STUBS:
            self.cpu.traps[addr] = self._cd_ok
        self.cpu.traps[VSYNC] = self._vsync
        self.cpu.traps[DRAW_LIST] = self._nothing
        self.cpu.on_syscall = self._syscall
        self.cpu.io_read = self._io_read
        for vector in BIOS_VECTORS:
            self.cpu.traps[vector] = self._bios

    # ---- traps ----------------------------------------------------------
    def _bios(self, cpu):
        vector = cpu.pc_trap
        fn = cpu.r[9]
        self.kernel[(vector, fn)] = self.kernel.get((vector, fn), 0) + 1
        if vector == 0xA0:
            cpu.r[2] = _bios_a(cpu, fn)
        elif vector == 0xB0:
            cpu.r[2] = _bios_b(cpu, fn, self.events)
        else:
            cpu.r[2] = 0

    def _vsync(self, cpu):
        # The game paces itself by waiting for this count to move on. Nothing
        # advances it here, so time has to come from somewhere: one call, one
        # frame, which is what a console with no interrupts can honestly offer.
        self.frames += 1
        cpu.r[2] = self.frames

    def _nothing(self, cpu):
        cpu.r[2] = 0

    def _io_read(self, addr, size):
        return GPU_READY if (addr & 0x1FFFFFFF) == GPUSTAT else 0

    def _syscall(self, cpu):
        # 1 enters a critical section, 2 leaves one; the answer to the first is
        # whether interrupts had been enabled, and nothing here has any
        self.kernel[("syscall", cpu.r[4])] = self.kernel.get(("syscall", cpu.r[4]), 0) + 1
        cpu.r[2] = 1 if cpu.r[4] == 1 else 0

    def _cd_ok(self, cpu):
        self.kernel[("cd", cpu.pc_trap)] = self.kernel.get(("cd", cpu.pc_trap), 0) + 1
        cpu.r[2] = 1

    def _cd_find(self, cpu):
        name = _basename(cpu.cstring(cpu.r[5], 64))
        found = self.disc.files.get(name)
        if found:
            cpu.load(cpu.r[4], _found_file(*found, name))
        self.searched.append((name, bool(found)))
        cpu.r[2] = cpu.r[4] if found else 0

    def _cd_stream(self, cpu):
        """Hand over a file the library streams rather than loads outright.

        A name opens a file; no name asks for the next piece of the one already
        open, so the position has to be kept between calls. The drive works in
        whole sectors and the caller knows it, asking for what it wants and
        being given the sector it lands in.
        """
        name, dest, want = cpu.r[4], cpu.r[5], cpu.r[6]
        if name:
            self.stream = [_basename(cpu.cstring(name, 64)), 0]
        found = self.disc.files.get(self.stream[0]) if self.stream else None
        if not found:
            cpu.r[2] = 0
            return
        lba, size = found
        left = size - self.stream[1]
        read = min(want, left) if want else left
        sectors = (read + 2047) // 2048
        cpu.load(dest, self.disc.read(lba + self.stream[1] // 2048, sectors * 2048))
        self.streamed.append((self.stream[0], dest, read))
        self.stream[1] += sectors * 2048
        cpu.r[2] = read

    def _cd_load(self, cpu):
        entry = cpu.r[4]
        name = _basename(cpu.cstring(cpu.read(entry, 4), 64))
        dest = cpu.read(entry + 4, 4)
        found = self.disc.files.get(name)
        if found:
            cpu.load(dest, self.disc.read_file(name))
            cpu.load(entry + 8, _found_file(*found, name)[:8])
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

    def boot(self):
        """Do the start-up code's own job, then hand back with main() ready.

        Running the real crt0 is not worth it — its static-initialiser loop
        returns through a register the loop itself clobbers — and everything it
        does that matters is a few lines here: clear the zero-initialised data,
        point the globals register where the code expects it, and put the stack
        somewhere sane.
        """
        cpu = self.cpu
        cpu.load(BSS, bytes(BSS_END - BSS))
        cpu.r[28] = 0x80010000      # $gp, as the start-up code sets it
        cpu.r[29] = cpu.r[30] = 0x801FFF00
        return MAIN

    def start_stage(self, index):
        """Run the game's own initialisation, then start one sub-stage.

        `main` has to run for its init — it installs callbacks the frame code
        calls straight through — but not for its loop, so the loop is answered
        instead of entered. The same goes for the library's command sender, which
        answers for a drive that is not here.
        """
        cpu = self.cpu
        self.boot()
        done = lambda c: c.r.__setitem__(2, 0)
        cpu.traps[FRAME_LOOP] = done
        cpu.traps[CD_COMMAND] = done
        cpu.call(MAIN)
        del cpu.traps[FRAME_LOOP]
        cpu.traps[PICK_STAGE] = lambda c: c.r.__setitem__(2, index)
        cpu.call(STAGE_START)
        return cpu.read(0x800edb30, 2), cpu.read(0x800edb5c, 2)

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
