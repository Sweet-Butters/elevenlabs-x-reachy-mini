# 리치 결선 발표 타이머

발표자 10명, 각 3분 기준입니다. 리치의 대사를 미리 MP3로 저장하므로 행사 중 인터넷 연결은 필요하지 않습니다. 기본 출력은 노트북 스피커입니다.

결선 중에는 **로봇의 대화 앱을 중지**해 주세요. 발표자의 말에 로봇이 응답하지 않도록 하기 위해서입니다.

## 행사 전 준비

작업 폴더에서 PowerShell을 열고 실행합니다.

```powershell
.\.venv\Scripts\python.exe scripts\make_timer_lines.py
.\.venv\Scripts\python.exe scripts\pitch_timer.py --lang ko
```

MP3 생성 시에만 ElevenLabs API 연결과 키가 필요합니다. 생성된 파일은 `audio/timer/ko/`, `audio/timer/en/`에 저장됩니다. 행사 전 노트북의 오디오 출력과 볼륨을 확인해 주세요.

## 진행 키

| 키 | 동작 |
|---|---|
| Enter 또는 Space | 다음 발표 시작 (완료 후에는 다음 발표자로 진행) |
| `p` | 현재 발표 일시정지 / 재개 |
| `r` | 현재 발표 초기화. Enter/Space로 같은 발표자 재시작 |
| `k` | 다음에 시작하는 발표 언어를 한국어로 선택 |
| `e` | 다음에 시작하는 발표 언어를 영어로 선택 |
| `q` | 종료 |

발표 중 `k`/`e`를 누르면 현재 발표의 언어는 유지하고 다음 발표의 언어가 바뀝니다. 발표 시작 전에도 언어를 선택할 수 있습니다. 안내는 경과 1분, 2분, 3분에 순서대로 재생됩니다.

## 시간 설정과 짧은 점검

```powershell
.\.venv\Scripts\python.exe scripts\pitch_timer.py --lang en --minutes 3 --announce-at 1,2,3
.\.venv\Scripts\python.exe scripts\pitch_timer.py --demo --time-scale 0.02 --lang ko
```

`--minutes`는 발표 길이(분), `--announce-at`은 세 안내의 경과 시점(분)입니다. `--time-scale`은 점검용 배율이며 기본값은 1입니다. 실제 행사에서는 배율 옵션을 사용하지 마세요. `--demo`는 한 발표를 자동 시작하고 오디오 재생이 끝나면 종료합니다.
