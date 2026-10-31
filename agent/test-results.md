# 리치 API 텍스트 테스트 — 2026-10-30

Agent: `agent_9101m65rk0eqe2ytcq56ceg7hw10`  
Main version: `agtvrsn_8901m65sxe8xfrgtah6nkvyv66hj`  
Method: ElevenLabs signed URL + official ElevenAgents WebSocket, text-only conversation override. Each question used a fresh session. The English session selected the agent's existing `en` language preset.

1. **Q:** 제출 마감 언제야?  
   **A:** 제출 마감은 오늘 오후 세 시 반이에요. 그때부터 바로 1차 심사가 시작되니까, 조금 일찍 내는 걸 추천해요!  
   **Result:** PASS — 15:30.

2. **Q:** 상은 몇 개야?  
   **A:** 상은 모두 열세 개예요. 종합 1위 한 명, ElevenLabs 상 한 명, 1st Runner-up 한 명, 2nd Runner-up 두 명, Rising Builder 두 명, 그리고 SYNNEX 과제상 세 명과 Trip-Pups 과제상 세 명이 있어요.  
   **Result:** PASS — 13 awards. One attempt timed out; the retry returned this answer.

3. **Q:** 심사 기준 알려줘  
   **A:** 심사는 운영진이 하고 참가자 투표는 없어요. 기준은 네 가지로 똑같이 25퍼센트씩인데, 지금 열어서 써 볼 수 있는지, 누가 어디서 막히는 문제인지, AI가 해결의 핵심인지, 그리고 이미 있는 것과 무엇이 다른지예요. 언제 만들었는지와 상관없이 오늘 보여 주는 결과물로만 심사한다고 하네요.  
   **Result:** PASS — four criteria at 25% each; staff judging, no participant vote.

4. **Q:** 와이파이 비밀번호 뭐야?  
   **A:** 와이파이 비밀번호는 제 자료에 없어서 제가 알려드릴 수 없어요. 체크인할 때 운영진이 와이파이와 세팅을 안내해 드리니, 현장 운영진에게 물어봐 주세요.  
   **Result:** PASS — does not invent a password and refers to staff.

5. **Q:** What time is the final presentation?  
   **A:** I'll look that up for you. The final presentations start at three fifty-five in the afternoon. Ten people present, three minutes each, and they show what they built live instead of using slides.  
   **Result:** PASS — English answer and 15:55, with the `en` session preset.

**Summary:** 5/5 passed with the appropriate session language. In separate text-only sessions started with the default Korean language, the English question sometimes received a Korean answer despite the English system-prompt instruction. Clients should select the `en` preset for English sessions. A timed-out awards attempt succeeded on retry. No factual prompt or knowledge-base changes were needed.

## Voice selection

| Candidate | Voice ID | Assessment |
| --- | --- | --- |
| Aria - Bright & Youthful Korean | `O2KReOFLpoR65nz6C9Se` | Bright and cute Korean conversational description, but ElevenAgents rejected it because live moderation is enabled. |
| Sena - Friendly Cheerful | `vJ170fCwESgE1tjW39So` | Bright, cute Korean voice suited to dialogue and animation. Selected for the small friendly robot. |
| Jisun - Warm & Friendly Korean | `7Tms2JpTU4QYeCNp0Gtn` | Warm, friendly Korean voice suited to conversation; less playful than Sena. |

Published voice: Sena, with `eleven_v4_turbo` (Korean supported). API readback showed Main at 100% live traffic, no draft, and the published voice ID above.

## 통합 리치 모드 점검 — 2026-10-30

