#!/usr/bin/env python3
import logging
import logging.handlers
import socketserver
import pickle
import struct
import signal
import sys

# Handler that receives a log record over the socket.
class LogRecordStreamHandler(socketserver.StreamRequestHandler):
    def handle(self):
        self.server.logger.debug("New connection established from %s:%s", *self.client_address)
        while True:
            try:
                self.server.logger.debug("Waiting to receive 4 bytes for message length...")
                chunk = self.connection.recv(4)
                if len(chunk) < 4:
                    self.server.logger.debug("Incomplete length data received; closing connection.")
                    break
                slen = struct.unpack('>L', chunk)[0]
                self.server.logger.debug("Expecting %d bytes of pickle data.", slen)
                chunk = self.connection.recv(slen)
                while len(chunk) < slen:
                    self.server.logger.debug("Received %d/%d bytes; waiting for remaining data...", len(chunk), slen)
                    more = self.connection.recv(slen - len(chunk))
                    if not more:
                        self.server.logger.error("Connection closed unexpectedly during data reception.")
                        break
                    chunk += more
                self.server.logger.debug("Received full pickle data (%d bytes).", len(chunk))
                obj = pickle.loads(chunk)
                record = logging.makeLogRecord(obj)
                self.server.logger.debug("Log record reconstructed: %s", record)
                self.server.logger.handle(record)
            except Exception as e:
                self.server.logger.error("Exception in LogRecordStreamHandler.handle: %s", e)
                break
        self.server.logger.debug("Connection handler terminating for %s:%s", *self.client_address)

# TCP server that listens for log records from remote clients.
class LogRecordSocketReceiver(socketserver.ThreadingTCPServer):
    allow_reuse_address = True

    def __init__(self, host='0.0.0.0', port=9020, handler=LogRecordStreamHandler):
        super().__init__((host, port), handler)
        # Configure the central logger.
        self.logger = logging.getLogger('CentralLogger')
        self.logger.setLevel(logging.DEBUG)
        self.logger.debug("Initializing central logger with DEBUG level.")

        # Changed mode to 'a' to append instead of overwrite.
        file_handler = logging.FileHandler("central.log", mode='a')
        formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

        # FIX: Use self.logger here instead of self.server.logger
        self.logger.debug("File handler attached to central logger.")

def main():
    server = LogRecordSocketReceiver()
    server.logger.debug("Central Log Server instantiated.")

    # Graceful shutdown on SIGINT/SIGTERM
    def shutdown_signal_handler(signum, frame):
        print("Received shutdown signal. Stopping central log server...")
        server.logger.debug("Shutdown signal (%d) received. Initiating shutdown.", signum)
        server.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown_signal_handler)
    signal.signal(signal.SIGTERM, shutdown_signal_handler)

    print("Central logging server running on port 9020")
    server.logger.debug("Central logging server starting serve_forever loop.")
    server.serve_forever()

if __name__ == '__main__':
    main()
