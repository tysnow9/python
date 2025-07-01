import telnetlib
import ftplib
import time as time_module
from io import BytesIO
import numpy as np
import cv2
import queue
import threading
import logging
import socket
from datetime import datetime, date, time, timedelta
try:
    from ping3 import ping
except ImportError:
    ping = None

class CameraController:
    """Manages IS8502C camera operations via Telnet (control) and FTP (image retrieval)."""

    def __init__(self, settings, logger=None):
        self.logger = logger or logging.getLogger(__name__)
        required_keys = ["ip", "telnet_port", "username", "password", "image_filename", "timeout", "stream_interval", "stop_time"]
        missing_keys = [key for key in required_keys if key not in settings]
        if missing_keys:
            raise ValueError(f"Missing required settings: {missing_keys}")

        self.settings = settings
        self.ip = settings["ip"]
        self.telnet_port = settings["telnet_port"]
        self.username = settings["username"]
        self.password = settings["password"]
        self.image_filename = settings["image_filename"]
        self.timeout = settings["timeout"]
        self.stream_interval = settings["stream_interval"]
        try:
            self.stop_time_obj = datetime.strptime(settings["stop_time"], "%H:%M").time()
        except ValueError:
            raise ValueError(f"Invalid stop_time format: {settings['stop_time']}. Expected 'HH:MM' (24-hour)")
        self.tn = None
        self.ftp = None
        self.streaming = False
        self.paused = False
        self.image_queue = queue.Queue()
        self.stream_thread = None
        self.last_capture_time = None
        self.trigger_count = 0
        self.ftp_keep_alive_running = False
        self.timeout_count = 0
        self.max_ftp_retries = 3
        self.keep_alive_interval = 5
        self.last_reconnect_time = 0
        self.reconnect_interval = 600
        self.ftp_session_start_time = 0
        if ping is None:
            self.logger.warning("ping3 library not installed; network diagnostics disabled")

    def _get_next_stop_datetime(self):
        """Calculate the next datetime for stop_time, considering date rollover."""
        now = datetime.now()
        stop_dt = datetime.combine(now.date(), self.stop_time_obj)
        if now >= stop_dt:
            stop_dt += timedelta(days=1)
        return stop_dt

    def connect_ftp(self):
        """Establish or re-establish FTP connection to the camera with robust cleanup."""
        try:
            if self.ftp:
                try:
                    self.ftp.quit()
                except:
                    pass
                try:
                    self.ftp.close()
                except:
                    pass
                self.ftp = None
            self.ftp = ftplib.FTP()
            self.ftp.set_pasv(True)
            self.ftp.connect(self.ip, timeout=self.timeout)
            ftp_response = self.ftp.login(self.username, self.password)
            self.logger.info(f"FTP login response: {ftp_response}")
            self.last_reconnect_time = time_module.time()
            self.ftp_session_start_time = self.last_reconnect_time
            self.logger.info(f"FTP session started at {datetime.fromtimestamp(self.ftp_session_start_time).strftime('%Y-%m-%d %H:%M:%S')}")
            self.logger.info(f"Periodic FTP reconnection triggered after {time_module.time() - self.last_reconnect_time:.1f} seconds")
            return True, "FTP connection established"
        except Exception as e:
            self.logger.error(f"FTP connection error: {e}")
            if self.ftp:
                try:
                    self.ftp.close()
                except:
                    pass
                self.ftp = None
            return False, f"FTP connection error: {e}"

    def connect(self):
        """Establish Telnet and FTP connections to the camera."""
        try:
            self.tn = telnetlib.Telnet(self.ip, self.telnet_port, timeout=self.timeout)
            welcome = self.tn.read_until(b"\r\n", timeout=3).decode("ascii").strip()
            self.logger.info(f"Telnet welcome message: {welcome}")
            if "In-Sight" not in welcome:
                self.tn.close()
                self.tn = None
                return False, "Invalid welcome message"

            login_prompt = self.tn.read_until(b"User:", timeout=3).decode("ascii").strip()
            self.logger.info(f"Telnet login prompt: {login_prompt}")
            self.tn.write(f"{self.username}\r\n".encode("ascii"))
            time_module.sleep(0.1)
            password_prompt = self.tn.read_until(b"Password:", timeout=3).decode("ascii").strip()
            self.logger.info(f"Telnet password prompt: {password_prompt}")
            self.tn.write(f"{self.password}\r\n".encode("ascii"))
            response = self.tn.read_until(b"User Logged In", timeout=3).decode("ascii").strip()
            self.logger.info(f"Telnet login response: {response}")
            if "User Logged In" not in response:
                self.tn.close()
                self.tn = None
                return False, "Telnet login failed"

            self.tn.read_very_eager()
            self.logger.debug("Drained residual data after login")

            retries = 2
            for attempt in range(retries):
                self.tn.write(b"GI\r\n")
                gi_response = self.tn.read_until(b"\r\n", timeout=2).decode("ascii").strip()
                self.logger.info(f"GI verification (attempt {attempt+1}): {gi_response}")
                if gi_response == "1":
                    serial_line = self.tn.read_until(b"\r\n", timeout=1).decode("ascii").strip()
                    if serial_line.startswith("Serial Number:") and len(serial_line.split()) > 2:
                        serial_number = serial_line.replace("Serial Number:", "").strip()
                        self.logger.info(f"Serial number: {serial_number}")
                        self.tn.read_until(b"\r\n", timeout=1)
                        self.logger.debug("Drained GI response data")
                        break
                    else:
                        self.logger.warning(f"Invalid serial number: {serial_line}")
                        if attempt < retries - 1:
                            time_module.sleep(0.3)
                        else:
                            self.tn.close()
                            self.tn = None
                            return False, "Invalid serial number"
                self.logger.warning(f"Invalid GI response: {gi_response}")
                if attempt < retries - 1:
                    time_module.sleep(0.3)
                else:
                    self.tn.close()
                    self.tn = None
                    return False, f"GI verification failed after {retries} attempts"

            success, msg = self.connect_ftp()
            if not success:
                if self.tn:
                    self.tn.close()
                    self.tn = None
                return False, msg
            return True, "Connected to camera"
        except Exception as e:
            self.logger.error(f"Connection error: {e}")
            if self.tn:
                self.tn.close()
                self.tn = None
            if self.ftp:
                try:
                    self.ftp.close()
                except:
                    pass
                self.ftp = None
            return False, f"Connection error: {e}"

    def keep_alive(self):
        while self.ftp_keep_alive_running:
            if not self.ftp:
                self.logger.warning("No FTP connection for keep-alive")
                time_module.sleep(self.keep_alive_interval)
                continue
            try:
                session_duration = time_module.time() - self.ftp_session_start_time
                if ping:
                    latency = ping(self.ip, unit='ms')
                    if latency is not None:
                        self.logger.debug(f"Ping latency to {self.ip}: {latency:.1f} ms")
                    else:
                        self.logger.debug(f"Ping to {self.ip} failed")
                if time_module.time() - self.last_reconnect_time > self.reconnect_interval:
                    self.logger.info(f"Performing periodic FTP reconnection after {session_duration:.1f} seconds")
                    success, msg = self.connect_ftp()
                    if not success:
                        self.logger.error(msg)
                        time_module.sleep(self.keep_alive_interval)
                        continue
                self.ftp.voidcmd("NOOP")
                self.logger.debug("FTP keep-alive sent")
            except Exception as e:
                self.logger.error(f"Keep-alive failed: {e}")
                if not self.ftp_keep_alive_running:
                    break
                session_duration = time_module.time() - self.ftp_session_start_time
                self.logger.info(f"FTP session duration before failure: {session_duration:.1f} seconds")
                success, msg = self.connect_ftp()
                if not success:
                    self.logger.error(msg)
                time_module.sleep(self.keep_alive_interval)

    def check_ftp_health(self):
        """Check FTP connection health with a NOOP command."""
        if not self.ftp:
            return False
        try:
            self.ftp.voidcmd("NOOP")
            return True
        except Exception as e:
            self.logger.warning(f"FTP health check failed: {e}")
            return False

    def send_native_command(self, command):
        """Send a Native Mode Telnet command and return its response."""
        if not self.tn:
            return False, "Error: Not connected to camera"

        command = command.strip().upper()
        cmd_base = command.split()[0] if " " in command else command
        if not command or len(cmd_base) < 2:
            return False, f"Error: Invalid command '{command}' (minimum 2 characters)"

        if cmd_base == "GV" and (len(command) < 5 or not command[2:3].isalpha() or
                                not command[3:].isdigit() or len(command[3:]) != 3):
            return False, f"Error: Invalid GV command '{command}' (expected GV[Column][Row], e.g., GVA005)"

        try:
            self.tn.read_very_eager()
            self.tn.write(f"{command}\r\n".encode("ascii"))
            status = self.tn.read_until(b"\r\n", timeout=2).decode("ascii").strip()
            response_lines = [status]
            for _ in range(5):
                try:
                    line = self.tn.read_until(b"\r\n", timeout=0.2).decode("ascii").strip()
                    if not line:
                        break
                    response_lines.append(line)
                except Exception:
                    break
            self.tn.read_very_eager()
            response = "\n".join(response_lines)
            if status == "1":
                self.logger.info(f"Command {command}: {response}")
                return True, f"Command {command}: {response}"
            if status == "0":
                return False, f"Error: Unrecognized command '{command}'"
            if status in ("-1", "-2"):
                return False, f"Error: Command '{command}' failed (Status {status})"
            return False, f"Error: Command '{command}' returned unknown status '{status}'"
        except Exception as e:
            return False, f"Error: Command '{command}' failed: {e}"

    def trigger_image(self):
        """Trigger image capture with SE8 command after checking FTP health."""
        if not self.tn:
            return False, None, "Not connected to camera"
        if not self.check_ftp_health():
            self.logger.info("FTP health check failed, attempting reconnect")
            success, msg = self.connect_ftp()
            if not success:
                return False, None, f"FTP reconnect failed: {msg}"
        try:
            start_time = time_module.time()
            self.tn.write(b"SE8\r\n")
            response = self.tn.read_until(b"\r\n", timeout=5).decode("ascii").strip()
            trigger_time = (time_module.time() - start_time) * 1000
            self.logger.info(f"Trigger SE8 response: {response}")
            if "1" in response:
                return True, trigger_time, "Trigger successful"
            return False, trigger_time, "Trigger failed"
        except Exception as e:
            self.logger.error(f"Trigger error: {e}")
            return False, 0, f"Trigger error: {e}"

    def get_image(self, retries=2):
        if not self.ftp:
            success, msg = self.connect_ftp()
            if not success:
                return False, None, msg
        for attempt in range(retries + 1):
            try:
                buffer = BytesIO()
                start_time = time_module.time()
                self.ftp.retrbinary(f"RETR {self.image_filename}", buffer.write, blocksize=16384)
                transfer_time = (time_module.time() - start_time) * 1000
                buffer.seek(0)
                img_array = np.frombuffer(buffer.read(), dtype=np.uint8)
                img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
                if img is None:
                    self.logger.error(f"FTP attempt {attempt + 1}: Failed to decode image")
                    if attempt < retries:
                        time_module.sleep(0.5 * (2 ** attempt))
                        continue
                    return False, None, f"FTP attempt {attempt + 1}: Failed to decode image"
                self.ftp.voidcmd("NOOP")
                self.logger.info(f"Image retrieved ({img.shape[1]}x{img.shape[0]}) in {transfer_time:.1f} ms")
                self.timeout_count = 0
                return True, img, f"Image retrieved ({img.shape[1]}x{img.shape[0]})"
            except (socket.timeout, EOFError) as e:
                self.timeout_count += 1
                self.logger.warning(f"FTP timeout {self.timeout_count} (attempt {attempt + 1}): {e}")
                if attempt < retries:
                    success, msg = self.connect_ftp()
                    if not success:
                        return False, None, msg
                    time_module.sleep(0.5 * (2 ** attempt))
                    continue
                return False, None, f"FTP timeout after {retries + 1} attempts: {e}"
            except Exception as e:
                self.logger.error(f"FTP attempt {attempt + 1}: Error: {e}")
                if attempt < retries:
                    success, msg = self.connect_ftp()
                    if not success:
                        return False, None, msg
                    time_module.sleep(0.5 * (2 ** attempt))
                    continue
                return False, None, f"FTP attempt {attempt + 1}: Error: {e}"
        return False, None, f"FTP retrieval failed after {retries + 1} attempts"

    def _stream_loop(self):
        """Internal loop for live streaming, pushing images to queue until stop_time is reached."""
        self.trigger_count = 0
        stop_datetime = self._get_next_stop_datetime()
        self.logger.debug(f"Stream will stop at {stop_datetime}")
        while self.streaming:
            if datetime.now() >= stop_datetime:
                break
            if self.paused:
                time_module.sleep(0.1)
                continue
            try:
                start_time = time_module.time()
                success, _, trigger_msg = self.trigger_image()
                if not success:
                    self.image_queue.put((False, None, trigger_msg))
                    time_module.sleep(0.1)
                    continue
                success, img, msg = self.get_image()
                self.image_queue.put((success, img, msg))
                elapsed = (time_module.time() - self.last_capture_time) * 1000
                self.last_capture_time = time_module.time()
                if success:
                    self.logger.info(f"Capture rate: {1000/elapsed:.1f} fps (elapsed: {elapsed:.1f} ms)")
                    self.trigger_count += 1
                    self.logger.info(f"Trigger count: {self.trigger_count}")
                sleep_time = max(self.stream_interval - (time_module.time() - start_time), 0.002)
                time_module.sleep(sleep_time)
            except Exception as e:
                self.logger.error(f"Stream error: {e}")
                self.image_queue.put((False, None, f"Stream error: {e}"))
                time_module.sleep(0.1)
        if self.streaming:
            self.streaming = False
            self.paused = False
            self.ftp_keep_alive_running = False
            self.logger.info(f"Streaming stopped at time {self.settings['stop_time']}")
            self.image_queue.put((False, None, f"Streaming stopped at time {self.settings['stop_time']}"))

    def start_live_stream(self):
        if self.streaming:
            return False, "Streaming already active"
        if not self.tn or not self.ftp:
            return False, "Not connected to camera"
        self.streaming = True
        self.paused = False
        self.last_capture_time = time_module.time()
        self.ftp_keep_alive_running = True
        self.stream_thread = threading.Thread(target=self._stream_loop, daemon=True)
        self.stream_thread.start()
        threading.Thread(target=self.keep_alive, daemon=True).start()
        self.logger.info(f"Streaming started, will stop at time {self.settings['stop_time']}")
        return True, f"Streaming started, will stop at time {self.settings['stop_time']}"

    def pause_streaming(self):
        if not self.streaming:
            return False, "Streaming not active"
        self.paused = True
        self.ftp_keep_alive_running = False
        self.logger.info("Streaming paused")
        return True, "Streaming paused"

    def resume_streaming(self):
        """Resume the streaming loop."""
        if not self.streaming:
            return self.start_live_stream()
        self.paused = False
        self.last_capture_time = time_module.time()
        self.logger.info("Streaming resumed")
        return True, "Streaming resumed"

    def stop(self):
        self.streaming = False
        self.paused = False
        self.ftp_keep_alive_running = False
        if self.stream_thread:
            self.stream_thread.join(timeout=2)
            self.stream_thread = None
        if self.tn:
            try:
                self.tn.close()
            except:
                pass
            self.tn = None
        if self.ftp:
            session_duration = time_module.time() - self.ftp_session_start_time
            self.logger.info(f"FTP session duration on stop: {session_duration:.1f} seconds")
            try:
                self.ftp.quit()
            except:
                pass
            try:
                self.ftp.close()
            except:
                pass
            self.ftp = None
            self.ftp_session_start_time = 0
        self.logger.info("Camera stopped and disconnected")
        return True, "Camera stopped and disconnected"

    def get_image_from_queue(self):
        """Retrieve the latest image from the queue."""
        try:
            return self.image_queue.get_nowait()
        except queue.Empty:
            return False, None, "No image available"