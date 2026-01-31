import serial
import threading
import time

class SerialMonitor:
    def __init__(self, port, baud_rate=9600, callback=None):
        self.port = port
        self.baud_rate = baud_rate
        self.callback = callback
        self.running = False
        self.thread = None
        self.serial_conn = None

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._monitor_loop)
        self.thread.daemon = True
        self.thread.start()
        print(f"Serial Monitor started on {self.port}")

    def stop(self):
        self.running = False
        if self.serial_conn:
            self.serial_conn.close()

    def _monitor_loop(self):
        while self.running:
            try:
                if not self.serial_conn or not self.serial_conn.is_open:
                    try:
                        self.serial_conn = serial.Serial(self.port, self.baud_rate, timeout=1)
                        print(f"Connected to {self.port}")
                    except serial.SerialException as e:
                        # Retry connection every 2 seconds
                        time.sleep(2)
                        continue

                line = self.serial_conn.readline()
                if line:
                    decoded = line.decode('utf-8').strip()
                    if decoded and self.callback:
                        self.callback(decoded)
            except Exception as e:
                print(f"Serial error: {e}")
                time.sleep(1)
