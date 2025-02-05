#!/usr/bin/env python3
import logging
import logging.handlers
import socketserver
import pickle
import struct

# Handler that receives a log record over the socket.
class LogRecordStreamHandler(socketserver.StreamRequestHandler):
    def handle(self):
        while True:
            # Read the length of the incoming pickle data (4 bytes, big-endian)
            chunk = self.connection.recv(4)
            if len(chunk) < 4:
                break
            slen = struct.unpack('>L', chunk)[0]
            # Read the actual pickle data
            chunk = self.connection.recv(slen)
            while len(chunk) < slen:
                chunk += self.connection.recv(slen - len(chunk))
            obj = pickle.loads(chunk)
            record = logging.makeLogRecord(obj)
            self.server.logger.handle(record)

# TCP server that listens for log records from remote clients.
class LogRecordSocketReceiver(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    def __init__(self, host='0.0.0.0', port=9020, handler=LogRecordStreamHandler):
        socketserver.ThreadingTCPServer.__init__(self, (host, port), handler)
        # Configure the central logger.
        self.logger = logging.getLogger('CentralLogger')
        self.logger.setLevel(logging.DEBUG)
        file_handler = logging.FileHandler("central.log", mode='w')
        formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

def main():
    server = LogRecordSocketReceiver()
    print("Central logging server running on port 9020")
    server.serve_forever()

if __name__ == '__main__':
    main()
