# Jetson-Orin-Nano-Soft-AP

Jetson Orin Nano 에서 자체적인 네트워크를 생성하여 핸드폰과 연결하고, Flask 에서 제공하는 API를 통해 Jetson Orin Nano에서 인식되는 SSID 리스트 받아와 연결해주는 기능


### 설정 방법
1. ~ 경로 (홈 경로) 에 setup_softap.sh, switch_to_wifi_client.sh, wifi_server.py 를 위치시킨다. (Clone 을 하면 그 경로로 이동해야 한다.)
2. setup_softap.sh, switch_to_wifi_client.sh 를 다음과 같이 권한을 바꾼다.
   ```bash
    chmod +x setup_softap.sh
   chmod +x setup_softap.sh
   ```
