// Original Canvas 2D renderer. Graph positions are illustrative, not model internals.
export class NeuralRing {
  constructor(canvas) {
    this.canvas=canvas; this.ctx=canvas.getContext('2d'); this.view='orbit'; this.zoom=1;
    this.rotation=.14; this.time=0; this.selected=null; this.state=null; this.paused=false;
    this.reduced=matchMedia('(prefers-reduced-motion: reduce)');
    this.reduced.addEventListener('change',()=>this.draw());
    this.nodes=[]; this.edges=[]; this.clusters=[]; this.last=0;
    this.generate();
    new ResizeObserver(()=>this.resize()).observe(canvas.parentElement);
    let dragging=false, lastX=0;
    canvas.addEventListener('pointerdown',e=>{dragging=true;lastX=e.clientX;canvas.setPointerCapture(e.pointerId)});
    canvas.addEventListener('pointermove',e=>{if(dragging){this.rotation+=(e.clientX-lastX)*.004;lastX=e.clientX;this.draw()}});
    canvas.addEventListener('pointerup',()=>dragging=false);
    canvas.addEventListener('pointercancel',()=>dragging=false);
    document.addEventListener('visibilitychange',()=>{this.last=0});
    requestAnimationFrame(t=>this.frame(t));
  }
  generate(){
    let seed=91;
    const rand=()=>{seed=(seed*16807)%2147483647;return (seed-1)/2147483646};
    const normal=()=>Math.sqrt(-2*Math.log(rand()||.01))*Math.cos(6.283*rand());
    for(let g=0;g<8;g++){
      const angle=g*Math.PI/4-Math.PI/2, cx=Math.cos(angle)*.53,cy=Math.sin(angle)*.53;
      this.clusters.push({x:cx,y:cy,z:0,g});
      const start=this.nodes.length;
      for(let i=0;i<145;i++){
        const reach=i<36 ? rand()*.8 : 0;
        this.nodes.push({x:cx*(1-reach)+normal()*.115,y:cy*(1-reach)+normal()*.115,z:normal()*.11,g,size:rand(),phase:rand()*6.28});
      }
      for(let i=start;i<this.nodes.length;i++){
        const a=this.nodes[i];const near=[];
        for(let j=start;j<i;j++){
          const b=this.nodes[j],d=Math.hypot(a.x-b.x,a.y-b.y,a.z-b.z);
          if(d<.21)near.push([j,d]);
        }
        near.sort((a,b)=>a[1]-b[1]);
        for(const [j] of near.slice(0,3))this.edges.push([i,j,g]);
      }
    }
    const start=this.nodes.length;
    for(let i=0;i<160;i++){
      this.nodes.push({x:normal()*.13,y:normal()*.13,z:normal()*.13,g:8,size:rand(),phase:rand()*6.28});
      if(i)for(let k=0;k<3;k++)this.edges.push([start+i,start+Math.floor(rand()*i),8]);
    }
    for(let g=0;g<8;g++)for(let k=0;k<8;k++)this.edges.push([g*145+k,start+Math.floor(rand()*160),g]);
    this.stars=Array.from({length:110},()=>[rand(),rand(),rand()]);
  }
  resize(){const box=this.canvas.getBoundingClientRect();this.w=box.width;this.h=box.height;const dpr=Math.min(devicePixelRatio||1,1.5);this.canvas.width=Math.round(this.w*dpr);this.canvas.height=Math.round(this.h*dpr);this.ctx?.setTransform(dpr,0,0,dpr,0,0);this.draw()}
  setState(state){this.state=state;this.draw()}
  setView(view){this.view=view;this.draw()}
  setZoom(value){this.zoom=Math.min(1.25,Math.max(.7,value));this.draw();return this.zoom}
  setSelected(id){this.selected=id;this.draw()}
  toggleMotion(){this.paused=!this.paused;this.draw();return this.paused}
  frame(t){
    if(!document.hidden && !this.paused && !this.reduced.matches && t-this.last>32){
      const delta=this.last ? Math.min(60,t-this.last) : 0;this.last=t;
      if(!this.state?.paused){this.time+=delta/1000;this.rotation+=delta*.000012}
      this.draw();
    }
    requestAnimationFrame(next=>this.frame(next));
  }
  draw(){
    const c=this.ctx,w=this.w,h=this.h;if(!c||!w||!h)return;
    c.clearRect(0,0,w,h);
    const r=Math.min(w*.405,h*.432)*this.zoom,cx=w/2,cy=h*.48;
    const tilt=this.view==='top'?0:this.view==='side'?1.0:.27;
    const rot=this.rotation, cr=Math.cos(rot),sr=Math.sin(rot),ct=Math.cos(tilt),st=Math.sin(tilt);
    const project=(p)=>{const x=p.x*cr-p.y*sr,y=p.x*sr+p.y*cr,z=p.z||0;return {x:cx+x*r,y:cy+(y*ct-z*st)*r,z:y*st+z*ct}};
    const colors=this.state?.agents.map(a=>a.color)||['#78f4d0','#e9bc71','#78b5ff','#b6a0ff','#e6ec98','#f39aba','#71d9ec','#c1cedd'];
    const active=this.state?.agents.map(a=>a.status==='working')||[];
    const selectedIndex=this.state?.agents.findIndex(a=>a.id===this.selected)??-1;
    c.fillStyle='#7aada4';
    for(const [x,y,b]of this.stars){c.globalAlpha=.06+b*.15;c.fillRect(x*w,y*h,b>.92?1.5:.7,b>.92?1.5:.7)}
    c.globalAlpha=1;
    const glow=c.createRadialGradient(cx,cy,0,cx,cy,r);glow.addColorStop(0,'#d1fff00b');glow.addColorStop(.5,'#56c3a505');glow.addColorStop(1,'#00000000');c.fillStyle=glow;c.fillRect(0,0,w,h);
    // Fine plotting guides frame the data without a full-page grid.
    c.strokeStyle='#66877f15';c.lineWidth=.6;
    for(let i=-3;i<=3;i++){const p=i*r*.27;c.beginPath();c.moveTo(cx-r,cy+p);c.lineTo(cx+r,cy+p);c.stroke();c.beginPath();c.moveTo(cx+p,cy-r);c.lineTo(cx+p,cy+r);c.stroke()}
    const ellipse=(radius,stroke,width=1)=>{c.beginPath();c.ellipse(cx,cy,r*radius,r*radius*ct,rot*.02,0,Math.PI*2);c.strokeStyle=stroke;c.lineWidth=width;c.stroke()};
    ellipse(.965,'#7eb3a028');ellipse(1.028,'#86d6b13a',.7);ellipse(1.09,'#5d8b7d32',.5);ellipse(.87,'#588c7d28',.5);
    // Instrument ring, grouped by the eight seats.
    for(let i=0;i<240;i++){
      const angle=i/240*6.283-Math.PI/2;
      const group=Math.floor(i/30),major=i%5===0, gap=i%30>27;
      if(gap)continue;
      const a=project({x:Math.cos(angle)*.988,y:Math.sin(angle)*.988});
      const b=project({x:Math.cos(angle)*(major?1.045:1.02),y:Math.sin(angle)*(major?1.045:1.02)});
      c.strokeStyle=major?'#ccebd6b0':'#8aa99a7a';c.lineWidth=major?1.6:.65;
      if(group===selectedIndex)c.strokeStyle=colors[group];
      c.beginPath();c.moveTo(a.x,a.y);c.lineTo(b.x,b.y);c.stroke();
    }
    for(let g=0;g<8;g++){
      c.beginPath();const from=g*Math.PI/4-Math.PI/2+.045,to=from+Math.PI/4-.09;
      for(let k=0;k<=30;k++){const a=from+(to-from)*k/30,p=project({x:Math.cos(a)*.93,y:Math.sin(a)*.93});if(k)c.lineTo(p.x,p.y);else c.moveTo(p.x,p.y)}
      c.strokeStyle=colors[g]+(g===selectedIndex?'dd':active[g]?'80':'35');c.lineWidth=g===selectedIndex?2:1;c.stroke();
      const mid=(from+to)/2,label=project({x:Math.cos(mid)*1.145,y:Math.sin(mid)*1.145});
      c.font=`${w<450?6:7}px ui-monospace,monospace`;c.fillStyle=colors[g]+'a0';c.textAlign='center';c.textBaseline='middle';
      c.fillText(this.state?.agents[g].id||'',label.x,label.y);
    }
    const points=this.nodes.map(p=>project(p));
    c.lineWidth=.55;
    for(let g=0;g<=8;g++){
      c.beginPath();
      for(const [a,b,group]of this.edges){if(group!==g)continue;const p=points[a],q=points[b];c.moveTo(p.x,p.y);c.lineTo(q.x,q.y)}
      const dim=selectedIndex>=0&&g!==selectedIndex&&g!==8;
      c.strokeStyle=(colors[g]||'#d9eee9')+(dim?'10':g===8?'40':active[g]?'70':'42');c.stroke();
    }
    for(let i=0;i<this.nodes.length;i++){
      const n=this.nodes[i],p=points[i],color=colors[n.g]||'#e2fff1';
      const dim=selectedIndex>=0&&n.g!==selectedIndex&&n.g!==8;
      const flicker=.7+Math.sin(this.time*1.4+n.phase)*.2;
      c.globalAlpha=dim?.18:(.3+n.size*.55)*flicker;c.fillStyle=color;
      c.beginPath();c.arc(p.x,p.y,.4+n.size*(n.g===8?1.55:1.25),0,6.283);c.fill();
      if(n.size>.975&&!dim){const size=7;const halo=c.createRadialGradient(p.x,p.y,0,p.x,p.y,size);halo.addColorStop(0,color+'b0');halo.addColorStop(.2,color+'40');halo.addColorStop(1,color+'00');c.globalAlpha=.6;c.fillStyle=halo;c.fillRect(p.x-size,p.y-size,size*2,size*2)}
    }
    c.globalAlpha=1;
    // Every cluster anchor represents a seat, and pulses follow its work state.
    this.clusters.forEach((n,g)=>{
      const p=project(n),color=colors[g];c.strokeStyle=color+'50';c.lineWidth=.6;c.beginPath();c.arc(p.x,p.y,8,0,6.283);c.stroke();
      c.fillStyle=color;c.beginPath();c.arc(p.x,p.y,2.2,0,6.283);c.fill();
      if(active[g] && !this.paused && !this.reduced.matches && !this.state?.paused){
        const pulse=(this.time*.4+g*.17)%1;
        c.strokeStyle=color+Math.round((1-pulse)*120).toString(16).padStart(2,'0');c.beginPath();c.arc(p.x,p.y,8+pulse*24,0,6.283);c.stroke();
        const t=(this.time*.17+g*.13)%1,x=cx+(p.x-cx)*t,y=cy+(p.y-cy)*t;
        c.fillStyle='#e4fff4';c.beginPath();c.arc(x,y,1.8,0,6.283);c.fill();
      }
      if(g===selectedIndex){c.strokeStyle=color;c.lineWidth=1;c.beginPath();c.arc(p.x,p.y,14,0,6.283);c.stroke()}
    });
    const cross=(x,y)=>{c.strokeStyle='#8fb5a448';c.lineWidth=.7;c.beginPath();c.moveTo(x-4,y);c.lineTo(x+4,y);c.moveTo(x,y-4);c.lineTo(x,y+4);c.stroke()};
    cross(cx-r*1.26,cy);cross(cx+r*1.26,cy);cross(cx,cy-r*1.17);cross(cx,cy+r*1.17);
    c.fillStyle='#819f8f';c.font='6px ui-monospace,monospace';c.textAlign='center';
    c.fillText('00:00',cx,cy-r*1.235);c.fillText('180',cx,cy+r*1.255);
    const out=document.getElementById('angle-value');if(out)out.textContent=((rot*180/Math.PI)%360).toFixed(1).padStart(5,'0');
    const tiltOut=document.getElementById('tilt-value');if(tiltOut)tiltOut.textContent=(tilt*180/Math.PI).toFixed(1).padStart(5,'0');
  }
}
