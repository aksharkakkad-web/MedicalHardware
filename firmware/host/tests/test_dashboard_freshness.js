// Execute the real inline dashboard script with browser APIs stubbed.
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const assert=require('node:assert/strict');
const html=fs.readFileSync(process.argv[2]||path.join(__dirname,'../dashboard/index.html'),'utf8');
const script=html.match(/<script>([\s\S]*?)<\/script>/)[1];
let clock=10000;
const els=new Map();
const ctx=new Proxy({}, {get:(t,k)=>k==='createImageData'?()=>({data:new Uint8ClampedArray(32*24*4)}):k==='createLinearGradient'||k==='createRadialGradient'?()=>({addColorStop(){}}):()=>{}});
function el(id){if(!els.has(id))els.set(id,{innerHTML:'',textContent:'',className:'',classList:{add(){},toggle(){}},style:{},width:512,height:384,getContext:()=>ctx,getBoundingClientRect:()=>({width:512,height:384}),addEventListener(){}});return els.get(id);}
const timers=[];const streams=[];
const sandbox={console,Math,Date:{now:()=>clock},devicePixelRatio:1,
 document:{getElementById:el,createElement:()=>el("canvas"),querySelectorAll:()=>[],documentElement:el('root')},
 getComputedStyle:()=>({getPropertyValue:()=> '#000'}),
 setInterval:f=>timers.push(f),EventSource:function(){streams.push(this)},
 window:{devicePixelRatio:1,addEventListener(){}},requestAnimationFrame:()=>{},fetch:()=>Promise.resolve({json:()=>Promise.resolve({})})};
vm.runInNewContext(script,sandbox);
for(const id of ['vHr','vResp','vDist','vPres']) el(id).innerHTML='72';
clock+=5000;for(const tick of timers)tick();
assert.match(el('vHr').innerHTML,/not available/,'Disconnect must clear numeric heart rate');
assert.match(el('vResp').innerHTML,/not available/,'Disconnect must clear numeric breathing');
assert.match(el('strip').innerHTML,/offline/,'Disconnect must clear live stream-rate indicators');
console.log('PASS: actual dashboard script clears vitals after SSE silence');
