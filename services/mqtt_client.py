import json
import time

import paho.mqtt.client as mqtt


class MqttClient:
    def __init__(self, host, port, username, password, topic, storage):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.topic = topic
        self.storage = storage
        self.client = mqtt.Client()

        if self.username:
            self.client.username_pw_set(self.username, self.password)

        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            client.subscribe(self.topic)

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
            payload.setdefault("topic", msg.topic)
            self.storage.insert_sensor_reading(payload)
        except Exception:
            return

    def run_forever(self):
        while True:
            try:
                self.client.connect(self.host, self.port, keepalive=60)
                self.client.loop_forever()
            except Exception:
                time.sleep(5)
