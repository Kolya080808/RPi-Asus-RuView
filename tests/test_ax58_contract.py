"""Exact-release regression checks; firmware remains a local, optional fixture."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import audit_ax58_contract as contract

MODULE = ROOT / 'recordings/source-classification-20261013/ax58-a15a0ecf225d-wl.ko'
HEADER = ROOT / 'recordings/ax58-review-20261012/gpl-selected/efa9a95e39e1-wlioctl.h'


@unittest.skipUnless(MODULE.exists() and HEADER.exists(), 'Retained exact-release fixtures unavailable')
class ContractTests(unittest.TestCase):
    def test_static_evidence_never_promotes_active_safety(self):
        report = contract.audit(MODULE, HEADER)
        self.assertIn('wrapper_evidence', report)
        self.assertFalse(report['safe_to_enable'])
        self.assertFalse(report['shutdown']['safe_to_activate_or_rollback_active'])
        self.assertFalse(report['runtime_validated'])
        self.assertFalse(report['slot_lifecycle']['userspace_precheck_sufficient'])

    def test_changed_lock_gate_or_teardown_instruction_is_rejected(self):
        text, refs = contract.read_elf(MODULE, contract.MODULE_SHA256)
        for address in (0x21e52c, 0x2215a4, 0x21e534, 0x22263c, 0x2b5a14,
                        0x2630fc, 0x26145c, 0x2b56a0, 0x2b5514, 0x2b5600, 0x2b6a64):
            with self.subTest(address=hex(address)):
                changed = bytearray(text)
                changed[address] ^= 1
                with patch.object(contract, 'read_elf', return_value=(changed, refs)):
                    with self.assertRaisesRegex(ValueError, 'A32 mismatch'):
                        contract.audit(MODULE, HEADER)

    def test_changed_registration_or_scheduler_target_is_rejected(self):
        text, refs = contract.read_elf(MODULE, contract.MODULE_SHA256)
        for address in (0x2630f4, 0x26310c, 0x21dac0):
            with self.subTest(address=hex(address)):
                changed = dict(refs)
                changed[address] = 'unexpected_target'
                with patch.object(contract, 'read_elf', return_value=(text, changed)):
                    with self.assertRaisesRegex(ValueError, 'Slot/scheduler relocation differs'):
                        contract.audit(MODULE, HEADER)

    def test_changed_lock_or_free_target_is_rejected(self):
        text, refs = contract.read_elf(MODULE, contract.MODULE_SHA256)
        for address in (0x21e530, 0x2215dc, 0x222614, 0x2614fc):
            with self.subTest(address=hex(address)):
                changed = dict(refs)
                changed[address] = 'unexpected_target'
                with patch.object(contract, 'read_elf', return_value=(text, changed)):
                    with self.assertRaisesRegex(ValueError, 'Lock/teardown relocation differs'):
                        contract.audit(MODULE, HEADER)


if __name__ == '__main__':
    unittest.main()
