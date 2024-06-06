FROM python:3.8-slim

# Set work directory
WORKDIR /app

# Copy the application source code 
COPY requirements.txt /app/
COPY mqtt_influx_telegraf_emulator.py /app/
COPY hobit_pb2.py /app/
COPY config.yaml /app/

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Command to run the application
CMD ["python", "mqtt_influx_telegraf_emulator.py"]
