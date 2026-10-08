import sqlite3
import threading
import time
from datetime import datetime

import usb.core
from flask import Flask, jsonify, request

VENDOR_ID = 0x1a86
PRODUCT_ID = 0x5512

CH341A_CMD_UIO_STREAM = 0xAB
CH341A_CMD_UIO_STM_IN = 0x00
CH341A_CMD_UIO_STM_DIR = 0x40
CH341A_CMD_UIO_STM_END = 0x20

EP_OUT = 0x02
EP_IN = 0x82

STABLE_COUNT = 5
POLL_INTERVAL = 0.05
DWELL_THRESHOLD_SECONDS = 2.0

sensor_state = {
    "detected": False,
    "raw": "0x00",
}
state_lock = threading.Lock()

DB_PATH = "events.db"
db_lock = threading.Lock()


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                duration_seconds REAL NOT NULL,
                classification TEXT NOT NULL
            )
        """)
        conn.commit()


def log_event(start_time, end_time):
    duration = (end_time - start_time).total_seconds()
    classification = (
        "dwell" if duration >= DWELL_THRESHOLD_SECONDS else "quick_pass"
    )
    with db_lock:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "INSERT INTO events (start_time, end_time, duration_seconds, classification) "
                "VALUES (?, ?, ?, ?)",
                (start_time.isoformat(), end_time.isoformat(), duration, classification),
            )
            conn.commit()
    print(f"Event logged: duration={duration:.2f}s classification={classification}")


def connect_device():
    dev = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)
    if dev is None:
        raise RuntimeError("CH341A device not found. Check the USB connection.")
    dev.set_configuration()
    return dev


def set_all_input(dev):
    dev.write(EP_OUT, bytes([
        CH341A_CMD_UIO_STREAM,
        CH341A_CMD_UIO_STM_DIR | 0x00,
        CH341A_CMD_UIO_STM_END,
    ]))


def read_pins(dev):
    dev.write(EP_OUT, bytes([
        CH341A_CMD_UIO_STREAM,
        CH341A_CMD_UIO_STM_IN,
        CH341A_CMD_UIO_STM_END,
    ]))
    data = dev.read(EP_IN, 8, timeout=1000)
    return data[0]


def sensor_loop():
    dev = connect_device()
    set_all_input(dev)
    print("Sensor polling started.")

    current_candidate = None
    candidate_count = 0
    last_stable_state = None
    event_start_time = None

    while True:
        try:
            raw = read_pins(dev)
        except usb.core.USBError as e:
            print(f"USB read error: {e}")
            time.sleep(0.5)
            continue

        d0 = raw & 0x01
        # The sensor output is active-low.
        detected = not bool(d0)

        if detected != current_candidate:
            current_candidate = detected
            candidate_count = 1
        else:
            candidate_count += 1

        if candidate_count >= STABLE_COUNT and current_candidate != last_stable_state:
            last_stable_state = current_candidate
            now = datetime.now()

            if last_stable_state:
                event_start_time = now
            else:
                if event_start_time is not None:
                    log_event(event_start_time, now)
                    event_start_time = None

            with state_lock:
                sensor_state["detected"] = last_stable_state
            print(f"State changed -> detected={last_stable_state}")

        with state_lock:
            sensor_state["raw"] = f"0x{raw:02x}"

        time.sleep(POLL_INTERVAL)


app = Flask(__name__)


@app.route("/sensor/status", methods=["GET"])
def get_status():
    with state_lock:
        return jsonify(dict(sensor_state))


@app.route("/events", methods=["GET"])
def get_events():
    since = request.args.get("since", default=None, type=str)
    until = request.args.get("until", default=None, type=str)

    if since:
        try:
            datetime.fromisoformat(since)
        except ValueError:
            return jsonify({
                "error": "Invalid 'since' time. Use ISO 8601 format."
            }), 400

    if until:
        try:
            datetime.fromisoformat(until)
        except ValueError:
            return jsonify({
                "error": "Invalid 'until' time. Use ISO 8601 format."
            }), 400

    query = (
        "SELECT start_time, end_time, duration_seconds, classification "
        "FROM events WHERE 1=1"
    )
    params = []

    if since:
        query += " AND start_time >= ?"
        params.append(since)

    if until:
        query += " AND start_time < ?"
        params.append(until)

    query += " ORDER BY start_time DESC"

    with db_lock:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, params).fetchall()

    events = [dict(row) for row in rows]
    return jsonify({
        "since": since,
        "until": until,
        "count": len(events),
        "events": events,
    })


@app.route("/events/latest", methods=["GET"])
def get_latest_event():
    with db_lock:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT start_time, end_time, duration_seconds, classification "
                "FROM events ORDER BY start_time DESC LIMIT 1"
            ).fetchone()

    if row is None:
        return jsonify({"message": "No events recorded yet"}), 404

    return jsonify(dict(row))


if __name__ == "__main__":
    init_db()

    polling_thread = threading.Thread(target=sensor_loop, daemon=True)
    polling_thread.start()

    app.run(host="0.0.0.0", port=5050)