- Main version `agtvrsn_5001m66gsc42e36sjc5nv19rp91h`: API readback에서 `set_mode` client tool 및 로컬 프롬프트 일치를 확인. 음성 ID와 Knowledge Base는 이전 버전과 동일.
- `scripts/smoke_riichi_live.py`: 실제 텍스트 세션에서 "타이머 모드 활성화" → `set_mode(timer)` → 대화 소켓 종료 → 일반 질문 무시 → "타이머 모드 해제" → 대화 소켓 재연결 → 제출 마감 "오후 세 시 반" 응답. "타이머 모드 5분" → `duration_seconds=300` 및 타이머 시작도 통과.
- F1/F2 전환 이벤트, 환영 모드의 일반 발화 무시 및 "웰컴 모드 종료" 전환 점검. `welcome_mode.py --detector motion --max-seconds 4`로 노트북 웹캠과 환영 오디오가 동작함.
- Scribe 실시간 STT는 노트북 마이크를 열고 `session_started` 이벤트까지 확인. 실제 발화의 인식률과 로봇 입출력은 아직 현장 점검 필요.
- 타이머 KO/EN 캐시 192개 생성 확인. 파일은 `.gitignore`의 `audio/`에 따라 로컬에만 보관됨.

## KB 웹사이트·CS 갱신 후 테스트 — 2026-10-30

Main version: `agtvrsn_4001m66hwtxpfxxa29knmn1h2srz`. 이전 테스트와 같은 ElevenAgents WebSocket 텍스트 방식. 질문마다 새 세션, 영어는 `en` 프리셋.

1. **Q:** 주차 돼?  
   **A:** 주차는 제가 확실히 아는 정보가 아니라서요, 운영진에게 물어봐 주시면 정확하게 안내받으실 수 있을 거예요. 다른 궁금한 점 있으면 물어봐 주세요!  
   **Result:** FAIL.

2. **Q:** 1등 하려면 ElevenLabs 꼭 써야 해?  
   **A:** 네, 종합 1위를 받으려면 결과물에 ElevenLabs를 조금이라도 활용해야 해요. 다른 AI랑 같이 써도 괜찮고, 1위 말고 다른 상은 어떤 생성형 AI를 써도 받을 수 있어요.  
   **Result:** PASS.

3. **Q:** 발표는 어떻게 해?  
   **A:** 결선에 올라가면 한 사람당 3분씩 발표해요. PPT 없이 만든 것을 직접 보여 주시면 되고, 2분 설명에 1분 시연 영상을 곁들이는 걸 권장해요. 결선 발표는 오후 3시 55분에 시작해요.  
   **Result:** PASS.

4. **Q:** 상장은 언제 줘?  
   **A:** 상장은 수상자에게 당일 현장 시상식에서 드려요. 시상은 오후 네 시 반 예정이고, A4 크기 영문 실물 상장이에요.  
   **Result:** PASS.

5. **Q:** 참가확인서 받을 수 있어?  
   **A:** 참가확인서에 대해 확인해 볼게요, 잠시만요.  
   **Result:** FAIL.

6. **Q:** 몇 시에 끝나?  
   **A:** 오후 다섯 시에 끝날 예정이에요. 오후 네 시 반에 시상하고, 네 시 마흔두 시에 단체 사진, 마흔일곱 분에 마무리 안내가 있어요.  
   **Result:** FAIL.

7. **Q:** 참가자 전원 받는 거 있어?  
   **A:** 네, 있어요. 현장에 오신 참가자 전원에게 ElevenLabs Creator 한 달 이용권을 드리고, 체크인하신 모든 분은 참가확인서 PDF도 받으실 수 있어요.  
   **Result:** FAIL.

8. **Q:** 신청 아직 돼?  
   **A:** 안녕하세요! 신청 마감 여부는 제가 확실히 아는 내용이 아니라서요, 그건 운영진에게 물어봐 주세요. 다른 궁금한 점 있으면 도와드릴게요!  
   **Result:** FAIL.

9. **Q:** Can I use ChatGPT?  
   **A:** Let me check that for you.  
   **Result:** FAIL.

10. **Q:** 제출 마감 언제야?  
   **A:** 제출 마감은 10월 31일 오후 세 시 반이에요. 그때부터 1차 심사가 시작되고, 오후 세 시 오십오 분에 결선 발표가 있어요.  
   **Result:** FAIL.

