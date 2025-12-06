// reverig-tool button injection (standalone plugin)
(function() {
    'use strict';
    
    // Forward logs to Millennium backend so they appear in the dev console
    function backendLog(message) {
        try {
            if (typeof Millennium !== 'undefined' && typeof Millennium.callServerMethod === 'function') {
                Millennium.callServerMethod('reverig-tool', 'Logger.warn', { message: String(message) });
            }
        } catch (err) {
            if (typeof console !== 'undefined' && console.warn) {
                console.warn('[reverig-tool] backendLog failed', err);
            }
        }
    }
    
    backendLog('reverig-tool script loaded');
    // anti-spam state
    const logState = { missingOnce: false, existsOnce: false };
    // click/run debounce state
    const runState = { inProgress: false, appid: null };
    
    // Helper: show a Steam-style popup with a 10s loading bar (custom UI)
    function showTestPopup() {

        // Avoid duplicates
        if (document.querySelector('.reverig-tool-overlay')) return;

        const overlay = document.createElement('div');
        overlay.className = 'reverig-tool-overlay';
        overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.6);z-index:99999;display:flex;align-items:center;justify-content:center;';

        const modal = document.createElement('div');
        modal.style.cssText = 'background:#1b2838;color:#fff;border:1px solid #2a475e;border-radius:4px;min-width:340px;max-width:560px;padding:18px 20px;box-shadow:0 8px 24px rgba(0,0,0,.6);';

        const title = document.createElement('div');
        title.style.cssText = 'font-size:16px;color:#66c0f4;margin-bottom:10px;font-weight:600;';
        title.className = 'reverig-tool-title';
        title.textContent = 'reverig-tool';

        const body = document.createElement('div');
        body.style.cssText = 'font-size:14px;line-height:1.4;margin-bottom:12px;';
        body.className = 'reverig-tool-status';
        body.textContent = 'Working…';

        const progressWrap = document.createElement('div');
        progressWrap.style.cssText = 'background:#2a475e;height:10px;border-radius:4px;overflow:hidden;position:relative;display:none;';
        progressWrap.className = 'reverig-tool-progress-wrap';
        const progressBar = document.createElement('div');
        progressBar.style.cssText = 'height:100%;width:0%;background:#66c0f4;transition:width 0.1s linear;';
        progressBar.className = 'reverig-tool-progress-bar';
        progressWrap.appendChild(progressBar);

        const percent = document.createElement('div');
        percent.style.cssText = 'text-align:right;color:#8f98a0;margin-top:8px;font-size:12px;display:none;';
        percent.className = 'reverig-tool-percent';
        percent.textContent = '0%';

        const btnRow = document.createElement('div');
        btnRow.style.cssText = 'margin-top:16px;display:flex;gap:8px;justify-content:flex-end;';
        const closeBtn = document.createElement('a');
        closeBtn.className = 'btnv6_blue_hoverfade btn_medium';
        closeBtn.innerHTML = '<span>Close</span>';
        closeBtn.href = '#';
        closeBtn.onclick = function(e){ e.preventDefault(); cleanup(); };
        btnRow.appendChild(closeBtn);

        modal.appendChild(title);
        modal.appendChild(body);
        modal.appendChild(progressWrap);
        modal.appendChild(percent);
        modal.appendChild(btnRow);
        overlay.appendChild(modal);
        overlay.addEventListener('click', function(e){ if (e.target === overlay) cleanup(); });
        document.body.appendChild(overlay);

        function cleanup(){
            overlay.remove();
        }
    }


    // Ensure consistent spacing for our buttons
    function ensureStyles() {
        if (!document.getElementById('reverig-tool-styles')) {
            const style = document.createElement('style');
            style.id = 'reverig-tool-styles';
            style.textContent = '.reverig-tool-restart-button, .reverig-tool-button{ margin-left:6px !important; }';
            document.head.appendChild(style);
        }
    }


    // Function to add the reverig-tool button
    function addReverigToolButton() {
        // Look for the SteamDB buttons container
        const steamdbContainer = document.querySelector('.steamdb-buttons') || 
                                document.querySelector('[data-steamdb-buttons]') ||
                                document.querySelector('.apphub_OtherSiteInfo');

        if (steamdbContainer) {
            // Check if button already exists to avoid duplicates
            if (document.querySelector('.reverig-tool-button') || window.__reverigToolButtonInserted) {
                if (!logState.existsOnce) { backendLog('reverig-tool button already exists, skipping'); logState.existsOnce = true; }
                // Even if reverig-tool exists, ensure Restart button is present
            }

            // Insert a Restart Steam button between Community Hub and our reverig-tool button
            try {
                if (!document.querySelector('.reverig-tool-restart-button') && !window.__reverigToolRestartInserted) {
                    ensureStyles();
                    const referenceBtn = steamdbContainer.querySelector('a');
                    const restartBtn = document.createElement('a');
                    if (referenceBtn && referenceBtn.className) {
                        restartBtn.className = referenceBtn.className + ' reverig-tool-restart-button';
                    } else {
                        restartBtn.className = 'btnv6_blue_hoverfade btn_medium reverig-tool-restart-button';
                    }
                    restartBtn.href = '#';
                    restartBtn.title = 'Restart Steam';
                    restartBtn.setAttribute('data-tooltip-text', 'Restart Steam');
                    const rspan = document.createElement('span');
                    rspan.textContent = 'Restart Steam';
                    restartBtn.appendChild(rspan);
                    // Normalize margins to match native buttons
                    try {
                        if (referenceBtn) {
                            const cs = window.getComputedStyle(referenceBtn);
                            restartBtn.style.marginLeft = cs.marginLeft;
                            restartBtn.style.marginRight = cs.marginRight;
                        }
                    } catch(_) {}

                    restartBtn.addEventListener('click', function(e){
                        e.preventDefault();
                        try {
                            if (typeof ShowConfirmDialog === 'function') {
                                // ShowConfirmDialog(title, message) returns a promise when confirmed
                                const p = ShowConfirmDialog('reverig-tool', 'Restart Steam now?');
                                if (p && typeof p.then === 'function') {
                                    p.then(function(){ try { Millennium.callServerMethod('reverig-tool', 'RestartSteam', { contentScriptQuery: '' }); } catch(_) {} });
                                }
                            } else {
                                if (window.confirm('Restart Steam now?')) { try { Millennium.callServerMethod('reverig-tool', 'RestartSteam', { contentScriptQuery: '' }); } catch(_) {} }
                            }
                        } catch(_) {
                            if (window.confirm('Restart Steam now?')) { try { Millennium.callServerMethod('reverig-tool', 'RestartSteam', { contentScriptQuery: '' }); } catch(_) {} }
                        }
                    });

                    if (referenceBtn && referenceBtn.parentElement) {
                        referenceBtn.after(restartBtn);
                    } else {
                        steamdbContainer.appendChild(restartBtn);
                    }
                    window.__reverigToolRestartInserted = true;
                    backendLog('Inserted Restart Steam button');
                }
            } catch(_) {}

            // If reverig-tool button already existed, stop here
            if (document.querySelector('.reverig-tool-button') || window.__reverigToolButtonInserted) {
                return;
            }
            
            // Create the reverig-tool button modeled after existing SteamDB/PCGW buttons
            let referenceBtn = steamdbContainer.querySelector('a');
                    const reverigToolButton = document.createElement('a');
                    reverigToolButton.href = '#';
            // Copy classes from an existing button to match look-and-feel, but set our own label
            if (referenceBtn && referenceBtn.className) {
                reverigToolButton.className = referenceBtn.className + ' reverig-tool-button';
            } else {
                reverigToolButton.className = 'btnv6_blue_hoverfade btn_medium reverig-tool-button';
            }
            const span = document.createElement('span');
            span.textContent = 'Add via reverig-tool';
            reverigToolButton.appendChild(span);
            // Tooltip/title
            reverigToolButton.title = 'Add via reverig-tool';
            reverigToolButton.setAttribute('data-tooltip-text', 'Add via reverig-tool');
            reverigToolButton.setAttribute('data-reverig-tool-mode', 'add');
            // Normalize margins to match native buttons
            try {
                if (referenceBtn) {
                    const cs = window.getComputedStyle(referenceBtn);
                    reverigToolButton.style.marginLeft = cs.marginLeft;
                    reverigToolButton.style.marginRight = cs.marginRight;
                }
            } catch(_) {}
            
            // Local click handler suppressed; delegated handler manages actions
                    reverigToolButton.addEventListener('click', function(e) {
                        e.preventDefault();
                        backendLog('reverig-tool button clicked (delegated handler will process)');
                    });
            
            // Before inserting, ask backend if reverig-tool already exists for this appid
            try {
                const match = window.location.href.match(/https:\/\/store\.steampowered\.com\/app\/(\d+)/) || window.location.href.match(/https:\/\/steamcommunity\.com\/app\/(\d+)/);
                const appid = match ? parseInt(match[1], 10) : NaN;
                if (!isNaN(appid) && typeof Millennium !== 'undefined' && typeof Millennium.callServerMethod === 'function') {
                    // prevent multiple concurrent checks
                    if (window.__reverigToolPresenceCheckInFlight && window.__reverigToolPresenceCheckAppId === appid) {
                        return;
                    }
                    window.__reverigToolPresenceCheckInFlight = true;
                    window.__reverigToolPresenceCheckAppId = appid;
                    Millennium.callServerMethod('reverig-tool', 'HasReverigToolForApp', { appid, contentScriptQuery: '' }).then(function(res){
                        try {
                            const payload = typeof res === 'string' ? JSON.parse(res) : res;
                            if (payload && payload.success && payload.exists === true) {
                                // Insert button in remove-mode
                                const restartExisting = steamdbContainer.querySelector('.reverig-tool-restart-button');
                                const btn = reverigToolButton.cloneNode(true);
                                btn.setAttribute('data-reverig-tool-mode', 'remove');
                                const s = btn.querySelector('span');
                                if (s) s.textContent = 'Remove via reverig-tool';
                                btn.title = 'Remove via reverig-tool';
                                btn.setAttribute('data-tooltip-text', 'Remove via reverig-tool');
                                if (!document.querySelector('.reverig-tool-button') && !window.__reverigToolButtonInserted) {
                                    if (restartExisting && restartExisting.after) {
                                        restartExisting.after(btn);
                                    } else if (referenceBtn && referenceBtn.after) {
                                        referenceBtn.after(btn);
                                    } else {
                                        steamdbContainer.appendChild(btn);
                                    }
                                    window.__reverigToolButtonInserted = true;
                                    backendLog('reverig-tool remove button inserted');
                                }
                                window.__reverigToolPresenceCheckInFlight = false;
                                return;
                            }
                            // Re-check in case another caller inserted during async
                            if (!document.querySelector('.reverig-tool-button') && !window.__reverigToolButtonInserted) {
                                const restartExisting = steamdbContainer.querySelector('.reverig-tool-restart-button');
                                if (restartExisting && restartExisting.after) {
                                        restartExisting.after(reverigToolButton);
                                } else if (referenceBtn && referenceBtn.after) {
                                    referenceBtn.after(reverigToolButton);
                                } else {
                                        steamdbContainer.appendChild(reverigToolButton);
                                }
                                window.__reverigToolButtonInserted = true;
                                backendLog('reverig-tool button inserted');
                            }
                            window.__reverigToolPresenceCheckInFlight = false;
                        } catch(_) {
                            if (!document.querySelector('.reverig-tool-button') && !window.__reverigToolButtonInserted) {
                                steamdbContainer.appendChild(reverigToolButton);
                                window.__reverigToolButtonInserted = true;
                                backendLog('reverig-tool button inserted');
                            }
                            window.__reverigToolPresenceCheckInFlight = false;
                        }
                    });
                } else {
                    if (!document.querySelector('.reverig-tool-button') && !window.__reverigToolButtonInserted) {
                        const restartExisting = steamdbContainer.querySelector('.reverig-tool-restart-button');
                        if (restartExisting && restartExisting.after) {
                            restartExisting.after(reverigToolButton);
                        } else if (referenceBtn && referenceBtn.after) {
                            referenceBtn.after(reverigToolButton);
                        } else {
                            steamdbContainer.appendChild(reverigToolButton);
                        }
                        window.__reverigToolButtonInserted = true;
                        backendLog('reverig-tool button inserted');
                        addDLCButton();
                    }
                }
            } catch(_) {
                if (!document.querySelector('.reverig-tool-button') && !window.__reverigToolButtonInserted) {
                    const restartExisting = steamdbContainer.querySelector('.reverig-tool-restart-button');
                    if (restartExisting && restartExisting.after) {
                        restartExisting.after(reverigToolButton);
                    } else if (referenceBtn && referenceBtn.after) {
                        referenceBtn.after(reverigToolButton);
                    } else {
                        steamdbContainer.appendChild(reverigToolButton);
                    }
                        window.__reverigToolButtonInserted = true;
                    backendLog('reverig-tool button inserted');
                    addDLCButton();
                }
            }
        } else {
            if (!logState.missingOnce) { backendLog('reverig-tool: steamdbContainer not found on this page'); logState.missingOnce = true; }
        }
    }

    
    // Try to add the button immediately if DOM is ready
    function onFrontendReady() {
        addReverigToolButton();
    }
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', onFrontendReady);
    } else {
        onFrontendReady();
    }
    
    // Delegate click handling in case the DOM is re-rendered and listeners are lost
    document.addEventListener('click', function(evt) {
        const anchor = evt.target && (evt.target.closest ? evt.target.closest('.reverig-tool-button') : null);
        if (anchor) {
            evt.preventDefault();
            backendLog('reverig-tool delegated click');
            // Defer popup until action actually starts (after auth)
            try {
                const match = window.location.href.match(/https:\/\/store\.steampowered\.com\/app\/(\d+)/) || window.location.href.match(/https:\/\/steamcommunity\.com\/app\/(\d+)/);
                const appid = match ? parseInt(match[1], 10) : NaN;
                if (!isNaN(appid) && typeof Millennium !== 'undefined' && typeof Millennium.callServerMethod === 'function') {
                    if (runState.inProgress && runState.appid === appid) {
                        backendLog('reverig-tool: operation already in progress for this appid');
                        return;
                    }
                    const mode = anchor.getAttribute('data-reverig-tool-mode') || 'add';
                    if (mode === 'remove') {
                        runState.inProgress = true; runState.appid = appid;
                        Millennium.callServerMethod('reverig-tool', 'RemoveReverigToolForApp', { appid, contentScriptQuery: '' }).then(function(res){
                            try{
                                const payload = typeof res === 'string' ? JSON.parse(res) : res;
                                if (payload && payload.success) {
                                    anchor.setAttribute('data-reverig-tool-mode', 'add');
                                    const s = anchor.querySelector('span');
                                    if (s) s.textContent = 'Add via reverig-tool';
                                    anchor.title = 'Add via reverig-tool';
                                    anchor.setAttribute('data-tooltip-text', 'Add via reverig-tool');
                                }
                            }catch(_){ }
                            runState.inProgress = false; runState.appid = null;
                            const overlay = document.querySelector('.reverig-tool-overlay'); if (overlay) overlay.remove();
                        });
                    } else {
                        runState.inProgress = true; runState.appid = appid;
                        if (!document.querySelector('.reverig-tool-overlay')) { showTestPopup(); }
                        Millennium.callServerMethod('reverig-tool', 'StartAddViaReverigTool', { appid, contentScriptQuery: '' });
                        startPolling(appid);
                    }
                }
            } catch(_) {}
        }
    }, true);

    // Poll backend for progress and update progress bar and text
    function startPolling(appid){
        const overlay = document.querySelector('.reverig-tool-overlay');
        if (!overlay) return;
        const percent = overlay.querySelector('.reverig-tool-percent');
        const bar = overlay.querySelector('.reverig-tool-progress-bar');
        const title = overlay.querySelector('.reverig-tool-title');
        const status = overlay.querySelector('.reverig-tool-status');
        const wrap = overlay.querySelector('.reverig-tool-progress-wrap');
        let done = false;
        const timer = setInterval(() => {
            if (done) { clearInterval(timer); return; }
            if (!overlay || !overlay.isConnected) { clearInterval(timer); return; }
            try {
                Millennium.callServerMethod('reverig-tool', 'GetAddViaReverigToolStatus', { appid, contentScriptQuery: '' }).then(function(res){
                    try {
                        const payload = typeof res === 'string' ? JSON.parse(res) : res;
                        const st = payload && payload.state ? payload.state : {};
                        if (st.currentApi && title) title.textContent = 'reverig-tool · ' + st.currentApi;
                        if (status) {
                            if (st.status === 'checking') status.textContent = 'Checking availability…';
                            if (st.status === 'downloading') status.textContent = 'Downloading…';
                            if (st.status === 'processing') status.textContent = 'Processing package…';
                            if (st.status === 'installing') status.textContent = 'Installing…';
                            if (st.status === 'done') status.textContent = 'Finishing…';
                            if (st.status === 'failed') status.textContent = 'Failed';
                        }
                        if (st.status === 'downloading'){
                            // reveal progress UI on first download tick
                            if (wrap && wrap.style.display === 'none') wrap.style.display = 'block';
                            if (percent && percent.style.display === 'none') percent.style.display = 'block';
                            const total = st.totalBytes || 0; const read = st.bytesRead || 0;
                            let pct = total > 0 ? Math.floor((read/total)*100) : (read ? 1 : 0);
                            if (pct > 100) pct = 100; if (pct < 0) pct = 0;
                            if (bar) bar.style.width = pct + '%';
                            if (percent) percent.textContent = pct + '%';
                        }
                        if (st.status === 'done'){
                            // keep popup open, show success in-place
                            if (bar) bar.style.width = '100%';
                            if (percent) percent.textContent = '100%';
                            if (status) status.textContent = 'Game Added!';
                            const btn = overlay.querySelector('.btnv6_blue_hoverfade.btn_medium');
                            if (btn) btn.innerHTML = '<span>Done</span>';
                            // hide progress visuals after a short beat
                            setTimeout(function(){ if (wrap) wrap.style.display = 'none'; if (percent) percent.style.display = 'none'; }, 300);
                            done = true; clearInterval(timer);
                            runState.inProgress = false; runState.appid = null;
                            // toggle button to Remove via reverig-tool
                            const btnEl = document.querySelector('.reverig-tool-button');
                            if (btnEl) {
                                btnEl.setAttribute('data-reverig-tool-mode', 'remove');
                                const s = btnEl.querySelector('span');
                                if (s) s.textContent = 'Remove via reverig-tool';
                                btnEl.title = 'Remove via reverig-tool';
                                btnEl.setAttribute('data-tooltip-text', 'Remove via reverig-tool');
                            }
                            // Auto-add DLCs after game is added
                            try {
                                Millennium.callServerMethod('reverig-tool', 'AddDLCs', { appid, contentScriptQuery: '' }).then(function(res) {
                                    try {
                                        const payload = typeof res === 'string' ? JSON.parse(res) : res;
                                        if (payload && payload.success && payload.message) {
                                            backendLog('Auto-added DLCs: ' + payload.message);
                                        }
                                    } catch(_) {}
                                });
                            } catch(_) {}
                        }
                        if (st.status === 'failed'){
                            // show error in the same popup
                            if (status) status.textContent = 'Failed: request game in discord';
                            const btn = overlay.querySelector('.btnv6_blue_hoverfade.btn_medium');
                            if (btn) btn.innerHTML = '<span>Close</span>';
                            if (wrap) wrap.style.display = 'none'; if (percent) percent.style.display = 'none';
                            done = true; clearInterval(timer);
                            runState.inProgress = false; runState.appid = null;
                        }
                    } catch(_){ }
                });
            } catch(_){ clearInterval(timer); }
        }, 300);
    }
    

    // Also try after a delay to catch dynamically loaded content
    setTimeout(addReverigToolButton, 1000);
    setTimeout(addReverigToolButton, 3000);
    
    // Use MutationObserver to catch dynamically added content
    if (typeof MutationObserver !== 'undefined') {
        const observer = new MutationObserver(function(mutations) {
            mutations.forEach(function(mutation) {
                if (mutation.type === 'childList' && mutation.addedNodes.length > 0) {
                    addReverigToolButton();
                }
            });
        });
        
        observer.observe(document.body, {
            childList: true,
            subtree: true
        });
    }
})();


