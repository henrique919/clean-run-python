(function(){
  "use strict";

  window.CLEANRUN_FRONTEND_BUILD="cards29";
  document.documentElement.dataset.cleanrunBuild="cards29";
  document.documentElement.dataset.theme=localStorage.getItem("cleanrun-theme")||document.documentElement.dataset.theme||"light";
  const CACHE_KEY="cleanrun-offline-state-v1";
  const QUEUE_KEY="cleanrun-offline-queue-v1";
  const DB_NAME="cleanrun-iq-offline";
  const THEME_KEY="cleanrun-theme";
  const LAST_CAPTURE_KEY="cleanrun-last-capture-fields";
  const WALK_CONTEXT_KEY="cleanrun-walk-context-v1";
  let capturePhotoMeta=[];
  let capturePhotoPreviewUrls=[];
  let editPhotos=[];
  let editPhotoMeta=[];
  let editPhotoPreviewUrls=[];
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
  const PHOTO_SKIP_BYTES=900000;

  const yieldToMain=()=>new Promise(resolve=>{
    if(typeof requestAnimationFrame==="function")requestAnimationFrame(()=>setTimeout(resolve,0));
    else setTimeout(resolve,0);
  });

  function revokePreviewUrl(url){
    if(url&&String(url).startsWith("blob:"))try{URL.revokeObjectURL(url)}catch{}
  }

  function revokePreviewUrls(urls){
    (urls||[]).forEach(revokePreviewUrl);
  }

  function readFileData(file){
    return new Promise((resolve,reject)=>{
      const reader=new FileReader();
      reader.onload=()=>resolve(reader.result);
      reader.onerror=()=>reject(reader.error);
      reader.readAsDataURL(file);
    });
  }

  function blobToDataUrl(blob){
    return new Promise((resolve,reject)=>{
      const reader=new FileReader();
      reader.onload=()=>resolve(reader.result);
      reader.onerror=()=>reject(reader.error);
      reader.readAsDataURL(blob);
    });
  }

  function canvasToJpegBlob(canvas,quality=PHOTO_QUALITY){
    return new Promise((resolve,reject)=>{
      canvas.toBlob(blob=>blob?resolve(blob):reject(new Error("Could not compress image.")), "image/jpeg", quality);
    });
  }

  async function decodeImageSource(file,objectUrl){
    if(typeof createImageBitmap==="function"){
      try{
        const bitmap=await createImageBitmap(file,{imageOrientation:"from-image"});
        return {width:bitmap.width,height:bitmap.height,draw:(ctx,x,y,w,h)=>{ctx.drawImage(bitmap,x,y,w,h);bitmap.close?.()}};
      }catch{}
    }
    const img=await new Promise((resolve,reject)=>{
      const image=new Image();
      image.onload=()=>resolve(image);
      image.onerror=reject;
      image.src=objectUrl;
    });
    return {width:img.naturalWidth,height:img.naturalHeight,draw:(ctx,x,y,w,h)=>ctx.drawImage(img,x,y,w,h)};
  }

  async function compressImageForUpload(file){
    if(!file?.type?.startsWith("image/"))return {dataUrl:await readFileData(file),previewUrl:null};
    const objectUrl=URL.createObjectURL(file);
    try{
      await yieldToMain();
      const decoded=await decodeImageSource(file,objectUrl);
      const scale=Math.min(1,MAX_PHOTO_EDGE/decoded.width,MAX_PHOTO_EDGE/decoded.height);
      if(scale>=1&&file.size<PHOTO_SKIP_BYTES){
        const dataUrl=await readFileData(file);
        return {dataUrl,previewUrl:URL.createObjectURL(file)};
      }
      const width=Math.max(1,Math.round(decoded.width*scale));
      const height=Math.max(1,Math.round(decoded.height*scale));
      const canvas=document.createElement("canvas");
      canvas.width=width;
      canvas.height=height;
      const ctx=canvas.getContext("2d",{alpha:false});
      ctx.fillStyle="#fff";
      ctx.fillRect(0,0,width,height);
      decoded.draw(ctx,0,0,width,height);
      await yieldToMain();
      const blob=await canvasToJpegBlob(canvas);
      return {dataUrl:await blobToDataUrl(blob),previewUrl:URL.createObjectURL(blob)};
    }catch(err){
      console.warn("[CleanRun] image compression failed; using original",err);
      const dataUrl=await readFileData(file);
      return {dataUrl,previewUrl:URL.createObjectURL(file)};
    }finally{
      URL.revokeObjectURL(objectUrl);
    }
  }

  async function fileToUploadData(file){
    return (await compressImageForUpload(file)).dataUrl;
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
  function ensureCaptureDescription(data,voiceText){
    const text=String(data.description||"").trim();
    if(text){data.description=text;return data.description}
    const voice=String(voiceText||"").trim();
    if(voice){data.description=voice;return data.description}
    const where=[data.room,data.unit,data.level,data.building].filter(Boolean).join(" · ");
    data.description=where?`Defect — ${where}`:"Site defect";
    return data.description;
  }
  function itemSearchHaystack(i){
    return [i.code,i.description,i.building,i.level,i.unit,i.room,i.trade,i.subcontractor,i.status,i.type,labels?.[i.status],typeLabels?.[i.type]].filter(Boolean).join(" ").toLowerCase();
  }
  function mergeSavedItem(item){
    if(!item||!state?.items)return;
    const idx=state.items.findIndex(x=>x.id===item.id);
    if(idx>=0)state.items[idx]={...state.items[idx],...item};
    else state.items.unshift(item);
    cacheState();
  }
  async function refreshStateBackground(){
    try{state=await api("/api/state");cacheState();updateOfflinePill()}catch{}
  }
  window.openReport=async function(reportType,query={}){
    const params=new URLSearchParams();
    if(state?.settings?.activeProject)params.set("project",state.settings.activeProject);
    Object.entries(query||{}).forEach(([key,value])=>{if(value!=null&&String(value).trim())params.set(key,String(value))});
    const path=`/api/reports/${encodeURIComponent(reportType)}${params.toString()?`?${params}`:""}`;
    const headers={};
    if(typeof authToken!=="undefined"&&authToken)headers.Authorization=`Bearer ${authToken}`;
    toast("Opening report…");
    try{
      const res=await fetch(path,{headers,credentials:"same-origin"});
      if(res.status===401){clearAuthToken();renderLogin("Sign in to continue.");return}
      if(!res.ok){let message=`Report failed (${res.status})`;try{const data=await res.json();message=data.detail||data.error||message}catch{message=await res.text()||message}throw new Error(message)}
      const html=await res.text();
      const url=URL.createObjectURL(new Blob([html],{type:"text/html;charset=utf-8"}));
      const tab=window.open(url,"_blank");
      if(!tab){URL.revokeObjectURL(url);return toast("Allow popups to open reports.",true)}
      setTimeout(()=>URL.revokeObjectURL(url),120000);
    }catch(err){toast(err.message||"Could not open report.",true)}
  };

  function rememberCaptureFields(data){
    const keep={project:data.project,building:data.building,level:data.level,unit:data.unit,room:data.room,trade:data.trade,subcontractor:data.subcontractor,dueDate:data.dueDate,priority:data.priority,type:data.type};
    try{localStorage.setItem(LAST_CAPTURE_KEY,JSON.stringify(keep))}catch{}
    if(state?.settings?.activeProject){
      try{
        const all=JSON.parse(localStorage.getItem(WALK_CONTEXT_KEY)||"{}")||{};
        all[state.settings.activeProject]={building:keep.building||"",level:keep.level||"",unit:keep.unit||"",room:keep.room||"",trade:keep.trade||"",subcontractor:keep.subcontractor||""};
        localStorage.setItem(WALK_CONTEXT_KEY,JSON.stringify(all));
      }catch{}
    }
  }
  function readWalkContext(){
    try{
      const all=JSON.parse(localStorage.getItem(WALK_CONTEXT_KEY)||"{}")||{};
      return all[state?.settings?.activeProject]||{};
    }catch{return {}}
  }
  function recentValues(field,limit=4){
    const project=state?.settings?.activeProject;
    if(!project)return [];
    const seen=new Set(),values=[];
    const push=value=>{const v=String(value||"").trim();if(!v||seen.has(v))return;seen.add(v);values.push(v)};
    push(readWalkContext()[field]);
    try{push(JSON.parse(localStorage.getItem(LAST_CAPTURE_KEY)||"{}")[field])}catch{}
    (state.items||[]).filter(i=>i.project===project).sort((a,b)=>(b.updatedAt||"").localeCompare(a.updatedAt||"")).forEach(i=>push(i[field]));
    return values.slice(0,limit);
  }
  function recentChipsRow(label,field,values){
    if(!values.length)return "";
    return `<div class="recent-chip-row"><span class="recent-chip-label">${esc(label)}</span>${values.map(v=>`<button type="button" class="recent-chip" onclick="applyRecentField('${field}',decodeURIComponent('${encodeURIComponent(v)}'))">${esc(v)}</button>`).join("")}</div>`;
  }
  function locationFieldsMarkup(cfg,values={}){
    return `<div class="field-list"><label>Project<select name="project">${options(state.settings.projects,values.project||state.settings.activeProject)}</select></label><label>Building *<select name="building" required onchange="updateLocationChip()"><option value="">Select building</option>${options(cfg.buildings||[],values.building||"")}</select></label><label>Level<select name="level" onchange="updateLocationChip()"><option value="">Select level</option>${options(cfg.levels||[],values.level||"")}</select></label><label>Unit / Area *<select name="unit" required onchange="updateLocationChip()"><option value="">Select unit / area</option>${options(cfg.units||[],values.unit||"")}</select></label><label>Room / Location<select name="room" onchange="updateLocationChip()"><option value="">Select room / location</option>${options(cfg.rooms||[],values.room||"")}</select></label></div>`;
  }
  function buildLocationSpeedBlock(){
    const cfg=state.settings.projectConfigs[state.settings.activeProject]||{};
    const ctx=readWalkContext();
    let last={};try{last=JSON.parse(localStorage.getItem(LAST_CAPTURE_KEY)||"{}")||{}}catch{}
    const seed={building:ctx.building||last.building||cfg.buildings?.[0]||"",level:ctx.level||last.level||cfg.levels?.[0]||"",unit:ctx.unit||last.unit||cfg.units?.[0]||"",room:ctx.room||last.room||"",project:state.settings.activeProject};
    return `<section class="form-card location-speed-card"><div class="spread"><div><h3>Location</h3><p class="meta">Stays set while you walk the site.</p></div><button type="button" class="btn alt small" onclick="toggleLocationDetails()">Change</button></div><button type="button" class="location-context-chip" id="locationContextChip" onclick="toggleLocationDetails()">Set location</button>${recentChipsRow("Recent areas","unit",recentValues("unit"))}${recentChipsRow("Recent buildings","building",recentValues("building"))}<div id="locationDetails" class="location-details hidden">${locationFieldsMarkup(cfg,seed)}</div></section>`;
  }
  window.updateLocationChip=function(){
    const form=$("#app form");if(!form)return;
    const parts=[form.building?.value,form.level?.value,form.unit?.value,form.room?.value].filter(Boolean);
    const chip=$("#locationContextChip");
    if(chip)chip.textContent=parts.length?parts.join(" · "):"Tap to set location";
  };
  window.toggleLocationDetails=function(){
    const panel=$("#locationDetails");
    if(panel)panel.classList.toggle("hidden");
  };
  window.applyRecentField=function(field,value){
    const form=$("#app form");if(!form?.elements[field])return;
    form.elements[field].value=value;
    if(field==="building"||field==="level"||field==="unit"||field==="room")updateLocationChip();
    toast(`Set ${field} to ${value}`);
  };
  window.toggleWalkCapture=function(){
    walkMode=!walkMode;
    if(walkMode)sessionStorage.removeItem("walkModeOff");
    else sessionStorage.setItem("walkModeOff","1");
    render();
  };
  window.quickCapture=function(){
    sessionStorage.removeItem("walkModeOff");
    walkMode=true;
    go("capture");
  };
  function applyCaptureDefaults(){
    let keep={};try{keep=JSON.parse(localStorage.getItem(LAST_CAPTURE_KEY)||"{}")||{}}catch{}
    const ctx=readWalkContext();
    const form=$("#app form");if(!form)return;
    const cfg=state.settings.projectConfigs[state.settings.activeProject]||{};
    const merged={...keep,...ctx};
    for(const key of ["project","building","level","unit","room","trade","subcontractor","dueDate","priority","type"]){
      const value=merged[key]||(key==="building"?cfg.buildings?.[0]:key==="unit"?cfg.units?.[0]:key==="level"?cfg.levels?.[0]:"");
      if(value&&form.elements[key])form.elements[key].value=value;
    }
    photoHint?.();toggleRaised?.();
  }
  function resetCaptureForNext(){
    const form=$("#app form");
    if(form?.description)form.description.value="";
    if($("#voiceText")){$("#voiceText").value="";captureVoiceCaptured=false;updateCaptureVoiceState()}
    clearCapturePhotoState();
    const host=$("#capturePreviews");if(host)host.innerHTML="";
    updatePhotoCount();
    applyCaptureDefaults();
    form?.querySelector('input[type="file"][capture="environment"]')?.focus?.();
  }
  function mountQuickCaptureFab(){
    let fab=$("#quickCaptureFab");
    if(!fab){
      fab=document.createElement("button");
      fab.id="quickCaptureFab";
      fab.type="button";
      fab.className="quick-capture-fab";
      fab.setAttribute("aria-label","Quick Capture");
      fab.innerHTML='<span class="quick-capture-fab__icon">+</span><span class="quick-capture-fab__label">Quick</span>';
      fab.onclick=()=>quickCapture();
      document.body.appendChild(fab);
    }
    const hide=!state||route==="capture"||matchMedia("(min-width:1024px)").matches;
    fab.hidden=hide;
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

  async function filesWithMeta(files,onRecord){
    const list=[...files];
    if(!list.length)return [];
    const geo=await locatePhoto();
    const records=[];
    for(let n=0;n<list.length;n++){
      const file=list[n];
      await yieldToMain();
      const packed=await compressImageForUpload(file);
      const record={
        src:packed.dataUrl,
        previewUrl:packed.previewUrl||packed.dataUrl,
        meta:{...geo,fileName:file?.name||`photo-${n+1}.jpg`,mimeType:file?.type||"image/jpeg",compressed:!!file?.type?.startsWith("image/")}
      };
      records.push(record);
      onRecord?.(record,n);
    }
    return records;
  }

  filesToData=async function(files){
    const records=await filesWithMeta(files);
    return records.map(record=>record.src);
  };

  window.formatFieldDate=window.formatFieldDate||function(iso){return iso||""};
  fmt=window.formatFieldDate;

  function cardDueText(item){
    if(["closed","complete"].includes(item?.status))return "CLOSED";
    return `DUE ${esc(formatFieldDate(item?.dueDate)).toUpperCase()}`;
  }

  const baseItemCard=itemCard;
  itemCard=function(i){
    const html=baseItemCard(i);
    if(!html.includes("cr-card-date")&&!html.includes("cr-card-meta"))return html;
    return html.replace(/DUE [^<]+/g,cardDueText(i)).replace(/Due \d{4}-\d{2}-\d{2}/g,`Due ${esc(formatFieldDate(i.dueDate))}`);
  };

  function issueHistoryForItem(item){
    let rows=[...(item?.issueHistory||[])];
    if(!rows.length&&item?.auditEvents?.length){
      rows=item.auditEvents.filter(e=>/^(Re-issued|Issued) to /.test(e.action||"")).map(e=>({
        at:e.at,to:(e.action||"").replace(/^(Re-issued|Issued) to /,""),by:e.by,reissue:(e.action||"").startsWith("Re-issued"),note:e.note
      }));
    }
    if(!rows.length&&item&&item.status!=="open"&&item.issuedAt){
      rows=[{at:item.issuedAt,to:item.subcontractor||"",by:item.createdBy,reissue:false}];
    }
    return rows;
  }

  cardPhoto=function(i){
    const src=(i.originalPhotoThumbnails||i.originalPhotos||[])[0];
    if(!src)return `<div class="cr-card-photo empty">NO PHOTO</div>`;
    return src.startsWith("seed://")?`<div class="cr-card-photo">${seedThumb(src)}</div>`:`<img class="cr-card-photo" src="${src}" alt="Issue evidence" loading="lazy" decoding="async" width="200" height="200">`;
  };

  fileToData=async function(file){
    if(file?.type?.startsWith("image/")){try{return await fileToUploadData(file)}catch(e){console.warn("[CleanRun] image compression failed; using original",e)}}
    return readFileDataUrl(file);
  };

  function previewSrc(mode,index){
    if(mode==="capture")return capturePhotoPreviewUrls[index]||capturePhotos[index];
    if(mode==="edit")return editPhotoPreviewUrls[index]||editPhotos[index];
    return "";
  }

  function previewFigure(src,meta,index,mode){
    const safeTitle=mode==="edit"?"Retrospective evidence":"Issue evidence";
    return `<figure data-photo-index="${index}"><img src="${src}" alt="${safeTitle} ${index+1}" onclick="openEvidencePhoto('${mode}',${index})"><figcaption class="photo-caption">${esc(geoLabel(meta))}</figcaption><div class="photo-tools"><button class="btn alt" type="button" onclick="markupEvidencePhoto('${mode}',${index})">Mark up</button><button class="btn alt" type="button" onclick="removeEvidencePhoto('${mode}',${index})">Remove</button></div></figure>`;
  }

  function updatePhotoCount(){
    const count=$("#photoCount");
    if(count)count.textContent=capturePhotos.length?`${capturePhotos.length} photo${capturePhotos.length===1?"":"s"} attached`:"No photos attached yet";
    document.querySelector("[data-photo-card]")?.classList.toggle("needs-photo",capturePhotos.length===0);
  }

  function appendCapturePreview(index){
    const host=$("#capturePreviews");
    if(!host)return;
    host.insertAdjacentHTML("beforeend",previewFigure(previewSrc("capture",index),capturePhotoMeta[index],index,"capture"));
    updatePhotoCount();
  }

  function renderCapturePreviews(){
    const host=$("#capturePreviews");
    if(host)host.innerHTML=capturePhotos.map((_,n)=>previewFigure(previewSrc("capture",n),capturePhotoMeta[n],n,"capture")).join("");
    updatePhotoCount();
  }

  function renderEditPreviews(){
    const host=$("#editPhotoGrid");
    if(!host)return;
    host.innerHTML=editPhotos.map((src,n)=>src.startsWith("seed://")
      ?`<figure><span class="thumb">${seedThumb(src)}</span><figcaption class="photo-caption">Original seeded evidence</figcaption></figure>`
      :previewFigure(previewSrc("edit",n),editPhotoMeta[n],n,"edit")).join("")||'<span class="meta">No photos attached.</span>';
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
    openWorkbench(src,"Mark up evidence",data=>{
      photos[index]=data;
      if(mode==="edit"){
        revokePreviewUrl(editPhotoPreviewUrls[index]);
        editPhotoPreviewUrls[index]=null;
        renderEditPreviews();
      }else{
        revokePreviewUrl(capturePhotoPreviewUrls[index]);
        capturePhotoPreviewUrls[index]=null;
        renderCapturePreviews();
      }
    });
  };
  window.removeEvidencePhoto=function(mode,index){
    if(mode==="edit"){
      revokePreviewUrl(editPhotoPreviewUrls[index]);
      editPhotos.splice(index,1);editPhotoMeta.splice(index,1);editPhotoPreviewUrls.splice(index,1);renderEditPreviews();
    }else{
      revokePreviewUrl(capturePhotoPreviewUrls[index]);
      capturePhotos.splice(index,1);capturePhotoMeta.splice(index,1);capturePhotoPreviewUrls.splice(index,1);renderCapturePreviews();
    }
  };
  window.addEditPhotos=async function(input){
    const files=input.files||[];
    if(!files.length)return;
    const start=editPhotos.length;
    await filesWithMeta(files,record=>{
      editPhotos.push(record.src);
      editPhotoMeta.push(record.meta);
      editPhotoPreviewUrls.push(record.previewUrl);
    });
    const host=$("#editPhotoGrid");
    if(host){
      for(let n=start;n<editPhotos.length;n++){
        host.insertAdjacentHTML("beforeend",previewFigure(previewSrc("edit",n),editPhotoMeta[n],n,"edit"));
      }
    }else renderEditPreviews();
    input.value="";
  };

  function ensureWorkbench(){
    if($("#photoWorkbench"))return;
    document.body.insertAdjacentHTML("beforeend",`<section class="photo-workbench" id="photoWorkbench" hidden aria-modal="true"><div class="photo-workbench__panel"><header class="photo-workbench__head"><strong id="photoWorkbenchTitle">Photo evidence</strong><button type="button" onclick="closePhotoWorkbench()">Close</button></header><div class="photo-workbench__stage"><canvas id="markupCanvas"></canvas></div><footer class="photo-workbench__tools"><label>Tool <select id="markupTool"><option value="pen">Pen</option><option value="circle">Circle</option><option value="box">Box</option><option value="arrow">Arrow</option><option value="text">Text box</option></select></label><label>Colour <input id="markupColor" type="color" value="#E5483B"></label><label>Width <input id="markupWidth" type="range" min="2" max="18" value="6"></label><button type="button" onclick="undoPhotoMarkup()">Undo</button><button type="button" onclick="resetPhotoMarkup()">Reset</button><button class="primary" id="saveMarkup" type="button" onclick="savePhotoMarkup()">Save marked-up copy</button></footer></div></section>`);
    const canvas=$("#markupCanvas");
    const point=e=>{const r=canvas.getBoundingClientRect(),p=e.touches?.[0]||e;return{x:(p.clientX-r.left)*canvas.width/r.width,y:(p.clientY-r.top)*canvas.height/r.height}};
    const style=ctx=>{ctx.strokeStyle=$("#markupColor").value;ctx.fillStyle=$("#markupColor").value;ctx.lineWidth=Number($("#markupWidth").value);ctx.lineCap="round";ctx.lineJoin="round";ctx.font="700 22px Inter, system-ui, sans-serif"};
    const arrow=(ctx,a,b)=>{const angle=Math.atan2(b.y-a.y,b.x-a.x),head=22+ctx.lineWidth;ctx.beginPath();ctx.moveTo(a.x,a.y);ctx.lineTo(b.x,b.y);ctx.stroke();ctx.beginPath();ctx.moveTo(b.x,b.y);ctx.lineTo(b.x-head*Math.cos(angle-Math.PI/6),b.y-head*Math.sin(angle-Math.PI/6));ctx.lineTo(b.x-head*Math.cos(angle+Math.PI/6),b.y-head*Math.sin(angle+Math.PI/6));ctx.closePath();ctx.fill()};
    const shape=(ctx,tool,a,b)=>{style(ctx);const x=Math.min(a.x,b.x),y=Math.min(a.y,b.y),w=Math.abs(b.x-a.x),h=Math.abs(b.y-a.y);if(tool==="box"){ctx.strokeRect(x,y,w,h)}else if(tool==="circle"){ctx.beginPath();ctx.ellipse(x+w/2,y+h/2,Math.max(1,w/2),Math.max(1,h/2),0,0,Math.PI*2);ctx.stroke()}else if(tool==="arrow"){arrow(ctx,a,b)}};
    const start=e=>{if(!workbench.save)return;e.preventDefault();const tool=$("#markupTool").value,p=point(e),ctx=canvas.getContext("2d");const base=document.createElement("canvas");base.width=canvas.width;base.height=canvas.height;base.getContext("2d").drawImage(canvas,0,0);workbench.baseCanvas=base;workbench.history.push(base);if(tool==="text"){const text=prompt("Markup text:","");if(!text){workbench.history.pop();workbench.baseCanvas=null;return}style(ctx);const pad=10,lines=text.split(/\n/).slice(0,4),width=Math.max(...lines.map(line=>ctx.measureText(line).width))+pad*2,height=lines.length*28+pad*2;ctx.fillStyle="rgba(255,255,255,.88)";ctx.fillRect(p.x,p.y,width,height);ctx.strokeStyle=$("#markupColor").value;ctx.strokeRect(p.x,p.y,width,height);ctx.fillStyle=$("#markupColor").value;lines.forEach((line,n)=>ctx.fillText(line,p.x+pad,p.y+pad+22+n*28));workbench.baseCanvas=null;return}workbench.drawing=true;workbench.last=p;workbench.start=p};
    const move=e=>{if(!workbench.drawing||!workbench.baseCanvas)return;e.preventDefault();const p=point(e),tool=$("#markupTool").value,ctx=canvas.getContext("2d");if(tool==="pen"){style(ctx);ctx.beginPath();ctx.moveTo(workbench.last.x,workbench.last.y);ctx.lineTo(p.x,p.y);ctx.stroke();workbench.last=p;return}ctx.clearRect(0,0,canvas.width,canvas.height);ctx.drawImage(workbench.baseCanvas,0,0);shape(ctx,tool,workbench.start,p)};
    const stop=e=>{if(!workbench.drawing)return;const tool=$("#markupTool").value;if(tool!=="pen")shape(canvas.getContext("2d"),tool,workbench.start,point(e));workbench.drawing=false;workbench.last=null;workbench.start=null;workbench.baseCanvas=null};
    canvas.addEventListener("pointerdown",start);canvas.addEventListener("pointermove",move);canvas.addEventListener("pointerup",stop);canvas.addEventListener("pointerleave",stop);
  }

  function drawSource(src){
    const img=new Image();img.onload=()=>{const canvas=$("#markupCanvas"),scale=Math.min(1,1400/img.naturalWidth,900/img.naturalHeight);canvas.width=Math.max(1,Math.round(img.naturalWidth*scale));canvas.height=Math.max(1,Math.round(img.naturalHeight*scale));canvas.getContext("2d").drawImage(img,0,0,canvas.width,canvas.height);workbench.history=[]};img.src=src;
  }
  function restoreCanvas(base){
    const canvas=$("#markupCanvas");
    if(!canvas||!base)return;
    canvas.getContext("2d").clearRect(0,0,canvas.width,canvas.height);
    canvas.getContext("2d").drawImage(base,0,0,canvas.width,canvas.height);
  }
  function openWorkbench(src,title,onSave){ensureWorkbench();workbench={source:src,title,save:onSave,drawing:false,last:null,history:[],baseCanvas:null};$("#photoWorkbenchTitle").textContent=title;$("#saveMarkup").hidden=!onSave;$("#photoWorkbench").hidden=false;drawSource(src)}
  window.closePhotoWorkbench=()=>{$("#photoWorkbench").hidden=true};
  window.resetPhotoMarkup=()=>drawSource(workbench.source);
  window.undoPhotoMarkup=()=>{const previous=workbench.history.pop();if(previous)restoreCanvas(previous)};
  window.savePhotoMarkup=async function(){
    const canvas=$("#markupCanvas");
    if(!canvas||!workbench.save)return;
    await yieldToMain();
    const blob=await canvasToJpegBlob(canvas,.92);
    workbench.save?.(await blobToDataUrl(blob));
    closePhotoWorkbench();
    toast("Marked-up evidence saved");
  };

  function clearCapturePhotoState(){
    revokePreviewUrls(capturePhotoPreviewUrls);
    capturePhotos=[];
    capturePhotoMeta=[];
    capturePhotoPreviewUrls=[];
  }

  loadCapturePhotos=async function(input){
    const files=input.files||[];
    if(!files.length)return;
    const button=input.closest("label");
    const release=button?setBusyButton(button,"Processing…"):()=>{};
    try{
      await filesWithMeta(files,record=>{
        capturePhotos.push(record.src);
        capturePhotoMeta.push(record.meta);
        capturePhotoPreviewUrls.push(record.previewUrl);
        appendCapturePreview(capturePhotos.length-1);
      });
    }catch(err){
      toast(err.message||"Could not read photo.",true);
    }finally{
      release();
      input.value="";
    }
  };

  startDictation=function(){
    const SR=window.SpeechRecognition||window.webkitSpeechRecognition;
    if(!SR)return toast("Speech recognition unavailable — type the note instead.",true);
    const r=new SR();
    r.lang="en-AU";
    r.onresult=e=>{const voice=$("#voiceText");if(voice)voice.value=e.results[0][0].transcript};
    r.onerror=()=>toast("Speech recognition failed — type the note instead.",true);
    r.start();
    toast("Listening…");
  };

  const originalGo=go;
  go=function(next){
    if(next==="capture"&&!sessionStorage.getItem("walkModeOff"))walkMode=true;
    return originalGo(next);
  };

  const originalCaptureView=captureView;
  captureView=function(){
    const walkBanner=walkMode?`<div class="walk-session-banner">Walk mode · ${walkCount} captured this walk · next save loops back here</div>`:"";
    let html=originalCaptureView()
      .replace("<section class=\"form-card\"><div class=\"form-card-title\">Photo Evidence</div>", "<section class=\"form-card\" data-photo-card=\"true\"><div class=\"spread\"><div class=\"form-card-title\">Photo Evidence</div><span class=\"photo-count\" id=\"photoCount\">No photos attached yet</span></div>")
      .replace("Start with evidence. Defects and client defects require at least one photo.", "Take a photo first. Add a short note, then save.")
      .replace(/<div class="photo-preview" id="capturePreviews"[^>]*>[\s\S]*?<\/div>/, '<div class="photo-preview" id="capturePreviews"></div>')
      .replace('onclick="walkMode=!walkMode;render()"','onclick="toggleWalkCapture()"')
      .replace("</header><form onsubmit=\"saveCapture(event)\">",`${walkBanner}</header><form onsubmit="saveCapture(event)">`);
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

  editItemForm=function(id){
    const i=state.items.find(x=>x.id===id);selectedEditItem=id;editPhotos=[...(i.originalPhotos||[])];editPhotoMeta=[...(i.originalPhotoMeta||[])];editPhotoPreviewUrls=editPhotos.map(()=>null);while(editPhotoMeta.length<editPhotos.length)editPhotoMeta.push({capturedAt:i.createdAt});
    $("#modalTitle").textContent=`Edit ${i.code}`;
    $("#modalBody").innerHTML=`<form class="field-list" onsubmit="saveItemEdit(event,'${id}')"><div class="fields admin-form-grid"><label>Item type<select name="type">${options(["defect","incomplete","client"],i.type)}</select></label><label>Project<select name="project">${options(state.settings.projects,i.project)}</select></label><label>Building<input name="building" value="${esc(i.building)}"></label><label>Level<input name="level" value="${esc(i.level)}"></label><label>Unit / Area<input name="unit" value="${esc(i.unit)}"></label><label>Room / Location<input name="room" value="${esc(i.room)}"></label><label>Trade<select name="trade"><option value=""></option>${options(trades,i.trade)}</select></label><label>Subcontractor<select name="subcontractor"><option value=""></option>${options(state.settings.subcontractors,i.subcontractor)}</select></label><label>Priority<select name="priority">${options(["high","urgent"],i.priority)}</select></label><label>Due date<input type="date" name="dueDate" value="${esc(i.dueDate)}"></label><label class="span">Description<textarea name="description">${esc(i.description)}</textarea></label></div><section class="edit-evidence"><div class="spread"><div><b>Original issue photos</b><div class="meta">Add evidence retrospectively, enlarge it or mark it up.</div></div><label class="btn alt">＋ Add photos<input hidden type="file" accept="image/*" multiple onchange="addEditPhotos(this)"></label></div><div class="edit-photo-grid" id="editPhotoGrid"></div></section><button class="btn">Save changes and evidence</button></form>`;
    renderEditPreviews();
  };

  saveItemEdit=async function(e,id){
    e.preventDefault();const data=Object.fromEntries(new FormData(e.currentTarget));data.by=state.settings.preparedBy;data.originalPhotos=editPhotos;data.originalPhotoMeta=editPhotoMeta;
    try{await yieldToMain();await api(`/api/items/${id}`,{method:"PATCH",body:JSON.stringify(data)});await reload();showItem(id);toast("Item details and evidence updated")}catch(err){toast(err.message,true)}
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
    const voice=$("#voiceText").value.trim();if(voice){data.voiceTranscript=voice;data.voiceNote={transcript:voice,createdAt:new Date().toISOString(),status:"parsed"}}
    ensureCaptureDescription(data,voice);
    rememberCaptureFields(data);
    const fail=message=>{captureSubmitting=false;release();toast(message,true)};
    if(data.type==="client"&&!data.raisedBy)return fail("A Client Defect requires a Raised By / source.");
    if(requireOriginalPhoto(data)){focusPhotoEvidence();return fail("Attach original photo evidence, or change Item Type to Incomplete Work.")}
    if(mode==="issue"&&(!data.trade||!data.subcontractor))return fail("Issue Now requires a trade and subcontractor.");
    try{
      toast(capturePhotos.length?"Uploading evidence…":"Saving item…");
      if(mode==="issue"){data.issueOnCreate=true;data.issueTo=data.subcontractor}
      const path=mode==="issue"?"/api/items?issue_now=true":"/api/items";
      await yieldToMain();
      const item=await api(path,{method:"POST",body:JSON.stringify(data)});
      clearCapturePhotoState();
      form.dataset.captureRequestId="";
      if(walkMode){walkCount++;mergeSavedItem(item);route="capture";render();resetCaptureForNext();toast(`${item.code} saved · capture next`);refreshStateBackground()}
      else{await reload();route="items";render();setTimeout(()=>scrollTo(0,0),0);toast(item.sync==="queued"?`${item.code} saved offline - queued to sync`:mode==="issue"?`${item.code} issued`:`${item.code} saved`)}
    }catch(err){toast(err.message,true)}finally{captureSubmitting=false;release()}
  };

  reviewView=function(){
    const items=state.items.filter(i=>i.project===state.settings.activeProject&&["ready_for_review","under_inspection"].includes(i.status));
    return `${subHeader("Review Queue")}<div class="screen-scroll"><section class="native-card review-hero"><div class="spread"><div><h2>${items.length} ready for supervisor review</h2><p class="meta">Compare original issue proof against rectification evidence, then close or reject.</p></div><button class="btn alt small" onclick="go('items')">All items</button></div></section>${items.length?items.map(i=>{const original=(i.originalPhotos||[]).find(p=>!String(p).startsWith("seed://")),rect=(i.rectificationEvidence||[]).find(e=>e.photo)?.photo;return `<article class="native-card review-card"><div class="review-grid"><div><h3>Original Issue</h3>${original?`<img src="${original}" alt="Original issue">`:`<div class="thumb">${seedThumb(i.originalPhotos?.[0])}</div>`}<p>${esc(i.description||"No description")}</p><small class="meta">${esc(loc(i))}</small></div><div><h3>Rectification Evidence</h3>${rect?`<img src="${rect}" alt="Rectification evidence">`:`<div class="empty">No rectification photo</div>`}<p>${esc(i.rectificationEvidence?.at(-1)?.comment||"No subcontractor comment")}</p><small class="meta">${esc(i.subcontractor||"Unassigned")} · Due ${esc(i.dueDate)}</small></div></div><div class="actions review-actions"><button class="btn" onclick="itemAction('${i.id}','${i.status==="ready_for_review"?"inspect":"close"}')">${i.status==="ready_for_review"?"Start Inspection":"Close"}</button><button class="btn danger" onclick="itemAction('${i.id}','reject')">Reject</button><button class="btn alt" onclick="showItem('${i.id}')">Open Detail</button></div></article>`}).join(""):`<div class="native-card empty"><b>No items ready for review</b><br><span class="meta">When subcontractors mark work ready, it will appear here.</span></div>`}</div>`;
  };

  function reviewPhoto(src,label){
    if(!src)return `<div class="review-photo-placeholder">No ${esc(label)} photo</div>`;
    return String(src).startsWith("seed://")?`<div class="review-photo-placeholder">${seedThumb(src)}</div>`:`<img src="${src}" alt="${esc(label)}">`;
  }
  reviewView=function(){
    const items=state.items.filter(i=>i.project===state.settings.activeProject&&["ready_for_review","under_inspection"].includes(i.status)).sort((a,b)=>(b.priority==="urgent")-(a.priority==="urgent")||a.dueDate.localeCompare(b.dueDate)||(a.readyForReviewAt||a.updatedAt||"").localeCompare(b.readyForReviewAt||b.updatedAt||""));
    return `${subHeader("Review Queue")}<div class="screen-scroll review-queue"><section class="native-card review-hero"><div class="spread"><div><h2>${items.length} ready for supervisor review</h2><p class="meta">Original issue beside subcontractor rectification evidence. Close out or reject from here.</p></div><button class="btn alt small" onclick="go('items')">All items</button></div></section>${items.length?items.map(i=>{const rect=(i.rectificationEvidence||[]).filter(e=>e.photo||e.comment).at(-1)||{},original=(i.originalPhotos||[])[0];return `<article class="native-card review-card"><div class="spread"><div><b>${esc(i.code)} · ${esc(typeLabels[i.type]||i.type)}</b><small class="meta">${esc([i.building,i.level,i.unit,i.room].filter(Boolean).join(" · ")||"No location")} · Due ${esc(i.dueDate)}</small></div><span class="badge ready">READY</span></div><div class="review-compare"><section class="review-pane"><h3>Original defect</h3>${reviewPhoto(original,"original issue")}<p>${esc(i.description||"No description")}</p><small>${esc(i.trade||"No trade")}</small></section><section class="review-pane"><h3>${esc(i.subcontractor||"Subcontractor")}</h3>${reviewPhoto(rect.photo,"rectification")}<p>${esc(rect.comment||"No subcontractor comment")}</p><small>Submitted by ${esc(rect.by||i.subcontractor||"Subcontractor")}</small></section></div><div class="review-decision-row"><button class="btn danger" onclick="reviewReject('${i.id}')">REJECT</button><button class="btn review-closeout" onclick="reviewCloseout('${i.id}')">CLOSE OUT</button></div></article>`}).join(""):`<div class="native-card empty"><b>No items ready for review</b><br><span class="meta">Items appear here only after rectification evidence is uploaded and marked ready.</span></div>`}</div>`;
  };

  itemAction=async function(id,act){
    if(act==="reopen")return toast("Reopen is not available yet.",true);
    const i=state.items.find(x=>x.id===id),body={by:state.settings.preparedBy};
    const release=setBusyButton(document.activeElement,"Working…");
    if(act==="issue"){body.to=i.subcontractor||prompt("Subcontractor name:","");body.reissue=i.status==="rejected"}
    if(act==="reject")body.reason=prompt("Why is this being rejected?","");
    if(act==="issue"&&!body.to){release();return toast("Choose a subcontractor before issuing.",true)}
    if((act==="reject")&&!body.reason){release();return toast("Rejection reason is required.",true)}
    if(act==="rectification"){body.comment=prompt("Rectification comment:","");body.photo=await chooseImage();body.photoMeta=lastChosenPhotoMeta;if(!body.photo&&!body.comment){release();return toast("Add a rectification photo or comment.",true)}body.advanceToReady=confirm("Mark ready for review after saving evidence?")}
    if(act==="close"){body.role=prompt("Signed off by role:","Site Manager")||"Site Manager";body.note=prompt("Closeout note (optional):","");if(i.type!=="incomplete"){body.photo=await chooseImage();body.photoMeta=lastChosenPhotoMeta;if(!body.photo){release();return toast("Closeout photo is required.",true)}}body.confirmed=confirm(`I confirm this item is rectified and accepted by ${state.settings.preparedBy}.`);if(!body.confirmed){release();return toast("Closeout confirmation cancelled.",true)}}
    try{await api(`/api/items/${id}/actions/${act}`,{method:"POST",body:JSON.stringify(body)});await reload();showItem(id);document.querySelector(".dialog")?.scrollTo?.(0,0);toast("Item updated")}catch(err){toast(err.message,true)}finally{release()}
  };

  window.reviewCloseout=function(id){
    const item=state.items.find(x=>x.id===id);if(!item)return toast("Item not found",true);
    $("#modalTitle").textContent=`Close out ${item.code}`;
    $("#modalBody").innerHTML=`<form class="field-list" onsubmit="submitReviewCloseout(event,'${id}')"><p class="meta">Site manager / foreman / project manager sign-off. This signature is stored as closeout evidence.</p><label>Signed by / role<input name="role" value="${esc(state.settings.preparedBy||"Site Manager")}"></label><label>Closeout note<textarea name="note" placeholder="Accepted after photo review / physical inspection"></textarea></label><canvas id="signaturePad" class="signature-pad"></canvas><div class="signature-tools"><button type="button" class="btn alt small" onclick="clearSignature()">Clear signature</button></div><button class="btn review-closeout">CLOSE OUT</button></form>`;
    $("#modal").hidden=false;wireSignaturePad();
  };
  window.clearSignature=function(){const c=$("#signaturePad");if(c)c.getContext("2d").clearRect(0,0,c.width,c.height)};
  window.wireSignaturePad=function(){const c=$("#signaturePad");if(!c)return;const ratio=window.devicePixelRatio||1,rect=c.getBoundingClientRect();c.width=Math.max(1,Math.round(rect.width*ratio));c.height=Math.max(1,Math.round(rect.height*ratio));const ctx=c.getContext("2d");ctx.scale(ratio,ratio);ctx.lineWidth=3;ctx.lineCap="round";ctx.strokeStyle="#121619";let drawing=false,moved=false;const pos=e=>{const r=c.getBoundingClientRect(),p=e.touches?e.touches[0]:e;return{x:p.clientX-r.left,y:p.clientY-r.top}};const start=e=>{drawing=true;const p=pos(e);ctx.beginPath();ctx.moveTo(p.x,p.y);e.preventDefault()};const move=e=>{if(!drawing)return;const p=pos(e);ctx.lineTo(p.x,p.y);ctx.stroke();moved=true;e.preventDefault()};const end=()=>{drawing=false};c.dataset.signed="";["mousedown","touchstart"].forEach(n=>c.addEventListener(n,start,{passive:false}));["mousemove","touchmove"].forEach(n=>c.addEventListener(n,move,{passive:false}));["mouseup","mouseleave","touchend"].forEach(n=>c.addEventListener(n,()=>{if(moved)c.dataset.signed="1";end()}))};
  window.submitReviewCloseout=async function(e,id){e.preventDefault();const form=e.currentTarget,c=$("#signaturePad");if(!c?.dataset.signed)return toast("Signature is required before closeout.",true);const data=Object.fromEntries(new FormData(form)),release=setBusyButton(e.submitter,"CLOSING...");try{await api(`/api/items/${id}/actions/close`,{method:"POST",body:JSON.stringify({by:state.settings.preparedBy,role:data.role||"Site Manager",note:data.note||"Signed off from review queue",photo:c.toDataURL("image/png"),confirmed:true,accepted:true})});closeModal();await reload();route="review";render();toast("Closed out")}catch(err){toast(err.message,true)}finally{release()}};
  window.reviewReject=async function(id){const item=state.items.find(x=>x.id===id);if(!item)return toast("Item not found",true);$("#modalTitle").textContent=`Reject ${item.code}`;$("#modalBody").innerHTML=`<div class="review-reject-options"><p class="meta">Reject flags the defect as REJECTED. You can optionally send a return photo/comment back to the subcontractor.</p><button class="btn danger" onclick="submitReviewReject('${id}','comment')">Reject with comment</button><button class="btn alt" onclick="submitReviewReject('${id}','photo')">Provide another photo</button><button class="btn alt" onclick="submitReviewReject('${id}','reissue')">Review & reissue</button></div>`;$("#modal").hidden=false};
  window.submitReviewReject=async function(id,mode){const reason=prompt("Reason for rejection:","Rectification not accepted. Please review and re-submit.")||"";if(!reason.trim())return toast("Rejection reason is required.",true);let photo=null;if(mode==="photo"||mode==="reissue"){photo=await chooseImage()}try{await api(`/api/items/${id}/actions/reject`,{method:"POST",body:JSON.stringify({by:state.settings.preparedBy,reason:mode==="reissue"?`${reason} Review & reissue.`:reason,photo,photoMeta:lastChosenPhotoMeta})});closeModal();await reload();route="review";render();toast("Rejected and returned to subcontractor")}catch(err){toast(err.message,true)}};

  const originalShowItem=showItem;
  showItem=function(id){
    originalShowItem(id);const i=state.items.find(x=>x.id===id),cards=[...document.querySelectorAll("#modalBody .native-card")],original=cards.find(c=>c.querySelector("h2")?.textContent==="Original Issue");
    const historyCard=cards.find(c=>c.querySelector("h2")?.textContent==="Assignment & Issue History");
    if(historyCard){
      const rows=issueHistoryForItem(i);
      historyCard.innerHTML=`<h2>Assignment & Issue History</h2>${rows.length?rows.map(e=>`<div class="event"><b>${e.reissue?"Re-issued":"Issued"} to ${esc(e.to)}</b><div class="meta">${esc(e.by||"")} · ${esc(fmt(e.at))}</div>${e.note?`<p>${esc(e.note)}</p>`:""}</div>`).join(""):'<div class="meta">Not yet issued to a subcontractor.</div>'}`;
    }
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

  function commandHomeBar(){
    return `<form class="command-home native-card" onsubmit="return submitHomeCommand(event)"><label for="homeCommand">Command search</label><div class="command-line"><input id="homeCommand" autocomplete="off" placeholder="Issue DEF-022 to AquaSeal  ·  Find all open items Block A L02"><button class="btn" type="submit">RUN</button></div><small><kbd>Cmd</kbd>/<kbd>Ctrl</kbd> + <kbd>K</kbd> from anywhere</small></form>`;
  }
  function cleanCommandText(value){return String(value||"").trim().replace(/\s+/g," ")}
  function commandKey(value){return String(value||"").replace(/[^a-z0-9]/gi,"").toUpperCase()}
  function commandCode(value){const raw=String(value||"").trim().toUpperCase();return raw.includes("-")?raw:raw.replace(/^([A-Z]+)(\d+)$/,"$1-$2")}
  function commandFindItem(code){const key=commandKey(code);return (state.items||[]).find(item=>commandKey(item.code)===key)}
  function commandFindSubcontractor(name){const wanted=commandKey(name),subs=state.settings?.subcontractors||[];return subs.find(sub=>commandKey(sub)===wanted)||subs.find(sub=>commandKey(sub).includes(wanted)||wanted.includes(commandKey(sub)))||cleanCommandText(name)}
  function commandStatus(value){const key=String(value||"").toLowerCase();if(["open","captured"].includes(key))return "Captured";if(key==="issued")return "Issued";if(key==="ready")return "Ready";if(key==="closed")return "Closed";if(key==="overdue")return "Overdue";if(key==="rejected")return "Rejected";return "All"}
  function commandPreviewText(value){
    const q=cleanCommandText(value);
    if(!q)return "Run field commands or search the closeout register.";
    const issue=q.match(/^issue\s+([a-z]{2,5}-?\d{1,5})\s+to\s+(.+)$/i);
    if(issue)return `Issue ${commandCode(issue[1])} to ${cleanCommandText(issue[2])}`;
    const find=q.match(/^(?:find|show|search)\s+(?:all\s+)?(?:(open|captured|issued|ready|closed|overdue|rejected)\s+)?(?:items?|defects?|works?)?\s*(.*)$/i);
    if(find)return `Find ${commandStatus(find[1])} items${find[2]?` matching “${find[2]}”`:""}`;
    if(/^capture|new defect|new item/i.test(q))return "Open capture.";
    if(/^review/i.test(q))return "Open review queue.";
    return `Search items for “${q}”`;
  }
  window.commandPreview=function(input){const target=$("#commandPreview");if(target)target.textContent=commandPreviewText(input.value)};
  window.openCommandPalette=function(prefill=""){
    $("#modalTitle").textContent="Command Palette";
    $("#modalBody").innerHTML=`<form class="command-palette" onsubmit="return submitCommandPalette(event)"><input id="commandInput" autocomplete="off" value="${esc(prefill)}" placeholder="Issue DEF-022 to AquaSeal"><div id="commandPreview" class="command-result">${esc(commandPreviewText(prefill))}</div><div class="command-hints"><span>Issue DEF-022 to AquaSeal</span><span>Find all open items Block A L02</span><span>Review ready items</span></div><button class="btn" type="submit">RUN COMMAND</button></form>`;
    $("#modal").hidden=false;
    setTimeout(()=>{const input=$("#commandInput");if(input){input.focus();input.select();input.addEventListener("input",()=>commandPreview(input))}},0);
  };
  window.submitCommandPalette=function(event){event.preventDefault();const input=$("#commandInput");runCommand(input?.value||"").catch(err=>toast(err.message,true));return false};
  window.submitHomeCommand=function(event){event.preventDefault();const input=event.currentTarget.querySelector("input");runCommand(input?.value||"").catch(err=>toast(err.message,true));if(input)input.value="";return false};
  window.runCommand=async function(raw){
    const q=cleanCommandText(raw);if(!q)return toast("Type a command or search term.",true);
    const issue=q.match(/^issue\s+([a-z]{2,5}-?\d{1,5})\s+to\s+(.+)$/i);
    if(issue){
      const item=commandFindItem(issue[1]);if(!item)return toast(`Could not find ${commandCode(issue[1])}.`,true);
      if(!["open","rejected"].includes(item.status))return toast(`${item.code} is already ${siteStatus(item).label}.`,true);
      const to=commandFindSubcontractor(issue[2]),body={to,by:state.settings.preparedBy,reissue:item.status==="rejected"};
      await api(`/api/items/${item.id}/actions/issue`,{method:"POST",body:JSON.stringify(body)});
      item.status="issued";item.subcontractor=to;item.issuedAt=item.issuedAt||new Date().toISOString();item.updatedAt=new Date().toISOString();item.issueHistory=item.issueHistory||[];item.issueHistory.push({at:item.updatedAt,to,by:body.by,reissue:!!body.reissue});
      closeModal();toast(`${item.code} issued to ${to}`);await reload();openDashboardSearch(item.code,"Issued");return;
    }
    const find=q.match(/^(?:find|show|search)\s+(?:all\s+)?(?:(open|captured|issued|ready|closed|overdue|rejected)\s+)?(?:items?|defects?|works?)?\s*(.*)$/i);
    if(find){closeModal();openDashboardSearch(cleanCommandText(find[2]),commandStatus(find[1]));return}
    if(/^capture|new defect|new item/i.test(q)){closeModal();go("capture");return}
    if(/^review/i.test(q)){closeModal();go("review");return}
    closeModal();openDashboardSearch(q,"All");
  };
  document.addEventListener("keydown",event=>{
    if((event.metaKey||event.ctrlKey)&&event.key.toLowerCase()==="k"){event.preventDefault();openCommandPalette()}
  });

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
    let html=originalItemsView();
    const chips=["All","Captured","Issued","Ready","Rejected","Overdue","Closed"].map(v=>`<button class="filter-chip light ${v===itemStatusFilter?'active':''}" data-value="${v}" onclick="setFilter(this,'status')">${v}</button>`).join("");
    html=html.replace(/<div class="hscroll" id="statusFilters">[\s\S]*?<\/div><\/div><div class="screen-scroll">/,`<div class="hscroll" id="statusFilters">${chips}</div></div><div class="screen-scroll">`);
    html=html.replace('<div class="screen-title">Items</div>','<div class="items-header-copy"><div class="screen-title">Items</div><button type="button" class="btn small quick-capture-inline" onclick="quickCapture()">Quick Capture</button></div>');
    return html;
  };

  function siteStatus(item){
    if(overdue(item))return {label:"OVERDUE",tone:"overdue"};
    if(["closed","complete"].includes(item.status))return {label:"CLOSED",tone:"closed"};
    if(item.status==="rejected")return {label:"REJECTED / RE-ISSUE",tone:"rejected"};
    if(["ready_for_review","under_inspection"].includes(item.status))return {label:"READY",tone:"ready"};
    if(["issued","in_progress"].includes(item.status))return {label:"ISSUED",tone:"issued"};
    return {label:"CAPTURED",tone:"captured"};
  }
  const cardActionLocks=new Set();
  window.cardAction=function(event,id,act){event.preventDefault();event.stopPropagation();event.stopImmediatePropagation?.();if(cardActionLocks.has(id))return false;const button=event.currentTarget;if(button?.disabled)return false;cardActionLocks.add(id);const release=setBusyButton(button,act==="issue"?"ISSUING...":"WORKING...");(async()=>{const item=state.items.find(x=>x.id===id);if(!item)return toast("Item not found. Refresh and try again.",true);const body={by:state.settings.preparedBy};if(act==="issue"){if(!["open","rejected"].includes(item.status))return toast(`${item.code} is already ${siteStatus(item).label}.`,true);body.to=item.subcontractor||prompt("Subcontractor name:","");body.reissue=item.status==="rejected";if(!body.to)return toast("Choose a subcontractor before issuing.",true)}await api(`/api/items/${id}/actions/${act}`,{method:"POST",body:JSON.stringify(body)});if(act==="issue"){item.status="issued";item.issuedAt=item.issuedAt||new Date().toISOString();item.updatedAt=new Date().toISOString();item.issueHistory=item.issueHistory||[];item.issueHistory.push({at:item.updatedAt,to:body.to,by:body.by,reissue:!!body.reissue});render();toast("ISSUED · moved to Issued")}await reload();if(route==="items")filterItems();else render()})().catch(err=>toast(err.message,true)).finally(()=>{cardActionLocks.delete(id);release()});return false};

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

  const commandDashboardView=dashboardView;
  dashboardView=function(){
    let html=commandDashboardView();
    html=html.replace(`onclick="go('capture')"`,`onclick="quickCapture()"`);
    html=html.replace("<b>Capture Item</b><small>Photo, voice-to-note or walk capture</small>","<b>Quick Capture</b><small>Photo first · walk the site · save and next</small>");
    if(matchMedia("(max-width:1023px)").matches)html=html.replace(/<form class="command-home[\s\S]*?<\/form>/,"");
    return html.includes("command-home")?html:html.replace(`</div></section><div class="dashboard-kpis">`,`</div></section>${commandHomeBar()}<div class="dashboard-kpis">`);
  };

  function subProfile(name){const profile=state.settings.subProfiles?.[name]||{},contacts=Array.isArray(profile.contacts)&&profile.contacts.length?profile.contacts:[{name:profile.contact||"",role:"Primary",email:profile.email||"",mobile:profile.mobile||profile.phone||""}];return {...profile,name,companyName:profile.companyName||profile.name||name,tradeType:profile.tradeType||profile.trade||"",contacts}}
  function contactRows(profile){return profile.contacts.map((c,n)=>`<div class="contact-row"><input name="contactName-${n}" placeholder="Contact name" value="${esc(c.name)}"><input name="contactRole-${n}" placeholder="Role" value="${esc(c.role)}"><input name="contactEmail-${n}" placeholder="Email" value="${esc(c.email)}"><input name="contactMobile-${n}" placeholder="Mobile" value="${esc(c.mobile)}"><button class="btn alt small" type="button" onclick="this.closest('.contact-row').remove()">Remove</button></div>`).join("")}
  window.addContactRow=function(){const host=$("#subContacts"),n=host.querySelectorAll(".contact-row").length;host.insertAdjacentHTML("beforeend",`<div class="contact-row"><input name="contactName-${n}" placeholder="Contact name"><input name="contactRole-${n}" placeholder="Role"><input name="contactEmail-${n}" placeholder="Email"><input name="contactMobile-${n}" placeholder="Mobile"><button class="btn alt small" type="button" onclick="this.closest('.contact-row').remove()">Remove</button></div>`)};
  window.editSubcontractorProfile=function(name){const p=subProfile(name);$("#modalTitle").textContent=`Subcontractor · ${p.companyName}`;$("#modalBody").innerHTML=`<form class="field-list" onsubmit="saveSubcontractorProfile(event,'${esc(name)}')"><div class="fields admin-form-grid"><label>Subcontractor Name<input name="companyName" value="${esc(p.companyName)}" required></label><label>Trade Type<select name="tradeType"><option value=""></option>${options(trades,p.tradeType)}</select></label><label>Contact Name<input name="contact" value="${esc(p.contact||p.contacts[0]?.name||"")}"></label><label>Email<input type="email" name="email" value="${esc(p.email||p.contacts[0]?.email||"")}"></label><label>Mobile<input name="mobile" value="${esc(p.mobile||p.phone||p.contacts[0]?.mobile||"")}"></label></div><section class="edit-evidence"><div class="spread"><div><b>Team members / additional contacts</b><div class="meta">Add supervisors, PMs, after-hours contacts or accounts contacts.</div></div><button class="btn alt" type="button" onclick="addContactRow()">+ Add member</button></div><div id="subContacts" class="contact-grid">${contactRows(p)}</div></section><button class="btn">Save subcontractor</button></form>`;$("#modal").hidden=false};
  window.saveSubcontractorProfile=async function(e,name){e.preventDefault();const form=e.currentTarget,data=Object.fromEntries(new FormData(form)),s=structuredClone(state.settings),contacts=[];form.querySelectorAll(".contact-row").forEach(row=>{const inputs=row.querySelectorAll("input"),contact={name:inputs[0].value.trim(),role:inputs[1].value.trim(),email:inputs[2].value.trim(),mobile:inputs[3].value.trim()};if(contact.name||contact.email||contact.mobile)contacts.push(contact)});const oldName=name,newName=data.companyName.trim();s.subProfiles=s.subProfiles||{};s.subcontractors=s.subcontractors.map(n=>n===oldName?newName:n);if(!s.subcontractors.includes(newName))s.subcontractors.push(newName);s.subcontractors=[...new Set(s.subcontractors)].sort();if(newName!==oldName)delete s.subProfiles[oldName];s.subProfiles[newName]={name:newName,companyName:newName,trade:data.tradeType,tradeType:data.tradeType,contact:data.contact,email:data.email,mobile:data.mobile,phone:data.mobile,contacts};await api("/api/settings",{method:"POST",body:JSON.stringify({subcontractors:s.subcontractors,subProfiles:s.subProfiles})});await reload();closeModal();route="settings";render();toast("Subcontractor profile saved")};
  addSubcontractor=async function(){const name=prompt("Company Name:","");if(!name)return;const s=structuredClone(state.settings);s.subProfiles=s.subProfiles||{};if(!s.subcontractors.includes(name))s.subcontractors.push(name);s.subcontractors.sort();s.subProfiles[name]={name,companyName:name,trade:"",tradeType:"",contact:"",email:"",mobile:"",contacts:[]};await api("/api/settings",{method:"POST",body:JSON.stringify({subcontractors:s.subcontractors,subProfiles:s.subProfiles})});await reload();editSubcontractorProfile(name)};
  window.toggleDesktopTheme=async function(){const next=preferredTheme()==="dark"?"light":"dark";localStorage.setItem(THEME_KEY,next);state.settings.theme=next;document.documentElement.dataset.theme=next;await api("/api/settings",{method:"POST",body:JSON.stringify({theme:next})});await reload();route="settings";render()};
  function subcontractorAdminPanel(){
    const s=state.settings;
    return `<section class="form-card subcontractor-admin"><div class="spread"><div><h2>Subcontractor database (${s.subcontractors.length})</h2><p class="meta">Company, trade, contact, email, mobile and multiple contacts.</p></div><button class="btn alt" type="button" onclick="addSubcontractor()">+ Add</button></div>${s.subcontractors.map(n=>{const p=subProfile(n);return `<button type="button" class="sub-profile-card" onclick="editSubcontractorProfile('${esc(n)}')"><b>${esc(p.companyName)}</b><span>${esc(p.tradeType||"No trade type")} · ${esc(p.contact||p.contacts[0]?.name||"No contact")}</span><small>${esc(p.email||p.contacts[0]?.email||"No email")} · ${esc(p.mobile||p.phone||p.contacts[0]?.mobile||"No mobile")} · ${p.contacts.length} contact${p.contacts.length===1?"":"s"}</small></button>`}).join("")}</section>`;
  }
  settingsView=function(){const s=state.settings,theme=preferredTheme();return `${subHeader("Settings & Admin")}<form class="settings-scroll" onsubmit="saveSettings(event)"><section class="form-card"><h2>Company & branding</h2><div class="field-list"><label>Company name<input name="company" value="${esc(s.company)}"></label><label>Prepared by<input name="preparedBy" value="${esc(s.preparedBy)}"></label></div><p class="meta">Used on report headers and audit events.</p><button class="btn" style="margin-top:10px">Save</button></section><section class="form-card"><h2>Desktop appearance</h2><p class="meta">Dark mode is active across desktop/admin screens and stays saved.</p><button class="btn alt" type="button" onclick="toggleDesktopTheme()">Dark / night mode: ${theme==="dark"?"On":"Off"}</button></section><section class="form-card"><h2>Projects</h2>${s.projects.map(p=>`<div class="spread" style="padding:10px 0;border-bottom:1px solid var(--line)"><b>${esc(p)}</b>${p===s.activeProject?'<span class="badge complete">Active</span>':""}</div>`).join("")}<div class="actions" style="margin-top:12px"><input id="newProject" placeholder="Add a project…"><button class="btn" type="button" onclick="addProject()">+</button></div></section>${subcontractorAdminPanel()}<section class="form-card"><h2>Session</h2><p class="meta">Sign out on shared devices when you are finished.</p><button class="btn alt" type="button" onclick="logout()">Sign out</button></section>${isProductionApp()?'<section class="form-card"><h2>Demo data</h2><p class="meta">Demo reset is disabled in production.</p></section>':'<section class="form-card"><h2>Demo data</h2><button class="btn danger" type="button" onclick="resetDemo()">↻ Reset to demo data</button></section>'}<div class="meta" style="text-align:center">CleanRun IQ Field App</div></form>`};
  const originalSubcontractorView=subcontractorView;
  subcontractorView=function(){
    if(typeof isSubcontractorPortalUser==="function"&&isSubcontractorPortalUser())return originalSubcontractorView();
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
    return `<header class="screen-header more-header"><div class="logo-box">CLEANRUN <span style="color:#16a34a">IQ</span></div><div style="color:#ffffffb3;margin-top:10px;font-size:13px">Field capture, review & closeout companion</div></header><div class="screen-scroll"><div class="native-card spread"><span style="font-size:22px;color:#16a34a">Sync</span><span style="flex:1"><b>Online</b><small class="meta" style="display:block">All field data synced</small></span><span class="badge"><b>${state.items.length}</b><br>items</span></div>${menuGroup("Closeout workflow",[["Review","Review Queue","Inspect ready work and close/reject","review"]])}${menuGroup("Reporting",[["Report","Reports & Handover","Evidence-chain & closeout reports","reports"]])}${menuGroup("Field roles",[["Subs","Subcontractor Mode","Assigned items & rectification upload","subcontractor"]])}${menuGroup("Admin",[["Setup","Project Setup","Buildings, levels, units & rooms","setup"],["Admin","Settings & Admin","Company, subcontractors, demo data","settings"]])}<div class="meta" style="text-align:center">CleanRun IQ Field App - ${esc(s.company)}</div></div>`;
  };

  function renderMobileNav(){
    if(matchMedia("(min-width:1024px)").matches)return;
    const ready=(state?.items||[]).filter(i=>i.project===state.settings.activeProject&&["ready_for_review","under_inspection"].includes(i.status)).length;
    const items=[["home","Home",navIcon?.home||"⌂"],["items","Items",navIcon?.items||"▤"],["capture","Capture","+"],["review",ready?`Review ${ready}`:"Review","✓"],["more","More",navIcon?.more||"•••"]];
    const active=["reports","settings","setup","subcontractor"].includes(route)?"more":route;
    $("#nav").innerHTML=items.map(([to,label,icon])=>`<button class="${active===to?'active':''} ${to==='capture'?'capture-tab':''}" onclick="${to==='capture'?'quickCapture()':`go('${to}')`}"><span class="tab-icon">${icon}</span><span>${label}</span></button>`).join("");
  }

  function renderDesktopNav(){
    if(!matchMedia("(min-width:1024px)").matches)return;
    const items=[
      ["home","Home",navIcon?.home||"⌂"],
      ["items","Items",navIcon?.items||"▤"],
      ["capture","Capture","+"],
      ["review","Review","✓"],
      ["more","More",navIcon?.more||"•••"]
    ];
    const active=["reports","setup","settings","subcontractor"].includes(route)?"more":route;
    $("#nav").innerHTML=items.map(([to,label,icon])=>`<button class="${active===to?'active':''} ${to==='capture'?'capture-tab':''}" onclick="${to==='capture'?'quickCapture()':`go('${to}')`}"><span class="tab-icon">${icon}</span><span>${label}</span></button>`).join("");
  }
  renderDesktopNav=function(){
    if(!matchMedia("(min-width:1024px)").matches)return;
    const items=[["home","Home",navIcon?.home||"⌂"],["items","Items",navIcon?.items||"▤"],["capture","Capture","+"],["review","Review","✓"],["reports","Reports","▥"],["setup","Project Setup","⚙"],["settings","Settings","☷"],["subcontractor","Subcontractors","⛑"]];
    $("#nav").innerHTML=items.map(([to,label,icon])=>`<button class="${route===to?'active':''} ${to==='capture'?'capture-tab':''}" onclick="${to==='capture'?'quickCapture()':`go('${to}')`}"><span class="tab-icon">${icon}</span><span>${label}</span></button>`).join("");
  };
  const originalRender=render;
  render=function(){
    document.body.dataset.route=route;applyTheme();
    if(route==="review"){$("#app").innerHTML=reviewView();$("#nav").innerHTML="";renderMobileNav();renderDesktopNav();updateOfflinePill();return}
    originalRender();renderMobileNav();renderDesktopNav();
    if(route==="capture"){const photoCard=$("#capturePreviews")?.closest("section");photoCard?.setAttribute("data-photo-card","true");const host=$("#capturePreviews");if(host&&host.childElementCount!==capturePhotos.length)renderCapturePreviews()}
    mountQuickCaptureFab();
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
  const FOCUS_MODES=[["level","Levels"],["unit","Units / areas"],["room","Rooms / locations"],["trade","Trades"],["subcontractor","Subcontractors"]];
  let itemProjectScope="active",itemBuildingValue="",itemFocusMode="level",itemFocusValue="";
  function focusLabel(mode){return (FOCUS_MODES.find(([value])=>value===mode)||FOCUS_MODES[0])[1]}
  function uniqueValues(values){return [...new Set(values.map(v=>String(v||"").trim()).filter(Boolean))].sort((a,b)=>a.localeCompare(b,undefined,{numeric:true,sensitivity:"base"}))}
  function activeConfig(){return state.settings.projectConfigs?.[state.settings.activeProject]||{}}
  function suggestedProjectCodePrefix(project){const first=String(project||"").match(/[A-Za-z0-9]+/)?.[0]||"";return first.slice(0,3).toUpperCase()}
  function sanitizeProjectCodeInput(value){return String(value||"").toUpperCase().replace(/[^A-Z0-9]/g,"").slice(0,6)}
  window.sanitizeProjectCodeInput=sanitizeProjectCodeInput;
  function itemDisplayCode(item){const cfg=state.settings.projectConfigs?.[item.project]||{},prefix=cfg.codePrefixLocked&&cfg.codePrefixHiddenOnCards!==false?cfg.codePrefix:"";return prefix&&item.code?.toUpperCase().startsWith(`${prefix}-`)?item.code.slice(prefix.length+1):item.code}
  function codePrefixCard(cfg){const project=state.settings.activeProject,locked=!!cfg.codePrefixLocked,prefix=cfg.codePrefix||suggestedProjectCodePrefix(project),status=locked?`Locked as ${esc(prefix)}. Cards show DEF-1001; reports keep ${esc(prefix)}-DEF-1001.`:"Choose once for this project. It cannot be changed after locking.";return `<section class="form-card project-code-card"><h2>Item numbering</h2><p class="meta">Attach silent project letters to new item numbers for clean registers across multiple projects.</p><label>Project code prefix<div class="project-code-lock"><input id="projectCodePrefix" maxlength="6" value="${esc(prefix)}" ${locked?"disabled":""} oninput="this.value=sanitizeProjectCodeInput(this.value)"><button class="btn alt" type="button" ${locked?"disabled":""} onclick="lockProjectCodePrefix()"> ${locked?"Locked":"Lock prefix"}</button></div></label><p class="meta">${status}</p></section>`}
  window.lockProjectCodePrefix=async function(){const project=state.settings.activeProject,prefix=sanitizeProjectCodeInput($("#projectCodePrefix")?.value||suggestedProjectCodePrefix(project));if(!prefix)return toast("Add a project prefix before locking.",true);const s=structuredClone(state.settings),cfg=s.projectConfigs[project]||{};cfg.codePrefix=prefix;cfg.codePrefixLocked=true;cfg.codePrefixHiddenOnCards=true;s.projectConfigs[project]=cfg;await api("/api/settings",{method:"POST",body:JSON.stringify({projectConfigs:s.projectConfigs})});await reload();route="setup";render();toast("Project prefix locked")};
  window.uploadSettingsSheet=async function(target,input){const file=input.files?.[0];if(!file)return;const form=new FormData();form.append("target",target);form.append("project",state.settings.activeProject);form.append("file",file);const headers={};if(authToken)headers.Authorization=`Bearer ${authToken}`;try{const res=await fetch("/api/settings/import",{method:"POST",headers,body:form});const data=await res.json().catch(()=>({}));if(!res.ok)throw new Error(data.detail||`Import failed (${res.status})`);await reload();route="setup";render();const label=target==="units"?"unit / area":"subcontractor";toast(`${data.imported||0} ${label} record${data.imported===1?"":"s"} imported`)}catch(err){toast(err.message||"Import failed",true)}finally{input.value=""}};
  function spreadsheetImportCard(){return `<section class="form-card setup-import-card"><h2>Spreadsheet import</h2><p class="meta">Upload Excel or CSV lists to populate setup data faster. Units are added to the active project; subcontractors are added to the project directory.</p><div class="setup-import-actions"><label class="btn alt">Upload units / areas<input hidden type="file" accept=".xlsx,.xlsm,.csv,.tsv" onchange="uploadSettingsSheet('units',this)"></label><label class="btn alt">Upload subcontractors<input hidden type="file" accept=".xlsx,.xlsm,.csv,.tsv" onchange="uploadSettingsSheet('subcontractors',this)"></label></div></section>`}
  function projectScopeOptions(){const projects=state.settings.projects||[];return [["active","Active project"],["all","All projects"],...projects.map(p=>[`project::${p}`,p])]}
  function scopeProjectName(){return itemProjectScope.startsWith("project::")?itemProjectScope.slice(9):state.settings.activeProject}
  function scopeMatches(item){if(itemProjectScope==="all")return true;if(itemProjectScope.startsWith("project::"))return item.project===scopeProjectName();return item.project===state.settings.activeProject}
  function scopedItems(){return state.items.filter(scopeMatches)}
  function buildingValues(){const cfg=activeConfig();return uniqueValues([...(cfg.buildings||[]),...scopedItems().map(i=>i.building)])}
  function itemsAfterBuilding(){return scopedItems().filter(i=>!itemBuildingValue||i.building===itemBuildingValue)}
  function configuredValues(mode){const cfg=activeConfig();if(mode==="level")return cfg.levels||[];if(mode==="unit")return cfg.units||[];if(mode==="room")return cfg.rooms||[];if(mode==="trade")return trades||[];if(mode==="subcontractor")return state.settings.subcontractors||[];return []}
  function focusValues(mode){return uniqueValues([...configuredValues(mode),...itemsAfterBuilding().map(i=>i[mode])])}
  function focusToken(mode,value){return `${mode}::${value}`}
  function focusTokenParts(){const [mode,...rest]=String(itemFocusValue||"").split("::");return rest.length?[mode,rest.join("::")]:["",""]}
  function itemFocusControls(){const buildings=buildingValues();const focusGroups=FOCUS_MODES.map(([mode,label])=>{const values=focusValues(mode);return values.length?`<optgroup label="${esc(label)}">${values.map(v=>{const token=focusToken(mode,v);return `<option value="${esc(token)}" ${token===itemFocusValue?"selected":""}>${esc(label.replace(/s$/,""))}: ${esc(v)}</option>`}).join("")}</optgroup>`:""}).join("");return `<div class="focus-controls"><select id="itemProjectScope" onchange="setItemProjectScope(this.value)">${projectScopeOptions().map(([value,label])=>`<option value="${esc(value)}" ${value===itemProjectScope?"selected":""}>${esc(label)}</option>`).join("")}</select><select id="itemBuildingValue" onchange="setItemBuildingValue(this.value)"><option value="">All buildings</option>${buildings.map(v=>`<option value="${esc(v)}" ${v===itemBuildingValue?"selected":""}>${esc(v)}</option>`).join("")}</select><select id="itemFocusValue" onchange="setItemFocusValue(this.value)"><option value="">All levels, trades and subcontractors</option>${focusGroups}</select></div>`}
  window.setItemProjectScope=function(scope){itemProjectScope=scope;itemBuildingValue="";itemFocusValue="";render()};
  window.setItemBuildingValue=function(value){itemBuildingValue=value;itemFocusValue="";render()};
  window.setItemFocusValue=function(value){itemFocusValue=value;const [mode]=focusTokenParts();if(mode)itemFocusMode=mode;filterItems()};
  const focusedItemsView=itemsView;
  itemsView=function(){const cfg=state.settings.projectConfigs?.[state.settings.activeProject]||{};itemProjectScope=cfg.itemsProjectScope||itemProjectScope||"active";itemFocusMode=cfg.itemsFocusMode||itemFocusMode||"level";const html=focusedItemsView();return html.replace("</div></div><div class=\"screen-scroll\">",`</div>${itemFocusControls()}</div><div class="screen-scroll">`)};
  filterItems=function(){const search=$("#search");if(!search)return;const q=search.value.toLowerCase();const [focusMode,focusValue]=focusTokenParts();const list=state.items.filter(i=>{const focusMatch=!focusValue||String(i[focusMode]||"")===focusValue;return scopeMatches(i)&&(!itemBuildingValue||i.building===itemBuildingValue)&&focusMatch&&(itemTypeFilter==="all"||i.type===itemTypeFilter)&&statusMatch(i,itemStatusFilter)&&(!q||itemSearchHaystack(i).includes(q))}).sort((a,b)=>b.updatedAt.localeCompare(a.updatedAt));$("#itemCount").textContent=`${list.length} item${list.length===1?"":"s"}`;$("#itemList").innerHTML=list.map(itemCard).join("")||'<div class="empty">No items match<br><span class="meta">Try a different project, building, focus area or capture a new item.</span></div>'};
  window.saveItemsProjectScope=async function(scope){const s=structuredClone(state.settings),project=s.activeProject,cfg=s.projectConfigs[project]||{};cfg.itemsProjectScope=scope;s.projectConfigs[project]=cfg;await api("/api/settings",{method:"POST",body:JSON.stringify({projectConfigs:s.projectConfigs})});await reload();route="setup";render();toast("Items project scope saved")};
  window.saveItemsFocusMode=async function(mode){const s=structuredClone(state.settings),project=s.activeProject,cfg=s.projectConfigs[project]||{};cfg.itemsFocusMode=mode;s.projectConfigs[project]=cfg;await api("/api/settings",{method:"POST",body:JSON.stringify({projectConfigs:s.projectConfigs})});await reload();route="setup";render();toast("Items focus saved")};
  const setupWithFocus=setupView;
  setupView=function(){const html=setupWithFocus(),cfg=state.settings.projectConfigs[state.settings.activeProject]||{},scope=cfg.itemsProjectScope||"active",mode=cfg.itemsFocusMode||"level";const card=`${codePrefixCard(cfg)}${spreadsheetImportCard()}<section class="form-card"><h2>Items page focus</h2><p class="meta">Choose the default project scope and third filter group for this project.</p><label>Project scope<select onchange="saveItemsProjectScope(this.value)">${projectScopeOptions().map(([value,label])=>`<option value="${esc(value)}" ${value===scope?"selected":""}>${esc(label)}</option>`).join("")}</select></label><label>Default focus group<select onchange="saveItemsFocusMode(this.value)">${FOCUS_MODES.map(([value,label])=>`<option value="${value}" ${value===mode?"selected":""}>${label}</option>`).join("")}</select></label></section>`;return html.replace("</section>",`</section>${card}`)};
  window.cardAction=function(event,id,act){event.preventDefault();event.stopPropagation();event.stopImmediatePropagation?.();if(cardActionLocks.has(id))return false;const button=event.currentTarget;if(button?.disabled)return false;cardActionLocks.add(id);const release=setBusyButton(button,act==="issue"?"ISSUING...":"WORKING...");(async()=>{const item=state.items.find(x=>x.id===id);if(!item)return toast("Item not found. Refresh and try again.",true);const body={by:state.settings.preparedBy};if(act==="issue"){if(!["open","rejected"].includes(item.status))return toast(`${item.code} is already ${siteStatus(item).label}.`,true);body.to=item.subcontractor||prompt("Subcontractor name:","");body.reissue=item.status==="rejected";if(!body.to)return toast("Choose a subcontractor before issuing.",true)}await api(`/api/items/${id}/actions/${act}`,{method:"POST",body:JSON.stringify(body)});await reload();if(route==="items")filterItems();else render();toast(act==="issue"?"ISSUED - moved to Issued":"Item updated")})().catch(err=>toast(err.message,true)).finally(()=>{cardActionLocks.delete(id);release()});return false};
  function planFit(plan){return {x:0,y:0,scale:1,...(plan?.fit||{})}}
  function pdfSrc(plan){const src=String(plan?.image||"");return src.includes("#")?src:`${src}#toolbar=0&navpanes=0&scrollbar=0&view=Fit`}
  function activePlan(){return state.plans.filter(p=>p.project===state.settings.activeProject)[0]}
  function applyPlanFit(plan,canvas=$("#planCanvas")){if(!plan||!canvas)return;const fit=planFit(plan);canvas.style.setProperty("--plan-x",`${fit.x}px`);canvas.style.setProperty("--plan-y",`${fit.y}px`);canvas.style.setProperty("--plan-scale",String(fit.scale));if(!isPdfPlan(plan)&&!String(plan.image||"").startsWith("seed-plan://")){canvas.style.backgroundSize=`${Math.round(100*fit.scale)}% auto`;canvas.style.backgroundPosition=`calc(50% + ${fit.x}px) calc(50% + ${fit.y}px)`;canvas.style.backgroundRepeat="no-repeat"}const pdf=canvas.querySelector(".plan-pdf");if(pdf){pdf.data=pdfSrc(plan);pdf.style.transform=`translate(${fit.x}px,${fit.y}px) scale(${fit.scale})`}}
  function fitControls(plan){const fit=planFit(plan),locked=!!plan.fitLocked;return `<div class="plan-fit-controls ${locked?"locked":""}"><div><b>${locked?"Plan fit locked":"Adjust plan fit"}</b><small>${locked?"Saved position is being used for pins.":"Move and resize the sheet, then save to lock it."}</small></div>${locked?`<button class="btn alt small" onclick="unlockPlanFit('${plan.id}')">Adjust</button>`:`<button class="btn alt small" onclick="nudgePlanFit('${plan.id}',0,-24)">Up</button><button class="btn alt small" onclick="nudgePlanFit('${plan.id}',-24,0)">Left</button><button class="btn alt small" onclick="nudgePlanFit('${plan.id}',24,0)">Right</button><button class="btn alt small" onclick="nudgePlanFit('${plan.id}',0,24)">Down</button><label>Size <input type="range" min="40" max="220" value="${Math.round(fit.scale*100)}" oninput="setPlanScale('${plan.id}',this.value)"></label><button class="btn small" onclick="savePlanFit('${plan.id}')">Save fit</button>`}</div>`}
  window.nudgePlanFit=function(id,dx,dy){const plan=state.plans.find(p=>p.id===id);if(!plan||plan.fitLocked)return;plan.fit=planFit(plan);plan.fit.x+=dx;plan.fit.y+=dy;applyPlanFit(plan)}
  window.setPlanScale=function(id,value){const plan=state.plans.find(p=>p.id===id);if(!plan||plan.fitLocked)return;plan.fit=planFit(plan);plan.fit.scale=Math.max(.4,Math.min(2.2,Number(value)/100));applyPlanFit(plan)}
  window.savePlanFit=async function(id){const plan=state.plans.find(p=>p.id===id);if(!plan)return;plan.fitLocked=true;await api(`/api/plans/${id}`,{method:"PATCH",body:JSON.stringify({fit:planFit(plan),fitLocked:true})});await reload();route="plans";render();toast("Plan fit saved")}
  window.unlockPlanFit=async function(id){const plan=state.plans.find(p=>p.id===id);if(!plan)return;plan.fitLocked=false;await api(`/api/plans/${id}`,{method:"PATCH",body:JSON.stringify({fit:planFit(plan),fitLocked:false})});await reload();route="plans";render()}
  const fitPlansView=plansView;
  plansView=function(){const html=fitPlansView(),plan=activePlan();return plan?html.replace('<p class="meta">Tap anywhere on the plan to drop a pin</p>',`${fitControls(plan)}<p class="meta">Tap anywhere on the plan to drop a pin</p>`):html}
  const fitWirePlan=wirePlan;
  wirePlan=function(){fitWirePlan();const plan=activePlan(),canvas=$("#planCanvas");if(canvas&&plan)applyPlanFit(plan,canvas)}
  window.openSubcontractorReportPicker=function(){const project=state.settings.activeProject,names=uniqueValues(state.items.filter(i=>i.project===project&&i.subcontractor).map(i=>i.subcontractor));if(!names.length)return toast("No subcontractors found for this project.",true);$("#modalTitle").textContent="Subcontractor Summary";$("#modalBody").innerHTML=`<div class="field-list"><label>Subcontractor<select id="reportSubcontractor">${names.map(name=>`<option value="${esc(name)}">${esc(name)}</option>`).join("")}</select></label><button class="btn" type="button" onclick="openSelectedSubcontractorReport()">Open report</button></div>`;$("#modal").hidden=false};
  window.openSelectedSubcontractorReport=function(){const value=$("#reportSubcontractor")?.value;if(!value)return toast("Choose a subcontractor.",true);closeModal();openReport("subcontractor",{subcontractor:value})};
  reportsView=function(){const project=state.settings.activeProject,items=state.items.filter(i=>i.project===project),closed=i=>["closed","complete"].includes(i.status),missingOriginal=i=>(i.type==="defect"||i.type==="client")&&!(i.originalPhotos||[]).length,missingRect=i=>!closed(i)&&!(i.rectificationEvidence||[]).length,missingClose=i=>closed(i)&&!(i.closeoutEvidence||[]).length,exception=i=>overdue(i)||i.status==="rejected"||missingOriginal(i)||missingRect(i)||missingClose(i);const reports=[["register","Project Defect Register","Working register for all defects, incomplete works, statuses, assignment and due dates"],["handover","Handover Evidence Pack","Closed and complete items with original, rectification and closeout evidence"],["exceptions","Exceptions Report","Unresolved risk items: overdue, rejected, missing evidence and past due work"],["subcontractor","Subcontractor Summary","Choose one subcontractor and generate a targeted follow-up report"],["client","Client Defects","Client-side defects and superintendent-raised issues"],["incomplete","Incomplete Works","Incomplete work items separated from defect closeout"]];const count=id=>id==="register"?items.length:id==="handover"?items.filter(closed).length:id==="exceptions"?items.filter(exception).length:id==="subcontractor"?uniqueValues(items.map(i=>i.subcontractor)).length:id==="client"?items.filter(i=>i.type==="client").length:id==="incomplete"?items.filter(i=>i.type==="incomplete").length:items.length;return `${subHeader('Reports & Handover')}<div class="screen-scroll"><div class="native-card" style="text-align:center"><div class="logo-box" style="display:inline-block">CLEANRUN <span style="color:#20C55E">IQ</span></div><div class="meta" style="margin-top:8px">${esc(project)} - prepared by ${esc(state.settings.preparedBy)}</div></div><div class="report-grid">${reports.map(([id,title,desc],n)=>{const action=id==="subcontractor"?"openSubcontractorReportPicker()":`openReport('${id}')`;return `<article class="native-card report ${n===0?'hero':''}" role="link" tabindex="0" onclick="${action}" onkeydown="if(event.key==='Enter'||event.key===' '){event.preventDefault();${action}}"><div class="item-main"><span class="menu-icon">${n<3?'▥':'▤'}</span><span style="flex:1"><h2>${title}</h2><p class="subtle">${desc}</p><b style="font-size:11px;color:${n<3?'#20C55E':'#121619'}">${count(id)} ${id==="subcontractor"?"subcontractor":"item"}${count(id)===1?'':'s'}</b></span><span class="chev">›</span></div></article>`}).join('')}</div><p class="meta" style="text-align:center">Reports are structured as professional evidence documents with cover summary, item index, grouped detail cards and explicit missing-evidence states.</p></div>`}
  function rerenderLatestHome(){if(typeof state!=="undefined"&&state&&route==="home")render()}
  ensureWorkbench();updateOfflinePill();setTimeout(rerenderLatestHome,0);setTimeout(rerenderLatestHome,250);window.addEventListener("load",rerenderLatestHome);initialiseOfflineStore();
})();
