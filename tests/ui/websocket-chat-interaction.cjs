const {chromium} = require(process.env.CHAT_PLAYWRIGHT_MODULE || 'playwright');
const fs = require('fs');
const out = process.env.CHAT_UI_EVIDENCE_DIR || fs.mkdtempSync(require('node:path').join(require('node:os').tmpdir(),'healthcore-chat-ui-'));
fs.mkdirSync(out,{recursive:true});
const uiBase = process.env.CHAT_UI_BASE_URL || 'http://127.0.0.1:3055';
const apiBase = process.env.CHAT_API_BASE_URL || 'http://127.0.0.1:8055';
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.CHAT_BROWSER_EXECUTABLE ? {executablePath:process.env.CHAT_BROWSER_EXECUTABLE} : {})});
 try {
  const page=await browser.newPage();
  await page.route(apiBase+'/**',r=>r.fulfill({status:200,contentType:'application/json',body:JSON.stringify({email:'fictional-staff@example.invalid',role:'admin',department_id:'technology',department_name:'Technology',capabilities:[],profile:null})}));
  await page.addInitScript(()=>{
   localStorage.setItem('healthcore_access_token','fictional-browser-test-only');
   window.__chatSockets=[];
   class Socket {
    static OPEN=1; static CLOSED=3;
    constructor(url){this.url=String(url);this.readyState=1;this.frames=[];window.__chatSockets.push(this);setTimeout(()=>this.onopen?.({}),0);}
    send(text){this.frames.push(JSON.parse(text));}
    close(){this.readyState=3;}
    emit(event,data){this.onmessage?.({data:JSON.stringify({event,data})});}
    drop(){this.readyState=3;this.onclose?.({code:1006});}
   }
   window.WebSocket=Socket;
  });
  await page.goto(uiBase+'/backoffice/knowledge');
  await page.waitForFunction(()=>window.__chatSockets.length>0);
  await page.evaluate(()=>{const s=window.__chatSockets[0];s.emit('session_snapshot',{session_id:s.url.split('/').at(-1),generating:true,messages:[]});});
  await page.getByRole('status').filter({hasText:'Connected'}).waitFor();
  await page.locator('#knowledge-question').fill('What does the compliance policy require?');
  await page.locator('form.knowledge-form button[type=submit]').click();
  await page.evaluate(()=>{const s=window.__chatSockets[0];const id=s.url.split('/').at(-1);s.emit('user_message',{session_id:id,text:'What does the compliance policy require?'});s.emit('token_chunk',{session_id:id,token:'The policy requires ',sequence:1});});
  await page.getByRole('button',{name:'Interrupt and ask this instead'}).waitFor();
  await page.evaluate(()=>window.__chatSockets[0].drop());
  await page.waitForFunction(()=>window.__chatSockets.length===2);
  await page.evaluate(()=>{const s=window.__chatSockets[1];s.emit('session_snapshot',{session_id:s.url.split('/').at(-1),generating:true,messages:[{message_id:'user_1',role:'user',text:'What does the compliance policy require?'},{message_id:'msg_partial',role:'assistant',text:'The policy requires '}]});});
  await page.getByRole('status').filter({hasText:'Connected'}).waitFor();
  await page.locator('#knowledge-question').fill('Please focus on UK GDPR.');
  await page.locator('form.knowledge-form button[type=submit]').click();
  const sent=await page.evaluate(()=>window.__chatSockets[1].frames.filter(x=>x.event!=='auth'));
  const result={case:'redirect immediately after reconnect while generation remains active',expected:'interrupt_requested',actual:sent.at(-1)?.event,passed:sent.at(-1)?.event==='interrupt_requested',same_session:await page.evaluate(()=>window.__chatSockets[0].url===window.__chatSockets[1].url),partial_visible:await page.locator('.knowledge-thread').innerText()};
  await page.screenshot({path:out+'/reconnect-after.png',fullPage:true});
  const assert = require('node:assert/strict');
  assert.equal(result.passed,true);
  await page.evaluate(()=>{const s=window.__chatSockets[1];const id=s.url.split('/').at(-1);s.emit('generation_interrupted',{session_id:id,message_id:'msg_partial',status:'interrupted'});s.emit('user_message',{session_id:id,text:'Please focus on UK GDPR.'});s.emit('token_chunk',{session_id:id,token:'The UK GDPR policy ',sequence:1});});
  await page.locator('.knowledge-interrupted-mark').waitFor();
  await page.waitForFunction(()=>document.querySelector('.knowledge-thread')?.textContent.includes('The UK GDPR policy '));
  const partialThread=await page.locator('.knowledge-thread').innerText();
  assert(partialThread.includes('The policy requires'));
  assert(partialThread.includes('Interrupted'));
  assert.equal(await page.locator('.knowledge-thread > li').count(),4);
  await page.screenshot({path:out+'/interrupted-new-turn.png',fullPage:true});
  await page.evaluate(()=>{const s=window.__chatSockets[1];const id=s.url.split('/').at(-1);s.emit('token_chunk',{session_id:id,token:'applies to this question.',sequence:2});s.emit('generation_completed',{session_id:id,message_id:'msg_redirected'});});
  await page.getByRole('button',{name:'Ask HealthCore knowledge',exact:true}).waitFor();
  assert((await page.locator('.knowledge-thread').innerText()).includes('The UK GDPR policy applies to this question.'));
  result.partial_preserved_and_marked=true;result.redirect_is_new_turn=true;result.incremental_rendering=true;result.completion_returns_to_idle=true;
  await page.evaluate(()=>window.__chatSockets[1].drop());
  await page.waitForFunction(()=>window.__chatSockets.length===3);
  await page.evaluate(()=>window.__chatSockets[2].drop());
  await page.getByRole('status').filter({hasText:'Reconnecting in 1s'}).waitFor({timeout:3000});
  result.progressive_reconnect_backoff=true;
  await page.waitForFunction(()=>window.__chatSockets.length===4);
  const beforeSnapshot=await page.locator('.knowledge-thread').innerText();
  await page.evaluate(()=>{const s=window.__chatSockets[3];s.emit('token_chunk',{session_id:s.url.split('/').at(-1),token:'Do not accept before snapshot.',sequence:99});});
  assert.equal(await page.locator('.knowledge-thread').innerText(),beforeSnapshot);
  result.tokens_wait_for_snapshot=true;
  await page.evaluate(()=>{const s=window.__chatSockets[3];s.emit('session_snapshot',{session_id:s.url.split('/').at(-1),generating:false,messages:[]});});
  await page.locator('#knowledge-question').fill('What does the policy require?');
  await page.locator('form.knowledge-form button[type=submit]').click();
  await page.getByRole('button',{name:'Interrupt and ask this instead'}).waitFor();
  await page.locator('#knowledge-question').fill('Focus on the relevant policy section.');
  await page.locator('form.knowledge-form button[type=submit]').click();
  const early=await page.evaluate(()=>window.__chatSockets[3].frames.filter(x=>x.event!=='auth'));
  assert.equal(early[0].event,'user_message');assert.equal(early[1].event,'interrupt_requested');
  result.redirect_before_first_token=true;
  await page.screenshot({path:out+'/interaction-after.png',fullPage:true});
  fs.writeFileSync(out+'/reconnect-after.json',JSON.stringify(result,null,2));console.log(JSON.stringify(result));if(!result.passed)throw new Error('Reconnect redirect did not interrupt');
 } finally {await browser.close();}
})().catch(e=>{console.error(e.message);process.exit(1)});
