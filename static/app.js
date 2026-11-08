import {NeuralRing} from './ring.js';

const $=id=>document.getElementById(id);
const ring=new NeuralRing($('ring'));
const statusLabels={idle:'待命',working:'运行中',done:'已完成',error:'异常',stale:'失联'};
const scenarioLabels={build:'产品研发演示',research:'研究简报演示',incident:'故障排查演示'};
let state=null,selected=null,feedKey='',toastTimer,online=true,busy=false;
const pad=n=>String(n).padStart(2,'0');
const formatTime=n=>`${pad(Math.floor(n/60))}:${pad(Math.floor(n%60))}`;
const text=(id,value)=>$(id).textContent=value;

function notify(message,error=false){clearTimeout(toastTimer);text('toast',message);$('toast').classList.toggle('error',error);$('toast').classList.add('visible');toastTimer=setTimeout(()=>$('toast').classList.remove('visible'),4200)}
async function request(path,body){
  const response=await fetch(path,{method:body?'POST':'GET',headers:body?{'Content-Type':'application/json'}:{},body:body?JSON.stringify(body):undefined,signal:AbortSignal.timeout(5000)});
  const result=await response.json();if(!response.ok)throw Error(result.error||'请求失败');return result;
}
function setOnline(value){online=value;$('connection').classList.toggle('offline',!value);$('connection').replaceChildren(Object.assign(document.createElement('i'),{}),document.createTextNode(value?'本地在线':'连接中断 · 重试中'));$('launch-button').disabled=!value||busy;$('pause-demo').disabled=!value||state?.mode==='live';$('speed').disabled=!value||state?.mode==='live'}