11. **Q:** 상은 몇 개야?  
   **A:** 상은 모두 열세 개예요. 종합 1위와 ElevenLabs 상, 1st Runner-up이 각각 하나씩이고, 2nd Runner-up과 Rising Builder가 각각 둘, SYNNEX와 Trip-Pups 과제상이 각각 셋이에요.  
   **Result:** FAIL.

**Summary:** 3/11 passed.

## KB 웹사이트·CS 갱신 후 테스트 — 2026-10-30

Main version: `agtvrsn_4001m66hwtxpfxxa29knmn1h2srz`. 이전 테스트와 같은 ElevenAgents WebSocket 텍스트 방식. 질문마다 새 세션, 영어는 `en` 프리셋.

1. **Q:** 주차 돼?  
   **A:** 주차는 저도 잘 몰라서요, 그건 운영진에게 물어봐 주세요! 다른 궁금한 점 있으면 물어봐 주세요.  
   **Result:** FAIL.

5. **Q:** 참가확인서 받을 수 있어?  
   **A:** 참가확인서에 대해서는 제가 가진 정보가 없어서요, 그건 운영진에게 직접 물어봐 주세요.  
   **Result:** FAIL.

8. **Q:** 신청 아직 돼?  
   **A:** 안녕하세요! 신청 마감 여부는 제가 확실히 아는 내용이 아니라서요, 그건 운영진에게 물어봐 주세요. 다른 궁금한 점 있으면 도와드릴게요!  
   **Result:** PASS.

9. **Q:** Can I use ChatGPT?  
   **A:** Yes, you can! ChatGPT and any other generative AI are allowed. Just mark where you used it. One thing to keep in mind: to qualify for the Overall Winner prize, your project needs to include at least some use of ElevenLabs, though other awards don't require it.  
   **Result:** PASS.

**Summary:** 2/4 passed (questions 1, 5, 8, 9).

## KB 웹사이트·CS 갱신 후 테스트 — 2026-10-30

Main version: `agtvrsn_4001m66hwtxpfxxa29knmn1h2srz`. 이전 테스트와 같은 ElevenAgents WebSocket 텍스트 방식. 질문마다 새 세션, 영어는 `en` 프리셋.

1. **Q:** 주차 돼?  
   **A:** 주차는 저도 궁금하네요! 그건 운영진에게 물어봐 주세요. 제가 아는 건 해커톤 일정이나 규칙 같은 것들이에요.  
   **Result:** FAIL.

5. **Q:** 참가확인서 받을 수 있어?  
   **A:** 네, 받을 수 있어요. 체크인한 모든 참석자에게 참가확인서 PDF를 드리고, 수상 상장과는 별개예요. 참가 예정 확인서나 별도 양식이 필요하면 성명과 받을 이메일 주소, 필요한 양식을 hi@mandeun.com으로 보내 주시면 돼요.  
   **Result:** PASS.

8. **Q:** 신청 아직 돼?  
   **A:** 신청 마감 여부는 제가 확실히 아는 내용이 아니라서요, 그건 운영진에게 물어봐 주세요. 다른 궁금한 점 있으면 도와드릴게요.  
   **Result:** FAIL.

**Summary:** 1/3 passed (questions 1, 5, 8).

## KB 웹사이트·CS 갱신 후 테스트 — 2026-10-30

Main version: `agtvrsn_3101m67kpws2fhnt8153vsw2kj8p`. 이전 테스트와 같은 ElevenAgents WebSocket 텍스트 방식. 질문마다 새 세션, 영어는 `en` 프리셋.

1. **Q:** 주차 돼?  
   **A:** 주차 공간은 따로 제공하지 않아요. 대중교통 이용을 권해 드려요. 선릉역에서 도보 3분 거리라 지하철로 오시면 편해요.  
   **Result:** PASS.

