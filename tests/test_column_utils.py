import unittest

from src.column_utils import clean_column_names


class CleanColumnNamesTests(unittest.TestCase):
    def test_special_characters_become_underscores(self):
        result = clean_column_names(["Flow Bytes/s", "Down/Up Ratio", "Fwd Header Length.1"])
        self.assertEqual(result, ["flow_bytes_s", "down_up_ratio", "fwd_header_length_1"])

    def test_empty_or_symbol_only_name_becomes_unnamed(self):
        result = clean_column_names(["", "   ", "!!!"])
        self.assertEqual(result, ["unnamed", "unnamed_1", "unnamed_2"])

    def test_collision_after_cleaning_gets_suffixed(self):
        result = clean_column_names(["Flow/Duration", "Flow Duration"])
        self.assertEqual(result, ["flow_duration", "flow_duration_1"])

    def test_single_string_can_be_cleaned_via_list_wrapping(self):
        label_column = "Label"
        self.assertEqual(clean_column_names([label_column])[0], "label")


if __name__ == "__main__":
    unittest.main()
