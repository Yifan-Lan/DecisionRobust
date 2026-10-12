'use strict';
const $ = id => document.getElementById(id);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const pretty = value => typeof value === 'string' ? value : JSON.stringify(value, null, 2);
const pct = value => value == null ? '—' : `${(value * 100).toFixed(1)}%`;
const labels = {sst2:'SST-2',mmlu:'MMLU',aegis2:'Aegis 2.0',bfcl:'BFCL',gui:'GUI',esci:'ESCI',nevir:'NevIR',siim:'Siim',jev_arm:'Jev Arm',jev_fsd:'Jev FSD',image_jevbench:'Image JevBench',imajev_bench:'ImajevBench',promptshield:'PromptShield',scpn:'SCPN',deepwordbug:'DeepWordBug',stresstest:'StressTest',textfooler:'TextFooler',promptattack_s2:'PromptAttack S2',promptattack_s3:'PromptAttack S3',sememe_pso:'SememePSO',noul:'Noul',choice:'Choice',score:'Score'};
const label = value => labels[value] || String(value).replaceAll('_',' ').replace(/\b\w/g, c => c.toUpperCase());
let data, index, suite='overview', sortKey='name', ascending=true, selected=new Set(), filtered=[], currentSample=null, sampleSequence=0;
const params = new URLSearchParams(location.search);
let chartMode=params.get('chart')==='lines'?'lines':'bars';
async function fetchJSON(url) { const response=await fetch(url); if(!response.ok) throw new Error(`${url}: HTTP ${response.status}`); return response.json(); }
function selectOptions(element, values, title, previous='') {
  element.replaceChildren();
  if(title) element.add(new Option(title,''));
  for(const [value,text] of values) element.add(new Option(text,value));
  if([...element.options].some(o=>o.value===previous)) element.value=previous;
}
function saveView(){
 const p=new URLSearchParams(); p.set('suite',suite);
 for(const id of ['example-suite','scenario','source','attack','sample']) if($(id).value)p.set(id,$(id).value);
 if(selected.size)p.set('models',[...selected].join(','));
 p.set('chart',chartMode);p.set('chart-version','2');
 if($('model-search').value)p.set('search',$('model-search').value);
 if($('selected-only').checked)p.set('selected-only','1');
 for(const key of ['chart-suite','chart-limit','chart-measure']) if($(key).value)p.set(key,$(key).value);
 if($('chart-complete').checked)p.set('chart-complete','1');
 history.replaceState(null,'',`${location.pathname}?${p}${location.hash}`);
}
const asrName = config => data.results[config]?.some(r=>r.asr_type==='targeted')?'Target ASR':'Flip ASR';
function metric(model,config){return data.results[config].find(r=>r.model===model);}
function renderTabs(){ $('suite-tabs').innerHTML=['overview',...Object.keys(data.suites)].map(c=>`<button data-suite="${c}" aria-pressed="${suite===c}">${c==='overview'?'All suites':esc(data.suites[c][0])}</button>`).join(''); }
function asrCell(r){
 if(!r)return '<td><span class="muted">—</span><small>Not measured</small></td>';
 const reason=Object.entries(r.excluded_reasons||{}).map(([k,v])=>`${k}: ${v}`).join('; ');
 if(!r.denominator)return `<td title="${esc(reason)}">—<small>${r.valid_pairs?'No clean-correct pairs':'Unsupported / unavailable'}</small></td>`;
 return `<td title="${esc(`${r.asr_type==='targeted'?'Target ASR':'Flip ASR'}: ${r.successes} successes / ${r.denominator} clean-correct pairs; ${r.valid_pairs}/${r.candidates} valid. ${reason}`)}"><span class="asr-number">${pct(r.asr)}</span>${r.used_for_selection?'<sup class="dagger">†</sup>':''}${r.valid_pairs<r.candidates?'<span class="dot" aria-label="Partial coverage"></span>':''}<small>${r.successes} / ${r.denominator}</small><div class="meter"><span style="width:${r.asr*100}%"></span></div></td>`;
}
function renderChart(){
 if(!data||!$('chart-suite').value)return;
 const lines=chartMode==='lines';
 $('chart-picker-label').textContent=`Choose models${selected.size?` · ${selected.size} selected`:' · automatic selection'}`;
 $('chart-models').innerHTML=Object.entries(data.models).sort((a,b)=>a[1].localeCompare(b[1])).map(([id,name])=>`<label><input type="checkbox" data-compare="${esc(id)}" ${selected.has(id)?'checked':''}>${esc(name)}</label>`).join('');
 $('chart-limit-label').hidden=lines;$('chart-measure-label').hidden=!lines;
 document.querySelectorAll('[data-chart]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.chart===chartMode)));
 DecisionCharts.render({data,config:$('chart-suite').value,mode:chartMode,measure:$('chart-measure').value,limit:$('chart-limit').value,complete:$('chart-complete').checked,selected,search:$('model-search').value,onlySelected:$('selected-only').checked});
}
function renderTable(){
 let rows=Object.entries(data.models).filter(([id,name])=>name.toLowerCase().includes($('model-search').value.toLowerCase())&&(!$('selected-only').checked||selected.has(id)));
 const value=([id,name])=>{if(sortKey==='name')return name; const r=metric(id,suite==='overview'?sortKey:suite); return r? (suite==='overview'?r.asr:sortKey==='coverage'?r.valid_pairs/r.candidates:r[sortKey]):null;};
 rows.sort((a,b)=>{const av=value(a),bv=value(b);if(av==null)return bv==null?0:1;if(bv==null)return -1;return(typeof av==='string'?av.localeCompare(bv):av-bv)*(ascending?1:-1);});
 const cols=suite==='overview'?Object.entries(data.suites).map(([id,[name]])=>[id,`${name} · ${asrName(id)}`]):[['asr',`${asrName(suite)} ↓`],['clean_accuracy_on_valid_pairs','Clean accuracy'],['adv_accuracy_on_valid_pairs','Adv. accuracy'],['coverage','Valid coverage']];
 const header=([key,name])=>`<th scope="col" aria-sort="${sortKey===key?(ascending?'ascending':'descending'):'none'}"><button data-sort="${key}">${esc(name)}${sortKey===key?(ascending?' ↑':' ↓'):''}</button></th>`;
 $('results-table').tHead.innerHTML='<tr>'+header(['name','Model'])+cols.map(header).join('')+'</tr>';
 $('results-table').tBodies[0].innerHTML=rows.map(([id,name])=>{const first=`<td><label style="font:inherit;letter-spacing:0"><input type="checkbox" data-model="${esc(id)}" ${selected.has(id)?'checked':''} aria-label="Compare ${esc(name)}">${esc(name)}</label></td>`;
 if(suite==='overview') return '<tr>'+first+cols.map(([c])=>asrCell(metric(id,c))).join('')+'</tr>';
 const r=metric(id,suite);return '<tr>'+first+asrCell(r)+`<td>${pct(r?.clean_accuracy_on_valid_pairs)}</td><td>${pct(r?.adv_accuracy_on_valid_pairs)}</td><td>${r?`${r.valid_pairs} / ${r.candidates}<small>${r.excluded_pairs} excluded</small>`:'—'}</td></tr>`;}).join('') || '<tr><td colspan="6">No matching models. Clear search or selection filters.</td></tr>';
 $('result-count').textContent=`${rows.length} models · ${selected.size} selected`;
 $('table-help').textContent=suite==='overview'?'Injection suites use Target ASR; text adversarial and image perturbation use Flip ASR. Click a column to sort. No pooled rank across suites.':`${asrName(suite)}. ${data.suites[suite][1]} ${data.info.collections[suite].candidates} candidates; ${data.info.collections[suite].original_questions} original questions. Accuracy uses valid candidate pairs.`;
 renderChart();
}
function setSuite(value){suite=value;if(suite!=='overview')$('chart-suite').value=suite;sortKey=suite==='overview'?'name':'asr';ascending=true;renderTabs();renderTable();saveView();}
function updateFilters(level=0, initial=false){
 let rows=index.filter(r=>r.config===$('example-suite').value);
 for(const [i,id] of ['scenario','source','attack'].entries()){
  const old=initial?params.get(id):i>=level?'':$(id).value;
  const values=[...new Set(rows.map(r=>r[id]))].sort();
  selectOptions($(id),values.map(v=>[v,label(v)]),`All ${id==='source'?'datasets':id==='attack'?'methods':'scenarios'}`,old);
  if($(id).value)rows=rows.filter(r=>r[id]===$(id).value);
 }
 filtered=rows;
 selectOptions($('sample'),rows.map(r=>[String(r.id),`#${r.id} · ${label(r.source)} · ${label(r.attack)} · ${label(r.mode)}`]),null,initial?params.get('sample'):'');
 // Prefer a concise sentiment example as the default text landing example.
 if(!initial && level===0 && rows.some(r=>r.source==='sst2'))$('sample').value=String(rows.find(r=>r.source==='sst2').id);
 $('distribution').textContent=`${rows.length} candidates · ${new Set(rows.map(r=>r.original_id)).size} original questions · ${new Set(rows.map(r=>r.scenario)).size} scenarios · ${new Set(rows.map(r=>r.source)).size} source datasets`;
 showSample();
}
function changes(a,b,path='$'){
 if(JSON.stringify(a)===JSON.stringify(b))return [];
 if(a&&b&&typeof a==='object'&&typeof b==='object'&&Array.isArray(a)===Array.isArray(b))return [...new Set([...Object.keys(a),...Object.keys(b)])].flatMap(k=>changes(a[k],b[k],`${path}.${k}`));
 return [{path,a,b}];
}
function highlight(a,b,side){
 a=pretty(a)??'(absent)'; b=pretty(b)??'(absent)';
 let start=0,end=0;while(start<Math.min(a.length,b.length)&&a[start]===b[start])start++;
 while(end<Math.min(a.length,b.length)-start&&a[a.length-1-end]===b[b.length-1-end])end++;
 const text=side==='clean'?a:b, stop=text.length-end;
 return esc(text.slice(0,start))+`<mark class="${side==='clean'?'removed':'added'}">${esc(text.slice(start,stop))}</mark>`+esc(text.slice(stop));
}
async function showSample(){
 const seq=++sampleSequence, id=$('sample').value;
 const offset=filtered.findIndex(r=>String(r.id)===id);$('prev').disabled=offset<=0;$('next').disabled=offset<0||offset>=filtered.length-1;
 if(!id){$('example').textContent='No examples match these filters.';return;}
 $('example').textContent='Loading example…';saveView();
 try{
 const row=await fetchJSON(`data/samples/${encodeURIComponent(id)}.json`);if(seq!==sampleSequence)return;currentSample=row;
 const config=$('example-suite').value;
 const diffs=changes(row.clean,row.adv).filter(d=>!d.path.startsWith('$.images'));
 const imageURL=path=>`https://huggingface.co/datasets/${data.release.dataset}/resolve/${data.release.data_revision}/raw/${config}/${path.split('/').map(encodeURIComponent).join('/')}`;
 const panel=side=>{const images=(row[side].images||[]).map((path,i)=>`<img src="${esc(imageURL(path))}" loading="lazy" alt="${side==='clean'?'Clean':'Attacked'} image ${i+1} for example ${row.id}" data-expand><div class="image-hint">Click image to inspect at full size.</div>`).join('');
 return `<article class="panel ${side==='adv'?'adv':''}"><h3>${side==='clean'?'Original input':'Attacked input'}</h3>${images}<div class="panel-content">${diffs.length?diffs.map(d=>`<div class="path">${esc(d.path)}</div><div class="change">${highlight(d.a,d.b,side)}</div>`).join(''):'<p class="muted">Text fields unchanged. The perturbation is in the image.</p>'}</div><details><summary>Full native ${side} request</summary><pre>${esc(JSON.stringify(row[side],null,2))}</pre></details></article>`;};
 const questions=Object.fromEntries(row.task.question_ids.map(q=>[q,row.clean.questions[q]]));
 const injectionTarget=data.injection_targets?.[`${config}:${row.id}`];
 const targetDisplay=injectionTarget?`<br><strong>Injection target:</strong> ${esc(pretty(injectionTarget.target))}${row.task.mode==='score'?' (native weighted score within ±0.5, and incorrect against GT)':''}`:'';
 $('example').innerHTML=`<div class="badges">${[`Example #${row.id}`,`Original #${row.original_id}`,label(row.source),label(row.scenario),label(row.attack),label(row.task.mode)].map(x=>`<span class="badge">${esc(x)}</span>`).join('')}</div><details class="question-box" open><summary>Question and answer options (clean)</summary><pre>${esc(JSON.stringify(questions,null,2))}</pre></details><div class="pair">${panel('clean')}${panel('adv')}</div><div class="ground-truth"><strong>Ground truth:</strong> ${esc(pretty(row.gt))}${targetDisplay}<br><span class="muted">Scored question IDs: ${esc(row.task.question_ids.join(', '))}. Full requests retain every question.</span></div>`;
 }catch(e){if(seq===sampleSequence)$('example').textContent=`Could not load example: ${e.message}`;}
}
async function main(){
 [data,index]=await Promise.all([fetchJSON('data/leaderboard.json'),fetchJSON('data/index.json')]);
 $('stats').innerHTML=[[Object.keys(data.suites).length,'Curated suites'],[Object.keys(data.models).length,'Evaluated models'],[data.info.candidates.toLocaleString(),'Attack candidates'],[data.info.original_questions,'Original questions']].map(([n,t])=>`<div class="stat"><strong>${n}</strong><span>${t}</span></div>`).join('');
 $('release-version').textContent=`Data v${data.release.version} · Results ${data.release.results_revision.slice(0,7)}`;
 const citation=await fetch('data/CITATION.bib');$('citation').textContent=await citation.text();
 if(params.get('suite')==='overview'||data.suites[params.get('suite')])suite=params.get('suite');
 selected=new Set((params.get('models')||'').split(',').filter(m=>data.models[m]));
 selectOptions($('chart-suite'),Object.entries(data.suites).map(([k,v])=>[k,v[0]]),null,params.get('chart-suite')||(suite!=='overview'?suite:''));
 if(params.get('chart-version')==='2'&&['10','20','all'].includes(params.get('chart-limit')))$('chart-limit').value=params.get('chart-limit');
 if(params.get('chart-measure')==='rank')$('chart-measure').value='rank';
 $('chart-complete').checked=params.get('chart-complete')==='1';
 $('model-search').value=params.get('search')||'';
 $('selected-only').checked=params.get('selected-only')==='1';
 sortKey=suite==='overview'?'name':'asr';renderTabs();renderTable();
 selectOptions($('details-model'),Object.entries(data.models).sort((a,b)=>a[1].localeCompare(b[1])),null);
 const details=()=>{$('details-json').textContent=JSON.stringify(data.model_details[$('details-model').value]||{},null,2);};details();$('details-model').onchange=details;
 selectOptions($('example-suite'),Object.entries(data.suites).map(([k,v])=>[k,v[0]]),null,params.get('example-suite'));
 if(!params.has('sample')){const initial=index.find(r=>r.config===$('example-suite').value&&r.source==='sst2');if(initial)params.set('sample',String(initial.id));}
 updateFilters(0,true);
 $('suite-tabs').onclick=e=>{const b=e.target.closest('[data-suite]');if(b)setSuite(b.dataset.suite);};
 $('results-table').onclick=e=>{const b=e.target.closest('[data-sort]');if(b){if(sortKey===b.dataset.sort)ascending=!ascending;else{sortKey=b.dataset.sort;ascending=true;}renderTable();}};
 $('results-table').onchange=e=>{const id=e.target.dataset.model;if(id){e.target.checked?selected.add(id):selected.delete(id);renderTable();saveView();}};
 document.querySelectorAll('[data-chart]').forEach(b=>b.onclick=()=>{chartMode=b.dataset.chart;renderChart();saveView();});
 for(const id of ['chart-limit','chart-measure','chart-complete'])$(id).onchange=()=>{renderChart();saveView();};
 $('chart-suite').onchange=()=>{if(suite!=='overview')setSuite($('chart-suite').value);else{renderChart();saveView();}};
 $('download-chart').onclick=DecisionCharts.download;
 $('chart-models').onchange=e=>{const id=e.target.dataset.compare;if(id){e.target.checked?selected.add(id):selected.delete(id);renderTable();saveView();}};
 $('model-search').oninput=()=>{renderTable();saveView();};$('selected-only').onchange=()=>{renderTable();saveView();};$('reset-models').onclick=()=>{selected.clear();$('selected-only').checked=false;renderTable();saveView();};
 $('example-suite').onchange=()=>updateFilters(0);
 ['scenario','source','attack'].forEach((id,i)=>$(id).onchange=()=>updateFilters(i+1));
 $('sample').onchange=showSample;
 for(const [id,delta]of [['prev',-1],['next',1]])$(id).onclick=()=>{const i=filtered.findIndex(r=>String(r.id)===$('sample').value);if(filtered[i+delta]){$('sample').value=String(filtered[i+delta].id);showSample();}};
 $('copy-link').onclick=async()=>{saveView();try{await navigator.clipboard.writeText(location.href);$('copy-link').textContent='Link copied ✓';}catch{$('copy-link').textContent='Copy this page’s URL from your address bar';}setTimeout(()=>$('copy-link').textContent='Copy view link',2500);};
 $('example').onclick=e=>{if(e.target.matches('[data-expand]')){const img=$('image-dialog').querySelector('img');img.src=e.target.src;img.alt=e.target.alt;$('image-dialog').showModal();}};
 $('close-image').onclick=()=>$('image-dialog').close();
}
main().catch(e=>{$('error').hidden=false;$('error').textContent=`Unable to load this release: ${e.message}. Please reload or visit the dataset on Hugging Face.`;console.error(e);});