2. **Q:** 1등 하려면 ElevenLabs 꼭 써야 해?  
   **A:** 네, 종합 1위를 받으려면 결과물에 ElevenLabs를 조금이라도 활용해야 해요. 다른 AI랑 같이 써도 괜찮고, 다른 상들은 어떤 생성형 AI를 써도 받을 수 있어요.  
   **Result:** PASS.

3. **Q:** 발표는 어떻게 해?  
   **A:** 결선에 올라가면 한 사람당 3분씩 발표해요. PPT 없이 만든 것을 직접 보여 주시면 되고, 2분 설명에 1분 시연 영상 구성을 권장해요.  
   **Result:** PASS.

4. **Q:** 상장은 언제 줘?  
   **A:** 상장은 오늘 오후 네 시 반 시상식에서 수상자에게 직접 드려요. A4 크기 영문 실물 상장이고, 성명과 프로젝트명, 상 이름이 들어가요.  
   **Result:** FAIL.

5. **Q:** 참가확인서 받을 수 있어?  
   **A:** 네, 체크인한 모든 참석자는 참가확인서 PDF를 받을 수 있어요. 참가 예정 확인서나 필요한 양식이 있으면 성명과 받을 이메일 주소를 hi@mandeun.com으로 보내 주시면 돼요.  
   **Result:** PASS.

6. **Q:** 몇 시에 끝나?  
   **A:** 오후 다섯 시에 끝나요. 시상이 오후 네 시 반, 단체 사진이 네 시 사십이 분, 마무리 안내가 네 시 사십칠 분에 있어요.  
   **Result:** PASS.

7. **Q:** 참가자 전원 받는 거 있어?  
   **A:** 네, 있어요! 현장에 오신 참가자 전원에게 ElevenLabs Creator 한 달 이용권을 드리고, 체크인하신 모든 분은 참가확인서 PDF도 받으실 수 있어요.  
   **Result:** PASS.

8. **Q:** 신청 아직 돼?  
   **A:** 이번 10월 31일 대회 신청은 마감됐어요. 선정 메일을 받은 분만 참가할 수 있고, 안내 누락이 의심되면 hi@mandeun.com으로 문의해 주세요.  
   **Result:** PASS.

9. **Q:** Can I use ChatGPT?  
   **A:** Yes, you can use ChatGPT and any other generative AI. Just note that to qualify for the Overall Winner prize, your project needs to include at least some use of ElevenLabs, though other awards don't require it.  
   **Result:** PASS.

10. **Q:** 제출 마감 언제야?  
   **A:** 제출 마감은 오늘 오후 세 시 반이에요. 그때부터 1차 심사가 시작돼요.  
   **Result:** PASS.

11. **Q:** 상은 몇 개야?  
   **A:** 상은 모두 열세 개예요. 종합 1위, ElevenLabs 상, 1st Runner-up이 각 하나씩이고, 2nd Runner-up과 Rising Builder가 각 두 개, SYNNEX와 Trip-Pups 과제상이 각 세 개예요.  
   **Result:** PASS.

**Summary:** 10/11 passed (questions 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11).

## KB 웹사이트·CS 갱신 후 테스트 — 2026-10-30

Main version: `agtvrsn_3101m67kpws2fhnt8153vsw2kj8p`. 이전 테스트와 같은 ElevenAgents WebSocket 텍스트 방식. 질문마다 새 세션, 영어는 `en` 프리셋.

4. **Q:** 상장은 언제 줘?  
   **A:** 상장은 오늘 오후 네 시 반 시상식에서 수상자에게 바로 드려요. A4 크기 영문 실물 상장이고, 성명과 프로젝트명, 상 이름, 날짜, 주최자 서명과 인장이 들어가요.  
   **Result:** PASS.

**Summary:** 1/1 passed (questions 4).

