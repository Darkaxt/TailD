import unittest
from pathlib import Path
import package_notices


class NoticesTest(unittest.TestCase):
    def test_every_pinned_network_distribution_has_runtime_notice_coverage(self):
        file=Path(__file__).resolve().parents[2]/'desktop/runtime-network-requirements.txt'
        names={line.split('==')[0] for line in file.read_text().splitlines()
               if line.strip() and not line.startswith('#')}
        self.assertTrue(names.issubset(set(package_notices.RUNTIME_DISTRIBUTIONS)))


if __name__=='__main__':unittest.main()
