# Jetson-Orin-Nano-Soft-AP ( 현재 Version 2 로 업로드 중이니 사용하지 마세요!)

Jetson Orin Nano 에서 자체적인 네트워크를 생성하여 핸드폰과 연결하고, Flask 에서 제공하는 API를 통해 Jetson Orin Nano에서 인식되는 SSID 리스트 받아와 연결해주는 기능

### 사용 필요성 
- 임베디드 프로젝트, IoT 프로젝트를 진행할 때, RaspberryPi 나 Jetson Orin Nano 에서 직접 Wifi 를 연결하지 않고 스마트폰에서 간접적으로 Wifi 를 연결할 때 사용하면 된다.
- 대표적으로 홈캠을 새로 사서 집에 있는 Wifi 에 연결할 때 필요한 프로세스를 구현했다고 생각하면 좋을 것 같다.

### 설정 방법

1. 다음 명령어를 입력해서 디렉토리에 들어간다.
   ```
   git clone https://github.com/wkdghdwns199/Jetson-Orin-Nano-Soft-AP.git
   cd Jetson-Orin-Nano-Soft-AP
   ```
2. setup_softap.sh, switch_to_wifi_client.sh 를 다음과 같이 권한을 바꾼다.
   ```bash
   chmod +x setup_softap.sh
   chmod +x switch_to_wifi_client.sh
   ```

3. 다음 명령어를 입력하여 AP모드로 변경한다. AP 명령어를 입력하면 사진과 같이 와이파이가 끊겨버린다.
   ```bash
   ./setup_softap.sh
   ```
<img width="500" height="500" alt="image" src="https://github.com/user-attachments/assets/3dfe717d-aa21-493a-bd6a-97e88ec5f009" />



4. 다음 명령어로 Wifi 리스트 API Host 를 실행한다.
   ```bash
   sudo python3 wifi_server.py # 만약 python3 가 안 깔려있다면 깔도록 하자.
   ```


5. 만약 AP모드를 끄고, 다시 Wifi 연결 모드로 변경하고 싶다면 다음 명령어를 입력한다.
   ```bash
   ./switch_to_wifi_client.sh
   ```


### 사용 방법
1. AP 모드로 변경해야 한다! (설정 방법 4번 참고) AP 모드로 변경하면 다음 Wifi 가 스마트폰에 뜰 것이다.
<img width="200" height="500" alt="image" src="https://github.com/user-attachments/assets/c1056d10-6c2f-4c85-9038-aeb6ac03d648" />


2. Wifi 연결 후 다음 주소로 스마트폰 브라우저에서 접속이 가능하다. Wifi 리스트 화면인데 리스트가 뜨기까지 시간이 좀 걸린다.
   ```bash
   http://192.168.4.1/wifi
   ```

3. 접속하면 다음과 같이 화면이 뜨는데, 그 중 하나를 선택하여 클릭한다.
<img width="200" height="500" alt="image" src="https://github.com/user-attachments/assets/14f5ebf0-0673-4efa-9254-272bca004cd7" />


4. 선택해서 다음과 같이 Wifi 비밀번호를 입력한다.
<img width="200" height="500" alt="image" src="https://github.com/user-attachments/assets/6f3bb30b-165e-4632-964f-cef17efb4731" />

5. AP 모드가 Jetson Orin Nano 에서 종료된다. (현재는 이러함)

6. 비밀번호를 입력하면 연결이 된다. (아직 연결 실패에 대한 예외처리 안함. 업데이트 예정)
<img width="500" height="500" alt="image" src="https://github.com/user-attachments/assets/ad501c2b-498c-482c-b134-9b547d6b04cc" />




### 순서도 (현재 ver)
1. AP모드 Jetson Orin Nano 에서 실행
2. Jetson Orin Nano 가 제공하는 Wifi 스마트폰에서 연결
3. 스마트폰에서 Jetson Orin Nano가 제공하는 Wifi 리스트 중 Wifi 선택
4. SSID, Password 입력, 전송
5. AP모드 종료
6. Jetson Orin Nano에서 해당 SSID 연결 정보 확인 후 연결
* 6번에서 Wifi 연결 실패하면 다시 3번부터 시작해야 함

![IMG_0639](https://github.com/user-attachments/assets/1a688f9a-d595-49f3-a3e9-f5158651da71)


### 참고
WiFi 리스트 API 주소
```
http://192.168.4.1/wifi-scan
```
SSID 연결 API 주소
```
http://192.168.4.1/connect
{
   ssid : string
   password : string
}
```

현재 Jetson Orin Nano에서 wifi 를 연결 시도하는 동안 Soft AP 모드가 꺼지면서 Wifi 연결에 실패했을 때의 확인이 안된다. 이는 AP+STA 기능이 있는 동글을 사거나, Jetson Orin Nano 와 호환되는 Wifi 동글을 끼워서 Soft AP 용 Wifi Interface, Wifi Client 용 Interface 2개를 설정하여 사용하는 방법을 써야 할 것 같다.

다른 임베디드 보드에서 본 라이브러리를 사용해보려면 다음과 같은 동글을 사서 임베디드 보드에 끼운다. ChatGPT 의견으로는 Realtek RTL8188CUS, Realtek RTL8812AU 칩셋이 내장되어 있는 Wifi 동글이어야 한다.
   ```
   https://link.coupang.com/a/cHxUdw
   ```
