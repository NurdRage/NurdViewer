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
    logging.getLogger(__name__).debug("Attempting to read central log IP from config file: %s", CONFIG_FILE)
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                ip = f.read().strip()
                if ip:
                    os.environ["CENTRAL_LOG_IP"] = ip
                    logging.getLogger(__name__).debug("Found central log IP in config: %s", ip)
                    return ip
                else:
                    logging.getLogger(__name__).debug("Config file exists but is empty.")
        except Exception as e:
            logging.getLogger(__name__).error("Error reading config file: %s", e)
    else:
        logging.getLogger(__name__).debug("Config file %s does not exist.", CONFIG_FILE)
    return None

def write_central_log_ip(ip):
    logging.getLogger(__name__).debug("Attempting to write central log IP (%s) to config file: %s", ip, CONFIG_FILE)
    try:
        with open(CONFIG_FILE, "w") as f:
            f.write(ip)
        logging.getLogger(__name__).debug("Successfully wrote central log IP to config.")
    except Exception as e:
        print(f"Warning: Unable to write central logging IP to config file: {e}")
        logging.getLogger(__name__).error("Failed to write config file: %s", e)

class SafeSocketHandler(logging.handlers.SocketHandler):
    def makePickle(self, record):
        # Convert any generator args to a tuple before pickling
        if record.args and isinstance(record.args, types.GeneratorType):
            logging.getLogger(__name__).debug("Converting generator args to tuple for record: %s", record)
            record.args = tuple(record.args)
        return super().makePickle(record)

def configure_logging(logger_name):
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)
    logger.debug("Configuring logging for logger: %s", logger_name)
    
    central_log_ip = os.environ.get('CENTRAL_LOG_IP')
    if central_log_ip:
        logger.debug("CENTRAL_LOG_IP found in environment: %s", central_log_ip)
    else:
        logger.debug("CENTRAL_LOG_IP not set in environment; checking config file.")
        central_log_ip = read_central_log_ip()
    
    if not central_log_ip:
        try:
            logger.debug("CENTRAL_LOG_IP still not configured; prompting user for configuration.")
            answer = input("CENTRAL_LOG_IP is not set. Would you like to configure centralized logging? (y/n): ").strip().lower()
            if answer == 'y':
                inp = input("Please enter the central logging server IP (default is 127.0.0.1): ").strip()
                central_log_ip = inp if inp else "127.0.0.1"
                os.environ["CENTRAL_LOG_IP"] = central_log_ip
                write_central_log_ip(central_log_ip)
                logger.debug("User configured CENTRAL_LOG_IP as: %s", central_log_ip)
            else:
                logger.debug("User declined to configure centralized logging; returning basic logger.")
                return logger
        except Exception as e:
            logger.error("Error during user input for CENTRAL_LOG_IP: %s. Defaulting to 127.0.0.1", e)
            central_log_ip = "127.0.0.1"
            os.environ["CENTRAL_LOG_IP"] = central_log_ip
            write_central_log_ip(central_log_ip)
    
    try:
        logger.debug("Attempting to add SafeSocketHandler for central logging using IP: %s", central_log_ip)
        sh = SafeSocketHandler(central_log_ip, 9020)
        sh.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
        sh.setFormatter(formatter)
        logger.addHandler(sh)
        logger.debug("SafeSocketHandler added to logger. Central logging will be used.")
        logger.debug("Using central logging IP: %s", central_log_ip)
    except Exception as e:
        logger.error("Failed to configure centralized logging: %s", e)
    return logger
