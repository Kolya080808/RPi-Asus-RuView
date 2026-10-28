"""PC-only bounded ARM instruction experiments; never connects to devices.

Uses the exact retained module with synthetic objects and explicit call stubs.
This is not a kernel emulator or a runtime safety certificate.
"""
import argparse
import hashlib
import json
import logging
from pathlib import Path
import struct

from elftools.elf.elffile import ELFFile
from unicorn import Uc, UcError, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE, UC_HOOK_MEM_INVALID
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3
from unicorn.arm_const import UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_CPSR

from audit_ax58_contract import MODULE_SHA256

LOG = logging.getLogger('ruview.ax58_emulation')
REGS = (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)
DATA = 0x40000000
CSI, WLC, PUB, SCB, BSS, AP, REQUEST = [DATA + x * 0x1000 for x in range(7)]
STACK, STOP = DATA + 0x20000, DATA + 0x30000
MAC = bytes.fromhex('020000000001')  # Synthetic locally administered address.


class Experiment:
    def __init__(self, module, peer_present):
        if module.stat().st_size > 32 * 1024 * 1024:
            raise ValueError('Module exceeds input limit')
        raw = module.read_bytes()
        if hashlib.sha256(raw).hexdigest() != MODULE_SHA256:
            raise ValueError('Unexpected module hash')
        self.uc = Uc(UC_ARCH_ARM, UC_MODE_ARM)
        self.uc.mem_map(DATA, 0x40000)
        self.timer_semantics = False
        self.timer_allocation = DATA + 0x8000
        self.calls, self.events = {}, []
        self.fault = None
        self.count = 0
        self.returned = False
        with module.open('rb') as stream:
            elf = ELFFile(stream)
            symbols = list(elf.get_section_by_name('.symtab').iter_symbols())
            bases, payloads = {}, {}
            cursor = 0x1000000
            for index, section in enumerate(elf.iter_sections()):
                if not section['sh_flags'] & 2 or not section['sh_size']:
                    continue
                size = (section['sh_size'] + 0xfff) & ~0xfff
                bases[index] = cursor
                self.uc.mem_map(cursor, size)
                payloads[index] = bytearray(section.data())
                cursor += size + 0x1000
            self.functions = {s.name: bases[s['st_shndx']] + s['st_value']
                              for s in symbols if s['st_info']['type'] == 'STT_FUNC'
                              and s['st_shndx'] in bases}
            self.text_base = bases[next(i for i, s in enumerate(elf.iter_sections()) if s.name == '.text')]
            external = {}
            for section in elf.iter_sections():
                if section['sh_type'] != 'SHT_REL' or section['sh_info'] not in bases:
                    continue
                index = section['sh_info']
                table = elf.get_section(section['sh_link'])
                for rel in section.iter_relocations():
                    symbol = table.get_symbol(rel['r_info_sym'])
                    offset, kind = rel['r_offset'], rel['r_info_type']
                    address = bases[index] + offset
                    if kind in (28, 29):  # ARM CALL/JUMP24: explicit hook dispatch.
                        self.calls[address] = (symbol.name, kind == 28)
                        continue
                    if symbol['st_shndx'] in bases:
                        target = bases[symbol['st_shndx']] + symbol['st_value']
                    elif symbol['st_shndx'] == 'SHN_ABS':
                        target = symbol['st_value']
                    else:
                        target = external.setdefault(symbol.name, DATA + 0x38000 + len(external) * 8)
                    word = struct.unpack_from('<I', payloads[index], offset)[0]
                    if kind == 2:  # ABS32, including switch table entries.
                        word = (word + target) & 0xffffffff
                    elif kind in (43, 44):  # MOVW/MOVT absolute halves, REL addends.
                        immediate = ((word >> 4) & 0xf000) | (word & 0xfff)
                        value = target + (immediate if kind == 43 else immediate << 16)
                        half = value & 0xffff if kind == 43 else (value >> 16) & 0xffff
                        word = (word & ~0x000f0fff) | ((half & 0xf000) << 4) | (half & 0xfff)
                    else:
                        # Unsupported relocations are listed; selected paths must not execute them.
                        self.calls[address] = (f'unsupported-relocation-{kind}', False)
                        continue
                    struct.pack_into('<I', payloads[index], offset, word)
            for index, data in payloads.items():
                self.uc.mem_write(bases[index], bytes(data))
        self.uc.hook_add(UC_HOOK_CODE, self._instruction)
        self.uc.hook_add(UC_HOOK_MEM_INVALID, self._invalid)
        self.put(CSI + 0x318, WLC)
        self.put(WLC, PUB)
        self.put(WLC + 8, DATA + 0x7000)
        self.put(WLC + 0x8a4, CSI)
        self.put(PUB + 0x14, 0x81)
        self.put(SCB + 0xc, BSS)
        self.put(SCB + 0x210, 0)
        self.uc.mem_write(SCB + 0x10, MAC)
        self.uc.mem_write(BSS + 6, b'\x01')
        self.put(AP + 0xc, WLC)
        self.put(AP + 0x68, 0x220)
        # A synthetic AP/up BSS with a real driver's empty/populated hash bucket.
        self.put(WLC + 0x1d8, DATA + 0x9000)
        self.put(DATA + 0x9000, BSS)
        self.put(WLC + 0x30, DATA + 0xa000)
        self.put(WLC + 0x58, DATA + 0xb000)
        self.put(DATA + 0xb010, 0x300)
        self.uc.mem_write(DATA + 0xb008, struct.pack('<H', 0x230))
        self.put(BSS + 0x300, DATA + 0xc000)
        self.uc.mem_write(BSS + 4, b'\x01')
        self.set_peer(peer_present)

    def set_peer(self, present):
        self.put(DATA + 0xc004, SCB if present else 0)

    def put(self, address, value):
        self.uc.mem_write(address, struct.pack('<I', value))

    def _invalid(self, uc, access, address, size, value, _):
        self.fault = dict(pc=hex(uc.reg_read(UC_ARM_REG_PC) - self.text_base),
                          address=hex(address), size=size, access=access)
        return False

    def _instruction(self, uc, address, size, _):
        self.count += 1
        if address == STOP:
            self.returned = True
            uc.emu_stop()
            return
        if address not in self.calls:
            return
        # A hook runs even when an ARM conditional instruction would be skipped.
        word = struct.unpack('<I', uc.mem_read(address, 4))[0]
        condition = word >> 28
        flags = uc.reg_read(UC_ARM_REG_CPSR)
        n, z, c, v = (bool(flags & (1 << bit)) for bit in (31, 30, 29, 28))
        conditions = (z, not z, c, not c, n, not n, v, not v,
                      c and not z, not c or z, n == v, n != v,
                      not z and n == v, z or n != v, True)
        if condition == 15:
            raise ValueError('Unsupported unconditional-extension instruction at call hook')
        if not conditions[condition]:
            uc.reg_write(UC_ARM_REG_PC, address + 4)
            return
        name, link = self.calls[address]
        # All stubbed dependencies are explicit and preserved in the result.
        args = [uc.reg_read(r) for r in REGS]
        result = None
        if name == 'memcmp':
            a, b = bytes(uc.mem_read(args[0], args[2])), bytes(uc.mem_read(args[1], args[2]))
            result = (a > b) - (a < b)
        elif name == 'wl_init_timer':
            result = self.timer_allocation
        elif name in ('wl_add_timer', 'wl_free_timer', 'wl_del_timer') and not self.timer_semantics:
            result = 0
        elif name in ('wlc_scb_iterinit', 'del_timer', 'add_timer', 'osl_mfree', 'down', 'up',
                      '_raw_spin_lock_bh', '_raw_spin_unlock_bh'):
            result = 0
        elif name == 'wlc_scb_iternext':
            result = 0
        elif name == 'wlc_read_tsf':
            self.put(args[1], 12345)
            result = 0
        if result is not None:
            self.events.append(dict(call=name, result=result, pc=hex(address - self.text_base), args=args))
            uc.reg_write(UC_ARM_REG_R0, result & 0xffffffff)
            uc.reg_write(UC_ARM_REG_PC, address + 4 if link else uc.reg_read(UC_ARM_REG_LR))
        elif name in self.functions:
            if link:
                uc.reg_write(UC_ARM_REG_LR, address + 4)
            uc.reg_write(UC_ARM_REG_PC, self.functions[name])
        else:
            raise ValueError(f'Unmodelled external call/relocation: {name} at {address:#x}')

    def run(self, function, *args):
        self.fault, self.returned = None, False
        self.count = 0
        for i, value in enumerate(args[:4]):
            self.uc.reg_write(REGS[i], value)
        self.uc.reg_write(UC_ARM_REG_SP, STACK)
        self.uc.reg_write(UC_ARM_REG_LR, STOP)
        for i, value in enumerate(args[4:]):
            self.put(STACK + 4 * i, value)
        try:
            self.uc.emu_start(self.functions[function], STOP + 4, timeout=1000000, count=10000)
        except UcError:
            if self.fault is None:
                raise
        if not self.returned and self.fault is None:
            raise RuntimeError('Instruction/time bound reached without a classified outcome')
        return dict(returned=self.returned, result=self.uc.reg_read(UC_ARM_REG_R0),
                    fault=self.fault, instructions=self.count,
                    slot_mac=bytes(self.uc.mem_read(CSI + 0x40, 6)).hex(),
                    scb_slot=struct.unpack('<I', self.uc.mem_read(SCB + 0x210, 4))[0],
                    slot_timer=struct.unpack('<I', self.uc.mem_read(CSI + 0x48, 4))[0],
                    enabled=self.uc.mem_read(PUB + 0x1d0, 1)[0])

    def command(self, command):
        self.uc.mem_write(REQUEST, struct.pack('<I6sHHHI', command, MAC, 1, 20, 0, 500))
        return self.run('wlc_csimon_doiovar', CSI, 1, 0, 0, REQUEST, 20)


