(function(){
  "use strict";

  const CACHE_KEY="cleanrun-offline-state-v1";
  const QUEUE_KEY="cleanrun-offline-queue-v1";
  const DB_NAME="cleanrun-iq-offline";
  let capturePhotoMeta=[];
  let editPhotos=[];
  let editPhotoMeta=[];
  let selectedEditItem="";
  let lastChosenPhotoMeta=null;
  let workbench={source:"",title:"Photo evidence",save:null,drawing:false,last:null,history:[]};
  let offlineQueue=[];

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
  captureView=function(){const html=originalCaptureView();setTimeout(renderCapturePreviews,0);return html};

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

  chooseImage=function(){return new Promise(resolve=>{const input=document.createElement("input");input.type="file";input.accept="image/*";input.onchange=async()=>{const records=await filesWithMeta(input.files||[]);lastChosenPhotoMeta=records[0]?.meta||null;resolve(records[0]?.src)};input.click()})};

  itemAction=async function(id,act){
    const i=state.items.find(x=>x.id===id),body={by:state.settings.preparedBy};
    if(act==="issue"){body.to=i.subcontractor||prompt("Subcontractor name:","");body.reissue=i.status==="rejected"}
    if(act==="reject"||act==="reopen")body.reason=prompt(act==="reject"?"Why is this being rejected?":"Reason for reopening:","");
    if(act==="rectification"){body.comment=prompt("Rectification comment:","");body.photo=await chooseImage();body.photoMeta=lastChosenPhotoMeta;body.advanceToReady=confirm("Mark ready for review after saving evidence?")}
    if(act==="close"){body.role=prompt("Signed off by role:","Site Manager")||"Site Manager";body.note=prompt("Closeout note (optional):","");if(i.type!=="incomplete"){body.photo=await chooseImage();body.photoMeta=lastChosenPhotoMeta}body.confirmed=confirm(`I confirm this item is rectified and accepted by ${state.settings.preparedBy}.`)}
    try{await api(`/api/items/${id}/actions/${act}`,{method:"POST",body:JSON.stringify(body)});await reload();showItem(id);toast("Item updated")}catch(err){toast(err.message,true)}
  };

  saveCapture=async function(e){
    e.preventDefault();
    const form=e.currentTarget,data=Object.fromEntries(new FormData(form)),mode=e.submitter?.value||"save";
    const release=setBusyButton(e.submitter,mode==="issue"?"Issuing…":"Saving…");
    data.id=offlineId();data.createdBy=state.settings.preparedBy;data.originalPhotos=capturePhotos;data.originalPhotoMeta=capturePhotoMeta;
    const voice=$("#voiceText").value.trim();if(voice){data.voiceTranscript=voice;data.voiceNote={transcript:voice,createdAt:new Date().toISOString(),status:"parsed"}}
    if(data.type==="client"&&!data.raisedBy){release();return toast("A Client Defect requires a Raised By / source.",true)}
    if(mode==="issue"&&(!data.trade||!data.subcontractor)){release();return toast("Issue Now requires a trade and subcontractor.",true)}
    try{
      toast(capturePhotos.length?"Compressing and uploading evidence…":"Saving item…");
      const item=await api("/api/items",{method:"POST",body:JSON.stringify(data)});
      if(mode==="issue")await api(`/api/items/${item.id}/actions/issue`,{method:"POST",body:JSON.stringify({to:data.subcontractor,by:data.createdBy})});
      capturePhotos=[];capturePhotoMeta=[];
      if(walkMode){walkCount++;await reload();route="capture";render();toast(`${item.code} saved · continue walk`)}
      else{await reload();route="items";render();setTimeout(()=>scrollTo(0,0),0);toast(item.sync==="queued"?`${item.code} saved offline · queued to sync`:`${item.code} saved`)}
    }catch(err){toast(err.message,true)}finally{release()}
  };

  itemAction=async function(id,act){
    const i=state.items.find(x=>x.id===id),body={by:state.settings.preparedBy};
    const release=setBusyButton(document.activeElement,"Working…");
    if(act==="issue"){body.to=i.subcontractor||prompt("Subcontractor name:","");body.reissue=i.status==="rejected"}
    if(act==="reject"||act==="reopen")body.reason=prompt(act==="reject"?"Why is this being rejected?":"Reason for reopening:","");
    if(act==="rectification"){body.comment=prompt("Rectification comment:","");body.photo=await chooseImage();body.photoMeta=lastChosenPhotoMeta;body.advanceToReady=confirm("Mark ready for review after saving evidence?")}
    if(act==="close"){body.role=prompt("Signed off by role:","Site Manager")||"Site Manager";body.note=prompt("Closeout note (optional):","");if(i.type!=="incomplete"){body.photo=await chooseImage();body.photoMeta=lastChosenPhotoMeta}body.confirmed=confirm(`I confirm this item is rectified and accepted by ${state.settings.preparedBy}.`)}
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
      const item={status:"open",createdAt:at,updatedAt:at,rectificationEvidence:[],closeoutEvidence:[],comments:[],issueHistory:[],inspectionHistory:[],auditEvents:[{at,action:"Created offline",by:body.createdBy}],sync:"queued",...body,code:`OFF-${String(Date.now()).slice(-4)}`};state.items.unshift(item);cacheState();return item;
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
    if(bucket==="open")itemStatusFilter="Open";
    if(bucket==="attention")itemStatusFilter="Overdue";
    if(bucket==="ready")itemStatusFilter="Ready for Review";
    render();
    setTimeout(()=>{document.querySelectorAll("#statusFilters button").forEach(btn=>btn.classList.toggle("active",btn.dataset.value===itemStatusFilter));filterItems();scrollTo(0,0)},0);
  };

  dashboardView=function(){
    const p=state.settings.activeProject,items=state.items.filter(i=>i.project===p),stats={open:items.filter(i=>i.status==="open").length,overdue:items.filter(overdue).length,ready:items.filter(i=>i.status==="ready_for_review").length,closed:items.filter(i=>["closed","complete"].includes(i.status)&&i.closedAt?.slice(0,10)===new Date().toISOString().slice(0,10)).length},attention=items.filter(i=>overdue(i)||i.status==="rejected"),ready=items.filter(i=>i.status==="ready_for_review"),rank={rejected:1,ready_for_review:2,open:3};
    const next=items.filter(i=>!["closed","complete"].includes(i.status)).sort((a,b)=>(overdue(a)?0:rank[a.status]||4)-(overdue(b)?0:rank[b.status]||4)||a.dueDate.localeCompare(b.dueDate)).slice(0,4);
    return `<header class="screen-header rounded"><div class="header-row"><div class="logo-box">CLEANRUN <span style="color:#16a34a">IQ</span></div><button class="circle-btn" onclick="go('items')">⌕</button></div><button class="project-selector" onclick="projectPicker()"><span><small>Active project</small><b>${esc(p)}</b></span><span>⌄</span></button><div class="sync">All changes synced</div></header><div class="screen-scroll"><button class="capture-cta" onclick="go('capture')"><span class="plus">+</span><span><b>Capture Item</b><small>Photo, voice-to-note or walk capture</small></span><span class="chev">›</span></button><div class="native-grid"><button class="native-stat dashboard-stat" style="--tone:#0e1f3a" onclick="openHomeBucket('open')"><b>${stats.open}</b><span>Open</span></button><button class="native-stat dashboard-stat" style="--tone:#dc2626" onclick="openHomeBucket('attention')"><b>${stats.overdue}</b><span>Overdue</span></button><button class="native-stat dashboard-stat" style="--tone:#7c3aed" onclick="openHomeBucket('ready')"><b>${stats.ready}</b><span>Ready for Review</span></button><button class="native-stat dashboard-stat" style="--tone:#16a34a" onclick="go('reports')"><b>${stats.closed}</b><span>Closed Today</span></button></div>${attention.length?`<button class="notice red dashboard-jump" onclick="openHomeBucket('attention')"><span>⚠</span><span><strong>${attention.length} need your attention</strong><small>Overdue or rejected items</small></span><span class="chev">›</span></button>`:""}${ready.length?`<button class="notice violet dashboard-jump" onclick="openHomeBucket('ready')"><span>✓</span><span><strong>${ready.length} ready to inspect</strong><small>Subcontractor marked ready for review</small></span><span class="chev">›</span></button>`:""}<section class="native-card admin-dashboard"><div class="spread"><div><h2>Desktop dashboard</h2><p class="meta">Live workload by trade, status and evidence count.</p></div><button class="btn alt small" onclick="go('items')">Manage items</button></div><div class="admin-kpis"><span><b>${items.filter(i=>i.subcontractor).length}</b> assigned</span><span><b>${items.reduce((n,i)=>n+(i.originalPhotos||[]).length,0)}</b> original photos</span><span><b>${items.filter(i=>i.status==="ready_for_review").length}</b> inspections waiting</span></div></section><div class="section-head"><h2>Next to deal with</h2><button onclick="go('items')">View all</button></div><div class="list">${next.map(itemCard).join("")||`<div class="native-card empty">✓<br><b>All clear on ${esc(p)}</b><br>Nothing open right now.</div>`}</div></div>`;
  };

  function subProfile(name){const profile=state.settings.subProfiles?.[name]||{},contacts=Array.isArray(profile.contacts)&&profile.contacts.length?profile.contacts:[{name:profile.contact||"",role:"Primary",email:profile.email||"",mobile:profile.mobile||profile.phone||""}];return {...profile,name,companyName:profile.companyName||profile.name||name,tradeType:profile.tradeType||profile.trade||"",contacts}}
  function contactRows(profile){return profile.contacts.map((c,n)=>`<div class="contact-row"><input name="contactName-${n}" placeholder="Contact name" value="${esc(c.name)}"><input name="contactRole-${n}" placeholder="Role" value="${esc(c.role)}"><input name="contactEmail-${n}" placeholder="Email" value="${esc(c.email)}"><input name="contactMobile-${n}" placeholder="Mobile" value="${esc(c.mobile)}"><button class="btn alt small" type="button" onclick="this.closest('.contact-row').remove()">Remove</button></div>`).join("")}
  window.addContactRow=function(){const host=$("#subContacts"),n=host.querySelectorAll(".contact-row").length;host.insertAdjacentHTML("beforeend",`<div class="contact-row"><input name="contactName-${n}" placeholder="Contact name"><input name="contactRole-${n}" placeholder="Role"><input name="contactEmail-${n}" placeholder="Email"><input name="contactMobile-${n}" placeholder="Mobile"><button class="btn alt small" type="button" onclick="this.closest('.contact-row').remove()">Remove</button></div>`)};
  window.editSubcontractorProfile=function(name){const p=subProfile(name);$("#modalTitle").textContent=`Subcontractor · ${p.companyName}`;$("#modalBody").innerHTML=`<form class="field-list" onsubmit="saveSubcontractorProfile(event,'${esc(name)}')"><div class="fields admin-form-grid"><label>Company Name<input name="companyName" value="${esc(p.companyName)}" required></label><label>Trade Type<select name="tradeType"><option value=""></option>${options(trades,p.tradeType)}</select></label><label>Primary Contact<input name="contact" value="${esc(p.contact||p.contacts[0]?.name||"")}"></label><label>Email<input type="email" name="email" value="${esc(p.email||p.contacts[0]?.email||"")}"></label><label>Mobile<input name="mobile" value="${esc(p.mobile||p.phone||p.contacts[0]?.mobile||"")}"></label></div><section class="edit-evidence"><div class="spread"><div><b>Additional contacts</b><div class="meta">Add supervisors, PMs, after-hours contacts or accounts contacts.</div></div><button class="btn alt" type="button" onclick="addContactRow()">+ Add contact</button></div><div id="subContacts" class="contact-grid">${contactRows(p)}</div></section><button class="btn">Save subcontractor</button></form>`;$("#modal").hidden=false};
  window.saveSubcontractorProfile=async function(e,name){e.preventDefault();const form=e.currentTarget,data=Object.fromEntries(new FormData(form)),s=structuredClone(state.settings),contacts=[];form.querySelectorAll(".contact-row").forEach(row=>{const inputs=row.querySelectorAll("input"),contact={name:inputs[0].value.trim(),role:inputs[1].value.trim(),email:inputs[2].value.trim(),mobile:inputs[3].value.trim()};if(contact.name||contact.email||contact.mobile)contacts.push(contact)});const oldName=name,newName=data.companyName.trim();s.subProfiles=s.subProfiles||{};s.subcontractors=s.subcontractors.map(n=>n===oldName?newName:n);if(!s.subcontractors.includes(newName))s.subcontractors.push(newName);s.subcontractors=[...new Set(s.subcontractors)].sort();if(newName!==oldName)delete s.subProfiles[oldName];s.subProfiles[newName]={name:newName,companyName:newName,trade:data.tradeType,tradeType:data.tradeType,contact:data.contact,email:data.email,mobile:data.mobile,phone:data.mobile,contacts};await api("/api/settings",{method:"POST",body:JSON.stringify({subcontractors:s.subcontractors,subProfiles:s.subProfiles})});await reload();closeModal();route="settings";render();toast("Subcontractor profile saved")};
  addSubcontractor=async function(){const name=prompt("Company Name:","");if(!name)return;const s=structuredClone(state.settings);s.subProfiles=s.subProfiles||{};if(!s.subcontractors.includes(name))s.subcontractors.push(name);s.subcontractors.sort();s.subProfiles[name]={name,companyName:name,trade:"",tradeType:"",contact:"",email:"",mobile:"",contacts:[]};await api("/api/settings",{method:"POST",body:JSON.stringify({subcontractors:s.subcontractors,subProfiles:s.subProfiles})});await reload();editSubcontractorProfile(name)};
  window.toggleDesktopTheme=async function(){const next=(state.settings.theme||"light")==="dark"?"light":"dark";document.documentElement.dataset.theme=next;await api("/api/settings",{method:"POST",body:JSON.stringify({theme:next})});await reload();route="settings";render()};
  settingsView=function(){const s=state.settings,theme=s.theme||"light";return `${subHeader("Settings & Admin")}<form class="settings-scroll" onsubmit="saveSettings(event)"><section class="form-card"><h2>Company & branding</h2><div class="field-list"><label>Company name<input name="company" value="${esc(s.company)}"></label><label>Prepared by<input name="preparedBy" value="${esc(s.preparedBy)}"></label></div><p class="meta">Used on report headers and audit events.</p><button class="btn" style="margin-top:10px">Save</button></section><section class="form-card"><h2>Desktop appearance</h2><p class="meta">Dark mode starts on desktop/admin screens first.</p><button class="btn alt" type="button" onclick="toggleDesktopTheme()">Night mode: ${theme==="dark"?"On":"Off"}</button></section><section class="form-card"><h2>Projects</h2>${s.projects.map(p=>`<div class="spread" style="padding:10px 0;border-bottom:1px solid var(--line)"><b>${esc(p)}</b>${p===s.activeProject?'<span class="badge complete">Active</span>':""}</div>`).join("")}<div class="actions" style="margin-top:12px"><input id="newProject" placeholder="Add a project…"><button class="btn" type="button" onclick="addProject()">+</button></div></section><section class="form-card subcontractor-admin"><div class="spread"><div><h2>Subcontractor database (${s.subcontractors.length})</h2><p class="meta">Company, trade, contact, email, mobile and multiple contacts.</p></div><button class="btn alt" type="button" onclick="addSubcontractor()">+ Add</button></div>${s.subcontractors.map(n=>{const p=subProfile(n);return `<button type="button" class="sub-profile-card" onclick="editSubcontractorProfile('${esc(n)}')"><b>${esc(p.companyName)}</b><span>${esc(p.tradeType||"No trade type")} · ${esc(p.contact||p.contacts[0]?.name||"No contact")}</span><small>${esc(p.email||p.contacts[0]?.email||"")} ${esc(p.mobile||p.phone||p.contacts[0]?.mobile||"")}</small></button>`}).join("")}</section><section class="form-card"><h2>Demo data</h2><button class="btn danger" type="button" onclick="resetDemo()">↻ Reset to demo data</button></section><div class="meta" style="text-align:center">CleanRun IQ Field App</div></form>`};

  function updateOfflinePill(force){
    let pill=$("#offlinePill");if(!pill){pill=document.createElement("div");pill.id="offlinePill";pill.className="offline-pill";document.body.appendChild(pill)}
    const count=pendingQueue().length;if(force==="syncing"){pill.className="offline-pill syncing";pill.textContent="↻ Syncing field changes…";return}
    const offline=!navigator.onLine;pill.className=`offline-pill${offline?" offline":""}`;pill.textContent=offline?`Offline · ${count} queued`:count?`Online · ${count} waiting to sync`:"Online · synced";
  }

  function renderDesktopNav(){
    if(!matchMedia("(min-width:1024px)").matches)return;
    const items=[
      ["home","Home","⌂"],["items","Items","▤"],["capture","Capture","+"],["plans","Plans","⌖"],
      ["reports","Reports","▥"],["setup","Project Setup","⚙"],["settings","Settings","☷"],["subcontractor","Subcontractors","⛑"]
    ];
    $("#nav").innerHTML=items.map(([to,label,icon])=>`<button class="${route===to?'active':''} ${to==='capture'?'capture-tab':''}" onclick="go('${to}')"><span class="tab-icon">${icon}</span><span>${label}</span></button>`).join("");
  }
  const originalRender=render;
  render=function(){document.body.dataset.route=route;if(typeof state!=="undefined"&&state)document.documentElement.dataset.theme=state.settings?.theme||"light";originalRender();renderDesktopNav();if(route==="capture")renderCapturePreviews();updateOfflinePill()};
  window.addEventListener("online",flushQueue);window.addEventListener("offline",updateOfflinePill);
  async function initialiseOfflineStore(){offlineQueue=await dbGet(QUEUE_KEY)||[];updateOfflinePill();setTimeout(flushQueue,500)}
  if("serviceWorker" in navigator)navigator.serviceWorker.register("/service-worker.js").catch(()=>{});
  ensureWorkbench();updateOfflinePill();setTimeout(()=>{if(typeof state!=="undefined"&&state)render()},0);initialiseOfflineStore();
})();
