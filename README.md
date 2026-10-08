# Prak26SS-sensor-monitoring

A sensor-driven business process built for the TUM Advanced Practical Course – Sustainable Process Automation: Humans, Software and the Mediator Pattern. An infrared proximity sensor installed at an entrance is connected to a CH341A USB GPIO board and monitored by a lightweight Python REST service. A CPEE process polls that service in a loop, classifies what happened since the last check, and publishes the result to a live dashboard.

## Scenario

This project implements activity monitoring for a smart office entrance using CPEE, Flask, and a web-based dashboard. Each interaction detected by the sensor is stored as an event by the Flask backend, while the CPEE workflow repeatedly defines a monitoring window, retrieves the events recorded during that interval, and evaluates the current activity level. A small number of events is treated as normal activity, whereas a burst of frequent events is flagged as abnormal because it may indicate a crowd, a blocked or unstable sensor, or possible tampering. The workflow also examines the latest event to determine whether someone simply walked past or remained near the entrance: an interaction lasting less than two seconds is classified as a `quick_pass`, while a longer interaction is classified as a `dwell`. The event count, activity status, latest-event duration, and classification are then displayed in the CPEE Frames dashboard, demonstrating how CPEE coordinates sensor-data retrieval, event processing, decision logic, and real-time visualization within a process automation scenario.

## Files

- sensor_service.py 
  Flask backend providing sensor status and event endpoints.

- dashboard.html
  Dashboard page used by CPEE Frames.

- requirements.txt 
  Python dependencies.

- sensor_monitoring.xml
  Executable CPEE process model containing the workflow logic, data elements, and service endpoint configuration.

- sensor_monitoring.svg
  Visual representation of the CPEE sensor-monitoring workflow.

## Running It

Connect the sensor wires as follows:

- Brown (`VCC`): power supply
- Blue (`GND`): ground
- Black (`OUT`): `CS0` pin on the CH341A SPI header

Set the CH341A board jumpers to `3.3 V`, then install the dependencies and start the service:

```bash
brew install libusb            # macOS
pip install flask pyusb
python3 sensor_service.py      # listens on port 5050
```

## Main API Endpoints

`GET /sensor/status`

Returns the current sensor state.

Example:
/sensor/status

Example response:

```json
{
  "detected": false,
  "raw": "0xff"
}
```

`GET /events`

Returns recorded sensor events.

The endpoint can optionally be restricted to a time interval using the query parameters:

- `since`
- `until`

Example:
/events?since=2026-10-08T09:00:00&until=2026-10-08T18:00:00

Example response:

```json
{
  "since": "2026-10-08T09:00:00",
  "until": "2026-10-08T18:00:00",
  "count": 1,
  "events": [
    {
      "start_time": "2026-10-08T10:15:30.100000",
      "end_time": "2026-10-08T10:15:31.600000",
      "duration_seconds": 1.5,
      "classification": "quick_pass"
    }
  ]
}
```

This is used by the CPEE workflow to count and inspect events within the current monitoring window.

`GET /events/latest`

Returns information about the latest recorded event.

The result is used by the workflow to determine the latest event classification and its duration.

Example response:

```json
{
  "start_time": "2026-10-08T10:15:30.100000",
  "end_time": "2026-10-08T10:15:31.600000",
  "duration_seconds": 1.5,
  "classification": "quick_pass"
}
```

## Dashboard

Dashboard HTML:

https://lehre.bpm.in.tum.de/~ge65hoh/dashboard.html

CPEE Frames:

https://cpee.org/out/frames/sensor_monitoring/

## Monitored Data

1. `started`  
   Time at which the monitoring process was initialized.
2. `filter_since`  
   Start of the current monitoring interval.
3. `filter_until`  
   End of the current monitoring interval.
4. `filtered_count`  
   Number of events detected within the current monitoring interval.
5. `activity_status`  
   Classification of recent activity, for example `normal` or `abnormal`.
6. `dwell_classification`  
   Classification of the latest event, for example `dwell` or `quick_pass`.
7. `dwell_duration`  
   Duration of the latest detected event.

## Process Logic

1. The workflow initializes the dashboard and creates the first monitoring window. `filter_since` is set to 60 seconds before the current time, while `started` records the process start time.

2. While `loop_active` is `true`, the workflow retrieves the current detection state from `GET /sensor/status`.

3. The current time is stored as `filter_until`. The workflow then calls `GET /events` with `filter_since` and `filter_until` to retrieve the events that started within this monitoring window.

4. The returned event count is evaluated. Fewer than five events are classified as `normal` activity; five or more events are classified as `abnormal`.

5. The workflow calls `GET /events/latest` and reads the latest event's classification and duration. An event lasting less than two seconds is classified by the sensor service as a `quick_pass`; an event lasting at least two seconds is classified as a `dwell`.

6. The monitoring window, event count, activity status, latest-event classification, and duration are published to the CPEE Frames dashboard.

7. The workflow waits for 30 seconds, sets `filter_since` to the previous `filter_until`, and begins the next monitoring cycle. This creates consecutive, non-overlapping monitoring windows.