def experiment(module):
    results = {}
    for name, present, remove in [('absent_after_add', False, False),
                                   ('present_control', True, False),
                                   ('explicit_delete_control', False, True)]:
        model = Experiment(module, True)
        add = model.command(1)
        deinit = model.run('wlc_ap_scb_deinit', AP, SCB)
        model.set_peer(present)  # Explicit synthetic departure; not a full scbfree emulation.
        deletion = model.command(0) if remove else None
        enable = model.command(2)
        results[name] = dict(add=add, disabled_ap_deinit=deinit, deletion=deletion,
                             enable=enable, stub_calls=model.events)
    timers = {}
    for queued in (False, True):
        model = Experiment(module, False)
        model.timer_semantics = True
        driver, timer = DATA + 0x7000, DATA + 0x8000
        model.put(driver + 0x40, timer)
        model.put(driver + 0x3c, 1)
        model.put(timer + 0x14, driver)
        model.put(timer + 0x2c, int(queued))
        model.uc.mem_write(timer + 0x25, b'\x01')
        cancel = model.run('wl_free_timer', driver, timer)
        freed_before = any(e['call'] == 'osl_mfree' for e in model.events)
        drained = model.run('_wl_timer', timer) if queued else None
        reclaim = model.run('wl_free_timer_freelist', driver, 0) if queued else None
        timers[str(queued)] = dict(cancel=cancel, freed_before_callback=freed_before,
                                  drain=drained, reclaim=reclaim, stub_calls=model.events)
    return dict(module_sha256=MODULE_SHA256, scenarios=results, timer_scenarios=timers,
                limits=['Synthetic objects and explicit external-call stubs; peer lookup executes real instructions',
                        'Peer removal is a synthetic hash-table update after the selected AP deinit function',
                        'Timer mode +0x100=0 only; no concurrent scheduler or kernel cancellation semantics',
                        'Only selected functions, not all teardown callbacks or a running kernel',
                        'No timing, hardware, device-crash or safe-activation claim'])