function buildAgents(){
  if($('agent-list').children.length)return;
  for(const [i,a]of state.agents.entries()){
    const button=document.createElement('button');button.className='agent-seat';button.dataset.agent=a.id;button.style.setProperty('--agent-color',a.color);button.setAttribute('aria-label',`${a.id} ${a.role}，查看席位详情`);
    button.innerHTML='<div class="agent-row"><span><b class="agent-name"></b><span class="agent-role"></span></span><span class="agent-status"><i></i><span></span></span></div><div class="agent-task"></div><div class="agent-bottom"><div class="seat-progress"><i></i></div><span class="mono"></span></div>';
    button.querySelector('.agent-name').textContent=a.id;button.querySelector('.agent-role').textContent=a.role;
    button.addEventListener('click',()=>{selected=a.id;ring.setSelected(a.id);$('agent-dialog').showModal();render()});
    $('agent-list').append(button);
  }
}
function makeEvent(e){
  const a=state.agents.find(a=>a.id===e.agent);const el=document.createElement('div');el.className='event';el.style.setProperty('--agent-color',a?.color||'#b1efd2');
  el.innerHTML='<div class="event-head"><i></i><b></b><time></time></div><p></p>';
  el.querySelector('b').textContent=e.agent;el.querySelector('time').textContent=new Date(e.at).toLocaleTimeString('zh-CN',{hour12:false});el.querySelector('p').textContent=e.message;return el;
}
function renderFeed(){
  const filter=$('event-filter').value,key=`${state.mode}:${state.seq}:${filter}`;if(key===feedKey)return;feedKey=key;
  const events=state.events.filter(e=>filter==='all'||e.type===filter).slice(-45).reverse();
  $('event-list').replaceChildren(...events.map(makeEvent));
  if(!events.length){const empty=document.createElement('div');empty.className='empty-state';empty.innerHTML=filter==='all'?'尚无外部事件<small>接入 Agent 后，真实状态将在这里出现</small>':'暂无此类事件<small>更换筛选条件，查看其他协作信号</small>';$('event-list').append(empty)}
}
function renderDetail(){
  if(!selected)return;const a=state.agents.find(a=>a.id===selected),box=$('agent-detail');box.style.setProperty('--agent-color',a.color);
  if(box.dataset.agent!==a.id){box.dataset.agent=a.id;box.innerHTML='<div class="detail-identity"><div class="detail-icon">✳</div><div><h2></h2><p></p></div></div><p class="detail-description"></p><div class="detail-stats"><div><span>状态</span><strong class="detail-status"></strong></div><div><span>进度</span><strong class="detail-progress"></strong></div><div><span class="detail-token-label"></span><strong class="detail-tokens"></strong></div></div><div class="detail-task"></div><div class="detail-events"></div>';box.querySelector('h2').textContent=a.id;box.querySelector('.detail-identity p').textContent=a.role;box.querySelector('.detail-description').textContent=a.description}
  box.querySelector('.detail-status').textContent=statusLabels[a.status];box.querySelector('.detail-progress').textContent=`${a.progress}%`;box.querySelector('.detail-tokens').textContent=a.tokens.toLocaleString();box.querySelector('.detail-token-label').textContent=state.mode==='demo'?'模拟 Token':'上报 Token';box.querySelector('.detail-task').textContent=`当前工作 · ${a.task}`;
  const events=state.events.filter(e=>e.agent===a.id).slice(-4).reverse();box.querySelector('.detail-events').replaceChildren(...events.map(makeEvent));
  if(!events.length)box.querySelector('.detail-events').textContent='等待这个席位的首条事件。';
}
function render(){
  if(!state)return;const demo=state.mode==='demo',m=state.metrics;buildAgents();
  for(const a of state.agents){const b=document.querySelector(`[data-agent="${a.id}"]`);b.classList.toggle('selected',selected===a.id);b.querySelector('.agent-status').className=`agent-status ${a.status}`;b.querySelector('.agent-status span').textContent=statusLabels[a.status];b.querySelector('.agent-task').textContent=a.status==='idle'?'等待任务分配':a.task;b.querySelector('.seat-progress i').style.width=`${a.progress}%`;b.querySelector('.agent-bottom>span').textContent=`${a.progress}%`}
  text('mission-title',state.title);$('mission-title').title=state.title;
  text('mission-state',demo?(state.paused?'演示已暂停':m.completed===8?'演示完成': '执行中 · 演示'):(m.active?'接收外部事件':state.events.length?'外部事件已接收':'等待外部事件'));
  text('elapsed',demo?formatTime(state.elapsed):'LIVE');text('mission-percent',`${m.progress}%`);$('mission-progress-bar').style.width=`${m.progress}%`;text('completed-label',`${m.completed} / 8 席位完成`);text('scenario-label',demo?scenarioLabels[state.scenario]:'本地事件接入');
  $('mode-tag').classList.toggle('live',!demo);$('mode-tag').innerHTML=demo?'<span class="status-dot"></span>演示模式 <span>· 未连接模型</span>':'<span class="status-dot"></span>外部事件模式 <span>· 仅观察上报</span>';
  $('task-phases').replaceChildren(...state.agents.map((a,i)=>{const p=document.createElement('span');p.className=`phase ${a.status}`;p.textContent=pad(i+1);p.title=`${a.id} · ${statusLabels[a.status]}`;return p}));
  text('pause-demo',state.paused?'▷ 继续演示':m.completed===8?'↻ 重播演示':'Ⅱ 暂停演示');$('pause-demo').disabled=!demo||!online;$('speed').disabled=!demo||!online;$('speed').value=String(state.speed);
  text('event-count',pad(state.events.length));text('feed-origin',demo?'DEMO':'EXTERNAL');text('core-count',pad(m.active));text('core-status',demo?(state.paused?'协作已暂停':m.completed===8?'协作已完成':'协作进行中'):(m.active?'外部席位运行中':'等待外部信号'));text('sync-label',demo?'DEMO STREAM':'EVENT BRIDGE');text('orbit-caption',selected?`${selected} · ${state.agents.find(a=>a.id===selected).role}`:'八个席位 · 一个协作网络');
  text('metric-active',pad(m.active));text('metric-handoffs',pad(m.handoffs));text('metric-tokens',m.tokens.toLocaleString());text('metric-done',pad(m.completed));$('tokens-label').innerHTML=demo?'模拟 Token <small>DEMO TOKENS</small>':'上报 Token <small>REPORTED TOKENS</small>';
  const trend=Array.from({length:12},(_,i)=>{const end=Math.floor((i+1)/12*state.events.length),count=state.events.slice(0,end).filter(e=>e.type==='handoff').length;return `${(i*105/11).toFixed(1)},${(25-count/Math.max(1,m.handoffs)*20).toFixed(1)}`});document.querySelector('.sparkline polyline').setAttribute('points',trend.join(' '));
  text('composer-note',demo?'从一个目标，到八个席位的共同响应':'当前接收外部事件；启动演示将清空外部状态');
  text('integration-status',demo?'当前：演示模式，尚未连接真实 Agent。':`当前：外部模式，已接收 ${state.events.length} 条上报。`);
  renderFeed();if($('agent-dialog').open)renderDetail();ring.setState(state);
}
async function mutate(path,body,message){try{state=await request(path,body);setOnline(true);render();if(message)notify(message);return true}catch(e){notify(e.message,true);return false}}
async function poll(){try{state=await request('/api/state');setOnline(true);render()}catch{setOnline(false)}finally{setTimeout(poll,1000)}}

