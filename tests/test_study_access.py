"""Study-window rules: end dates and how an extension window is placed."""

import unittest
from datetime import date

from study_access.services.rules import (
    StudyAccessError,
    classify_study_window,
    expected_end_date,
    extension_start_date,
    extensions_remaining,
    period_covers,
    root_application_id,
)


class StudyWindowRulesTest(unittest.TestCase):
    def test_end_date_is_inclusive(self):
        start = date(2026, 1, 1)
        end = expected_end_date(start, 90)
        self.assertEqual(end, date(2026, 4, 1))
        self.assertTrue(period_covers(start, end, start))
        self.assertTrue(period_covers(start, end, end))
        self.assertFalse(period_covers(start, end, date(2026, 4, 2)))

    def test_zero_days_are_rejected(self):
        with self.assertRaises(StudyAccessError):
            expected_end_date(date(2026, 1, 1), 0)

    def test_not_started_keeps_the_full_allocation(self):
        window = classify_study_window([], date(2026, 3, 1), 90)
        self.assertEqual(window["status"], "not_started")
        self.assertFalse(window["can_study"])
        self.assertFalse(window["access_expired"])
        self.assertEqual(window["days_remaining"], 90)
        self.assertIsNone(window["period"])

    def test_active_window_counts_down_and_includes_the_end_date(self):
        period = {
            "id": 1,
            "start_date": date(2026, 1, 1),
            "expected_end_date": date(2026, 4, 1),
            "allocated_days": 90,
            "period_type": "initial",
        }
        last_day = classify_study_window([period], date(2026, 4, 1), 90)
        self.assertEqual(last_day["status"], "active")
        self.assertTrue(last_day["can_study"])
        self.assertEqual(last_day["days_remaining"], 0)

        after = classify_study_window([period], date(2026, 4, 2), 90)
        self.assertEqual(after["status"], "expired")
        self.assertFalse(after["can_study"])
        self.assertTrue(after["access_expired"])
        self.assertEqual(after["days_remaining"], 0)

    def test_extension_stacks_after_an_open_period(self):
        start = extension_start_date(date(2026, 4, 1), date(2026, 3, 15))
        self.assertEqual(start, date(2026, 4, 2))
        self.assertEqual(expected_end_date(start, 30), date(2026, 5, 2))

    def test_extension_after_expiry_starts_on_the_approval_day(self):
        start = extension_start_date(date(2026, 4, 1), date(2026, 5, 10))
        self.assertEqual(start, date(2026, 5, 10))

    def test_root_application_id_stays_on_the_first_application(self):
        self.assertEqual(root_application_id(10, None), 10)
        self.assertEqual(root_application_id(44, 10), 10)

    def test_three_extensions_is_the_limit(self):
        self.assertEqual(extensions_remaining(0), 3)
        self.assertEqual(extensions_remaining(2), 1)
        self.assertEqual(extensions_remaining(3), 0)
        self.assertEqual(extensions_remaining(4), 0)


if __name__ == "__main__":
    unittest.main()
