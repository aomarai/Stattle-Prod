"""
Tests for the logging utility module.

Covers:
- Logger setup and configuration.
- JSON formatter setup.
- Logger retrieval with appropriate names.
- Log level configuration via environment variables.
"""

import logging
from unittest.mock import Mock, patch

from utils.logging import setup_logger, get_logger


class TestSetupLogger:
    """Tests for logger setup and configuration."""

    def test_setup_logger_configures_root_logger(self):
        """setup_logger configures the root logger."""
        with patch("logging.getLogger") as mock_get_logger:
            mock_root_logger = Mock()
            mock_root_logger.handlers = []
            mock_get_logger.return_value = mock_root_logger

            with patch.dict("os.environ", {}, clear=True):
                setup_logger()

            mock_root_logger.setLevel.assert_called_once()

    def test_setup_logger_uses_warning_level_by_default(self):
        """setup_logger uses WARNING level when LOG_LEVEL is not set."""
        with patch("logging.getLogger") as mock_get_logger:
            mock_root_logger = Mock()
            mock_root_logger.handlers = []
            mock_get_logger.return_value = mock_root_logger

            with patch.dict("os.environ", {}, clear=True):
                setup_logger()

                mock_root_logger.setLevel.assert_called_once_with("WARNING")

    def test_setup_logger_respects_log_level_env_var(self):
        """setup_logger respects the LOG_LEVEL environment variable."""
        with patch("logging.getLogger") as mock_get_logger:
            mock_root_logger = Mock()
            mock_root_logger.handlers = []
            mock_get_logger.return_value = mock_root_logger

            with patch.dict("os.environ", {"LOG_LEVEL": "DEBUG"}):
                setup_logger()

                mock_root_logger.setLevel.assert_called_once_with("DEBUG")

    def test_setup_logger_respects_custom_log_level(self):
        """setup_logger respects custom log levels."""
        with patch("logging.getLogger") as mock_get_logger:
            mock_root_logger = Mock()
            mock_root_logger.handlers = []
            mock_get_logger.return_value = mock_root_logger

            with patch.dict("os.environ", {"LOG_LEVEL": "INFO"}):
                setup_logger()

                mock_root_logger.setLevel.assert_called_once_with("INFO")

    def test_setup_logger_adds_stream_handler(self):
        """setup_logger adds a StreamHandler to the root logger."""
        with patch("logging.getLogger") as mock_get_logger:
            with patch("logging.StreamHandler") as mock_handler_class:
                mock_root_logger = Mock()
                mock_root_logger.handlers = []
                mock_handler = Mock()
                mock_handler_class.return_value = mock_handler
                mock_get_logger.return_value = mock_root_logger

                with patch.dict("os.environ", {}, clear=True):
                    setup_logger()

                    mock_root_logger.addHandler.assert_called_once_with(mock_handler)

    def test_setup_logger_configures_json_formatter(self):
        """setup_logger configures JSON formatter for logs."""
        with patch("logging.getLogger") as mock_get_logger:
            with patch("logging.StreamHandler") as mock_handler_class:
                with patch(
                    "pythonjsonlogger.json.JsonFormatter"
                ) as mock_formatter_class:
                    mock_root_logger = Mock()
                    mock_root_logger.handlers = []
                    mock_handler = Mock()
                    mock_handler_class.return_value = mock_handler
                    mock_formatter = Mock()
                    mock_formatter_class.return_value = mock_formatter
                    mock_get_logger.return_value = mock_root_logger

                    with patch.dict("os.environ", {}, clear=True):
                        setup_logger()

                        mock_formatter_class.assert_called_once()
                        mock_handler.setFormatter.assert_called_once_with(
                            mock_formatter
                        )

    def test_setup_logger_does_not_add_duplicate_handlers(self):
        """setup_logger does not add duplicate handlers if handlers already exist."""
        with patch("logging.getLogger") as mock_get_logger:
            with patch("logging.StreamHandler") as mock_handler_class:
                mock_root_logger = Mock()
                existing_handler = Mock()
                mock_root_logger.handlers = [existing_handler]
                mock_handler = Mock()
                mock_handler_class.return_value = mock_handler
                mock_get_logger.return_value = mock_root_logger

                with patch.dict("os.environ", {}, clear=True):
                    setup_logger()

                    # addHandler should not be called when handlers already exist
                    mock_root_logger.addHandler.assert_not_called()

    def test_setup_logger_json_formatter_format_string(self):
        """setup_logger uses correct JSON log format."""
        with patch("logging.getLogger") as mock_get_logger:
            with patch("logging.StreamHandler") as mock_handler_class:
                with patch(
                    "pythonjsonlogger.json.JsonFormatter"
                ) as mock_formatter_class:
                    mock_root_logger = Mock()
                    mock_root_logger.handlers = []
                    mock_handler = Mock()
                    mock_handler_class.return_value = mock_handler
                    mock_get_logger.return_value = mock_root_logger

                    with patch.dict("os.environ", {}, clear=True):
                        setup_logger()

                        call_args = mock_formatter_class.call_args
                        format_string = call_args[0][0]
                        assert "[%(asctime)s]" in format_string
                        assert "[%(name)s]" in format_string
                        assert "[%(levelname)s]" in format_string
                        assert "%(message)s" in format_string


