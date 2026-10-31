const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
async function untilReady(path, options) {
  // The page may load before wrapped_run has connected to Reachy.
  for (let attempt = 0; attempt < 20; attempt++) {
    try {
      const response = await fetch(path, options);
      if (response.status !== 503) return response;
    } catch (error) {
      if (attempt === 19) throw error;
    }
    await pause(500);
  }
  throw Error('로봇 연결 시간 초과');
}
async function send(action,value=null){try{let r=await untilReady('/api/command',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action,value})});if(!r.ok)throw Error(await r.text());await status()}catch(e){document.getElementById('connection').textContent='명령 오류: '+e.message}}
let dance=true;function toggleDance(){dance=!dance;send('dance',dance)}
async function saveKey(){let field=document.getElementById('key');try{let r=await fetch('/api/key',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({key:field.value})});if(!r.ok)throw Error(await r.text());field.value='';document.getElementById('key_status').textContent='저장됨. 대화 모드를 다시 눌러 연결하세요.'}catch(e){document.getElementById('key_status').textContent='저장 실패: '+e.message}}
async function status(){try{let r=await untilReady('/api/status',{cache:'no-store'});if(!r.ok)throw Error(r.status);let s=await r.json();document.getElementById('connection').textContent='연결됨 · 키 '+(s.key_saved?'저장됨':'필요');for(let id of ['mode','timer_state','tracking'])document.getElementById(id).textContent=s[id];document.getElementById('transcript').textContent=s.last_transcript||'—';document.getElementById('error').textContent=s.error||'없음';document.getElementById('remaining').textContent=Math.floor(s.remaining/60)+':'+String(s.remaining%60).padStart(2,'0');if(document.activeElement!==document.getElementById('length'))document.getElementById('length').value=s.length;dance=s.dance;document.getElementById('dance').textContent=dance?'춤 끄기':'춤 켜기'}catch(e){document.getElementById('connection').textContent='연결 대기 중…'}}
status();setInterval(status,1500);
