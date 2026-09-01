import unittest

from port_viewer.scanner import parse_ss_output


SAMPLE = """\
udp UNCONN 0 0 0.0.0.0%lxcbr0:67 0.0.0.0:*
udp UNCONN 0 0 *:46393 *:* users:((\"codex\",pid=878725,fd=68))
tcp LISTEN 0 4096 127.0.0.1:11434 0.0.0.0:*
tcp LISTEN 0 511 [::1]:631 [::]:* users:((\"cupsd\",pid=123,fd=7))
udp UNCONN 0 0 [fe80::1]%wlan0:546 [::]:*
"""


class ParseSsOutputTests(unittest.TestCase):
    def test_parses_and_sorts_entries(self):
        entries = parse_ss_output(SAMPLE)
        self.assertEqual([entry.port for entry in entries], [67, 546, 631, 11434, 46393])
        self.assertEqual(entries[0].address, "0.0.0.0%lxcbr0")
        self.assertEqual(entries[1].address, "fe80::1%wlan0")
        self.assertEqual(entries[2].address, "::1")

    def test_extracts_process_and_pid(self):
        entries = parse_ss_output(SAMPLE)
        cupsd = entries[2]
        self.assertEqual(cupsd.process, "cupsd")
        self.assertEqual(cupsd.pid, 123)
        self.assertEqual(cupsd.process_label, "cupsd  ·  PID 123")

    def test_marks_process_as_hidden_when_ss_omits_it(self):
        entries = parse_ss_output(SAMPLE)
        self.assertIsNone(entries[0].process)
        self.assertEqual(entries[0].process_label, "Process hidden")

    def test_normalizes_wildcard_addresses(self):
        entries = parse_ss_output(SAMPLE)
        wildcard = next(entry for entry in entries if entry.port == 46393)
        self.assertEqual(wildcard.address, "All interfaces")


if __name__ == "__main__":
    unittest.main()