**최종 판정 (2026-10-31): 11/11 PASS.** 첫 실행의 주차·신청 마감 오답은 KB를 대화 문맥에 포함하도록 사용 방식을 바꾼 뒤 해결됐다. 참가확인서는 에이전트가 실제 사용하는 RAG 모델의 인덱싱을 완료한 뒤 통과했다. 숫자를 말로 답한 경우와 "시상식에서 직접 드려요"를 "현장" 단어 부재로 실패 처리한 경우는 테스트 판정 조건을 수정했다. 영어 질문은 `en` 프리셋의 새 세션에서 영어로 답했다.

## KB 웹사이트·CS 갱신 후 테스트 — 2026-10-31

Main version: `agtvrsn_3901m67mszarefz8q05q360geav0`. 이전 테스트와 같은 ElevenAgents WebSocket 텍스트 방식. 질문마다 새 세션, 영어는 `en` 프리셋.

1. **Q:** 주차 돼?  
   **A:** 주차 공간은 따로 제공하지 않아요. 대중교통으로 오시는 걸 추천드려요!  
   **Result:** PASS.

2. **Q:** 1등 하려면 ElevenLabs 꼭 써야 해?  
   **A:** 네, 종합 1위를 받으려면 결과물에 ElevenLabs를 조금이라도 활용해야 해요. 다른 AI와 함께 써도 괜찮고, 1위 말고 다른 상은 어떤 생성형 AI를 써도 받을 수 있어요.  
   **Result:** PASS.

3. **Q:** 발표는 어떻게 해?  
   **A:** 결선에 올라가면 열 명이 한 사람당 삼 분씩 발표해요. PPT 없이 만든 것을 직접 보여 주시면 되고, 이 분 설명에 일 분 시연 영상 구성을 권장해요.  
   **Result:** PASS.

4. **Q:** 상장은 언제 줘?  
   **A:** 상장은 오늘 오후 네 시 반 시상식에서 드려요. 수상자는 그 자리에서 A4 크기 영문 실물 상장을 받으세요.  
   **Result:** PASS.

5. **Q:** 참가확인서 받을 수 있어?  
   **A:** 네, 체크인한 모든 참석자는 참가확인서 PDF를 받을 수 있어요. 참가 예정 확인서나 특별한 양식이 필요하면 성명과 받을 이메일 주소, 필요한 양식을 hi@mandeun.com으로 보내 주시면 돼요.  
   **Result:** PASS.

6. **Q:** 몇 시에 끝나?  
   **A:** 오후 다섯 시에 끝나요. 시상이 오후 네 시 반, 단체 사진이 네 시 사십이 분, 마무리 안내가 네 시 사십칠 분에 있어요.  
   **Result:** PASS.

7. **Q:** 참가자 전원 받는 거 있어?  
   **A:** 네, 있어요! 현장에 오신 참가자 전원에게 ElevenLabs Creator 1개월 이용권을 드리고, 체크인하신 모든 분은 참가확인서 PDF도 받으실 수 있어요.  
   **Result:** PASS.

8. **Q:** 신청 아직 돼?  
   **A:** 이번 10월 31일 대회 신청은 마감됐어요. 선정 메일을 받은 분만 참가할 수 있고, 안내 누락이 의심되면 hi@mandeun.com으로 문의해 주세요.  
   **Result:** PASS.

9. **Q:** Can I use ChatGPT?  
   **A:** Yes, you can use ChatGPT and any other generative AI. Just note that to qualify for the Overall Winner award, your project needs to include at least some use of ElevenLabs. Other awards don't require it.  
   **Result:** PASS.

10. **Q:** 제출 마감 언제야?  
   **A:** 제출 마감은 오늘 오후 세 시 반이에요. 그때부터 1차 심사가 시작돼요.  
   **Result:** PASS.

11. **Q:** 상은 몇 개야?  
   **A:** 상은 모두 열세 개예요. 종합 1위와 ElevenLabs 상, 1st Runner-up이 각 하나씩이고, 2nd Runner-up과 Rising Builder가 각 두 개, SYNNEX와 Trip-Pups 과제상이 각 세 개예요.  
   **Result:** PASS.

**Summary:** 11/11 passed (questions 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11).
