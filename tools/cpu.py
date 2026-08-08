"""An R3000A interpreter: enough PlayStation to run Metal Slug X's own code.

Object placement in this game is computation, not data — the stage overlays
spawn things by calling executable routines as the camera scrolls. Reading that
back out means running it, so this executes the game's instructions against a
model of main memory and lets the caller trap any address.

There is no GPU, no sound and no disc here. Writes to hardware registers are
swallowed and reads give zero, which is all the placement code needs: it moves
values around in RAM and calls routines that this module intercepts.
"""
import struct

RAM_SIZE = 2 * 1024 * 1024
SCRATCH = 0x1F800000
SCRATCH_END = SCRATCH + 1024
IO = 0x1F801000
IO_END = 0x1F804000

REG = ["zero", "at", "v0", "v1", "a0", "a1", "a2", "a3",
       "t0", "t1", "t2", "t3", "t4", "t5", "t6", "t7",
       "s0", "s1", "s2", "s3", "s4", "s5", "s6", "s7",
       "t8", "t9", "k0", "k1", "gp", "sp", "fp", "ra"]


class Halt(Exception):
    """Raised to stop the machine from inside a trap."""


class Cpu:
    def __init__(self):
        self.ram = bytearray(RAM_SIZE)
        self.scratch = bytearray(1024)
        self.r = [0] * 32
        self.cop2 = [0] * 64
        self.hi = self.lo = 0
        self.pc = 0
        self.traps = {}        # address -> fn(cpu); a trapped call returns to $ra
        self.steps = 0
        self.limit = 20_000_000
        self.trace = None      # set to a deque to keep the last addresses executed
        self.on_syscall = None
        self.io_read = None    # hardware registers; without one they read zero

    # ---- memory ---------------------------------------------------------
    def _view(self, addr):
        a = addr & 0x1FFFFFFF
        if a < RAM_SIZE:
            return self.ram, a
        if SCRATCH <= a < SCRATCH_END:
            return self.scratch, a - SCRATCH
        return None, 0

    def read(self, addr, size):
        buf, off = self._view(addr)
        if buf is None:
            return self.io_read(addr, size) if self.io_read else 0
        if size == 1:
            return buf[off]
        if size == 2:
            return buf[off] | (buf[off + 1] << 8)
        return int.from_bytes(buf[off:off + 4], "little")

    def write(self, addr, size, value):
        buf, off = self._view(addr)
        if buf is None:
            return
        buf[off:off + size] = (value & ((1 << (size * 8)) - 1)).to_bytes(size, "little")

    def load(self, addr, blob):
        buf, off = self._view(addr)
        buf[off:off + len(blob)] = blob

    def cstring(self, addr, limit=64):
        out = bytearray()
        while len(out) < limit:
            b = self.read(addr + len(out), 1)
            if not b:
                break
            out.append(b)
        return out.decode("ascii", "replace")

    # ---- execution ------------------------------------------------------
    def call(self, addr, args=(), ra=0xDEAD0000):
        """Run a routine to completion and return $v0."""
        for i, v in enumerate(args):
            self.r[4 + i] = v & 0xFFFFFFFF
        self.r[31] = ra
        self.pc = addr
        self.run(stop=ra)
        return self.r[2]

    def run(self, stop):
        pc = self.pc
        delay = None            # (target,) queued by a branch
        while True:
            if pc == stop:
                self.pc = pc
                return
            fn = self.traps.get(pc)
            if fn is not None:
                self.pc_trap = pc
                fn(self)
                pc = self.r[31]
                delay = None
                continue
            if pc < 0x80:
                # a call through an uninitialised pointer; walking up through
                # zeroed memory would otherwise reach a kernel vector and look
                # like a real call
                raise Halt(f"jump to null (0x{pc:08x}) from 0x{self.r[31]:08x}")
            self.steps += 1
            if self.steps > self.limit:
                raise Halt(f"step limit at 0x{pc:08x}")
            if self.trace is not None:
                self.trace.append(pc)
            word = self.read(pc, 4)
            target = self.step(word, pc)
            if delay is not None:
                pc, delay = delay, None
                continue
            if target is not None:
                delay = target      # the next instruction runs before the jump
                pc += 4
            else:
                pc += 4

    def step(self, word, pc):
        r = self.r
        op = word >> 26
        rs, rt, rd = (word >> 21) & 31, (word >> 16) & 31, (word >> 11) & 31
        sa, funct = (word >> 6) & 31, word & 63
        imm = word & 0xFFFF
        simm = imm - 0x10000 if imm & 0x8000 else imm
        M = 0xFFFFFFFF

        def s32(v):
            return v - 0x100000000 if v & 0x80000000 else v

        if op == 0:
            if funct == 0x00: r[rd] = (r[rt] << sa) & M
            elif funct == 0x02: r[rd] = (r[rt] & M) >> sa
            elif funct == 0x03: r[rd] = (s32(r[rt]) >> sa) & M
            elif funct == 0x04: r[rd] = (r[rt] << (r[rs] & 31)) & M
            elif funct == 0x06: r[rd] = (r[rt] & M) >> (r[rs] & 31)
            elif funct == 0x07: r[rd] = (s32(r[rt]) >> (r[rs] & 31)) & M
            elif funct == 0x08: r[0] = 0; return r[rs]
            elif funct == 0x09:
                r[rd] = pc + 8
                return r[rs]
            elif funct == 0x0c:
                if self.on_syscall is None:
                    raise Halt(f"syscall at 0x{pc:08x}")
                self.on_syscall(self)
            elif funct == 0x0d: raise Halt(f"break at 0x{pc:08x}")
            elif funct == 0x10: r[rd] = self.hi
            elif funct == 0x11: self.hi = r[rs]
            elif funct == 0x12: r[rd] = self.lo
            elif funct == 0x13: self.lo = r[rs]
            elif funct == 0x18:
                p = s32(r[rs]) * s32(r[rt]); self.lo = p & M; self.hi = (p >> 32) & M
            elif funct == 0x19:
                p = r[rs] * r[rt]; self.lo = p & M; self.hi = (p >> 32) & M
            elif funct == 0x1a:
                a, b = s32(r[rs]), s32(r[rt])
                self.lo, self.hi = (0, a) if b == 0 else (int(a / b) & M, (a - int(a / b) * b) & M)
            elif funct == 0x1b:
                a, b = r[rs], r[rt]
                self.lo, self.hi = (0, a) if b == 0 else ((a // b) & M, (a % b) & M)
            elif funct in (0x20, 0x21): r[rd] = (r[rs] + r[rt]) & M
            elif funct in (0x22, 0x23): r[rd] = (r[rs] - r[rt]) & M
            elif funct == 0x24: r[rd] = r[rs] & r[rt]
            elif funct == 0x25: r[rd] = r[rs] | r[rt]
            elif funct == 0x26: r[rd] = r[rs] ^ r[rt]
            elif funct == 0x27: r[rd] = (~(r[rs] | r[rt])) & M
            elif funct == 0x2a: r[rd] = 1 if s32(r[rs]) < s32(r[rt]) else 0
            elif funct == 0x2b: r[rd] = 1 if r[rs] < r[rt] else 0
            else: raise Halt(f"special {funct:#04x} at 0x{pc:08x}")
            r[0] = 0
            return None

        if op == 1:
            link = rt in (16, 17)
            take = (s32(r[rs]) >= 0) if rt in (1, 17) else (s32(r[rs]) < 0)
            if link:
                r[31] = pc + 8
            r[0] = 0
            return pc + 4 + simm * 4 if take else None

        if op == 2:
            return (pc & 0xF0000000) | ((word & 0x3FFFFFF) << 2)
        if op == 3:
            r[31] = pc + 8
            return (pc & 0xF0000000) | ((word & 0x3FFFFFF) << 2)
        if op == 4:
            return pc + 4 + simm * 4 if r[rs] == r[rt] else None
        if op == 5:
            return pc + 4 + simm * 4 if r[rs] != r[rt] else None
        if op == 6:
            return pc + 4 + simm * 4 if s32(r[rs]) <= 0 else None
        if op == 7:
            return pc + 4 + simm * 4 if s32(r[rs]) > 0 else None

        if op in (8, 9): r[rt] = (r[rs] + simm) & M
        elif op == 0x0a: r[rt] = 1 if s32(r[rs]) < simm else 0
        elif op == 0x0b: r[rt] = 1 if r[rs] < (simm & M) else 0
        elif op == 0x0c: r[rt] = r[rs] & imm
        elif op == 0x0d: r[rt] = r[rs] | imm
        elif op == 0x0e: r[rt] = r[rs] ^ imm
        elif op == 0x0f: r[rt] = (imm << 16) & M
        elif op == 0x10:                       # cop0: status and cause only
            r[rt] = 0 if rs == 0 else r[rt]
        elif op == 0x12:
            # The geometry coprocessor only ever feeds drawing here, so its
            # registers are kept and its arithmetic is skipped: placement code
            # reads coordinates out of memory, never out of the GTE.
            if word & (1 << 25):
                pass
            elif rs == 0: r[rt] = self.cop2[rd]
            elif rs == 2: r[rt] = self.cop2[32 + rd]
            elif rs == 4: self.cop2[rd] = r[rt]
            elif rs == 6: self.cop2[32 + rd] = r[rt]
        elif op == 0x32: self.cop2[rt] = self.read((r[rs] + simm) & M, 4)
        elif op == 0x3a: self.write((r[rs] + simm) & M, 4, self.cop2[rt])
        elif op == 0x20:
            v = self.read((r[rs] + simm) & M, 1); r[rt] = v - 256 if v & 0x80 else v
        elif op == 0x21:
            v = self.read((r[rs] + simm) & M, 2); r[rt] = (v - 0x10000 if v & 0x8000 else v) & M
        elif op == 0x23: r[rt] = self.read((r[rs] + simm) & M, 4)
        elif op == 0x24: r[rt] = self.read((r[rs] + simm) & M, 1)
        elif op == 0x25: r[rt] = self.read((r[rs] + simm) & M, 2)
        elif op == 0x28: self.write((r[rs] + simm) & M, 1, r[rt])
        elif op == 0x29: self.write((r[rs] + simm) & M, 2, r[rt])
        elif op == 0x2b: self.write((r[rs] + simm) & M, 4, r[rt])
        elif op in (0x22, 0x26, 0x2a, 0x2e):   # unaligned word access
            addr = (r[rs] + simm) & M
            aligned = addr & ~3
            shift = (addr & 3) * 8
            word32 = self.read(aligned, 4)
            if op == 0x22:                     # lwl
                r[rt] = ((word32 << (24 - shift)) | (r[rt] & ((1 << (24 - shift)) - 1))) & M
            elif op == 0x26:                   # lwr
                r[rt] = ((word32 >> shift) | (r[rt] & ~((M >> shift)))) & M
            elif op == 0x2a:                   # swl
                keep = ~(M >> (24 - shift)) & M
                self.write(aligned, 4, (word32 & keep) | (r[rt] >> (24 - shift)))
            else:                              # swr
                keep = (1 << shift) - 1
                self.write(aligned, 4, (word32 & keep) | ((r[rt] << shift) & M))
        else:
            raise Halt(f"opcode {op:#04x} at 0x{pc:08x}")
        r[0] = 0
        return None
