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
    const [sources,geo]=await Promise.all([filesToData(list),locatePhoto()]);
    return sources.map((src,n)=>({src,meta:{...geo,fileName:list[n]?.name||`photo-${n+1}.jpg`,mimeType:list[n]?.type||"image/jpeg"}}));
  }

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
    document.body.insertAdjacentHTML("beforeend",`<section class="photo-workbench" id="photoWorkbench" hidden aria-modal="true"><div class="photo-workbench__panel"><header class="photo-workbench__head"><strong id="photoWorkbenchTitle">Photo evidence</strong><button type="button" onclick="closePhotoWorkbench()">Close</button></header><div class="photo-workbench__stage"><canvas id="markupCanvas"></canvas></div><footer class="photo-workbench__tools"><label>Pen <input id="markupColor" type="color" value="#E5483B"></label><label>Width <input id="markupWidth" type="range" min="2" max="18" value="6"></label><button type="button" onclick="undoPhotoMarkup()">Undo</button><button type="button" onclick="resetPhotoMarkup()">Reset</button><button class="primary" id="saveMarkup" type="button" onclick="savePhotoMarkup()">Save marked-up copy</button></footer></div></section>`);
    const canvas=$("#markupCanvas");
    const point=e=>{const r=canvas.getBoundingClientRect(),p=e.touches?.[0]||e;return{x:(p.clientX-r.left)*canvas.width/r.width,y:(p.clientY-r.top)*canvas.height/r.height}};
    const start=e=>{if(!workbench.save)return;e.preventDefault();workbench.history.push(canvas.toDataURL("image/png"));workbench.drawing=true;workbench.last=point(e)};
    const move=e=>{if(!workbench.drawing)return;e.preventDefault();const p=point(e),ctx=canvas.getContext("2d");ctx.strokeStyle=$("#markupColor").value;ctx.lineWidth=Number($("#markupWidth").value);ctx.lineCap="round";ctx.lineJoin="round";ctx.beginPath();ctx.moveTo(workbench.last.x,workbench.last.y);ctx.lineTo(p.x,p.y);ctx.stroke();workbench.last=p};
    const stop=()=>{workbench.drawing=false;workbench.last=null};
    canvas.addEventListener("pointerdown",start);canvas.addEventListener("pointermove",move);canvas.addEventListener("pointerup",stop);canvas.addEventListener("pointerleave",stop);
  }

  function drawSource(src){
    const img=new Image();img.onload=()=>{const canvas=$("#markupCanvas"),scale=Math.min(1,1400/img.naturalWidth,900/img.naturalHeight);canvas.width=Math.max(1,Math.round(img.naturalWidth*scale));canvas.height=Math.max(1,Math.round(img.naturalHeight*scale));canvas.getContext("2d").drawImage(img,0,0,canvas.width,canvas.height);workbench.history=[]};img.src=src;
  }
  function openWorkbench(src,title,onSave){ensureWorkbench();workbench={source:src,title,save:onSave,drawing:false,last:null,history:[]};$("#photoWorkbenchTitle").textContent=title;$("#saveMarkup").hidden=!onSave;$("#photoWorkbench").hidden=false;drawSource(src)}
  window.closePhotoWorkbench=()=>{$("#photoWorkbench").hidden=true};
  window.resetPhotoMarkup=()=>drawSource(workbench.source);
  window.undoPhotoMarkup=()=>{const previous=workbench.history.pop();if(previous)drawSource(previous)};
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
    data.id=offlineId();data.createdBy=state.settings.preparedBy;data.originalPhotos=capturePhotos;data.originalPhotoMeta=capturePhotoMeta;
    const voice=$("#voiceText").value.trim();if(voice){data.voiceTranscript=voice;data.voiceNote={transcript:voice,createdAt:new Date().toISOString(),status:"parsed"}}
    if(data.type==="client"&&!data.raisedBy)return toast("A Client Defect requires a Raised By / source.",true);
    if(mode==="issue"&&(!data.trade||!data.subcontractor))return toast("Issue Now requires a trade and subcontractor.",true);
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

  function updateOfflinePill(force){
    let pill=$("#offlinePill");if(!pill){pill=document.createElement("div");pill.id="offlinePill";pill.className="offline-pill";document.body.appendChild(pill)}
    const count=pendingQueue().length;if(force==="syncing"){pill.className="offline-pill syncing";pill.textContent="↻ Syncing field changes…";return}
    const offline=!navigator.onLine;pill.className=`offline-pill${offline?" offline":""}`;pill.textContent=offline?`Offline · ${count} queued`:count?`Online · ${count} waiting to sync`:"Online · synced";
  }

  const originalRender=render;
  render=function(){document.body.dataset.route=route;originalRender();if(route==="capture")renderCapturePreviews();updateOfflinePill()};
  window.addEventListener("online",flushQueue);window.addEventListener("offline",updateOfflinePill);
  async function initialiseOfflineStore(){offlineQueue=await dbGet(QUEUE_KEY)||[];updateOfflinePill();setTimeout(flushQueue,500)}
  if("serviceWorker" in navigator)navigator.serviceWorker.register("/service-worker.js").catch(()=>{});
  ensureWorkbench();updateOfflinePill();setTimeout(()=>{if(typeof state!=="undefined"&&state)render()},0);initialiseOfflineStore();
})();