def activation_experiment(module):
    """Inspect an already-enabled synthetic state, never a live ordering recipe."""
    cases = {}
    for name, present, state_bit, allocation, initialize in (
            ('absent_peer', False, False, True, False),
            ('existing_peer_bit_clear', True, False, True, False),
            ('existing_peer_bit_set', True, True, True, False),
            ('add_allocation_failure', True, True, False, False),
            ('new_peer_initialization', False, False, True, True),
            ('new_peer_allocation_failure', False, False, False, True)):
        model = Experiment(module, present)
        # Synthetic prerequisite, deliberately not an ENB/ADD command sequence.
        model.uc.mem_write(PUB + 0x1d0, b'\x01')
        model.uc.mem_write(SCB + 0x2a, bytes([2 if state_bit else 0]))
        model.timer_allocation = DATA + 0x8000 if allocation else 0
        add = model.command(1)
        init = None
        if initialize:
            model.set_peer(True)
            init = model.run('wlc_csimon_scb_init', WLC, SCB)
        # Deliberately inspect the callback even after a failed init to expose its
        # own guards. Whether its caller permits this is a separate runtime gate.
        model.timer_semantics = True
        callback = model.run('wlc_ap_auth_tx_complete', WLC, 0, SCB) if present or initialize else None
        cases[name] = dict(add=add, initialize=init, auth_callback=callback, stub_calls=model.events)
    return dict(module_sha256=MODULE_SHA256, activation_cases=cases,
                limits=['Already-enabled synthetic state, not an activation recommendation',
                        'Callback invocation after failure is hypothetical; caller suppression is not modelled',
                        'No full association state machine, concurrent kernel, radio or device execution'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--module', required=True, type=Path)
    parser.add_argument('--activation-matrix', action='store_true',
                        help='Inspect guarded ADD and association callback prerequisites offline')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    try:
        run = activation_experiment if args.activation_matrix else experiment
        print(json.dumps(run(args.module), indent=2))
    except Exception:
        LOG.exception('Local ARM lifecycle experiment failed')
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
