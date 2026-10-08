# Prak26SS-sensor-monitoring

Sensor monitoring dashboard implemented with CPEE and Flask for TUM Sustainable Process Automation course.

## Files

- sensor_service.py 
  Flask backend providing sensor status and event endpoints.

- dashboard.html
  Dashboard page used by CPEE Frames.

- requirements.txt 
  Python dependencies.

## Main API Endpoints

- /sensor/status
- /events
  /events?since=2026-10-08T09:00:00&until=2026-10-08T18:00:00
- /events/latest

## Dashboard

Dashboard HTML:

https://lehre.bpm.in.tum.de/~ge65hoh/dashboard.html

CPEE Frames:

https://cpee.org/out/frames/sensor_monitoring/

## Monitored Data

- started
- filter_since
- filter_until
- filtered_count
- activity_status
- dwell_classification
- dwell_duration
