# 리치 Wireless 현장 설치 및 휴대폰 제어

이 패키지는 Reachy Mini 1.13.x 앱입니다. 로봇 데몬이 전달한 연결된 ReachyMini를 사용합니다. 노트북 스크립트는 그대로 실행할 수 있습니다.

## 현장 전 준비

1. 설치할 때는 노트북과 로봇이 같은 네트워크에 있어야 합니다. 현장에서는 휴대폰 핫스팟을 켜고 로봇을 그 Wi-Fi에 연결합니다. Reachy Mini Control의 Wi-Fi 설정 흐름을 이용하세요. 로봇 IP는 Control 앱 또는 핫스팟의 연결 기기 목록에서 확인합니다. 휴대폰 브라우저에서 `reachy-mini.local`이 안 열리면 IP를 사용합니다.
2. 인터넷 연결을 확인합니다. ElevenLabs 대화, Scribe, 첫 TTS 생성에는 인터넷이 필요합니다.
3. `riichi_app/config.json`에서 `agent_id`, `greetings`, `language`를 현장 대사로 바꿉니다. `voice_id`도 필요하면 여기서 바꿉니다. 대사 변경 뒤 앱을 재설치하고 재시작합니다. 음성 MP3는 첫 사용 때 로봇의 `~/.cache/riichi/speech`에 생성되어 재사용됩니다.

## 설치

현재 이 앱은 Hugging Face에 게시되지 않았습니다. **오늘은 수동 설치가 필요**하며, 설치 단계에서만 노트북을 쓰면 됩니다. 로봇에는 앱 전용 `/venvs/apps_venv/` 환경이 있습니다. 예시는 프로젝트 루트에서 실행합니다.

```bash
scp -r apps/riichi_app pollen@<robot-ip>:/tmp/riichi_app
ssh pollen@<robot-ip> "/venvs/apps_venv/bin/pip install /tmp/riichi_app"
```

필요한 기본 패키지는 `pyproject.toml`에 선언되어 있습니다. YOLO 사람 추적은 ARM용 onnxruntime 설치가 가능한 경우에만 추가합니다.

```bash
ssh pollen@<robot-ip> "/venvs/apps_venv/bin/pip install '/tmp/riichi_app[tracking]'"
```

YOLO11n ONNX 파일은 Git에 포함하지 않습니다. 다른 컴퓨터에서 `ultralytics`의 `YOLO('yolo11n.pt').export(format='onnx', imgsz=640)`로 `yolo11n.onnx`를 만든 뒤 다음 위치로 복사합니다.

```bash
ssh pollen@<robot-ip> "mkdir -p ~/.cache/riichi"
scp yolo11n.onnx pollen@<robot-ip>:~/.cache/riichi/yolo11n.onnx
```

onnxruntime이나 모델을 준비하지 못해도 앱은 시작됩니다. 상태 화면에 이유를 표시하고, 정해진 간격으로 인사합니다. `config.json`의 `detection_fps` 기본값은 2이며 CPU 부하가 높으면 1 이하로 낮춥니다. 이 변경에도 재설치가 필요합니다.

게시가 허용된 뒤에는 Hugging Face Space의 `reachy_mini_python_app` 태그로 앱을 배포할 수 있고, Reachy Mini Control의 Applications → Discover Apps에서 설치할 수 있습니다. 이 경로는 아직 실행하지 않았습니다.

## 휴대폰에서 사용

Reachy Mini Control에서 설치된 `riichi_app`을 시작하거나 중지합니다. 앱 실행 뒤 휴대폰 브라우저에서 `http://<robot-ip>:8042`를 엽니다. 로봇과 휴대폰은 같은 핫스팟 네트워크에 있어야 합니다. 큰 버튼으로 환영, 대화, 타이머, 춤, 볼륨, 테스트 말하기를 조작합니다. 시작 기본 모드는 환영입니다. 대화 모드는 “리치야” 또는 “Hey Reachy”를 부른 뒤 질문합니다. 타이머는 낮은 우선순위이며 전화 화면에서 시작/다음, 일시정지, 초기화, 길이를 조작합니다. 손인사 감지는 사용하지 않습니다.

## API 키

화면 아래의 비밀번호 입력칸에서 키를 저장합니다. 키는 응답에 포함되지 않으며 로봇의 앱 실행 계정 홈에 `~/.elevenlabs/reachy.env`로 저장됩니다. 환경 변수 `ELEVENLABS_API_KEY`도 사용할 수 있습니다. 웹 페이지는 HTTP이므로 키 입력은 본인이 관리하는 핫스팟에서 하세요. 키를 저장한 뒤 대화 모드를 다시 선택하면 연결을 시도합니다. 사전 설정을 원하면 로봇에서 해당 파일에 `ELEVENLABS_API_KEY=...` 한 줄을 넣고 파일 권한을 600으로 지정합니다. 값을 Git, 채팅, 로그에 붙여 넣지 마세요.

## 장애 확인

상태 화면은 현재 모드, 최근 음성 인식, 추적 상태, 오류를 표시합니다. `사람 추적 사용 불가`가 보이면 ONNX 설치/모델 경로를 확인합니다. `STT 연결` 또는 `대화 연결`이 보이면 API 키와 핫스팟 인터넷을 확인합니다. 로봇에서 이 앱의 ARM CPU 사용량 및 실제 스피커·마이크 동작은 현장 검증이 필요합니다.

참고: [Reachy Mini 1.13 앱 문서](https://huggingface.co/docs/reachy_mini/SDK/apps), [Wireless 연결](https://huggingface.co/docs/reachy_mini/platforms/reachy_mini/getting_started).
