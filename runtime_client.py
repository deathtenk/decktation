import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import threading
import uuid


class RuntimeClientError(RuntimeError):
    pass


class RuntimeClient:
    def __init__(self, plugin_path, logger, event_handler=None):
        self.plugin_path = Path(plugin_path)
        self.logger = logger
        self.event_handler = event_handler
        self.process = None
        self._reader_thread = None
        self._write_lock = threading.Lock()
        self._pending = {}
        self._pending_lock = threading.Lock()
        self._started = False

    def _runtime_executable(self):
        executable = self.plugin_path / "bin" / "decktation-runtime"
        if executable.is_file() and os.access(executable, os.X_OK):
            return [str(executable)], {}

        python_bin = "/usr/bin/python3"
        if not os.path.exists(python_bin):
            python_bin = shutil.which("python3")
        if not python_bin:
            raise RuntimeClientError("No python3 found for source runtime fallback")

        python_path_entries = [
            str(self.plugin_path / "runtime" / "src"),
            str(self.plugin_path),
        ]
        for extra_path in ("lib", os.path.join("bin", "python")):
            candidate = self.plugin_path / extra_path
            if candidate.exists():
                python_path_entries.append(str(candidate))
        existing_pythonpath = os.environ.get("PYTHONPATH")
        if existing_pythonpath:
            python_path_entries.append(existing_pythonpath)

        env = {
            "PYTHONPATH": os.pathsep.join(python_path_entries),
        }
        return [python_bin, "-m", "decktation_runtime.server"], env

    def start(self):
        if self.process and self.process.poll() is None:
            return

        command, extra_env = self._runtime_executable()
        env = {
            **os.environ,
            **extra_env,
        }
        self.process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=env,
        )
        self._started = True
        self._reader_thread = threading.Thread(
            target=self._reader_loop,
            name="decktation-runtime-client",
            daemon=True,
        )
        self._reader_thread.start()

    def _reader_loop(self):
        try:
            for line in self.process.stdout:
                message = line.strip()
                if not message:
                    continue
                try:
                    payload = json.loads(message)
                except json.JSONDecodeError:
                    self.logger.info("Runtime raw output: %s", message)
                    continue

                if "id" in payload:
                    with self._pending_lock:
                        pending = self._pending.pop(payload["id"], None)
                    if pending:
                        pending.put(payload)
                    continue

                if "event" in payload and self.event_handler:
                    self.event_handler(payload["event"], payload.get("payload", {}))
        finally:
            error = RuntimeClientError("Runtime process exited")
            with self._pending_lock:
                pending_items = list(self._pending.values())
                self._pending.clear()
            for pending in pending_items:
                pending.put(error)

    def request(self, method, params=None, timeout=30):
        self.start()
        if not self.process or self.process.poll() is not None:
            raise RuntimeClientError("Runtime process is not running")

        request_id = uuid.uuid4().hex
        response_queue = queue.Queue(maxsize=1)
        with self._pending_lock:
            self._pending[request_id] = response_queue

        payload = {
            "id": request_id,
            "method": method,
            "params": params or {},
        }
        with self._write_lock:
            try:
                self.process.stdin.write(json.dumps(payload) + "\n")
                self.process.stdin.flush()
            except Exception as exc:
                with self._pending_lock:
                    self._pending.pop(request_id, None)
                raise RuntimeClientError(f"Failed to send runtime request: {exc}") from exc

        try:
            response = response_queue.get(timeout=timeout)
        except queue.Empty as exc:
            with self._pending_lock:
                self._pending.pop(request_id, None)
            raise RuntimeClientError(f"Timed out waiting for runtime response to {method}") from exc

        if isinstance(response, Exception):
            raise response
        if not response.get("ok", False):
            error = response.get("error", {})
            raise RuntimeClientError(error.get("message", f"Runtime request failed: {method}"))
        return response.get("result", {})

    def stop(self):
        process = self.process
        if not process:
            return

        if process.poll() is None:
            try:
                self.request("shutdown", {}, timeout=5)
            except Exception:
                pass

        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        self.process = None
