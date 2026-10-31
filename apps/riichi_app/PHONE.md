# 행사 당일: 휴대폰으로 리치 사용

## 한 번만 준비

1. 로봇과 휴대폰을 같은 Wi-Fi에 연결하고, 로봇에 `riichi_app`을 설치한다. 공개 Hugging Face Space라면 로봇 데몬의 `POST /api/apps/install`에 `{"name":"riichi_app","url":"https://huggingface.co/spaces/<계정>/<Space>","source_kind":"hf_space","extra":{"id":"<계정>/<Space>"}}`를 보낸 뒤 반환된 `job_id`를 `/api/apps/job-status/<job_id>`로 확인한다. 공개 Space는 앱 목록에서 찾기 쉽지만 코드가 공개된다. 비공개 Space는 HF 로그인/토큰이 필요하고 목록에 자동 노출되지 않는다. 이 경우 데몬의 `POST /api/apps/install-private-space`에 `{"space_id":"<계정>/<Space>"}`를 보내거나, 인증된 상태에서 설치한다.
2. Space를 쓰지 않으면 노트북에서 `scp -r apps/riichi_app pollen@<로봇 IP>:/tmp/riichi_app` 후 `ssh pollen@<로봇 IP> "/venvs/apps_venv/bin/pip install /tmp/riichi_app"`를 실행한다. 로봇의 앱 환경은 `/venvs/apps_venv/`이다. 수동 설치 앱도 휴대폰의 **Apps → On your robot**에 표시되고 시작할 수 있다.
3. 노트북이나 휴대폰 브라우저에서 `http://<로봇 IP>:8042`를 열어 ElevenLabs API 키를 한 번 저장한다. 이후 키는 로봇의 `~/.elevenlabs/reachy.env`에 남는다. 인터넷 연결도 필요하다.
4. 설치 후 `PUT http://<로봇 IP>:8000/api/apps/startup-app`에 `{"startup_app":"riichi_app"}`를 보내고 `GET /api/apps/startup-app`으로 확인한다. 이 설정은 설치된 앱만 받으며 즉시 적용된다. 다음 부팅 후 첫 기상 또는 대기 중 안테나 터치에 앱이 시작된다. 이미 다른 앱/원격 세션이 로봇을 사용 중이면 그 앱을 밀어내지 않는다. 해제할 때는 `{"startup_app":null}`.

## 행사 당일

로봇 전원을 켜고 휴대폰의 ReachyMini 앱에서 로봇에 연결한다. **Apps → On your robot → riichi_app → Start**를 누른다. 시작 앱으로 설정되어 이미 실행 중이면 Start를 누를 필요가 없다. 종료는 같은 화면의 **Stop**. 환영/대화/타이머/춤 조작은 휴대폰 브라우저에서 `http://<로봇 IP>:8042`를 연다. 현재 모바일 앱은 로봇 Python 앱의 `custom_app_url`을 자동으로 열지 않는다. IP가 바뀌면 휴대폰의 연결된 로봇 주소 또는 공유기/핫스팟 연결 기기 목록에서 새 IP를 확인한다.

실제 휴대폰·로봇의 화면, 기상 동작, 마이크/스피커, 네트워크와 ARM 추적 성능은 현장 사전 점검이 필요하다.
