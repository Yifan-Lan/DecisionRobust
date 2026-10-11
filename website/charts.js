/* Dependency-free charts. All values come from the published candidate-pair metrics. */
'use strict';
window.DecisionCharts = (() => {
  const colors=['#315cda','#dc513f','#8a4cba','#08808d','#bb7816','#d14789','#4b668f','#6153dd','#896342','#44748a'];
  const e = s => String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const percent = v => `${(v*100).toFixed(1)}%`;
  const eligible = (r,complete) => r && r.denominator>0 && Number.isFinite(r.asr) && (!complete||r.valid_pairs===r.candidates);
  const ranks = rows => new Map(rows.map(r=>[r.model,1+rows.filter(o=>o.asr<r.asr).length]));
  const text=(x,y,value,attrs='')=>`<text x="${x}" y="${y}" ${attrs}>${e(value)}</text>`;
  const shortNames=['Text adversarial','Text injection','Image perturbation','Image overlay','Image instruction'];
  function tooltip(r,rank,suite){return `${r.model_name}\n${suite}\nASR ${percent(r.asr)} · rank ${rank}\n${r.successes} / ${r.denominator} clean-correct pairs\nClean accuracy ${percent(r.clean_accuracy_on_valid_pairs)}\nValid coverage ${r.valid_pairs} / ${r.candidates}${r.used_for_selection?'\n† Used in selecting this suite':''}`;}
  function mark(r,rank,suite,shape){const tip=tooltip(r,rank,suite);return `<g class="chart-mark" tabindex="0" role="img" aria-label="${e(tip)}" data-model="${e(r.model)}" data-config="${e(r.config)}" data-asr="${r.asr}" data-rank="${rank}" data-tip="${e(tip)}"><title>${e(tip)}</title>${shape}</g>`;}
  function svg(body,height,title,desc,width=1000){return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${width} ${height}" role="img" aria-labelledby="plot-title plot-desc" style="font-family:system-ui,sans-serif;font-size:12px;fill:#35435d;background:white;min-width:${width>1000?width:680}px"><title id="plot-title">${e(title)}</title><desc id="plot-desc">${e(desc)}</desc>${body}</svg>`;}
  function render({data,config,mode,measure,limit,complete,selected,search,onlySelected}){
    const configs=Object.keys(data.suites), pools=Object.fromEntries(configs.map(c=>[c,data.results[c].filter(r=>eligible(r,complete))]));
    const rankMaps=Object.fromEntries(configs.map(c=>[c,ranks(pools[c])]));
    const matches=r=>r.model_name.toLowerCase().includes(search.toLowerCase())&&(!selected.size? !onlySelected : selected.has(r.model));
    const anchor=pools[config].filter(matches).sort((a,b)=>a.asr-b.asr||a.model_name.localeCompare(b.model_name));
    let body='',legend='',description='',title='',height=0, count=0,plotWidth=1000;
    const titleName=data.suites[config][0];
    if(mode==='bars'){
      const rows=anchor.slice(0,limit==='all'?Infinity:Number(limit));count=rows.length;
      title=`${titleName} · ASR ranking`;
      description=`${rows.length} of ${anchor.length} eligible ${selected.size?'selected ':''}models shown, ordered by ASR. ${complete?'Full coverage required.':'Partial coverage included.'} Hover or focus a bar for accuracy, coverage, and denominator.`;
      if(rows.length){
        height=560;plotWidth=Math.max(1000,rows.length*85+200);
        const left=165,right=plotWidth-40,top=44,bottom=320,step=(right-left)/rows.length,barWidth=Math.min(52,step*.65);
        for(let v=0;v<=100;v+=20){const y=bottom-(bottom-top)*v/100;body+=`<path d="M${left} ${y}H${right}" stroke="#e6ebf3"/>`+text(left-16,y+4,`${v}%`,'text-anchor="end" fill="#718099" font-size="11"');}
        body+=text(left,18,'ASR · LOWER IS BETTER','fill="#718099" font-size="10" letter-spacing="1"');
        body+=text((left+right)/2,540,'MODEL / RANK','text-anchor="middle" fill="#718099" font-size="10" letter-spacing="1"');
        rows.forEach((r,i)=>{const x=left+step*(i+.5),rank=rankMaps[config].get(r.model),partial=r.valid_pairs<r.candidates,barHeight=r.asr*(bottom-top),y=bottom-barHeight;
          body+=text(x,342,`#${rank}`,'text-anchor="middle" fill="#7b88a1" font-size="10"');
          body+=text(x+3,363,r.model_name,`font-size="11" text-anchor="end" transform="rotate(-45 ${x+3} 363)"`);
          body+=mark(r,rank,titleName,`<rect x="${x-step/2}" y="${top}" width="${step}" height="${bottom-top}" fill="transparent"/><rect class="focus-ring" x="${x-barWidth/2}" y="${y}" width="${barWidth}" height="${barHeight}" rx="2" fill="${i===0?'#142b62':'#5676d6'}"${partial?' fill-opacity=".55"':''}/>${r.asr===0?`<path d="M${x-barWidth/2} ${bottom}h${barWidth}" stroke="#315cda" stroke-width="2"/>`:''}${text(x,y-10,`${percent(r.asr)}${r.used_for_selection?' †':''}${partial?' ○':''}`,'text-anchor="middle" font-size="11" font-weight="600" fill="#203d87"')}`);
        });
      }
    }else{
      // With no manual selection, use the six best ASRs on the reference dataset.
      // Explicitly selected models may have no measurement on that reference dataset.
      const ids=selected.size?[...selected].filter(id=>data.models[id]?.toLowerCase().includes(search.toLowerCase())):anchor.slice(0,6).map(r=>r.model);
      const visible=ids.filter(id=>configs.some(c=>pools[c].some(r=>r.model===id)));count=visible.length;
      title=measure==='rank'?'Rank across datasets':'ASR across datasets';
      description=selected.size?`${visible.length} selected models with eligible results. Use Choose models to change the comparison.`:`Default comparison: up to six lowest-ASR models on ${titleName}. Use Choose models to choose your own comparison.`;
      description+=' Dataset categories are not a time series; lines connect adjacent available results only.';
      if(visible.length){
        height=400;const left=70,right=910,top=36,bottom=318;
        const maxRank=Math.max(2,...configs.map(c=>pools[c].length));
        const x=i=>left+i*(right-left)/4;
        const y=r=>measure==='rank'?top+(r-1)/(maxRank-1)*(bottom-top):bottom-r*(bottom-top);
        const ticks=measure==='rank'?[...new Set([1,...Array.from({length:Math.floor(maxRank/5)},(_,i)=>(i+1)*5),maxRank])]:[0,.2,.4,.6,.8,1];
        for(const tick of ticks)body+=`<path d="M${left} ${y(tick)}H${right}" stroke="#e4eaf3"/>`+text(left-15,y(tick)+4,measure==='rank'?`#${tick}`:percent(tick),'text-anchor="end" fill="#718099" font-size="11"');
        body+=text(left,16,measure==='rank'?'RANK · 1 IS BEST':'ASR · LOWER IS BETTER','fill="#66738b" font-size="10" letter-spacing="1"');
        configs.forEach((c,i)=>{body+=`<path d="M${x(i)} ${top}V${bottom}" stroke="#eef1f7"/>`+text(x(i),345,shortNames[i],'text-anchor="middle" font-size="11"');body+=text(x(i),364,`${pools[c].length} eligible models`,'text-anchor="middle" font-size="9" fill="#78869d"');});
        // Draw connections first so every marker remains above every line.
        const series=visible.map((id,i)=>({id,color:colors[i%colors.length],dash:i>=colors.length?'5 4':null,points:configs.map((c,k)=>{const r=pools[c].find(v=>v.model===id);return r?{r,rank:rankMaps[c].get(id),x:x(k),y:y(measure==='rank'?rankMaps[c].get(id):r.asr),c}:null;})}));
        for(const line of series){for(let i=1;i<line.points.length;i++){const a=line.points[i-1],b=line.points[i];if(a&&b)body+=`<path d="M${a.x} ${a.y}L${b.x} ${b.y}" stroke="${line.color}" stroke-width="2" stroke-opacity=".8" fill="none"${line.dash?` stroke-dasharray="${line.dash}"`:''}/>`;}}
        for(const line of series){for(const p of line.points){if(!p)continue;const partial=p.r.valid_pairs<p.r.candidates;body+=mark(p.r,p.rank,data.suites[p.c][0],`<circle class="focus-ring" cx="${p.x}" cy="${p.y}" r="5" fill="${partial?'white':line.color}" stroke="${line.color}" stroke-width="2"/>${p.r.used_for_selection?text(p.x+8,p.y-7,'†',`fill="${line.color}" font-size="11"`):''}`);}legend+=`<span class="chart-chip"><i style="background:${line.color}"></i>${e(data.models[line.id])}</span>`;}
      }
    }
    const empty='No eligible results match these filters. Change the dataset, model selection, or coverage filter.';
    document.getElementById('chart-title').textContent=title;
    document.getElementById('chart-description').textContent=description;
    document.getElementById('chart').innerHTML=count?svg(body,height,title,description,plotWidth):`<p class="chart-empty">${empty}</p>`;
    document.getElementById('chart-legend').innerHTML=legend;
    document.getElementById('download-chart').disabled=!count;
    bindTooltips();
  }
  function bindTooltips(){
    const host=document.getElementById('chart'),tip=document.getElementById('chart-tooltip');tip.hidden=true;
    function hide(){tip.hidden=true;}
    function show(target,x,y){if(!target)return;tip.textContent=target.dataset.tip;tip.hidden=false;const w=tip.offsetWidth,h=tip.offsetHeight;tip.style.left=`${Math.max(8,Math.min(x+14,innerWidth-w-12))}px`;tip.style.top=`${Math.max(8,Math.min(y+14,innerHeight-h-12))}px`;}
    host.onpointermove=event=>{const target=event.target.closest('.chart-mark');if(target)show(target,event.clientX,event.clientY);else if(!host.contains(document.activeElement))hide();};
    host.onpointerleave=()=>{if(!host.contains(document.activeElement))hide();};
    host.querySelectorAll('.chart-mark').forEach(target=>{target.addEventListener('focus',()=>{const box=target.getBoundingClientRect();show(target,box.x+box.width/2,box.y+box.height);});target.addEventListener('blur',hide);});
    host.onkeydown=event=>{if(event.key==='Escape')hide();};
  }
  function download(){
    const chart=document.querySelector('#chart svg');if(!chart)return;
    const blob=new Blob([new XMLSerializer().serializeToString(chart)],{type:'image/svg+xml;charset=utf-8'});
    const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='decisionrobust-'+document.getElementById('chart-title').textContent.toLowerCase().replace(/[^a-z0-9]+/g,'-')+'.svg';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  }
  return {render,download};
})();
