"""Tests for exit code mapping."""

from codeofpaper_cli.exit_codes import (
    AUTH_ERROR,
    CONNECTION_ERROR,
    EXIT_CODE_HINTS,
    GENERAL_ERROR,
    NOT_FOUND,
    RATE_LIMITED,
    SUCCESS,
    exit_code_from_status,
)


class TestExitCodeFromStatus:
    def test_200_is_success(self):
        assert exit_code_from_status(200) == SUCCESS

    def test_201_is_success(self):
        assert exit_code_from_status(201) == SUCCESS

    def test_204_is_success(self):
        assert exit_code_from_status(204) == SUCCESS

    def test_404_is_not_found(self):
        assert exit_code_from_status(404) == NOT_FOUND

    def test_429_is_rate_limited(self):
        assert exit_code_from_status(429) == RATE_LIMITED

    def test_401_is_auth_error(self):
        assert exit_code_from_status(401) == AUTH_ERROR

    def test_403_is_auth_error(self):
        assert exit_code_from_status(403) == AUTH_ERROR

    def test_500_is_general_error(self):
        assert exit_code_from_status(500) == GENERAL_ERROR

    def test_502_is_general_error(self):
        assert exit_code_from_status(502) == GENERAL_ERROR

    def test_unknown_4xx_is_general_error(self):
        assert exit_code_from_status(418) == GENERAL_ERROR


class TestExitCodeConstants:
    def test_values_are_distinct(self):
        codes = [SUCCESS, GENERAL_ERROR, CONNECTION_ERROR, NOT_FOUND, RATE_LIMITED, AUTH_ERROR]
        assert len(set(codes)) == len(codes)

    def test_success_is_zero(self):
        assert SUCCESS == 0

    def test_hints_exist_for_error_codes(self):
        for code in [CONNECTION_ERROR, NOT_FOUND, RATE_LIMITED, AUTH_ERROR]:
            assert code in EXIT_CODE_HINTS
