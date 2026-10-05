const assert=require('node:assert/strict');
const {test}=require('node:test');
const fs=require('node:fs');
const vm=require('node:vm');
const source=fs.readFileSync(require('node:path').join(__dirname,'../web/app.js'),'utf8').split("applyTheme(localStorage.getItem")[0];
function harness(){
  const nodes=new Map(),timers=new Map();let next=0;
  const node=()=>({children:[],attrs:{},setAttribute(k,v){this.attrs[k]=v;},append(...x){this.children.push(...x);},replaceChildren(...x){this.children=x;}});
  const context=vm.createContext({console,AbortSignal,confirm:()=>true,document:{getElementById(id){if(!nodes.has(id))nodes.set(id,node());return nodes.get(id);},createElement:node,createElementNS:node},setTimeout(fn){timers.set(++next,fn);return next;},clearTimeout(id){timers.delete(id);},cancelAnimationFrame(){}});
  vm.runInContext(source,context);
  vm.runInContext("load=async()=>{};toast=()=>{};pause=()=>{};state.capture={id:'current',session:{id:'current',status:'running',records:0}};",context);
  return {context,nodes,timers,run:s=>vm.runInContext(s,context)};
}
test('repeated polling retains ID and redraws a growing live trace',async()=>{
  const h=harness();let calls=0;const urls=[];
  h.context.fetch=async url=>{urls.push(url);calls++;return {ok:true,json:async()=>({session:{id:'current',status:'running',records:calls+1},samples:Array.from({length:calls+1},(_,i)=>({valid:true,seconds:i,smooth:i*.01}))})};};
  await h.run('pollCapture()');const first=h.nodes.get('live-signal-chart').children.at(-1).attrs.d;
  await h.run('pollCapture()');assert.deepEqual(urls,['/api/captures/current/live?after=-1','/api/captures/current/live?after=-1']);
  assert.notEqual(h.nodes.get('live-signal-chart').children.at(-1).attrs.d,first);assert.equal(h.timers.size,1);
});
test('overlapping polls share one request; stale response cannot resurrect deleted capture',async()=>{
  const h=harness();let resolve,calls=0;
  h.context.fetch=()=>{calls++;return new Promise(r=>resolve=r);};
  const a=h.run('pollCapture()'),b=h.run('pollCapture()');assert.equal(calls,1);
  h.run('state.capture=null');resolve({ok:true,json:async()=>({session:{id:'current',status:'running'}})});
  await Promise.all([a,b]);assert.equal(h.run('state.capture'),null);assert.equal(h.timers.size,0);
});
test('current and library deletion controls stay independent, paused deletion needs no library selection',()=>{
  const h=harness();h.run("state.capture.paused=true;renderCapture()");
  assert.equal(h.nodes.get('capture-delete').disabled,false);assert.equal(h.nodes.get('session-delete').disabled,true);
  h.run("state.capture=null;state.session={id:'saved',status:'captured'};renderCapture()");
  assert.equal(h.nodes.get('capture-delete').disabled,true);assert.equal(h.nodes.get('session-delete').disabled,false);
});
test('delete targets its supplied ID and clears replay when the selected session is removed',async()=>{
  const h=harness(),urls=[];h.context.fetch=async url=>{urls.push(url);return {ok:true,json:async()=>({deleted:'current'})};};
  h.run("state.session={id:'library',status:'captured'}");await h.run("deleteSession(state.capture.id)");
  assert.deepEqual(urls,['/api/sessions/current/delete']);assert.equal(h.run('state.session.id'),'library');assert.equal(h.run('state.capture'),null);
  await h.run("deleteSession(state.session.id)");assert.equal(h.run('state.session'),null);assert.equal(h.nodes.get('replay-message').textContent,'No session selected.');
});
test('live graph breaks across invalid samples and gaps',()=>{
  const h=harness();h.run('renderLive([{valid:true,seconds:0,smooth:.01},{valid:false},{valid:true,seconds:2,smooth:.02},{valid:true,seconds:3,smooth:.03,gap:true}])');
  const d=h.nodes.get('live-signal-chart').children.at(-1).attrs.d;assert.equal((d.match(/M/g)||[]).length,3);assert.equal(d.includes('L'),false);
});

test('live cursor appends deltas and honors server window resets',async()=>{
  const h=harness(),urls=[];let n=0;
  h.context.fetch=async url=>{urls.push(url);n++;return {ok:true,json:async()=>({session:{id:'current',status:'running',records:n},reset:n!==2,next_seq:n===3?999:n-1,samples:[{seq:n===3?999:n-1,valid:true,seconds:n,smooth:.01}]})};};
  await h.run('pollCapture()');await h.run('pollCapture()');
  assert.equal(h.run('state.capture.samples.length'),2);
  assert.equal(urls[1],'/api/captures/current/live?after=0');
  await h.run('pollCapture()');assert.equal(h.run('state.capture.samples.length'),1);assert.equal(h.run('state.capture.next_seq'),999);
});

test('Swagger deep links stay inside the API workspace across direct loads',()=>{
  const h=harness();
  assert.equal(h.run("pageFromHash('#api-docs').name"),'api-docs');
  assert.equal(h.run("pageFromHash('#/Sessions%20and%20replay/get_api_sessions').name"),'api-docs');
  assert.equal(h.run("pageFromHash('#/Sessions%20and%20replay/get_api_sessions').preserve"),true);
  assert.equal(h.run("pageFromHash('#sessions').name"),'sessions');
});
