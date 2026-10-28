"""Optional PC-only execution checks using the retained exact-release module."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
MODULE = ROOT / 'recordings/source-classification-20261013/ax58-a15a0ecf225d-wl.ko'
AVAILABLE = all(importlib.util.find_spec(name) for name in ('unicorn', 'elftools'))
if AVAILABLE:
    import emulate_ax58_lifecycle as emulator


@unittest.skipUnless(AVAILABLE and MODULE.exists(), 'Optional emulator or retained module unavailable')
class EmulationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = emulator.experiment(MODULE)

    def test_absent_peer_fault_is_in_original_enable_instruction(self):
        case = self.report['scenarios']['absent_after_add']
        self.assertEqual(case['add']['result'], 0)
        self.assertEqual(case['disabled_ap_deinit']['slot_mac'], emulator.MAC.hex())
        self.assertEqual(case['enable']['fault']['pc'], '0x2b561c')
        self.assertEqual(case['enable']['fault']['address'], '0x210')
        self.assertFalse(case['enable']['returned'])
        self.assertEqual(case['enable']['enabled'], 1)
        self.assertFalse(any(e['call'] in ('wlc_scbapfind', 'wlc_scbfindband')
                             for e in case['stub_calls']))

    def test_present_peer_control_returns_success(self):
        result = self.report['scenarios']['present_control']['enable']
        self.assertTrue(result['returned'])
        self.assertEqual(result['result'], 0)
        self.assertIsNone(result['fault'])

    def test_explicit_deletion_removes_slot_before_empty_enable(self):
        case = self.report['scenarios']['explicit_delete_control']
        self.assertEqual(case['deletion']['slot_mac'], '000000000000')
        self.assertEqual(case['deletion']['result'], 0)
        self.assertTrue(case['enable']['returned'])
        self.assertIsNone(case['enable']['fault'])

    def test_queued_timer_is_retained_then_reclaimed(self):
        case = self.report['timer_scenarios']['True']
        self.assertFalse(case['freed_before_callback'])
        self.assertTrue(case['drain']['returned'])
        self.assertIsNone(case['drain']['fault'])
        self.assertTrue(case['reclaim']['returned'])
        self.assertEqual(sum(e['call'] == 'osl_mfree' for e in case['stub_calls']), 1)
        self.assertFalse(any(e['call'] == 'wl_add_timer' for e in case['stub_calls']))

    def test_unqueued_timer_is_reclaimed_without_drain(self):
        case = self.report['timer_scenarios']['False']
        self.assertTrue(case['freed_before_callback'])
        self.assertTrue(case['cancel']['returned'])
        self.assertIsNone(case['cancel']['fault'])

    def test_wrong_module_fails_before_emulation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'not-firmware.bin'
            path.write_bytes(b'not the retained ELF')
            with self.assertRaisesRegex(ValueError, 'Unexpected module hash'):
                emulator.Experiment(path, False)


@unittest.skipUnless(AVAILABLE and MODULE.exists(), 'Optional emulator or retained module unavailable')
class ActivationMatrixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = emulator.activation_experiment(MODULE)['activation_cases']

    def test_guarded_add_without_peer_is_not_capture_readiness(self):
        case = self.cases['absent_peer']
        self.assertTrue(case['add']['returned'])
        self.assertEqual(case['add']['result'], 0)
        self.assertEqual(case['add']['slot_mac'], emulator.MAC.hex())
        self.assertEqual(case['add']['scb_slot'], 0)
        self.assertEqual(case['add']['slot_timer'], 0)
        self.assertIsNone(case['auth_callback'])

    def test_existing_unbound_peer_callback_has_its_own_failure(self):
        case = self.cases['existing_peer_bit_clear']
        self.assertEqual(case['add']['result'], 0)
        fault = case['auth_callback']['fault']
        self.assertEqual((fault['pc'], fault['address']), ('0x2b5a94', '0xc'))

    def test_bound_peer_and_later_initialization_controls(self):
        for name in ('existing_peer_bit_set', 'new_peer_initialization'):
            with self.subTest(name=name):
                case = self.cases[name]
                self.assertTrue(case['auth_callback']['returned'])
                self.assertIsNone(case['auth_callback']['fault'])
                self.assertNotEqual(case['auth_callback']['scb_slot'], 0)
                self.assertNotEqual(case['auth_callback']['slot_timer'], 0)
                self.assertTrue(any(e['call'] == 'add_timer' for e in case['stub_calls']))

    def test_allocation_failure_does_not_make_callback_safe_to_invoke(self):
        for name, step in (('add_allocation_failure', 'add'),
                           ('new_peer_allocation_failure', 'initialize')):
            with self.subTest(name=name):
                case = self.cases[name]
                self.assertEqual(case[step]['result'], 0xffffffea)
                self.assertEqual(case[step]['slot_timer'], 0)
                fault = case['auth_callback']['fault']
                self.assertEqual((fault['pc'], fault['address']), ('0x22214c', '0x25'))


if __name__ == '__main__':
    unittest.main()
