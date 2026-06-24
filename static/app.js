(function() {
    'use strict';
    var type='video', quality='1080p', audioFmt=null, audioMode='video', subs=false, artFmt='pdf', poll=null;
    var projects=[], activeProject='all';
    var input=document.getElementById('urlInput');
    var debounce;

    input.addEventListener('input', function(){clearTimeout(debounce);var u=input.value.trim();u.length>8?debounce=setTimeout(function(){det(u)},300):hideType()});
    input.addEventListener('keydown', function(e){if(e.key==='Enter')startDownload()});

    function det(u){
        u=u.toLowerCase();
        if(/^10\.\d{4,}/.test(u)||/doi\.org\/10\./.test(u))return showT('doi','\u{1F4C4}','Academic Paper (DOI)','DOI resolution');
        if(u.includes('arxiv.org'))return showT('arxiv','\u{1F4D1}','arXiv Paper','Preprint');
        if(u.includes('pubmed')||u.includes('ncbi.nlm.nih.gov'))return showT('pubmed','\u{1F3E5}','PubMed','Medical literature');
        if(/springer|wiley|sciencedirect|nature\.com|science\.org|ieee|acm/.test(u))return showT('academic','\u{1F4DA}','Academic Article','Journal article');
        showT('video','\u{1F3AC}','Video','YouTube, Vimeo, TikTok + 1000 more');
    }

    function showT(t,icon,label,hint){
        type=t;document.getElementById('typeIcon').textContent=icon;
        document.getElementById('typeLabel').textContent=label;
        document.getElementById('typeHint').textContent=hint;
        document.getElementById('typeBadge').classList.add('active');
        document.getElementById('optionsPanel').classList.add('active');
        document.getElementById('videoOptions').style.display=t==='video'?'block':'none';
        document.getElementById('articleOptions').style.display=t!=='video'?'block':'none';
    }

    function hideType(){document.getElementById('typeBadge').classList.remove('active');document.getElementById('optionsPanel').classList.remove('active');type='video'}

    window.pickQ=function(el){document.querySelectorAll('.quality-card').forEach(function(c){c.classList.remove('selected')});el.classList.add('selected');quality=el.dataset.q};
    window.setMode=function(m){audioMode=m;document.querySelectorAll('.audio-toggle-btn').forEach(function(b){b.classList.toggle('active',b.dataset.mode===m)});document.getElementById('audioFormats').classList.toggle('active',m==='audio');document.querySelectorAll('.quality-card').forEach(function(c){c.style.opacity=m==='audio'?'0.4':'1'});if(m==='audio'){quality='audio';document.querySelectorAll('.quality-card').forEach(function(c){c.classList.remove('selected')})}else{var d=document.querySelector('.quality-card[data-q="1080p"]');if(d){d.classList.add('selected');quality='1080p'}}};
    window.pickA=function(el){document.querySelectorAll('.audio-chip[data-fmt]').forEach(function(c){c.classList.remove('selected')});el.classList.add('selected');audioFmt=el.dataset.fmt};
    window.pickArt=function(el){document.querySelectorAll('#articleOptions .audio-chip').forEach(function(c){c.classList.remove('selected')});el.classList.add('selected');artFmt=el.dataset.fmt};
    window.togSub=function(){subs=!subs;document.getElementById('subToggle').classList.toggle('active',subs)};

    window.startDownload=function(){
        var url=input.value.trim();if(!url)return;
        var btn=document.getElementById('downloadBtn');
        btn.classList.add('loading');btn.disabled=true;
        document.getElementById('progressSection').classList.add('active');
        resetProg();showSt('loading','Resolving...');

        fetch('/api/download',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url:url,type:type==='video'?'auto':type,quality:quality,format:audioMode==='audio'?(audioFmt||'mp3'):'mp4',subtitles:subs})})
        .then(function(res){return res.json()})
        .then(function(d){if(d.error)throw new Error(d.error);pollSt(d.download_id,d.type)})
        .catch(function(e){showSt('error',e.message||'Failed')})
        .finally(function(){btn.classList.remove('loading');btn.disabled=false});
    };

    function pollSt(id,dlType){
        var misses=0;
        poll=setInterval(function(){
            fetch('/api/status/'+encodeURIComponent(id))
            .then(function(r){return r.json()})
            .then(function(d){
                if(d.status==='error'){clearInterval(poll);showSt('error',d.message||d.error)}
                else if(d.status==='complete'){clearInterval(poll);updProg(d);setPh('ready');if(d.filename){showSt('success','Ready \u2014 saved to library');triggerDl(id)}else{showSt('success',d.message||'Found \u2014 no downloadable file available')}refreshLibIfOpen()}
                else if(d.status==='not_found'){if(++misses>8){clearInterval(poll);showSt('error','Download not found')}}
                else{misses=0;updProg(d);setPh(d.phase||d.status)}
            })
            .catch(function(){clearInterval(poll);showSt('error','Connection lost')});
        },700);
    }

    function updProg(d){
        var p=d.progress||'0';
        document.getElementById('progressFill').style.width=p+'%';
        document.getElementById('statProgress').textContent=p+'%';
        document.getElementById('statSpeed').textContent=d.speed||'\u2014';
        document.getElementById('statEta').textContent=d.eta||'\u2014';
        var l={starting:'Init',downloading:'Download',fetching:'Fetch',processing:'Process',encoding:'Encode',complete:'Done'};
        document.getElementById('statStatus').textContent=l[d.status]||d.status;

        if(d.type==='article'&&d.title){
            document.getElementById('paperInfo').classList.add('active');
            document.getElementById('paperTitle').textContent=d.title;
            document.getElementById('paperAuthors').textContent=(d.authors||[]).join(', ');
            document.getElementById('paperDoi').textContent=d.doi||'';
            document.getElementById('paperJournal').textContent=d.journal||'';
            document.getElementById('paperYear').textContent=d.year||'';
        }

        var st=d.status==='complete'?'success':'loading';
        showSt(st,d.message||'Working...');
    }

    function setPh(p){
        ['phase1','phase2','phase3'].forEach(function(id){document.getElementById(id).className='phase'});
        if(['init','starting','downloading','fetching'].indexOf(p)!==-1)document.getElementById('phase1').classList.add('active');
        else if(['processing','encoding'].indexOf(p)!==-1){document.getElementById('phase1').classList.add('done');document.getElementById('phase2').classList.add('active')}
        else if(['ready','complete'].indexOf(p)!==-1){document.getElementById('phase1').classList.add('done');document.getElementById('phase2').classList.add('done');document.getElementById('phase3').classList.add('active')}
    }

    function resetProg(){document.getElementById('progressFill').style.width='0%';document.getElementById('statProgress').textContent='0%';document.getElementById('statSpeed').textContent='\u2014';document.getElementById('statEta').textContent='\u2014';document.getElementById('statStatus').textContent='Waiting';document.getElementById('paperInfo').classList.remove('active');document.getElementById('statusBar').classList.remove('active');['phase1','phase2','phase3'].forEach(function(id){document.getElementById(id).className='phase'})}

    function showSt(t,msg){var b=document.getElementById('statusBar');b.className='status-bar active '+t;document.getElementById('statusMsg').textContent=msg}

    function triggerDl(id){var a=document.createElement('a');a.href='/api/stream/'+encodeURIComponent(id);a.style.display='none';document.body.appendChild(a);a.click();setTimeout(function(){a.remove()},1000)}

    // Institution
    var insts=[
        {n:'MIT',r:'USA'},{n:'Harvard',r:'USA'},{n:'Stanford',r:'USA'},{n:'Oxford',r:'UK'},
        {n:'Cambridge',r:'UK'},{n:'ETH Zurich',r:'Switzerland'},{n:'U of Tokyo',r:'Japan'},
        {n:'NUS',r:'Singapore'},{n:'U of Cape Town',r:'South Africa'},{n:'U of Nairobi',r:'Kenya'},
        {n:'Makerere',r:'Uganda'},{n:'U of Ghana',r:'Ghana'},{n:'U of Malaya',r:'Malaysia'},
        {n:'U of S\u00e3o Paulo',r:'Brazil'},{n:'IISc',r:'India'},{n:'Tsinghua',r:'China'},
        {n:'Seoul National',r:'South Korea'},{n:'U of Buenos Aires',r:'Argentina'},
    ];
    window.openInst=function(){document.getElementById('instModal').classList.add('active');filterInst('')};
    window.filterInst=function(q){document.getElementById('instList').innerHTML=insts.filter(function(i){return i.n.toLowerCase().indexOf(q.toLowerCase())!==-1||i.r.toLowerCase().indexOf(q.toLowerCase())!==-1}).map(function(i){return '<div class="inst-item" data-url="https://login.research4life.org/" onclick="window.open(this.dataset.url,\'_blank\');document.getElementById(\'instModal\').classList.remove(\'active\')"><div class="inst-icon">\u{1F3DB}\uFE0F</div><div><div class="inst-name">'+i.n+'</div><div class="inst-region">'+i.r+'</div></div></div>'}).join('')};
    window.openR4L=function(){document.getElementById('r4lModal').classList.add('active')};
    window.openSH=function(){var u=input.value.trim();var m=u.match(/10\.\d{4,}\/[^\s&?]+/);window.open(m?'https://sci-hub.su/'+m[0]:'https://sci-hub.su','_blank')};
    window.openOA=function(){var u=input.value.trim();var m=u.match(/10\.\d{4,}\/[^\s&?]+/);window.open(m?'https://api.unpaywall.org/v2/'+m[0]+'?email=dl@rs.app':'https://unpaywall.org','_blank')};

    // ── Library ──────────────────────────────────────────────────────
    var TYPE_ICON={video:'\u{1F3AC}',article:'\u{1F4C4}'};
    function esc(s){return String(s==null?'':s).replace(/[&<>"']/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]})}
    function fmtSize(b){b=Number(b)||0;if(!b)return'';var u=['B','KB','MB','GB','TB'],i=0;while(b>=1024&&i<u.length-1){b/=1024;i++}return b.toFixed(i?1:0)+' '+u[i]}
    function mainEls(){return[document.querySelector('.hero'),document.querySelector('.input-card'),document.getElementById('progressSection'),document.getElementById('features')]}

    window.showLibrary=function(){mainEls().forEach(function(e){if(e)e.style.display='none'});document.getElementById('libraryView').style.display='block';window.scrollTo(0,0);loadDrive();loadProjects();loadLibrary('')};
    window.showMain=function(){document.getElementById('libraryView').style.display='none';mainEls().forEach(function(e){if(e&&e.id!=='progressSection')e.style.display=''})};

    function refreshLibIfOpen(){if(document.getElementById('libraryView').style.display==='block'){var s=document.getElementById('libSearch');loadLibrary(s?s.value.trim():'')}}

    function loadLibrary(q){
        var params=[];
        if(q)params.push('q='+encodeURIComponent(q));
        if(activeProject&&activeProject!=='all')params.push('project='+encodeURIComponent(activeProject));
        fetch('/api/library'+(params.length?('?'+params.join('&')):''))
        .then(function(r){return r.json()})
        .then(function(d){renderLib(d.resources||[])})
        .catch(function(){});
    }
    var libDebounce;
    window.searchLib=function(q){clearTimeout(libDebounce);libDebounce=setTimeout(function(){loadLibrary((q||'').trim())},250)};

    function renderLib(items){
        var grid=document.getElementById('libList'),empty=document.getElementById('libEmpty');
        if(!items.length){grid.innerHTML='';empty.style.display='block';return}
        empty.style.display='none';
        grid.innerHTML=items.map(function(it){
            var m=it.meta||{};
            var sub=[it.type,m.journal,m.year].filter(Boolean).join(' · ');
            var sz=fmtSize(it.size);
            return '<div class="lib-card">'+
                '<div class="lib-icon">'+(TYPE_ICON[it.type]||'\u{1F4E6}')+'</div>'+
                '<div class="lib-body"><div class="lib-title">'+esc(it.title||it.filename||'Untitled')+'</div>'+
                '<div class="lib-sub">'+esc(sub)+(sz?(' · '+sz):'')+'</div></div>'+
                '<div class="lib-actions">'+
                projMoveSelect(it)+
                (it.filename?('<button class="lib-btn lib-ask" data-id="'+esc(it.id)+'" data-title="'+esc(it.title||it.filename||'')+'">Ask</button>'):'')+
                (it.filename?('<a class="lib-btn" href="/api/stream/'+encodeURIComponent(it.id)+'">Download</a>'):'')+
                (it.filename&&drive.connected?('<button class="lib-btn lib-drive" data-id="'+esc(it.id)+'">Drive</button>'):'')+
                '<button class="lib-btn lib-del" data-id="'+esc(it.id)+'">Delete</button>'+
                '</div></div>';
        }).join('');
        Array.prototype.forEach.call(grid.querySelectorAll('.lib-del'),function(b){b.onclick=function(){delRes(b.getAttribute('data-id'))}});
        Array.prototype.forEach.call(grid.querySelectorAll('.lib-drive'),function(b){b.onclick=function(){syncDrive(b.getAttribute('data-id'),b)}});
        Array.prototype.forEach.call(grid.querySelectorAll('.lib-ask'),function(b){b.onclick=function(){setAskScope(b.getAttribute('data-id'),b.getAttribute('data-title'))}});
        Array.prototype.forEach.call(grid.querySelectorAll('.lib-move'),function(s){s.onchange=function(){moveResource(s.getAttribute('data-id'),s.value)}});
    }

    function projMoveSelect(it){
        var opts='<option value="">Unfiled</option>'+projects.map(function(p){
            return '<option value="'+esc(p.id)+'"'+(it.project_id===p.id?' selected':'')+'>'+esc(p.name)+'</option>';
        }).join('');
        return '<select class="lib-move" data-id="'+esc(it.id)+'" title="Move to project">'+opts+'</select>';
    }
    function moveResource(id,pid){
        fetch('/api/resource/move',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:id,project:pid})})
        .then(function(r){return r.json()}).then(function(){loadProjects();refreshLibIfOpen()}).catch(function(){});
    }

    function delRes(id){
        fetch('/api/delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:id})})
        .then(function(r){return r.json()})
        .then(function(){refreshLibIfOpen()})
        .catch(function(){});
    }

    // ── Google Drive ─────────────────────────────────────────────────
    var drive={configured:false,connected:false,email:null};
    function loadDrive(){
        return fetch('/api/auth/status').then(function(r){return r.json()})
        .then(function(d){drive=d;renderDriveBar()})
        .catch(function(){});
    }
    function renderDriveBar(){
        var bar=document.getElementById('driveBar');
        if(!drive.configured){bar.style.display='none';return}
        bar.style.display='flex';
        if(drive.connected){
            bar.innerHTML='<span class="drive-status"><span class="drive-dot on"></span>Drive connected'+(drive.email?(' · '+esc(drive.email)):'')+'</span>'+
                '<button class="drive-btn ghost" id="driveLogout">Disconnect</button>';
            document.getElementById('driveLogout').onclick=function(){
                fetch('/api/auth/logout',{method:'POST'}).then(function(){loadDrive().then(refreshLibIfOpen)})};
        }else{
            bar.innerHTML='<span class="drive-status"><span class="drive-dot"></span>Save your library to Google Drive</span>'+
                '<button class="drive-btn" onclick="window.connectDrive()">Connect Drive</button>';
        }
    }
    window.connectDrive=function(){window.location.href='/api/auth/google/start'};
    function syncDrive(id,btn){
        if(btn){btn.disabled=true;btn.textContent='…'}
        fetch('/api/drive/sync',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:id})})
        .then(function(r){return r.json()})
        .then(function(d){if(btn){btn.disabled=false;btn.textContent=d.synced?'✓ Drive':'Drive';if(d.error)btn.textContent='Failed'}})
        .catch(function(){if(btn){btn.disabled=false;btn.textContent='Failed'}});
    }

    // ── AI assistant ─────────────────────────────────────────────────
    var askScopeId=null;
    function setAskScope(id,title){
        askScopeId=id;
        var s=document.getElementById('askScope');
        s.style.display='flex';
        s.innerHTML='<span class="ask-scope-text">Asking about: '+esc(title||'this resource')+'</span><button class="ask-scope-x" id="askScopeX">×</button>';
        document.getElementById('askScopeX').onclick=clearAskScope;
        var inp=document.getElementById('askInput');inp.placeholder='Ask about this resource...';inp.focus();
        window.scrollTo({top:0,behavior:'smooth'});
    }
    function clearAskScope(){askScopeId=null;document.getElementById('askScope').style.display='none';document.getElementById('askInput').placeholder='Ask the AI about your library...'}

    window.askAI=function(){
        var inp=document.getElementById('askInput');var q=inp.value.trim();if(!q)return;
        var btn=document.getElementById('askBtn');var ans=document.getElementById('askAnswer');
        btn.disabled=true;btn.textContent='…';
        ans.style.display='block';ans.className='ask-answer loading';ans.textContent='Thinking…';
        var provider=document.getElementById('askProvider').value||undefined;
        var key=document.getElementById('askKey').value.trim();
        if(key)sessionStorage.setItem('rs_ai_key',key); else key=sessionStorage.getItem('rs_ai_key')||undefined;
        var body={question:q};
        if(askScopeId)body.id=askScopeId;
        else if(activeProject&&activeProject!=='all'&&activeProject!=='unfiled')body.project=activeProject;
        if(provider)body.provider=provider;
        if(key)body.key=key;
        fetch('/api/ai/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})
        .then(function(r){return r.json()})
        .then(function(d){
            btn.disabled=false;btn.textContent='Ask';
            if(d.error){ans.className='ask-answer error';ans.textContent=d.error;return}
            ans.className='ask-answer';
            ans.innerHTML='<div class="ask-text"></div><div class="ask-model">'+esc((d.provider||'')+' · '+(d.model||''))+'</div>';
            ans.querySelector('.ask-text').textContent=d.answer||'(no answer)';
        })
        .catch(function(){btn.disabled=false;btn.textContent='Ask';ans.className='ask-answer error';ans.textContent='Request failed.'});
    };

    // ── Projects ─────────────────────────────────────────────────────
    function loadProjects(){
        return fetch('/api/projects').then(function(r){return r.json()})
        .then(function(d){projects=d.projects||[];renderProjBar()}).catch(function(){});
    }
    function renderProjBar(){
        var bar=document.getElementById('projBar');
        function chip(key,label,count){
            var on=activeProject===key;
            return '<button class="proj-chip'+(on?' on':'')+'" data-k="'+esc(key)+'">'+esc(label)+(count!=null?(' <span class="proj-count">'+count+'</span>'):'')+'</button>';
        }
        var html=chip('all','All')+chip('unfiled','Unfiled');
        html+=projects.map(function(p){return chip(p.id,p.name,p.count)}).join('');
        html+='<button class="proj-chip proj-new" id="projNew">+ New</button>';
        bar.innerHTML=html;
        Array.prototype.forEach.call(bar.querySelectorAll('.proj-chip[data-k]'),function(b){b.onclick=function(){selectProject(b.getAttribute('data-k'))}});
        var nb=document.getElementById('projNew'); if(nb)nb.onclick=newProject;
        // right-click a project chip to rename/delete
        Array.prototype.forEach.call(bar.querySelectorAll('.proj-chip[data-k]'),function(b){
            var k=b.getAttribute('data-k');
            if(k==='all'||k==='unfiled')return;
            b.oncontextmenu=function(e){e.preventDefault();projectMenu(k)};
        });
    }
    function selectProject(k){activeProject=k;renderProjBar();loadLibrary(libQuery())}
    function libQuery(){var s=document.getElementById('libSearch');return s?s.value.trim():''}
    function newProject(){
        var name=prompt('Project name:'); if(!name)return; name=name.trim(); if(!name)return;
        fetch('/api/projects',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:name})})
        .then(function(r){return r.json()}).then(function(d){if(d.project){activeProject=d.project.id}loadProjects().then(function(){renderProjBar();loadLibrary('')})}).catch(function(){});
    }
    function projectMenu(id){
        var p=projects.filter(function(x){return x.id===id})[0]; if(!p)return;
        var act=prompt('Type "rename" or "delete" for project "'+p.name+'":'); if(!act)return;
        act=act.trim().toLowerCase();
        if(act==='delete'){
            fetch('/api/projects/delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:id})})
            .then(function(){if(activeProject===id)activeProject='all';loadProjects().then(function(){loadLibrary('')})});
        }else if(act==='rename'){
            var nn=prompt('New name:',p.name); if(!nn)return;
            fetch('/api/projects/rename',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:id,name:nn.trim()})})
            .then(function(){loadProjects()});
        }
    }

    // ── Settings (AI providers) ──────────────────────────────────────
    var PROVIDER_LABELS={openai:'OpenAI',anthropic:'Anthropic (Claude)',groq:'Groq',openrouter:'OpenRouter',custom:'Custom',ollama:'Ollama (local)'};
    window.openSettings=function(){loadSettings();document.getElementById('settingsModal').classList.add('active')};
    function loadSettings(){
        fetch('/api/ai/status').then(function(r){return r.json()}).then(function(d){
            // default provider dropdown: ready + connected + catalog
            var avail={}; (d.providers||[]).forEach(function(p){avail[p.provider]=p.model});
            (d.connected||[]).forEach(function(c){avail[c.provider]=c.model||avail[c.provider]});
            var sel=document.getElementById('setProvider');
            var opts='<option value="">Auto (best available)</option>';
            (d.catalog||[]).forEach(function(p){
                var ready=avail.hasOwnProperty(p)?' ✓':'';
                opts+='<option value="'+p+'">'+(PROVIDER_LABELS[p]||p)+ready+'</option>';
            });
            sel.innerHTML=opts;
            sel.value=(d.settings&&d.settings.default_provider)||'';
            document.getElementById('setModel').value=(d.settings&&d.settings.default_model)||'';
            // connected list
            var c=document.getElementById('setConnected');
            var list=(d.connected||[]);
            if(!list.length){c.innerHTML='<div class="set-empty">No providers connected. Ollama and any env keys work automatically.</div>'}
            else{c.innerHTML=list.map(function(x){
                return '<div class="set-conn"><span><b>'+(PROVIDER_LABELS[x.provider]||x.provider)+'</b> <span class="set-hint">'+esc(x.model||'')+' · key '+esc(x.key_hint)+'</span></span><button class="drive-btn ghost" data-p="'+esc(x.provider)+'">Disconnect</button></div>';
            }).join('');
            Array.prototype.forEach.call(c.querySelectorAll('button[data-p]'),function(b){b.onclick=function(){disconnectProvider(b.getAttribute('data-p'))}});}
        }).catch(function(){});
    }
    window.onAddProvider=function(){document.getElementById('addBase').style.display=document.getElementById('addProvider').value==='custom'?'block':'none'};
    window.saveSettings=function(){
        fetch('/api/ai/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({default_provider:document.getElementById('setProvider').value,default_model:document.getElementById('setModel').value.trim()})})
        .then(function(r){return r.json()}).then(function(){var m=document.getElementById('addMsg');m.textContent='Saved.';m.className='set-msg ok';setTimeout(function(){m.textContent=''},1500)});
    };
    window.connectProvider=function(){
        var body={provider:document.getElementById('addProvider').value,key:document.getElementById('addKey').value.trim(),model:document.getElementById('addModel').value.trim(),base_url:document.getElementById('addBase').value.trim()};
        var m=document.getElementById('addMsg');m.textContent='Connecting…';m.className='set-msg';
        fetch('/api/ai/connect',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})
        .then(function(r){return r.json()}).then(function(d){
            if(d.error){m.textContent=d.error;m.className='set-msg err';return}
            m.textContent='Connected.';m.className='set-msg ok';
            document.getElementById('addKey').value='';document.getElementById('addModel').value='';document.getElementById('addBase').value='';
            loadSettings();
        }).catch(function(){m.textContent='Failed.';m.className='set-msg err'});
    };
    function disconnectProvider(p){
        fetch('/api/ai/disconnect',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({provider:p})})
        .then(function(){loadSettings()});
    }

    // React to the OAuth redirect landing back on the page
    (function(){
        var p=new URLSearchParams(window.location.search);
        if(p.get('drive')){history.replaceState({},'',window.location.pathname);window.showLibrary()}
    })();
})();
