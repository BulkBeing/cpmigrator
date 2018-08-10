import logging
import os, sys
import datetime


class Logger(object):
    def __init__(self, name='migration', level=logging.DEBUG):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        self.formatter = logging.Formatter("%(levelname)s %(asctime)s - %(message)s")
        # Log to console
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(self.formatter)
        stream_handler.setLevel(logging.ERROR)
        self.logger.addHandler(stream_handler)
        # Log to a file
        fh = logging.FileHandler("/var/log/auto-migration.log")
        fh.setFormatter(self.formatter)
        self.logger.addHandler(fh)

    def debug(self, msg):
        self.logger.debug(msg)

    def info(self, msg):
        self.logger.info(msg)

    def warning(self, msg):
        self.logger.warning(msg)

    def error(self, msg):
        self.logger.error(msg)

    def critical(self, msg):
        self.logger.critical(msg)
        sys.exit(-1)


