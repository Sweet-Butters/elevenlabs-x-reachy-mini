# 리치 비상용 진행 스크립트

## 조립 직후 로봇 점검

로봇과 노트북을 같은 휴대폰 핫스팟에 연결하고 로봇 전원과 데몬을 켠 뒤, 저장소 루트에서 한 명령으로 점검합니다. 네트워크, SDK 연결, 머리, 안테나, 카메라, 로봇 스피커, 로봇 마이크 순서로 PASS/FAIL과 다음 확인 항목이 표시됩니다. 머리와 안테나 주변에 걸리는 물건이 없는지 먼저 확인하세요.

```powershell
.venv\Scripts\python.exe scripts/robot_check.py
```

호스트는 `--host` → `REACHY_HOST` 환경 변수 → 사설 IP로 확인된 `reachy-mini.local` → 노트북의 같은 /24 네트워크 검색 순으로 찾고, 사용한 주소를 출력합니다. 직접 지정하려면 `--host 192.168.x.x`를 붙이세요. 카메라 화면을 3초간 보려면 `--show`, 한 단계만 다시 검사하려면 `--step camera`처럼 지정합니다. 각 단계의 제한 시간은 `--timeout 20`으로 조정할 수 있습니다. 카메라와 마이크 데이터는 저장하지 않으며, 스피커 PASS는 재생 요청을 보냈다는 뜻이므로 실제 소리를 들어 확인하세요.

## 통합 리치 앱 (`riichi.py`)

노트북 마이크·스피커·웹캠으로 먼저 실행합니다. 기본 시작 모드는 대화입니다. 타이머·환영 모드에서는 ElevenLabs 대화 연결을 완전히 끊고, 노트북 마이크는 종료 명령을 듣는 Scribe 실시간 STT에만 사용합니다. 인터넷이 끊기면 F1/F2/F3 키로 전환하세요. 타이머의 미리 만든 MP3는 오프라인에서도 재생됩니다.

대화 모드 기본값은 Scribe STT가 확정한 문장만 받습니다. `--robot`이면 로봇 마이크, 아니면 노트북 마이크를 사용합니다. “리치야, 제출 마감 언제야?”, “리치”, “Hey Reachy”, “Richie”처럼 **문장 맨 앞이나 짧은 인사 뒤에 이름**을 말해야 답합니다. 이름 없는 주변 대화는 화면에 `게이트> ignore`로만 표시됩니다. “리치야”만 말하면 “네!”라고 답하고 6초 안의 다음 문장을 받습니다. 답변 뒤 5초 안에는 이름 없는 후속 질문 한 번을 받습니다. `--followup-seconds 0`으로 후속 질문을 끄고, `--no-wake-word`로 기존 상시 음성 대화를 복원합니다. 대화 중 모드 명령에도 “리치야, 타이머 모드 5분”처럼 이름을 붙이세요. 타이머·환영 모드의 종료 명령은 기존처럼 이름 없이 말합니다. 키보드 F1/F2/F3는 언제나 사용 가능합니다.

로봇 카메라를 쓰는 대화·환영 모드에서는 손을 어깨 위로 들어 좌우로 흔들면 “네, 저도 반가워요! 안녕하세요!” 등으로 인사합니다. 기본 10초 간격이며 `--wave-cooldown 15`로 조정하거나 `--no-wave`로 끌 수 있습니다. 타이머 모드에서는 손인사를 감지하지 않습니다. 행사 전 `make_wave_lines.py`로 MP3를 만들고 `yolo11n-pose.onnx`를 저장소 루트에 내려받으세요.

```powershell
.venv\Scripts\python.exe scripts/make_timer_lines.py
.venv\Scripts\python.exe scripts/riichi.py
.venv\Scripts\python.exe scripts/riichi.py --mode timer --minutes 5
.venv\Scripts\python.exe scripts/riichi.py --mode timer --seconds 30
.venv\Scripts\python.exe scripts/riichi.py --text
.venv\Scripts\python.exe scripts/make_wave_lines.py
Invoke-WebRequest -Uri 'https://huggingface.co/unileon-robotics/YOLO11-ONNX/resolve/main/yolo11n-pose.onnx' -OutFile yolo11n-pose.onnx
```

대화 중 진행자는 이름을 붙여 "리치야, 타이머 모드 활성화", "타이머 모드 켜", "타이머 모드 5분", "타이머 30초", "타이머 모드 1분 30초", "timer 3 minutes", "Welcome Mode 시작", "웰컴 모드"라고 말할 수 있습니다. 길이를 포함한 타이머 명령은 그 길이로 발표를 바로 시작하고 길이를 알립니다. 길이 없는 모드 명령은 준비 상태로 전환합니다. 전환이 안 되면 **F2**로 타이머, **F3**으로 환영, **F1**로 대화를 직접 선택하세요. 현재 모드는 화면에 표시됩니다. 타이머 중에는 "타이머 모드 해제", "타이머 모드 꺼", "타이머 모드 off", "timer mode off"만 대화 모드로 돌아갑니다. "타이머 10분"은 다음 발표 길이를 바꿉니다. 다른 말에는 답하지 않습니다. 환영 중 "웰컴 모드 종료"로 대화 모드에 돌아갑니다.

타이머 조작: **Enter/Space** 발표 시작, `p` 일시정지·재개, `r` 초기화, `k`/`e` 다음 발표 언어, `n` 새 길이 입력, `q` 앱 종료. 문자 점검 모드에서는 `/f1`, `/f2`, `/f3`, `/enter`, `/p`, `/r`, `/k`, `/e`, `/quit`을 입력합니다. 실시간 STT에 네트워크가 필요하며 STT가 실패해도 화면에 오류가 표시되고 키보드 전환은 계속 가능합니다. 로봇 조립 후에는 `--robot`과 필요하면 `--camera robot`을 붙여 환영 모드의 로봇 동작을 사용합니다.

