#!/usr/bin/env python3
import os
import logging
import logging.handlers
import types

class SafeSocketHandler(logging.handlers.SocketHandler):
    def makePickle(self, record):
        # If record.args is a generator, convert it to a tuple.
        if record.args and isinstance(record.args, types.GeneratorType):
            record.args = tuple(record.args)
        return super().makePickle(record)

def configure_logging(logger_name):
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)
    # Get the CENTRAL_LOG_IP from environment (or prompt if not set)
    central_log_ip = os.getenv('CENTRAL_LOG_IP')
    if not central_log_ip:
        try:
            answer = input("CENTRAL_LOG_IP is not set. Would you like to configure centralized logging? (y/n): ").strip().lower()
            if answer == 'y':
                inp = input("Please enter the central logging server IP (default is 127.0.0.1): ").strip()
                central_log_ip = inp if inp else "127.0.0.1"
                os.environ["CENTRAL_LOG_IP"] = central_log_ip
            else:
                # If the user declines, skip adding the socket handler.
                return logger
        except Exception:
            central_log_ip = "127.0.0.1"
            os.environ["CENTRAL_LOG_IP"] = central_log_ip

    try:
        sh = SafeSocketHandler(central_log_ip, 9020)
        sh.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
        sh.setFormatter(formatter)
        logger.addHandler(sh)
        logger.debug("Using central logging IP: %s", central_log_ip)
    except Exception as e:
        logger.error("Failed to configure centralized logging: %s", e)
    return logger
