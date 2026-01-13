"""
Custom logging handler for GUI integration.
Provides thread-safe message passing between automation thread and GUI.
"""

import logging
from queue import Queue
from datetime import datetime


class GUILogHandler(logging.Handler):
    """Custom logging handler that sends logs to a queue for GUI consumption"""

    def __init__(self, queue: Queue):
        super().__init__()
        self.queue = queue

    def emit(self, record):
        msg = self.format(record)
        level = record.levelname
        self.queue.put((msg, level))


class LogMessage:
    """Represents a log message with timestamp, level, and content"""

    def __init__(self, message: str, level: str = "INFO"):
        self.timestamp = datetime.now()
        self.message = message
        self.level = level.upper()

    @property
    def formatted(self):
        """Get formatted log message with timestamp"""
        time_str = self.timestamp.strftime("%H:%M:%S")
        return f"[{time_str}] {self.message}"

    @property
    def color(self):
        """Get color for this log level"""
        colors = {
            "INFO": "#ffffff",      # White
            "SUCCESS": "#00ff00",   # Green
            "WARNING": "#ffaa00",   # Orange
            "ERROR": "#ff4444",     # Red
            "DEBUG": "#888888",     # Gray
        }
        return colors.get(self.level, "#ffffff")

    def __str__(self):
        return self.formatted


class LogBuffer:
    """
    Thread-safe log buffer that collects messages from automation thread
    and provides them to the GUI for display.
    """

    def __init__(self, max_messages: int = 10000):
        self.queue = Queue()
        self.messages = []
        self.max_messages = max_messages

    def add(self, message: str, level: str = "INFO"):
        """Add a log message (thread-safe)"""
        log_msg = LogMessage(message, level)
        self.queue.put(log_msg)

    def get_callback(self):
        """Get a callback function for the bot to use"""
        def callback(message: str, level: str = "INFO"):
            self.add(message, level)
        return callback

    def poll(self):
        """
        Get all pending messages from the queue.
        Call this from the GUI thread.
        """
        new_messages = []
        while not self.queue.empty():
            try:
                msg = self.queue.get_nowait()
                self.messages.append(msg)
                new_messages.append(msg)

                # Trim old messages if buffer is full
                if len(self.messages) > self.max_messages:
                    self.messages = self.messages[-self.max_messages:]

            except:
                break

        return new_messages

    def clear(self):
        """Clear all messages"""
        self.messages.clear()
        # Also drain the queue
        while not self.queue.empty():
            try:
                self.queue.get_nowait()
            except:
                break


class ProgressTracker:
    """
    Thread-safe progress tracker for reporting progress from automation thread.
    """

    def __init__(self):
        self.queue = Queue()
        self.current = 0
        self.total = 0
        self.message = ""
        self.indeterminate = False

    def update(self, current: int, total: int, message: str = ""):
        """Update progress (thread-safe)"""
        self.queue.put((current, total, message))

    def get_callback(self):
        """Get a callback function for the bot to use"""
        def callback(current: int, total: int, message: str = ""):
            self.update(current, total, message)
        return callback

    def poll(self):
        """
        Get the latest progress update.
        Call this from the GUI thread.
        Returns: (current, total, message, changed)
        """
        changed = False
        while not self.queue.empty():
            try:
                current, total, message = self.queue.get_nowait()
                self.current = current
                self.total = total
                self.message = message
                self.indeterminate = (total < 0)
                changed = True
            except:
                break

        return self.current, self.total, self.message, changed

    def reset(self):
        """Reset progress"""
        self.current = 0
        self.total = 0
        self.message = ""
        self.indeterminate = False
        # Drain queue
        while not self.queue.empty():
            try:
                self.queue.get_nowait()
            except:
                break
