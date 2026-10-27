"""Unit tests for livestock_metrics.calculate_fcr."""

import pytest

from src.software_factory.utils.livestock_metrics import calculate_fcr


class TestCalculateFCR:
    def test_calculate_fcr_invalid_types_str(self):
        with pytest.raises(TypeError):
            calculate_fcr("10", 2)
        with pytest.raises(TypeError):
            calculate_fcr(10, "2")

    def test_calculate_fcr_invalid_types_none(self):
        with pytest.raises(TypeError):
            calculate_fcr(None, 2)
        with pytest.raises(TypeError):
            calculate_fcr(10, None)

    def test_calculate_fcr_invalid_types_list(self):
        with pytest.raises(TypeError):
            calculate_fcr([10], 2)
        with pytest.raises(TypeError):
            calculate_fcr(10, [2])

    def test_calculate_fcr_invalid_types_bool_excluded(self):
        # bool is subclass of int in Python but must be rejected explicitly
        with pytest.raises(TypeError):
            calculate_fcr(True, 2)
        with pytest.raises(TypeError):
            calculate_fcr(False, 2)
        with pytest.raises(TypeError):
            calculate_fcr(10, True)
        with pytest.raises(TypeError):
            calculate_fcr(10, False)

    def test_calculate_fcr_negative_feed_consumed(self):
        with pytest.raises(ValueError):
            calculate_fcr(-5, 2)

    def test_calculate_fcr_negative_weight_gain(self):
        with pytest.raises(ValueError):
            calculate_fcr(10, -1)

    def test_calculate_fcr_negative_both(self):
        with pytest.raises(ValueError):
            calculate_fcr(-1, -1)

    def test_calculate_fcr_weight_gain_zero_raises(self):
        with pytest.raises((ValueError, ZeroDivisionError)):
            calculate_fcr(10, 0)
        with pytest.raises((ValueError, ZeroDivisionError)):
            calculate_fcr(0, 0)

    def test_calculate_fcr_valid_integers(self):
        result = calculate_fcr(10, 2)
        assert isinstance(result, (int, float))
        assert result == 5.0

    def test_calculate_fcr_valid_floats(self):
        result = calculate_fcr(12.5, 2.5)
        assert isinstance(result, (int, float))
        assert result == 5.0

    def test_calculate_fcr_valid_mixed_int_float(self):
        result = calculate_fcr(7, 1.4)
        assert isinstance(result, (int, float))
        # 7 / 1.4 = 5.0
        assert result == 5.0

    def test_calculate_fcr_valid_zero_feed(self):
        result = calculate_fcr(0, 3)
        assert isinstance(result, (int, float))
        assert result == 0.0
