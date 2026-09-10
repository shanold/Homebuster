import importlib.util
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "movie_catalogue" / "password_policy.py"
spec = importlib.util.spec_from_file_location("homebuster_password_policy", MODULE_PATH)
password_policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(password_policy)


class PasswordPolicyTests(unittest.TestCase):
    def test_configured_length_is_enforced(self):
        config = {"PASSWORD_MIN_LENGTH": 14}
        self.assertEqual(password_policy.password_min_length(config), 14)
        self.assertEqual(
            password_policy.password_length_error("short", config),
            "Password must be at least 14 characters.",
        )
        self.assertIsNone(password_policy.password_length_error("x" * 14, config))

    def test_invalid_or_too_small_values_fall_back_to_eight(self):
        self.assertEqual(password_policy.password_min_length({"PASSWORD_MIN_LENGTH": "oops"}), 8)
        self.assertEqual(password_policy.password_min_length({"PASSWORD_MIN_LENGTH": 0}), 8)


if __name__ == "__main__":
    unittest.main()