저장소 루트에서 PowerShell로 실행합니다. Python 3.13과 Windows 11 기준입니다. API 키는 `ELEVENLABS_API_KEY` 환경 변수에서 읽고, 없으면 `C:\Users\정회광\.elevenlabs\reachy.env`에서 읽습니다. 키 값은 화면에 표시하지 않습니다.

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

실시간 대화에는 인터넷, 마이크, 스피커가 필요합니다. 종료는 `Ctrl+C`입니다.

```powershell
.venv\Scripts\python.exe scripts/chat.py
```

Orca 터미널에서는 한 명령으로 실행할 수 있습니다.

```powershell
orca terminal create --command ".venv\Scripts\python.exe scripts/chat.py"
```

키보드로 대화하려면 다음을 실행합니다. 종료는 `/quit`입니다.

```powershell
.venv\Scripts\python.exe scripts/chat.py --text
```

행사 전 인터넷이 되는 곳에서 MP3를 미리 만듭니다. 기본값은 에이전트에 설정된 목소리이며, 필요하면 `--voice VOICE_ID`를 붙입니다. 기존 파일은 건너뛰고, 다시 만들려면 `--force`를 붙입니다.

```powershell
.venv\Scripts\python.exe scripts/make_lines.py
```

MP3가 만들어진 뒤 아래 두 명령은 인터넷과 API 키 없이 작동합니다. 번호는 [대본](../agent/lines.ko.md)에 있습니다.

```powershell
.venv\Scripts\python.exe scripts/play_lines.py --list
.venv\Scripts\python.exe scripts/play_lines.py 1
```

## 입구 환영 모드 (13:00~13:15 체크인)

행사 전에 인터넷이 연결된 상태에서 [환영 대사](../agent/welcome-lines.ko.md) MP3를 생성합니다. 기본으로 ElevenLabs 에이전트에 현재 설정된 목소리를 사용합니다. 실행 중에는 인터넷과 API 키가 필요하지 않습니다.

```powershell
.venv\Scripts\python.exe scripts/make_lines.py --welcome --voice vJ170fCwESgE1tjW39So
Invoke-WebRequest -Uri 'https://huggingface.co/Kalray/yolo11/resolve/main/yolo11n.onnx?download=true' -OutFile yolo11n.onnx
.venv\Scripts\python.exe scripts/welcome_mode.py --preview
```

웹캠 화면에 파란 영역과 초록색 사람 박스가 나타납니다. 카메라를 입구 쪽으로 향하게 하고, 사람의 **몸통이 보이도록** 조정하세요. 로봇은 낮은 탁자에 있어 얼굴이 잘릴 수 있으므로 얼굴 감지는 사용하지 않습니다. 사람 박스가 약 1초 동안 커지면 접근으로 보고 인사합니다. 한 무리에게 인사가 반복되지 않도록 기본 8초 간격을 둡니다. `Q` 또는 `Esc`로 미리보기 종료, `Ctrl+C`로 명령 종료입니다.

로봇 조립과 같은 Wi-Fi 연결, 데몬 실행이 끝나면 다음 한 명령으로 시작합니다. 기본 카메라는 노트북 웹캠이며 로봇 머리·안테나·스피커를 사용합니다. 로봇 카메라를 쓰려면 `--camera robot`을 추가합니다.

```powershell
.venv\Scripts\python.exe scripts/welcome_mode.py --robot --preview
.venv\Scripts\python.exe scripts/welcome_mode.py --robot --camera robot --preview
```

현장에서 입구가 화면의 일부라면 `--region x1,y1,x2,y2`로 영역을 지정하세요. 좌표는 화면 너비·높이의 0~1 비율이며 기본은 전체 화면입니다. 예를 들어 왼쪽 절반은 `--region 0,0,0.5,1`입니다. `--sensitivity`는 0~1이며 클수록 작은 접근 변화도 인사합니다(기본 0.5). 인사가 너무 잦으면 값을 낮추거나 `--cooldown 12`를 사용하세요. 사람 감지가 카메라 각도 때문에 잘 안 되면 `--detector motion`으로 영역 안의 움직임을 감지할 수 있습니다. 이 모드에서는 사람 외의 움직임에도 반응할 수 있으므로 영역을 좁히세요.

```powershell
.venv\Scripts\python.exe scripts/welcome_mode.py --robot --region 0.1,0.1,0.9,0.95 --sensitivity 0.7 --cooldown 10 --preview
.venv\Scripts\python.exe scripts/welcome_mode.py --robot --detector motion --region 0.1,0.1,0.9,0.95 --preview
```

테스트 때만 `--max-seconds 20`을 붙이면 자동 종료합니다. 사람 감지는 CPU 1스레드의 YOLO11 nano ONNX 모델로 처리하며 PyTorch는 실행하지 않습니다. 모델 파일은 행사 전에 위 명령으로 한 번 내려받아 저장소 루트에 두세요. 모델은 Git에 포함되지 않습니다. 이후 감지는 인터넷 없이 작동합니다. **카메라 프레임·영상은 디스크에 저장하거나 업로드하지 않습니다. 얼굴 인식도 하지 않습니다.** 미리보기는 화면에만 표시됩니다. `--robot` 실행 시에는 MP3 파일만 로컬 Wi-Fi로 로봇에 전송하여 로봇 스피커에서 재생합니다.
