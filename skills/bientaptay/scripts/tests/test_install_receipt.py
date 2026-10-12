import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('installer', Path(__file__).resolve().parents[1] / 'install_bientaptay.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)

class ReceiptFlagsTests(unittest.TestCase):
    def test_receipt_row_count_must_match_inventory(self):
        inventory = [{'row_count': 2}, {'row_count': 3}]
        installer.validate_receipt_count({'text_row_count': 5}, inventory)
        for count in (None, True, '5', 4, 6, -1):
            with self.subTest(count=count), self.assertRaises(ValueError):
                installer.validate_receipt_count({'text_row_count': count}, inventory)
        with self.assertRaises(ValueError):
            installer.validate_receipt_count({}, inventory)

    def test_only_json_true_is_accepted(self):
        fields = ('canonical_unchanged', 'translation_files_unchanged', 'reference_files_unchanged')
        valid = dict.fromkeys(fields, True)
        installer.validate_receipt_flags(valid)
        for field in fields:
            for value in (False, None, 'false', 'true', 1, [], {}):
                with self.subTest(field=field, value=value):
                    candidate = dict(valid, **{field: value})
                    with self.assertRaises(ValueError):
                        installer.validate_receipt_flags(candidate)
            candidate = dict(valid)
            del candidate[field]
            with self.assertRaises(ValueError):
                installer.validate_receipt_flags(candidate)
