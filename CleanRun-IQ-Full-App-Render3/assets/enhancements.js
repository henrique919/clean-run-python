(function(){
  "use strict";

  window.CLEANRUN_FRONTEND_BUILD="cards19";
  document.documentElement.dataset.cleanrunBuild="cards19";
  const CACHE_KEY="cleanrun-offline-state-v1";
  const QUEUE_KEY="cleanrun-offline-queue-v1";
  const DB_NAME="cleanrun-iq-offline";
  const THEME_KEY="cleanrun-theme";
  const LAST_CAPTURE_KEY="cleanrun-last-capture-fields";
  let capturePhotoMeta=[];
  let editPhotos=[];
  let editPhotoMeta=[];
  let selectedEditItem="";
  let lastChosenPhotoMeta=null;
  let workbench={source:"",title:"Photo evidence",save:null,drawing:false,last:null,history:[]};
  let offlineQueue=[];
  let captureSubmitting=false;

  const readJson=(key,fallback)=>{try{return JSON.parse(localStorage.getItem(key)||"")||fallback}catch{return fallback}};
  const openOfflineDb=()=>new Promise((resolve,reject)=>{const request=indexedDB.open(DB_NAME,1);request.onupgradeneeded=()=>request.result.createObjectStore("kv");request.onsuccess=()=>resolve(request.result);request.onerror=()=>reject(request.error)});
  const dbGet=async(key)=>{try{const db=await openOfflineDb();return await new Promise((resolve,reject)=>{const request=db.transaction("kv","readonly").objectStore("kv").get(key);request.onsuccess=()=>resolve(request.result);request.onerror=()=>reject(request.error)})}catch{return readJson(key,null)}};
  const dbSet=async(key,value)=>{try{const db=await openOfflineDb();await new Promise((resolve,reject)=>{const request=db.transaction("kv","readwrite").objectStore("kv").put(value,key);request.onsuccess=()=>resolve();request.onerror=()=>reject(request.error)})}catch{try{localStorage.setItem(key,JSON.stringify(value))}catch{}}};
  const cacheState=()=>{if(typeof state!=="undefined"&&state)dbSet(CACHE_KEY,state)};
  const pendingQueue=()=>offlineQueue;
  const setQueue=q=>{offlineQueue=q;dbSet(QUEUE_KEY,q);updateOfflinePill()};
  const offlineId=()=>`offline-${crypto.randomUUID?crypto.randomUUID():Date.now()+"-"+Math.random().toString(16).slice(2)}`;
  const MAX_PHOTO_EDGE=1600;
  const PHOTO_QUALITY=.72;

  function readFileData(file){
    return new Promise((resolve,reject)=>{
      const reader=new FileReader();
      reader.onload=()=>resolve(reader.result);
      reader.onerror=()=>reject(reader.error);
      reader.readAsDataURL(file);
    });
  }

  function loadImage(src){
    return new Promise((resolve,reject)=>{
      const img=new Image();
      img.onload=()=>resolve(img);
      img.onerror=reject;
      img.src=src;
    });
  }

  async function fileToUploadData(file){
    if(!file?.type?.startsWith("image/"))return readFileData(file);
    const original=await readFileData(file);
    const img=await loadImage(original);
    const scale=Math.min(1,MAX_PHOTO_EDGE/img.naturalWidth,MAX_PHOTO_EDGE/img.naturalHeight);
    if(scale>=1&&file.size<900000)return original;
    const canvas=document.createElement("canvas");
    canvas.width=Math.max(1,Math.round(img.naturalWidth*scale));
    canvas.height=Math.max(1,Math.round(img.naturalHeight*scale));
    canvas.getContext("2d").drawImage(img,0,0,canvas.width,canvas.height);
    const compressed=canvas.toDataURL("image/jpeg",PHOTO_QUALITY);
    return compressed.length<original.length?compressed:original;
  }

  function setBusyButton(button,label){
    if(!button)return()=>{};
    const old=button.innerHTML;
    button.classList.add("is-busy");
    button.disabled=true;
    if(label)button.innerHTML=label;
    return()=>{button.classList.remove("is-busy");button.disabled=false;button.innerHTML=old};
  }
  function setBusyForm(form,label){
    const buttons=[...form.querySelectorAll("button[type='submit']")],snapshots=buttons.map(button=>({button,html:button.innerHTML,disabled:button.disabled}));
    buttons.forEach(button=>{button.classList.add("is-busy");button.disabled=true;if(button===document.activeElement&&label)button.innerHTML=label});
    return()=>snapshots.forEach(({button,html,disabled})=>{button.classList.remove("is-busy");button.disabled=disabled;button.innerHTML=html});
  }
  function rememberCaptureFields(data){
    const keep={project:data.project,building:data.building,level:data.level,unit:data.unit,room:data.room,trade:data.trade,subcontractor:data.subcontractor,dueDate:data.dueDate,priority:data.priority,type:data.type};
    try{localStorage.setItem(LAST_CAPTURE_KEY,JSON.stringify(keep))}catch{}
  }
  function applyCaptureDefaults(){
    let keep={};try{keep=JSON.parse(localStorage.getItem(LAST_CAPTURE_KEY)||"{}")||{}}catch{}
    const form=$("#app form");if(!form)return;
    for(const [key,value] of Object.entries(keep)){if(value&&form.elements[key])form.elements[key].value=value}
    photoHint?.();toggleRaised?.();
  }
  function preferredTheme(){
    return localStorage.getItem(THEME_KEY)||state?.settings?.theme||"light";
  }
  function applyTheme(){
    document.documentElement.dataset.theme=preferredTheme();
  }
  applyTheme();

  function geoLabel(meta){
    if(!meta||meta.latitude==null)return "Location unavailable";
    return `📍 ${Number(meta.latitude).toFixed(5)}, ${Number(meta.longitude).toFixed(5)}${meta.accuracy?` ±${Math.round(meta.accuracy)}m`:""}`;
  }

  function locatePhoto(){
    const base={capturedAt:new Date().toISOString()};
    return new Promise(resolve=>{
      if(!navigator.geolocation)return resolve(base);
      navigator.geolocation.getCurrentPosition(
        p=>resolve({...base,latitude:p.coords.latitude,longitude:p.coords.longitude,accuracy:p.coords.accuracy}),
        ()=>resolve(base),
        {enableHighAccuracy:true,timeout:5000,maximumAge:30000}
      );
    });
  }

  async function filesWithMeta(files){
    const list=[...files];
    const [sources,geo]=await Promise.all([Promise.all(list.map(fileToUploadData)),locatePhoto()]);
    return sources.map((src,n)=>({src,meta:{...geo,fileName:list[n]?.name||`photo-${n+1}.jpg`,mimeType:list[n]?.type||"image/jpeg",compressed:!!list[n]?.type?.startsWith("image/")}}));
  }

  filesToData=async function(files){
    return Promise.all([...files].map(fileToUploadData));
  };

  function previewFigure(src,meta,index,mode){
    const safeTitle=mode==="edit"?"Retrospective evidence":"Issue evidence";
    return `<figure><img src="${src}" alt="${safeTitle} ${index+1}" onclick="openEvidencePhoto('${mode}',${index})"><figcaption class="photo-caption">${esc(geoLabel(meta))}</figcaption><div class="photo-tools"><button class="btn alt" type="button" onclick="markupEvidencePhoto('${mode}',${index})">Mark up</button><button class="btn alt" type="button" onclick="removeEvidencePhoto('${mode}',${index})">Remove</button></div></figure>`;
  }

  function renderCapturePreviews(){
    const host=$("#capturePreviews");
    if(host)host.innerHTML=capturePhotos.map((src,n)=>previewFigure(src,capturePhotoMeta[n],n,"capture")).join("");
    const count=$("#photoCount");
    if(count)count.textContent=capturePhotos.length?`${capturePhotos.length} photo${capturePhotos.length===1?"":"s"} attached`:"No photos attached yet";
    document.querySelector("[data-photo-card]")?.classList.toggle("needs-photo",capturePhotos.length===0);
  }

  function renderEditPreviews(){
    const host=$("#editPhotoGrid");
    if(!host)return;
    host.innerHTML=editPhotos.map((src,n)=>src.startsWith("seed://")
      ?`<figure><span class="thumb">${seedThumb(src)}</span><figcaption class="photo-caption">Original seeded evidence</figcaption></figure>`
      :previewFigure(src,editPhotoMeta[n],n,"edit")).join("")||'<span class="meta">No photos attached.</span>';
  }

  window.openEvidencePhoto=function(mode,index){
    const photos=mode==="edit"?editPhotos:capturePhotos;
    const src=photos[index];
    if(src&&!src.startsWith("seed://"))openWorkbench(src,"Evidence photo",null);
  };
  window.markupEvidencePhoto=function(mode,index){
    const photos=mode==="edit"?editPhotos:capturePhotos;
    const src=photos[index];
    if(!src||src.startsWith("seed://"))return toast("Seed previews cannot be marked up.",true);
    openWorkbench(src,"Mark up evidence",data=>{photos[index]=data;mode==="edit"?renderEditPreviews():renderCapturePreviews()});
  };
  window.removeEvidencePhoto=function(mode,index){
    if(mode==="edit"){editPhotos.splice(index,1);editPhotoMeta.splice(index,1);renderEditPreviews()}
    else{capturePhotos.splice(index,1);capturePhotoMeta.splice(index,1);renderCapturePreviews()}
  };
  window.addEditPhotos=async function(input){
    const records=await filesWithMeta(input.files||[]);
    editPhotos.push(...records.map(r=>r.src));editPhotoMeta.push(...records.map(r=>r.meta));renderEditPreviews();input.value="";
  };

  function ensureWorkbench(){
    if($("#photoWorkbench"))return;
    document.body.insertAdjacentHTML("beforeend",`<section class="photo-workbench" id="photoWorkbench" hidden aria-modal="true"><div class="photo-workbench__panel"><header class="photo-workbench__head"><strong id="photoWorkbenchTitle">Photo evidence</strong><button type="button" onclick="closePhotoWorkbench()">Close</button></header><div class="photo-workbench__stage"><canvas id="markupCanvas"></canvas></div><footer class="photo-workbench__tools"><label>Tool <select id="markupTool"><option value="pen">Pen</option><option value="circle">Circle</option><option value="box">Box</option><option value="arrow">Arrow</option><option value="text">Text box</option></select></label><label>Colour <input id="markupColor" type="color" value="#E5483B"></label><label>Width <input id="markupWidth" type="range" min="2" max="18" value="6"></label><button type="button" onclick="undoPhotoMarkup()">Undo</button><button type="button" onclick="resetPhotoMarkup()">Reset</button><button class="primary" id="saveMarkup" type="button" onclick="savePhotoMarkup()">Save marked-up copy</button></footer></div></section>`);
    const canvas=$("#markupCanvas");
    const point=e=>{const r=canvas.getBoundingClientRect(),p=e.touches?.[0]||e;return{x:(p.clientX-r.left)*canvas.width/r.width,y:(p.clientY-r.top)*canvas.height/r.height}};
    const style=ctx=>{ctx.strokeStyle=$("#markupColor").value;ctx.fillStyle=$("#markupColor").value;ctx.lineWidth=Number($("#markupWidth").value);ctx.lineCap="round";ctx.lineJoin="round";ctx.font="700 22px Inter, system-ui, sans-serif"};
    const arrow=(ctx,a,b)=>{const angle=Math.atan2(b.y-a.y,b.x-a.x),head=22+ctx.lineWidth;ctx.beginPath();ctx.moveTo(a.x,a.y);ctx.lineTo(b.x,b.y);ctx.stroke();ctx.beginPath();ctx.moveTo(b.x,b.y);ctx.lineTo(b.x-head*Math.cos(angle-Math.PI/6),b.y-head*Math.sin(angle-Math.PI/6));ctx.lineTo(b.x-head*Math.cos(angle+Math.PI/6),b.y-head*Math.sin(angle+Math.PI/6));ctx.closePath();ctx.fill()};
    const shape=(ctx,tool,a,b)=>{style(ctx);const x=Math.min(a.x,b.x),y=Math.min(a.y,b.y),w=Math.abs(b.x-a.x),h=Math.abs(b.y-a.y);if(tool==="box"){ctx.strokeRect(x,y,w,h)}else if(tool==="circle"){ctx.beginPath();ctx.ellipse(x+w/2,y+h/2,Math.max(1,w/2),Math.max(1,h/2),0,0,Math.PI*2);ctx.stroke()}else if(tool==="arrow"){arrow(ctx,a,b)}};
    const start=e=>{if(!workbench.save)return;e.preventDefault();const tool=$("#markupTool").value,p=point(e),ctx=canvas.getContext("2d");workbench.history.push(canvas.toDataURL("image/png"));if(tool==="text"){const text=prompt("Markup text:","");if(!text){workbench.history.pop();return}style(ctx);const pad=10,lines=text.split(/\n/).slice(0,4),width=Math.max(...lines.map(line=>ctx.measureText(line).width))+pad*2,height=lines.length*28+pad*2;ctx.fillStyle="rgba(255,255,255,.88)";ctx.fillRect(p.x,p.y,width,height);ctx.strokeStyle=$("#markupColor").value;ctx.strokeRect(p.x,p.y,width,height);ctx.fillStyle=$("#markupColor").value;lines.forEach((line,n)=>ctx.fillText(line,p.x+pad,p.y+pad+22+n*28));return}workbench.drawing=true;workbench.last=p;workbench.start=p;workbench.snapshot=canvas.toDataURL("image/png")};
    const move=e=>{if(!workbench.drawing)return;e.preventDefault();const p=point(e),tool=$("#markupTool").value,ctx=canvas.getContext("2d");if(tool==="pen"){style(ctx);ctx.beginPath();ctx.moveTo(workbench.last.x,workbench.last.y);ctx.lineTo(p.x,p.y);ctx.stroke();workbench.last=p;return}const img=new Image();img.onload=()=>{ctx.clearRect(0,0,canvas.width,canvas.height);ctx.drawImage(img,0,0);shape(ctx,tool,workbench.start,p)};img.src=workbench.snapshot};
    const stop=e=>{if(!workbench.drawing)return;const tool=$("#markupTool").value;if(tool!=="pen")shape(canvas.getContext("2d"),tool,workbench.start,point(e));workbench.drawing=false;workbench.last=null;workbench.start=null;workbench.snapshot=null};
    canvas.addEventListener("pointerdown",start);canvas.addEventListener("pointermove",move);canvas.addEventListener("pointerup",stop);canvas.addEventListener("pointerleave",stop);
  }

  function drawSource(src){
    const img=new Image();img.onload=()=>{const canvas=$("#markupCanvas"),scale=Math.min(1,1400/img.naturalWidth,900/img.naturalHeight);canvas.width=Math.max(1,Math.round(img.naturalWidth*scale));canvas.height=Math.max(1,Math.round(img.naturalHeight*scale));canvas.getContext("2d").drawImage(img,0,0,canvas.width,canvas.height);workbench.history=[]};img.src=src;
  }
  function restoreCanvas(src){
    const img=new Image();img.onload=()=>{const canvas=$("#markupCanvas");canvas.getContext("2d").clearRect(0,0,canvas.width,canvas.height);canvas.getContext("2d").drawImage(img,0,0,canvas.width,canvas.height)};img.src=src;
  }
  function openWorkbench(src,title,onSave){ensureWorkbench();workbench={source:src,title,save:onSave,drawing:false,last:null,history:[]};$("#photoWorkbenchTitle").textContent=title;$("#saveMarkup").hidden=!onSave;$("#photoWorkbench").hidden=false;drawSource(src)}
  window.closePhotoWorkbench=()=>{$("#photoWorkbench").hidden=true};
  window.resetPhotoMarkup=()=>drawSource(workbench.source);
  window.undoPhotoMarkup=()=>{const previous=workbench.history.pop();if(previous)restoreCanvas(previous)};
  window.savePhotoMarkup=()=>{const data=$("#markupCanvas").toDataURL("image/jpeg",.92);workbench.save?.(data);closePhotoWorkbench();toast("Marked-up evidence saved")};

  const originalLoadCapturePhotos=loadCapturePhotos;
  loadCapturePhotos=async function(input){
    const records=await filesWithMeta(input.files||[]);
    capturePhotos.push(...records.map(r=>r.src));capturePhotoMeta.push(...records.map(r=>r.meta));renderCapturePreviews();input.value="";
  };

  const originalCaptureView=captureView;
  captureView=function(){
    const html=originalCaptureView()
      .replace("<section class=\"form-card\"><div class=\"form-card-title\">Photo Evidence</div>", "<section class=\"form-card\" data-photo-card=\"true\"><div class=\"spread\"><div class=\"form-card-title\">Photo Evidence</div><span class=\"photo-count\" id=\"photoCount\">No photos attached yet</span></div>")
      .replace("Start with evidence. Defects and client defects require at least one photo.", "Start with proof from site. Defects and client defects cannot be saved without original evidence.");
    setTimeout(()=>{applyCaptureDefaults();renderCapturePreviews()},0);
    return html;
  };

  function requireOriginalPhoto(data){
    return ["defect","client"].includes(data.type)&&!capturePhotos.length;
  }
  function focusPhotoEvidence(){
    const card=document.querySelector("[data-photo-card]")||$("#capturePreviews")?.closest("section");
    card?.scrollIntoView({behavior:"smooth",block:"center"});
    card?.classList.add("photo-required-pulse");
    setTimeout(()=>card?.classList.remove("photo-required-pulse"),1800);
  }

  saveCapture=async function(e){
    e.preventDefault();const form=e.currentTarget,data=Object.fromEntries(new FormData(form)),mode=e.submitter?.value||"save";
    const release=setBusyButton(e.submitter,mode==="issue"?"Issuing…":"Saving…");
    data.id=offlineId();data.createdBy=state.settings.preparedBy;data.originalPhotos=capturePhotos;data.originalPhotoMeta=capturePhotoMeta;
    const voice=$("#voiceText").value.trim();if(voice){data.voiceTranscript=voice;data.voiceNote={transcript:voice,createdAt:new Date().toISOString(),status:"parsed"}}
    if(data.type==="client"&&!data.raisedBy){release();return toast("A Client Defect requires a Raised By / source.",true)}
    if(mode==="issue"&&(!data.trade||!data.subcontractor)){release();return toast("Issue Now requires a trade and subcontractor.",true)}
    try{const item=await api("/api/items",{method:"POST",body:JSON.stringify(data)});if(mode==="issue")await api(`/api/items/${item.id}/actions/issue`,{method:"POST",body:JSON.stringify({to:data.subcontractor,by:data.createdBy})});capturePhotos=[];capturePhotoMeta=[];if(walkMode){walkCount++;await reload();route="capture";render();toast(`${item.code} saved · continue walk`)}else{await reload();route="items";render();toast(item.sync==="queued"?`${item.code} saved offline · queued to sync`:`${item.code} saved`)}}catch(err){toast(err.message,true)}
  };

  editItemForm=function(id){
    const i=state.items.find(x=>x.id===id);selectedEditItem=id;editPhotos=[...(i.originalPhotos||[])];editPhotoMeta=[...(i.originalPhotoMeta||[])];while(editPhotoMeta.length<editPhotos.length)editPhotoMeta.push({capturedAt:i.createdAt});
    $("#modalTitle").textContent=`Edit ${i.code}`;
    $("#modalBody").innerHTML=`<form class="field-list" onsubmit="saveItemEdit(event,'${id}')"><div class="fields admin-form-grid"><label>Item type<select name="type">${options(["defect","incomplete","client"],i.type)}</select></label><label>Project<select name="project">${options(state.settings.projects,i.project)}</select></label><label>Building<input name="building" value="${esc(i.building)}"></label><label>Level<input name="level" value="${esc(i.level)}"></label><label>Unit / Area<input name="unit" value="${esc(i.unit)}"></label><label>Room / Location<input name="room" value="${esc(i.room)}"></label><label>Trade<select name="trade"><option value=""></option>${options(trades,i.trade)}</select></label><label>Subcontractor<select name="subcontractor"><option value=""></option>${options(state.settings.subcontractors,i.subcontractor)}</select></label><label>Priority<select name="priority">${options(["high","urgent"],i.priority)}</select></label><label>Due date<input type="date" name="dueDate" value="${esc(i.dueDate)}"></label><label class="span">Description<textarea name="description">${esc(i.description)}</textarea></label></div><section class="edit-evidence"><div class="spread"><div><b>Original issue photos</b><div class="meta">Add evidence retrospectively, enlarge it or mark it up.</div></div><label class="btn alt">＋ Add photos<input hidden type="file" accept="image/*" multiple onchange="addEditPhotos(this)"></label></div><div class="edit-photo-grid" id="editPhotoGrid"></div></section><button class="btn">Save changes and evidence</button></form>`;
    renderEditPreviews();
  };

  saveItemEdit=async function(e,id){
    e.preventDefault();const data=Object.fromEntries(new FormData(e.currentTarget));data.by=state.settings.preparedBy;data.originalPhotos=editPhotos;data.originalPhotoMeta=editPhotoMeta;
    try{await api(`/api/items/${id}`,{method:"PATCH",body:JSON.stringify(data)});await reload();showItem(id);toast("Item details and evidence updated")}catch(err){toast(err.message,true)}
  };

  chooseImage=function(){return new Promise(resolve=>{
    let settled=false;
    const done=value=>{if(settled)return;settled=true;resolve(value||null)};
    const input=document.createElement("input");input.type="file";input.accept="image/*";
    input.onchange=async()=>{try{const records=await filesWithMeta(input.files||[]);lastChosenPhotoMeta=records[0]?.meta||null;done(records[0]?.src)}catch(err){toast(err.message,true);done(null)}};
    input.oncancel=()=>done(null);
    setTimeout(()=>window.addEventListener("focus",()=>setTimeout(()=>{if(!settled&&!input.files?.length)done(null)},350),{once:true}),0);
    input.click();
  })};

  saveCapture=async function(e){
    e.preventDefault();
    if(captureSubmitting)return toast("Still saving this item. Please wait…",true);
    captureSubmitting=true;
    const form=e.currentTarget,data=Object.fromEntries(new FormData(form)),mode=e.submitter?.value||"save";
    const release=setBusyForm(form,mode==="issue"?"Issuing…":"Saving…");
    form.dataset.captureRequestId=form.dataset.captureRequestId||offlineId();
    data.id=form.dataset.captureRequestId;data.createdBy=state.settings.preparedBy;data.originalPhotos=capturePhotos;data.originalPhotoMeta=capturePhotoMeta;
    rememberCaptureFields(data);
    const voice=$("#voiceText").value.trim();if(voice){data.voiceTranscript=voice;data.voiceNote={transcript:voice,createdAt:new Date().toISOString(),status:"parsed"}}
    const fail=message=>{captureSubmitting=false;release();toast(message,true)};
    if(data.type==="client"&&!data.raisedBy)return fail("A Client Defect requires a Raised By / source.");
    if(requireOriginalPhoto(data)){focusPhotoEvidence();return fail("Attach original photo evidence, or change Item Type to Incomplete Work.")}
    if(mode==="issue"&&(!data.trade||!data.subcontractor))return fail("Issue Now requires a trade and subcontractor.");
    try{
      toast(capturePhotos.length?"Compressing and uploading evidence…":"Saving item…");
      if(mode==="issue"){data.issueOnCreate=true;data.issueTo=data.subcontractor}
      const item=await api("/api/items",{method:"POST",body:JSON.stringify(data)});
      capturePhotos=[];capturePhotoMeta=[];
      if(walkMode){walkCount++;await reload();route="capture";render();toast(`${item.code} saved · continue walk`)}
      else{await reload();route="items";render();setTimeout(()=>scrollTo(0,0),0);toast(item.sync==="queued"?`${item.code} saved offline · queued to sync`:`${item.code} saved`)}
    }catch(err){toast(err.message,true)}finally{captureSubmitting=false;release()}
  };

  reviewView=function(){
    const items=state.items.filter(i=>i.project===state.settings.activeProject&&["ready_for_review","under_inspection"].includes(i.status));
    return `${subHeader("Review Queue")}<div class="screen-scroll"><section class="native-card review-hero"><div class="spread"><div><h2>${items.length} ready for supervisor review</h2><p class="meta">Compare original issue proof against rectification evidence, then close or reject.</p></div><button class="btn alt small" onclick="go('items')">All items</button></div></section>${items.length?items.map(i=>{const original=(i.originalPhotos||[]).find(p=>!String(p).startsWith("seed://")),rect=(i.rectificationEvidence||[]).find(e=>e.photo)?.photo;return `<article class="native-card review-card"><div class="review-grid"><div><h3>Original Issue</h3>${original?`<img src="${original}" alt="Original issue">`:`<div class="thumb">${seedThumb(i.originalPhotos?.[0])}</div>`}<p>${esc(i.description||"No description")}</p><small class="meta">${esc(loc(i))}</small></div><div><h3>Rectification Evidence</h3>${rect?`<img src="${rect}" alt="Rectification evidence">`:`<div class="empty">No rectification photo</div>`}<p>${esc(i.rectificationEvidence?.at(-1)?.comment||"No subcontractor comment")}</p><small class="meta">${esc(i.subcontractor||"Unassigned")} · Due ${esc(i.dueDate)}</small></div></div><div class="actions review-actions"><button class="btn" onclick="itemAction('${i.id}','${i.status==="ready_for_review"?"inspect":"close"}')">${i.status==="ready_for_review"?"Start Inspection":"Close"}</button><button class="btn danger" onclick="itemAction('${i.id}','reject')">Reject</button><button class="btn alt" onclick="showItem('${i.id}')">Open Detail</button></div></article>`}).join(""):`<div class="native-card empty"><b>No items ready for review</b><br><span class="meta">When subcontractors mark work ready, it will appear here.</span></div>`}</div>`;
  };

  itemAction=async function(id,act){
    const i=state.items.find(x=>x.id===id),body={by:state.settings.preparedBy};
    const release=setBusyButton(document.activeElement,"Working…");
    if(act==="issue"){body.to=i.subcontractor||prompt("Subcontractor name:","");body.reissue=i.status==="rejected"}
    if(act==="reject"||act==="reopen")body.reason=prompt(act==="reject"?"Why is this being rejected?":"Reason for reopening:","");
    if(act==="issue"&&!body.to){release();return toast("Choose a subcontractor before issuing.",true)}
    if((act==="reject"||act==="reopen")&&!body.reason){release();return toast(`${act==="reject"?"Rejection":"Reopen"} reason is required.`,true)}
    if(act==="rectification"){body.comment=prompt("Rectification comment:","");body.photo=await chooseImage();body.photoMeta=lastChosenPhotoMeta;if(!body.photo&&!body.comment){release();return toast("Add a rectification photo or comment.",true)}body.advanceToReady=confirm("Mark ready for review after saving evidence?")}
    if(act==="close"){body.role=prompt("Signed off by role:","Site Manager")||"Site Manager";body.note=prompt("Closeout note (optional):","");if(i.type!=="incomplete"){body.photo=await chooseImage();body.photoMeta=lastChosenPhotoMeta;if(!body.photo){release();return toast("Closeout photo is required.",true)}}body.confirmed=confirm(`I confirm this item is rectified and accepted by ${state.settings.preparedBy}.`);if(!body.confirmed){release();return toast("Closeout confirmation cancelled.",true)}}
    try{await api(`/api/items/${id}/actions/${act}`,{method:"POST",body:JSON.stringify(body)});await reload();showItem(id);document.querySelector(".dialog")?.scrollTo?.(0,0);toast("Item updated")}catch(err){toast(err.message,true)}finally{release()}
  };

  const originalShowItem=showItem;
  showItem=function(id){
    originalShowItem(id);const i=state.items.find(x=>x.id===id),cards=[...document.querySelectorAll("#modalBody .native-card")],original=cards.find(c=>c.querySelector("h2")?.textContent==="Original Issue");
    if(original){const photos=[...original.querySelectorAll(".photo-preview img")];photos.forEach((img,n)=>{img.title="Open enlarged photo";img.onclick=()=>openWorkbench(img.src,`${i.code} · Original issue ${n+1}`,null);const meta=i.originalPhotoMeta?.[n];if(meta){const cap=document.createElement("div");cap.className="photo-caption";cap.textContent=geoLabel(meta);img.insertAdjacentElement("afterend",cap)}});const add=document.createElement("button");add.className="btn alt small";add.textContent="＋ Add / mark up photos";add.onclick=()=>editItemForm(id);original.querySelector("h2")?.insertAdjacentElement("afterend",add)}
    document.querySelectorAll("#modalBody .evidence img").forEach(img=>{img.title="Open enlarged photo";img.onclick=()=>openWorkbench(img.src,img.alt||"Evidence photo",null)});
  };

  function offlineError(err){return !navigator.onLine||err instanceof TypeError||/fetch|network|offline/i.test(String(err?.message||err))}
  function optimistic(path,opt,body){
    const method=(opt.method||"GET").toUpperCase(),at=new Date().toISOString();
    if(method==="POST"&&path==="/api/items"){
      const clean={...body},issueOnCreate=!!clean.issueOnCreate,issueTo=clean.issueTo||clean.subcontractor;delete clean.issueOnCreate;delete clean.issueTo;
      const existing=state.items.find(x=>x.id===clean.id);if(existing)return existing;
      const item={status:issueOnCreate?"issued":"open",createdAt:at,updatedAt:at,rectificationEvidence:[],closeoutEvidence:[],comments:[],issueHistory:[],inspectionHistory:[],auditEvents:[{at,action:"Created offline",by:clean.createdBy}],sync:"queued",...clean,code:`OFF-${String(Date.now()).slice(-4)}`};
      if(issueOnCreate){item.issuedAt=at;item.issueHistory.push({at,to:issueTo,by:clean.createdBy,reissue:false});item.auditEvents.push({at,action:`Issue to ${issueTo} queued offline`,by:clean.createdBy})}
      state.items.unshift(item);cacheState();return item;
    }
    const itemMatch=path.match(/^\/api\/items\/([^/]+)$/);if(itemMatch&&method==="PATCH"){const item=state.items.find(x=>x.id===decodeURIComponent(itemMatch[1]));Object.assign(item||{},body,{sync:"queued",updatedAt:at});cacheState();return item}
    const actionMatch=path.match(/^\/api\/items\/([^/]+)\/actions\/([^/]+)$/);if(actionMatch&&method==="POST"){
      const item=state.items.find(x=>x.id===decodeURIComponent(actionMatch[1])),act=actionMatch[2];if(item){const status={issue:"issued",start:"in_progress",ready:"ready_for_review",inspect:"under_inspection",reject:"rejected",close:item.type==="incomplete"?"complete":"closed",reopen:"open"}[act];if(status)item.status=status;if(act==="comment")item.comments.push({at,text:body.text,by:body.by});item.auditEvents.push({at,action:`${act} queued offline`,by:body.by});item.sync="queued";cacheState()}return item||{queued:true}
    }
    return {queued:true,id:body.id||offlineId(),...body};
  }

  const networkApi=api;
  api=async function(path,opt={}){
    try{const value=await networkApi(path,opt);if(path==="/api/state")dbSet(CACHE_KEY,value);return value}
    catch(err){
      if(!offlineError(err))throw err;
      const method=(opt.method||"GET").toUpperCase();if(method==="GET"&&path==="/api/state"){const cached=await dbGet(CACHE_KEY);if(cached)return cached;throw new Error("No offline data has been cached on this device yet.")}
      if(method!=="GET"){const body=opt.body?JSON.parse(opt.body):{};const queue=pendingQueue();queue.push({path,opt:{...opt},queuedAt:new Date().toISOString()});setQueue(queue);return optimistic(path,opt,body)}
      throw err;
    }
  };

  async function flushQueue(){
    if(!navigator.onLine)return updateOfflinePill();let queue=pendingQueue();if(!queue.length)return updateOfflinePill();updateOfflinePill("syncing");let sent=0;
    while(queue.length){try{await networkApi(queue[0].path,queue[0].opt);queue.shift();setQueue(queue);sent++}catch{break}}
    if(sent){try{state=await networkApi("/api/state");cacheState();render()}catch{}}
    updateOfflinePill();if(sent)toast(`${sent} offline change${sent===1?"":"s"} synced`);
  }

  window.openHomeBucket=function(bucket){
    route="items";
    if(bucket==="all")itemStatusFilter="All";
    if(bucket==="open")itemStatusFilter="Captured";
    if(bucket==="issued")itemStatusFilter="Issued";
    if(bucket==="attention")itemStatusFilter="Overdue";
    if(bucket==="ready")itemStatusFilter="Ready";
    if(bucket==="closed")itemStatusFilter="Closed";
    render();
    setTimeout(()=>{document.querySelectorAll("#statusFilters button").forEach(btn=>btn.classList.toggle("active",btn.dataset.value===itemStatusFilter));filterItems();scrollTo(0,0)},0);
  };
  window.openDashboardSearch=function(query,status="All"){
    route="items";itemStatusFilter=status;render();
    setTimeout(()=>{document.querySelectorAll("#statusFilters button").forEach(btn=>btn.classList.toggle("active",btn.dataset.value===itemStatusFilter));const search=$("#search");if(search)search.value=query||"";filterItems();scrollTo(0,0)},0);
  };

  statusMatch=function(i,s){
    if(s==="All")return true;
    if(s==="Captured")return i.status==="open"&&!overdue(i);
    if(s==="Issued")return ["issued","in_progress"].includes(i.status)&&!overdue(i);
    if(s==="Ready")return ["ready_for_review","under_inspection"].includes(i.status)&&!overdue(i);
    if(s==="Rejected")return i.status==="rejected";
    if(s==="Overdue")return overdue(i);
    if(s==="Closed")return ["closed","complete"].includes(i.status);
    return true;
  };
  const originalItemsView=itemsView;
  itemsView=function(){
    const html=originalItemsView();
    const chips=["All","Captured","Issued","Ready","Rejected","Overdue","Closed"].map(v=>`<button class="filter-chip light ${v===itemStatusFilter?'active':''}" data-value="${v}" onclick="setFilter(this,'status')">${v}</button>`).join("");
    return html.replace(/<div class="hscroll" id="statusFilters">[\s\S]*?<\/div><\/div><div class="screen-scroll">/,`<div class="hscroll" id="statusFilters">${chips}</div></div><div class="screen-scroll">`);
  };

  function siteStatus(item){
    if(overdue(item))return {label:"OVERDUE",tone:"overdue"};
    if(["closed","complete"].includes(item.status))return {label:"CLOSED",tone:"closed"};
    if(item.status==="rejected")return {label:"REJECTED / RE-ISSUE",tone:"rejected"};
    if(["ready_for_review","under_inspection"].includes(item.status))return {label:"READY",tone:"ready"};
    if(["issued","in_progress"].includes(item.status))return {label:"ISSUED",tone:"issued"};
    return {label:"CAPTURED",tone:"captured"};
  }
  function cardPhoto(item){
    const src=(item.originalPhotos||[])[0];
    if(!src)return `<div class="cr-card-photo empty">NO PHOTO</div>`;
    return src.startsWith("seed://")?`<div class="cr-card-photo">${seedThumb(src)}</div>`:`<img class="cr-card-photo" src="${src}" alt="Issue evidence">`;
  }
  window.cardAction=function(event,id,act){event.preventDefault();event.stopPropagation();event.stopImmediatePropagation?.();const button=event.currentTarget;if(button?.disabled)return false;const release=setBusyButton(button,act==="issue"?"ISSUING...":"WORKING...");(async()=>{const item=state.items.find(x=>x.id===id);if(!item)return toast("Item not found. Refresh and try again.",true);const body={by:state.settings.preparedBy};if(act==="issue"){body.to=item.subcontractor||prompt("Subcontractor name:","");body.reissue=item.status==="rejected";if(!body.to)return toast("Choose a subcontractor before issuing.",true)}await api(`/api/items/${id}/actions/${act}`,{method:"POST",body:JSON.stringify(body)});await reload();toast(act==="issue"?"ISSUED":"ITEM UPDATED")})().catch(err=>toast(err.message,true)).finally(release);return false};
  itemCard=function(i){
    const status=siteStatus(i),closed=["closed","complete"].includes(i.status),urgent=i.priority==="urgent",dateText=closed?"CLOSED":`DUE ${esc(new Date(i.dueDate+"T00:00:00").toLocaleDateString(undefined,{day:"numeric",month:"short",year:"numeric"})).toUpperCase()}`,location=[i.building,i.level,i.unit,i.room].filter(Boolean).join(" · ");
    const issueButton=i.status==="open"?`<button class="cr-issue-cta" type="button" onclick="return cardAction(event,'${i.id}','issue')">Issue ›</button>`:"";
    const reissue=i.status==="rejected"?`<button class="cr-card-action" type="button" onclick="return cardAction(event,'${i.id}','issue')">Re-Issue ›</button>`:"";
    return `<article class="native-card native-item cr-item-card status-${status.tone}" onclick="showItem('${i.id}')"><div class="cr-card-band"><div><span class="cr-card-code">${esc(i.code).toUpperCase()}</span><span class="cr-card-type">${esc(typeLabels[i.type]||i.type).toUpperCase()}</span></div><span class="cr-card-status badge ${status.tone}">${status.label}</span></div><div class="cr-card-main"><div class="cr-card-media">${cardPhoto(i)}</div><div class="cr-card-copy"><div class="cr-card-trade">${esc(i.trade||"No trade")}</div><div class="cr-card-sub">${esc(i.subcontractor||"Unassigned")}</div><div class="cr-card-desc">${esc(i.description||"No description")}</div><div class="cr-card-meta"><span>${esc(location||"NO LOCATION").toUpperCase()}</span><span>${dateText}</span></div></div></div><div class="cr-card-actions">${issueButton}${reissue}${urgent?'<span class="badge overdue">URGENT</span>':""}</div></article>`;
  };

  itemCard=function(i){
    const status=siteStatus(i),closed=["closed","complete"].includes(i.status),urgent=i.priority==="urgent";
    const dateText=closed?"CLOSED":`DUE ${esc(new Date(i.dueDate+"T00:00:00").toLocaleDateString(undefined,{day:"numeric",month:"short",year:"numeric"})).toUpperCase()}`;
    const location=[i.building,i.level,i.unit,i.room].filter(Boolean).join(" · ");
    const issueButton=i.status==="open"?`<button class="cr-issue-cta" type="button" onpointerdown="event.stopPropagation()" onclick="return cardAction(event,'${i.id}','issue')">ISSUE ›</button>`:"";
    const reissue=i.status==="rejected"?`<button class="cr-card-action" type="button" onpointerdown="event.stopPropagation()" onclick="return cardAction(event,'${i.id}','issue')">RE-ISSUE ›</button>`:"";
    return `<article class="native-card native-item cr-item-card status-${status.tone}" onclick="showItem('${i.id}')"><div class="cr-card-band"><div><span class="cr-card-code">${esc(i.code).toUpperCase()}</span><span class="cr-card-type">${esc(typeLabels[i.type]||i.type).toUpperCase()}</span></div><span class="cr-card-status badge ${status.tone}">${status.label}</span></div><div class="cr-card-main"><div class="cr-card-media">${cardPhoto(i)}</div><div class="cr-card-copy"><div class="cr-card-location">${esc(location||"NO LOCATION").toUpperCase()}</div><div class="cr-card-desc">${esc(i.description||"No description")}</div><div class="cr-card-assignment"><div><div class="cr-card-trade">${esc(i.trade||"No trade")}</div><div class="cr-card-sub">${esc(i.subcontractor||"Unassigned")}</div></div><div class="cr-card-date">${dateText}</div></div></div></div><div class="cr-card-actions" onclick="event.stopPropagation()">${issueButton}${reissue}${urgent?'<span class="badge overdue">URGENT</span>':""}</div></article>`;
  };

  dashboardView=function(){
    const p=state.settings.activeProject,items=state.items.filter(i=>i.project===p),today=new Date().toISOString().slice(0,10);
    const active=items.filter(i=>!["closed","complete"].includes(i.status)),assigned=items.filter(i=>i.subcontractor),closed=items.filter(i=>["closed","complete"].includes(i.status)),overdueItems=items.filter(overdue),ready=items.filter(i=>i.status==="ready_for_review"),issued=items.filter(i=>["issued","in_progress"].includes(i.status)),todayDue=active.filter(i=>i.dueDate===today),activity=items.filter(i=>(i.updatedAt||i.createdAt||"").slice(0,10)===today);
    const closeoutPct=assigned.length?Math.round(closed.length/assigned.length*100):0,activityPct=items.length?Math.round(activity.length/items.length*100):0;
    const groupBy=(key)=>Object.values(items.reduce((acc,i)=>{const name=(key(i)||"Unassigned").trim()||"Unassigned";const row=acc[name]||(acc[name]={name,total:0,open:0,closed:0,overdue:0});row.total++;if(["closed","complete"].includes(i.status))row.closed++;else row.open++;if(overdue(i))row.overdue++;return acc},{})).sort((a,b)=>b.open-a.open||b.total-a.total||a.name.localeCompare(b.name));
    const subPerf=groupBy(i=>i.subcontractor).slice(0,5),tradePerf=groupBy(i=>i.trade).slice(0,5),topSub=subPerf[0],topTrade=tradePerf[0];
    const safeQuery=(value)=>encodeURIComponent(value||"");
    const perfRow=(r)=>{const pct=r.total?Math.round(r.closed/r.total*100):0;return `<button class="dashboard-row" onclick="openDashboardSearch(decodeURIComponent('${safeQuery(r.name)}'))"><span><strong>${esc(r.name)}</strong><small>${r.open} open · ${r.closed}/${r.total} closed${r.overdue?` · ${r.overdue} overdue`:""}</small></span><span class="dashboard-score">${pct}%</span><span class="dashboard-bar"><span style="width:${pct}%"></span></span></button>`};
    const schedule=todayDue.length?todayDue.slice(0,4).map(i=>`<button class="schedule-item" onclick="showItem('${i.id}')"><b>${esc(i.code)} · ${esc(i.trade||"No trade")}</b><small>${esc([i.building,i.level,i.unit,i.room].filter(Boolean).join(" · ")||"No location")} · ${esc(i.subcontractor||"Unassigned")}</small></button>`).join(""):`<div class="schedule-item"><b>No items due today</b><small>Good breathing room — keep capture moving.</small></div>`;
    const next=active.sort((a,b)=>(overdue(a)?0:a.status==="ready_for_review"?1:a.status==="open"?2:3)-(overdue(b)?0:b.status==="ready_for_review"?1:b.status==="open"?2:3)||a.dueDate.localeCompare(b.dueDate)).slice(0,4);
    return `<header class="screen-header rounded"><div class="header-row"><div class="logo-box">CLEANRUN <span style="color:#16a34a">IQ</span></div><button class="circle-btn" onclick="go('items')">⌕</button></div><button class="project-selector" onclick="projectPicker()"><span><small>Active project</small><b>${esc(p)}</b></span><span>⌄</span></button><div class="sync">All changes synced</div></header><div class="screen-scroll home-dashboard"><button class="capture-cta" onclick="go('capture')"><span class="plus">+</span><span><b>Capture Item</b><small>Photo, voice-to-note or walk capture</small></span><span class="chev">›</span></button><section class="native-card dashboard-hero"><div class="spread"><div><h2>Closeout control room</h2><p class="meta">Live subcontractor, trade and schedule performance for ${esc(p)}.</p></div><button class="btn alt small" onclick="openHomeBucket('all')">All items</button></div><div class="gamify-strip"><span><b>${closeoutPct}%</b> closeout rate</span><span><b>${activityPct}%</b> activity today</span><span><b>${topSub?esc(topSub.name):"—"}</b> most open defects</span></div></section><div class="dashboard-kpis"><button class="dashboard-kpi" onclick="openHomeBucket('open')"><b>${items.filter(i=>i.status==="open").length}</b><span>Captured</span><small>awaiting issue</small></button><button class="dashboard-kpi" onclick="openHomeBucket('issued')"><b>${issued.length}</b><span>Issued</span><small>with subcontractors</small></button><button class="dashboard-kpi" onclick="openHomeBucket('attention')"><b>${overdueItems.length}</b><span>Overdue</span><small>needs attention</small></button><button class="dashboard-kpi" onclick="openHomeBucket('ready')"><b>${ready.length}</b><span>Ready</span><small>to inspect</small></button></div><section class="dashboard-board"><div class="dashboard-panel"><h3>Subcontractor performance</h3>${subPerf.length?subPerf.map(perfRow).join(""):`<p class="meta">No subcontractor assignments yet.</p>`}</div><div class="dashboard-panel"><h3>Trade pressure</h3>${tradePerf.length?tradePerf.map(perfRow).join(""):`<p class="meta">No trade data yet.</p>`}</div></section><section class="dashboard-board"><div class="dashboard-panel"><h3>Today's schedule</h3><div class="dashboard-schedule">${schedule}</div></div><div class="dashboard-panel"><h3>Quick focus</h3><button class="dashboard-row" onclick="openDashboardSearch(decodeURIComponent('${safeQuery(topTrade?.name||"")}'))"><span><strong>${topTrade?esc(topTrade.name):"No trade pressure"}</strong><small>Highest open trade workload</small></span><span class="dashboard-score">${topTrade?topTrade.open:0}</span></button><button class="dashboard-row" onclick="go('reports')"><span><strong>${closed.length}/${assigned.length||items.length} closed</strong><small>Closeout progress across assigned work</small></span><span class="dashboard-score">${closeoutPct}%</span></button></div></section><div class="section-head"><h2>Next to deal with</h2><button onclick="go('items')">View all</button></div><div class="list">${next.map(itemCard).join("")||`<div class="native-card empty">✓<br><b>All clear on ${esc(p)}</b><br>Nothing open right now.</div>`}</div></div>`;
  };

  function subProfile(name){const profile=state.settings.subProfiles?.[name]||{},contacts=Array.isArray(profile.contacts)&&profile.contacts.length?profile.contacts:[{name:profile.contact||"",role:"Primary",email:profile.email||"",mobile:profile.mobile||profile.phone||""}];return {...profile,name,companyName:profile.companyName||profile.name||name,tradeType:profile.tradeType||profile.trade||"",contacts}}
  function contactRows(profile){return profile.contacts.map((c,n)=>`<div class="contact-row"><input name="contactName-${n}" placeholder="Contact name" value="${esc(c.name)}"><input name="contactRole-${n}" placeholder="Role" value="${esc(c.role)}"><input name="contactEmail-${n}" placeholder="Email" value="${esc(c.email)}"><input name="contactMobile-${n}" placeholder="Mobile" value="${esc(c.mobile)}"><button class="btn alt small" type="button" onclick="this.closest('.contact-row').remove()">Remove</button></div>`).join("")}
  window.addContactRow=function(){const host=$("#subContacts"),n=host.querySelectorAll(".contact-row").length;host.insertAdjacentHTML("beforeend",`<div class="contact-row"><input name="contactName-${n}" placeholder="Contact name"><input name="contactRole-${n}" placeholder="Role"><input name="contactEmail-${n}" placeholder="Email"><input name="contactMobile-${n}" placeholder="Mobile"><button class="btn alt small" type="button" onclick="this.closest('.contact-row').remove()">Remove</button></div>`)};
  window.editSubcontractorProfile=function(name){const p=subProfile(name);$("#modalTitle").textContent=`Subcontractor · ${p.companyName}`;$("#modalBody").innerHTML=`<form class="field-list" onsubmit="saveSubcontractorProfile(event,'${esc(name)}')"><div class="fields admin-form-grid"><label>Company Name<input name="companyName" value="${esc(p.companyName)}" required></label><label>Trade Type<select name="tradeType"><option value=""></option>${options(trades,p.tradeType)}</select></label><label>Primary Contact<input name="contact" value="${esc(p.contact||p.contacts[0]?.name||"")}"></label><label>Email<input type="email" name="email" value="${esc(p.email||p.contacts[0]?.email||"")}"></label><label>Mobile<input name="mobile" value="${esc(p.mobile||p.phone||p.contacts[0]?.mobile||"")}"></label></div><section class="edit-evidence"><div class="spread"><div><b>Additional contacts</b><div class="meta">Add supervisors, PMs, after-hours contacts or accounts contacts.</div></div><button class="btn alt" type="button" onclick="addContactRow()">+ Add contact</button></div><div id="subContacts" class="contact-grid">${contactRows(p)}</div></section><button class="btn">Save subcontractor</button></form>`;$("#modal").hidden=false};
  window.saveSubcontractorProfile=async function(e,name){e.preventDefault();const form=e.currentTarget,data=Object.fromEntries(new FormData(form)),s=structuredClone(state.settings),contacts=[];form.querySelectorAll(".contact-row").forEach(row=>{const inputs=row.querySelectorAll("input"),contact={name:inputs[0].value.trim(),role:inputs[1].value.trim(),email:inputs[2].value.trim(),mobile:inputs[3].value.trim()};if(contact.name||contact.email||contact.mobile)contacts.push(contact)});const oldName=name,newName=data.companyName.trim();s.subProfiles=s.subProfiles||{};s.subcontractors=s.subcontractors.map(n=>n===oldName?newName:n);if(!s.subcontractors.includes(newName))s.subcontractors.push(newName);s.subcontractors=[...new Set(s.subcontractors)].sort();if(newName!==oldName)delete s.subProfiles[oldName];s.subProfiles[newName]={name:newName,companyName:newName,trade:data.tradeType,tradeType:data.tradeType,contact:data.contact,email:data.email,mobile:data.mobile,phone:data.mobile,contacts};await api("/api/settings",{method:"POST",body:JSON.stringify({subcontractors:s.subcontractors,subProfiles:s.subProfiles})});await reload();closeModal();route="settings";render();toast("Subcontractor profile saved")};
  addSubcontractor=async function(){const name=prompt("Company Name:","");if(!name)return;const s=structuredClone(state.settings);s.subProfiles=s.subProfiles||{};if(!s.subcontractors.includes(name))s.subcontractors.push(name);s.subcontractors.sort();s.subProfiles[name]={name,companyName:name,trade:"",tradeType:"",contact:"",email:"",mobile:"",contacts:[]};await api("/api/settings",{method:"POST",body:JSON.stringify({subcontractors:s.subcontractors,subProfiles:s.subProfiles})});await reload();editSubcontractorProfile(name)};
  window.toggleDesktopTheme=async function(){const next=preferredTheme()==="dark"?"light":"dark";localStorage.setItem(THEME_KEY,next);state.settings.theme=next;document.documentElement.dataset.theme=next;await api("/api/settings",{method:"POST",body:JSON.stringify({theme:next})});await reload();route="settings";render()};
  function subcontractorAdminPanel(){
    const s=state.settings;
    return `<section class="form-card subcontractor-admin"><div class="spread"><div><h2>Subcontractor database (${s.subcontractors.length})</h2><p class="meta">Company, trade, contact, email, mobile and multiple contacts.</p></div><button class="btn alt" type="button" onclick="addSubcontractor()">+ Add</button></div>${s.subcontractors.map(n=>{const p=subProfile(n);return `<button type="button" class="sub-profile-card" onclick="editSubcontractorProfile('${esc(n)}')"><b>${esc(p.companyName)}</b><span>${esc(p.tradeType||"No trade type")} · ${esc(p.contact||p.contacts[0]?.name||"No contact")}</span><small>${esc(p.email||p.contacts[0]?.email||"No email")} · ${esc(p.mobile||p.phone||p.contacts[0]?.mobile||"No mobile")} · ${p.contacts.length} contact${p.contacts.length===1?"":"s"}</small></button>`}).join("")}</section>`;
  }
  settingsView=function(){const s=state.settings,theme=preferredTheme();return `${subHeader("Settings & Admin")}<form class="settings-scroll" onsubmit="saveSettings(event)"><section class="form-card"><h2>Company & branding</h2><div class="field-list"><label>Company name<input name="company" value="${esc(s.company)}"></label><label>Prepared by<input name="preparedBy" value="${esc(s.preparedBy)}"></label></div><p class="meta">Used on report headers and audit events.</p><button class="btn" style="margin-top:10px">Save</button></section><section class="form-card"><h2>Desktop appearance</h2><p class="meta">Dark mode is active across desktop/admin screens and stays saved.</p><button class="btn alt" type="button" onclick="toggleDesktopTheme()">Dark / night mode: ${theme==="dark"?"On":"Off"}</button></section><section class="form-card"><h2>Projects</h2>${s.projects.map(p=>`<div class="spread" style="padding:10px 0;border-bottom:1px solid var(--line)"><b>${esc(p)}</b>${p===s.activeProject?'<span class="badge complete">Active</span>':""}</div>`).join("")}<div class="actions" style="margin-top:12px"><input id="newProject" placeholder="Add a project…"><button class="btn" type="button" onclick="addProject()">+</button></div></section>${subcontractorAdminPanel()}<section class="form-card"><h2>Demo data</h2><button class="btn danger" type="button" onclick="resetDemo()">↻ Reset to demo data</button></section><div class="meta" style="text-align:center">CleanRun IQ Field App</div></form>`};
  const originalSubcontractorView=subcontractorView;
  subcontractorView=function(){
    const admin=`${subHeader("Subcontractors")}<div class="settings-scroll">${subcontractorAdminPanel()}<section class="form-card"><div class="spread"><div><h2>Assigned work mode</h2><p class="meta">Use this when a trade is uploading rectification evidence.</p></div><button class="btn alt" type="button" onclick="document.getElementById('subWorkMode')?.scrollIntoView({behavior:'smooth'})">Go to work mode</button></div></section><div id="subWorkMode">${originalSubcontractorView()}</div></div>`;
    return admin;
  };

  function updateOfflinePill(force){
    let pill=$("#offlinePill");if(!pill){pill=document.createElement("div");pill.id="offlinePill";pill.className="offline-pill";document.body.appendChild(pill)}
    pill.onclick=flushQueue;
    const count=pendingQueue().length;if(force==="syncing"){pill.hidden=false;pill.className="offline-pill syncing";pill.textContent="↻ Syncing field changes…";return}
    const offline=!navigator.onLine;
    pill.hidden=!offline&&!count;
    pill.className=`offline-pill${offline?" offline":count?" waiting":""}`;
    pill.textContent=offline?`Offline · ${count} queued`:count?`Online · ${count} waiting to sync`:"Online · synced";
  }

  moreView=function(){
    const s=state.settings;
    return `<header class="screen-header more-header"><div class="logo-box">CLEANRUN <span style="color:#16a34a">IQ</span></div><div style="color:#ffffffb3;margin-top:10px;font-size:13px">Field capture, review & closeout companion</div></header><div class="screen-scroll"><div class="native-card spread"><span style="font-size:22px;color:#16a34a">Sync</span><span style="flex:1"><b>Online</b><small class="meta" style="display:block">All field data synced</small></span><span class="badge"><b>${state.items.length}</b><br>items</span></div>${menuGroup("Closeout workflow",[["Review","Review Queue","Inspect ready work and close/reject","review"],["Plans","Plans","PDF plans & pinned issue locations","plans"]])}${menuGroup("Reporting",[["Report","Reports & Handover","Evidence-chain & closeout reports","reports"]])}${menuGroup("Field roles",[["Subs","Subcontractor Mode","Assigned items & rectification upload","subcontractor"]])}${menuGroup("Admin",[["Setup","Project Setup","Buildings, levels, units & rooms","setup"],["Admin","Settings & Admin","Company, subcontractors, demo data","settings"]])}<div class="meta" style="text-align:center">CleanRun IQ Field App - ${esc(s.company)}</div></div>`;
  };

  function renderMobileNav(){
    if(matchMedia("(min-width:1024px)").matches)return;
    const ready=(state?.items||[]).filter(i=>i.project===state.settings.activeProject&&["ready_for_review","under_inspection"].includes(i.status)).length;
    const items=[["home","Home",navIcon?.home||"⌂"],["items","Items",navIcon?.items||"▤"],["capture","Capture","+"],["review",ready?`Review ${ready}`:"Review","✓"],["more","More",navIcon?.more||"•••"]];
    const active=["reports","settings","setup","subcontractor","plans"].includes(route)?"more":route;
    $("#nav").innerHTML=items.map(([to,label,icon])=>`<button class="${active===to?'active':''} ${to==='capture'?'capture-tab':''}" onclick="go('${to}')"><span class="tab-icon">${icon}</span><span>${label}</span></button>`).join("");
  }

  function renderDesktopNav(){
    if(!matchMedia("(min-width:1024px)").matches)return;
    const items=[
      ["home","Home",navIcon?.home||"⌂"],
      ["items","Items",navIcon?.items||"▤"],
      ["capture","Capture","+"],
      ["review","Review","✓"],
      ["plans","Plans","⌖"],
      ["more","More",navIcon?.more||"•••"]
    ];
    const active=["reports","setup","settings","subcontractor"].includes(route)?"more":route;
    $("#nav").innerHTML=items.map(([to,label,icon])=>`<button class="${active===to?'active':''} ${to==='capture'?'capture-tab':''}" onclick="go('${to}')"><span class="tab-icon">${icon}</span><span>${label}</span></button>`).join("");
  }
  const originalRender=render;
  render=function(){
    document.body.dataset.route=route;applyTheme();
    if(route==="review"){$("#app").innerHTML=reviewView();$("#nav").innerHTML="";renderMobileNav();renderDesktopNav();updateOfflinePill();return}
    originalRender();renderMobileNav();renderDesktopNav();
    if(route==="capture"){const photoCard=$("#capturePreviews")?.closest("section");photoCard?.setAttribute("data-photo-card","true");renderCapturePreviews()}
    updateOfflinePill();
  };
  window.addEventListener("online",flushQueue);window.addEventListener("offline",updateOfflinePill);
  async function initialiseOfflineStore(){offlineQueue=await dbGet(QUEUE_KEY)||[];updateOfflinePill();setTimeout(flushQueue,500)}
  if("serviceWorker" in navigator){
    let refreshing=false;
    navigator.serviceWorker.addEventListener("controllerchange",()=>{if(refreshing)return;refreshing=true;location.reload()});
    navigator.serviceWorker.register("/service-worker.js").then(reg=>{
      if(reg.waiting)reg.waiting.postMessage("SKIP_WAITING");
      reg.addEventListener("updatefound",()=>{
        const worker=reg.installing;
        worker?.addEventListener("statechange",()=>{if(worker.state==="installed"&&navigator.serviceWorker.controller)worker.postMessage("SKIP_WAITING")});
      });
    }).catch(()=>{});
  }
  function rerenderLatestHome(){if(typeof state!=="undefined"&&state&&route==="home")render()}
  ensureWorkbench();updateOfflinePill();setTimeout(rerenderLatestHome,0);setTimeout(rerenderLatestHome,250);window.addEventListener("load",rerenderLatestHome);initialiseOfflineStore();
})();