class TestGetLogger:
    """Tests for logger retrieval."""

    def test_get_logger_returns_logger_for_module(self):
        """get_logger returns a logger for the specified module name."""
        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = Mock(spec=logging.Logger)
            mock_get_logger.return_value = mock_logger

            result = get_logger("my_module")

            assert result is mock_logger
            mock_get_logger.assert_called_once_with("my_module")

    def test_get_logger_with_different_names(self):
        """get_logger returns different loggers for different module names."""
        with patch("logging.getLogger") as mock_get_logger:
            mock_logger1 = Mock(spec=logging.Logger)
            mock_logger2 = Mock(spec=logging.Logger)
            mock_get_logger.side_effect = [mock_logger1, mock_logger2]

            logger1 = get_logger("module1")
            logger2 = get_logger("module2")

            assert logger1 is mock_logger1
            assert logger2 is mock_logger2
            assert mock_get_logger.call_count == 2

    def test_get_logger_with_dunder_name(self):
        """get_logger works with __name__ pattern."""
        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = Mock(spec=logging.Logger)
            mock_get_logger.return_value = mock_logger

            result = get_logger("__main__")

            assert result is mock_logger
            mock_get_logger.assert_called_once_with("__main__")

    def test_get_logger_with_package_path(self):
        """get_logger works with package.module format."""
        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = Mock(spec=logging.Logger)
            mock_get_logger.return_value = mock_logger

            result = get_logger("services.github")

            assert result is mock_logger
            mock_get_logger.assert_called_once_with("services.github")

    def test_get_logger_returns_logging_logger_instance(self):
        """get_logger returns actual logging.Logger instances."""
        # This is an integration test without mocking
        logger = get_logger("test_module")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test_module"

    def test_get_logger_same_name_returns_same_logger(self):
        """get_logger returns the same logger instance for the same name."""
        # This is an integration test without mocking
        logger1 = get_logger("test_module")
        logger2 = get_logger("test_module")
        assert logger1 is logger2


class TestLoggingIntegration:
    """Integration tests for logging setup and usage."""

    def test_setup_and_get_logger_work_together(self):
        """setup_logger and get_logger work together correctly."""
        with patch("logging.getLogger") as mock_get_logger:
            with patch("logging.StreamHandler") as mock_handler_class:
                with patch(
                    "pythonjsonlogger.json.JsonFormatter"
                ) as mock_formatter_class:
                    mock_root_logger = Mock()
                    mock_root_logger.handlers = []
                    mock_handler = Mock()
                    mock_handler_class.return_value = mock_handler
                    mock_formatter = Mock()
                    mock_formatter_class.return_value = mock_formatter
                    mock_logger = Mock(spec=logging.Logger)

                    def getLogger_side_effect(name=None):
                        if name is None:
                            return mock_root_logger
                        return mock_logger

                    mock_get_logger.side_effect = getLogger_side_effect

                    with patch.dict("os.environ", {"LOG_LEVEL": "INFO"}):
                        setup_logger()
                        logger = get_logger("my_module")

                        assert logger is mock_logger
                        mock_root_logger.setLevel.assert_called_once_with("INFO")

    def test_get_logger_returns_usable_logger(self):
        """get_logger returns a usable logger that can log messages."""
        # Real logging test with actual logger
        logger = get_logger("test_logger")

        # Logger should have logging methods
        assert hasattr(logger, "debug")
        assert hasattr(logger, "info")
        assert hasattr(logger, "warning")
        assert hasattr(logger, "error")
        assert hasattr(logger, "critical")

    def test_multiple_loggers_have_different_names(self):
        """Multiple loggers can be created with different names."""
        logger1 = get_logger("module1")
        logger2 = get_logger("module2")
        logger3 = get_logger("module3")

        assert logger1.name == "module1"
        assert logger2.name == "module2"
        assert logger3.name == "module3"
        assert logger1 is not logger2
        assert logger2 is not logger3


class TestLoggerConfiguration:
    """Tests for logger configuration details."""

    def test_setup_logger_sets_root_logger(self):
        """setup_logger configures the root logger specifically."""
        with patch("logging.getLogger") as mock_get_logger:
            mock_root_logger = Mock()
            mock_root_logger.handlers = []
            mock_get_logger.return_value = mock_root_logger

            with patch.dict("os.environ", {}, clear=True):
                setup_logger()

                # getLogger() with no args gets the root logger
                mock_get_logger.assert_called_with()

    def test_setup_logger_stream_handler_uses_stderr(self):
        """setup_logger creates a StreamHandler (defaults to stderr)."""
        with patch("logging.getLogger") as mock_get_logger:
            with patch("logging.StreamHandler") as mock_handler_class:
                mock_root_logger = Mock()
                mock_root_logger.handlers = []
                mock_handler = Mock()
                mock_handler_class.return_value = mock_handler
                mock_get_logger.return_value = mock_root_logger

                with patch.dict("os.environ", {}, clear=True):
                    setup_logger()

                    # StreamHandler should be instantiated
                    mock_handler_class.assert_called_once()

    def test_all_log_levels_are_supported(self):
        """setup_logger supports all standard log levels."""
        log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

        for level in log_levels:
            with patch("logging.getLogger") as mock_get_logger:
                mock_root_logger = Mock()
                mock_root_logger.handlers = []
                mock_get_logger.return_value = mock_root_logger

                with patch.dict("os.environ", {"LOG_LEVEL": level}):
                    setup_logger()

                    mock_root_logger.setLevel.assert_called_once_with(level)