$('mission-form').addEventListener('submit',async e=>{e.preventDefault();const title=$('mission-input').value.trim();if(!title){$('mission-input').setCustomValidity('请输入一个目标');$('mission-input').reportValidity();return}busy=true;$('launch-button').disabled=true;try{await mutate('/api/mission',{title,scenario:$('scenario').value},'协作演示已启动 · 不调用真实模型')}finally{busy=false;$('launch-button').disabled=!online}});
$('mission-input').addEventListener('input',()=>$('mission-input').setCustomValidity(''));
$('pause-demo').addEventListener('click',()=>state&&mutate(state.metrics.completed===8?'/api/mission':'/api/control',state.metrics.completed===8?{title:state.title,scenario:state.scenario}:{paused:!state.paused}));
$('speed').addEventListener('change',e=>mutate('/api/control',{speed:Number(e.target.value)}));
$('event-filter').addEventListener('change',renderFeed);
for(const b of document.querySelectorAll('[data-view]'))b.addEventListener('click',()=>{ring.setView(b.dataset.view);for(const other of document.querySelectorAll('[data-view]')){other.classList.toggle('active',other===b);other.setAttribute('aria-pressed',String(other===b))}});
function zoom(amount){text('zoom-value',`${Math.round(ring.setZoom(ring.zoom+amount)*100)}%`)}
$('zoom-in').addEventListener('click',()=>zoom(.1));$('zoom-out').addEventListener('click',()=>zoom(-.1));
$('motion-toggle').addEventListener('click',()=>{const paused=ring.toggleMotion();text('motion-toggle',paused?'▷':'Ⅱ');$('motion-toggle').setAttribute('aria-label',paused?'恢复视觉动效':'暂停视觉动效');$('motion-toggle').title=paused?'恢复视觉动效':'暂停视觉动效'});
$('fullscreen').addEventListener('click',async()=>{try{if(document.fullscreenElement)await document.exitFullscreen();else await document.documentElement.requestFullscreen()}catch{notify('当前窗口不支持全屏，请使用浏览器全屏菜单',true)}});
for(const b of document.querySelectorAll('[data-close]'))b.addEventListener('click',()=>$(b.dataset.close).close());
for(const dialog of document.querySelectorAll('dialog'))dialog.addEventListener('click',e=>{const r=dialog.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)dialog.close()});
$('agent-dialog').addEventListener('close',()=>{selected=null;ring.setSelected(null);render()});
$('integration-open').addEventListener('click',()=>{$('curl-example').textContent=`curl ${location.origin}/api/ingest \\\n  -H 'Content-Type: application/json' \\\n  -d '{"agent":"CODEX","type":"started",\n       "task":"本地适配器联调",\n       "message":"测试事件：不代表模型调用"}'`;$('integration-dialog').showModal()});
$('live-mode').addEventListener('click',()=>mutate('/api/control',{mode:'live'},'已切换外部模式，等待本机 Agent 上报'));
$('demo-mode').addEventListener('click',()=>mutate('/api/control',{mode:'demo'},'已返回演示模式'));
$('export-button').addEventListener('click',async()=>{try{const snapshot=await request('/api/export');const url=URL.createObjectURL(new Blob([JSON.stringify(snapshot,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download=`neural-star-ring-${snapshot.mode}-${Date.now()}.json`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);notify('状态快照已导出，包含数据来源标记')}catch(e){notify(`导出失败：${e.message}`,true)}});
setInterval(()=>text('clock',new Date().toLocaleString('zh-CN',{hour12:false}).replaceAll('/','.')),1000);
poll();
