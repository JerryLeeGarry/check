"""Regression tests; no network, SSH server, or optional packages required."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CHECK = ROOT / 'check'


class CheckTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.bin = Path(self.tmp.name)
        self.env = dict(os.environ, PATH=f'{self.bin}:/usr/bin:/bin', TERM='xterm')
        self.env.pop('NO_COLOR', None)
        self.env.pop('CHECK_COLOR', None)
        self.mock('curl', "printf '203.0.113.7'")
        self.mock('ip', "printf 'default via 192.0.2.1 dev eth0\\n'")
        self.mock('vnstat', 'exit 1')
        self.mock('tmux', 'exit 1')

    def tearDown(self):
        self.tmp.cleanup()

    def mock(self, name, body):
        target = self.bin / name
        target.write_text('#!/bin/bash\n' + body + '\n')
        target.chmod(0o755)

    def run_check(self, *args, **kwargs):
        return subprocess.run([str(CHECK), *args], env=self.env,
                              text=True, capture_output=True, **kwargs)

    def function(self, script):
        return subprocess.run(['bash', '-c', 'source "$1"; ' + script,
                               'test', str(CHECK)], env=self.env,
                              text=True, capture_output=True, check=True).stdout

    def test_thresholds_and_zero(self):
        output = self.function('RED=R; YELLOW=Y; GREEN=G; '
                               'for n in 0 80 81 90 91 110; do usage_color "$n" 100; done; '
                               'usage_color 0 0; percent 0 0')
        self.assertEqual(output, 'GGYYRRG0.0')

    def test_fractional_threshold(self):
        self.assertEqual(self.function('RED=R; YELLOW=Y; GREEN=G; usage_color 8001 10000'), 'Y')

    def test_public_ip_fallback_order(self):
        for winner in ['ifconfig.me', 'ip.sb', 'api.ipify.org', 'none']:
            with self.subTest(winner=winner):
                calls = self.bin / 'curl-calls'
                calls.write_text('')
                self.env['CURL_CALLS'] = str(calls)
                self.env['IP_WINNER'] = winner
                self.mock('curl', '''printf '%s\\n' "$*" >> "$CURL_CALLS"
[[ "$*" == "-s -m 3 ${@: -1}" ]] || exit 9
if [[ "${@: -1}" == "$IP_WINNER" ]]; then
    printf '203.0.113.7'
elif [[ "${@: -1}" == 'ip.sb' ]]; then
    printf '<html>unavailable</html>'
else
    exit 28
fi''')
                self.assertEqual(self.function('public_ip'),
                                 '未知' if winner == 'none' else '203.0.113.7')
                endpoints = ['ifconfig.me', 'ip.sb', 'api.ipify.org']
                count = 3 if winner == 'none' else endpoints.index(winner) + 1
                self.assertEqual(calls.read_text().splitlines(),
                                 [f'-s -m 3 {host}' for host in endpoints[:count]])

    def test_local_and_no_color(self):
        result = self.run_check()
        self.assertEqual(result.returncode, 0, result.stderr)
        for text in ['203.0.113.7', '主机名', 'CPU 核数', '15 分钟', '内存',
                     'Swap', '根分区', '无法读取 vnstat', 'tmux', '5 个进程']:
            self.assertIn(text, result.stdout)
        self.assertNotIn('\x1b', result.stdout)
        self.assertEqual(result.stderr, '')

    def test_vnstat_bytes_and_quota(self):
        self.mock('vnstat', '''[[ "$*" == '-i eth0 --oneline b' ]] || exit 9
printf '1;eth0;2026-11-12;1;2;3;0;2026-11;600000000000;150000000000;750000000000;0;1;2;3\\n' ''')
        result = self.run_check()
        self.assertIn('50.0%', result.stdout)
        self.assertIn('eth0', result.stdout)
        self.assertIn('2026-11', result.stdout)

    def test_vnstat_malformed(self):
        self.mock('vnstat', "printf 'invalid;data\\n'")
        self.assertIn('格式不支持', self.run_check().stdout)

    def test_missing_optional_tools(self):
        # Source just the optional sections with an isolated PATH.
        (self.bin / 'vnstat').unlink()
        (self.bin / 'tmux').unlink()
        for name in ['awk', 'ps']:
            (self.bin / name).symlink_to('/usr/bin/' + name)
        result = self.function('init_colors; PATH="${PATH%%:*}"; show_network; show_sessions_and_processes')
        self.assertIn('sudo apt install -y vnstat', result)
        self.assertIn('未安装 tmux', result)

    def test_remote_payload_and_status(self):
        self.mock('ssh', '''[[ "$*" == '-T -o ConnectTimeout=10 -- production CHECK_COLOR=auto bash -s' ]] || exit 88
bash -s''')
        result = self.run_check('production')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('主机名', result.stdout)
        self.mock('ssh', 'exit 42')
        self.assertEqual(self.run_check('production').returncode, 42)

    def test_remote_color(self):
        self.env['NO_COLOR'] = '1'
        self.mock('ssh', '''[[ "${@: -1}" == 'CHECK_COLOR=never bash -s' ]] || exit 88
bash -s''')
        result = self.run_check('production')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('\x1b', result.stdout)

    def test_color_output(self):
        self.env['CHECK_COLOR'] = 'always'
        self.assertIn('\x1b[', self.run_check().stdout)
        self.env['NO_COLOR'] = '1'
        self.assertNotIn('\x1b[', self.run_check().stdout)

    def test_bad_arguments(self):
        for args in [('--bad',), ('one', 'two'), ('bad;command',), ('-oProxyCommand=bad',)]:
            with self.subTest(args=args):
                self.assertEqual(self.run_check(*args).returncode, 2)
        self.assertEqual(self.run_check('--help').returncode, 0)


if __name__ == '__main__':
    unittest.main()
