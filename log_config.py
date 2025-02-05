#!/usr/bin/env python3
import os
import logging
import logging.handlers
import types

"""
log_config.py
-------------
Manages centralized logging configuration. If CENTRAL_LOG_IP is not set,
it may prompt for user input (which can block in non-interactive environments).

For a non-interactive environment, consider setting CENTRAL_LOG_IP manually
(e.g., export CENTRAL_LOG_IP=<ip>) or pre-writing ~/.central_log_config.
"""

CONFIG_FILE = os.path.expanduser("~/.central_log_config")

def read_central_log_ip():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                ip = f.read().strip()
                if ip:
                    os.environ["CENTRAL_LOG_IP"] = ip
                    return ip
        except Exception:
            pass
    return None

def write_central_log_ip(ip):
    try:
        with open(CONFIG_FILE, "w") as f:
            f.write(ip)
    except Exception as e:
        print(f"Warning: Unable to write central logging IP to config file: {e}")

class SafeSocketHandler(logging.handlers.SocketHandler):
    def makePickle(self, record):
        # Convert any generator args to a tuple before pickling
        if record.args and isinstance(record.args, types.GeneratorType):
            record.args = tuple(record.args)
        return super().makePickle(record)

def configure_logging(logger_name):
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)
    
    central_log_ip = os.environ.get('CENTRAL_LOG_IP')
    if not central_log_ip:
        central_log_ip = read_central_log_ip()
    
    if not central_log_ip:
        try:
            answer = input("CENTRAL_LOG_IP is not set. Would you like to configure centralized logging? (y/n): ").strip().lower()
            if answer == 'y':
                inp = input("Please enter the central logging server IP (default is 127.0.0.1): ").strip()
                central_log_ip = inp if inp else "127.0.0.1"
                os.environ["CENTRAL_LOG_IP"] = central_log_ip
                write_central_log_ip(central_log_ip)
            else:
                return logger
        except Exception:
            central_log_ip = "127.0.0.1"
            os.environ["CENTRAL_LOG_IP"] = central_log_ip
            write_central_log_ip(central_log_ip)
    
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
