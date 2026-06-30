import unittest

class TestBasicMath(unittest.TestCase):
    def setUp(self):
        self.value = 10

    def test_addition(self):
        self.assertEqual(self.value + 5, 15)

    def test_subtraction(self):
        self.assertTrue(self.value - 5 == 5)
