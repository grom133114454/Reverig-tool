import Millennium
import PluginUtils  # type: ignore

logger = PluginUtils.Logger()

import json
import os
import shutil

import requests
import httpx
import threading
import time
import re
import sys
import zipfile
import subprocess
if sys.platform.startswith('win'):
    try:
        import winreg  # type: ignore
    except Exception:
        winreg = None  # type: ignore


WEBKIT_DIR_NAME = "reverig-tool"
WEB_UI_JS_FILE = "reverig-tool.js"
CSS_ID = None
JS_ID = None
DEFAULT_HEADERS = {
    'Accept': 'application/json',
    'X-Requested-With': 'SteamDB',
    'User-Agent': 'https://github.com/BossSloth/Steam-SteamDB-extension',
    'Origin': 'https://github.com/BossSloth/Steam-SteamDB-extension',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'cross-site',
}
API_URL = 'https://extension.steamdb.info/api'
HTTP_CLIENT = None
DOWNLOAD_STATE = {}
DOWNLOAD_LOCK = threading.Lock()
STEAM_INSTALL_PATH = None

class Logger:
    @staticmethod
    def warn(message: str) -> None:
        logger.warn(message)

    @staticmethod
    def error(message: str) -> None:
        logger.error(message)

def GetPluginDir():
    return os.path.abspath(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', '..'))

def Request(url: str, params: dict) -> str:
    response = None
    try:
        response = requests.get(url, params=params, headers=DEFAULT_HEADERS)
        response.raise_for_status()
        return response.text
    except Exception as error:
        return json.dumps({
            'success': False,
            'error': str(error) + ' ' + (response.text if response else 'No response')
        })

def GetApp(appid: int, contentScriptQuery: str) -> str:
    logger.log(f"Getting app info for {appid}")

    return Request(
        f'{API_URL}/ExtensionApp/',
        {'appid': int(appid)}
    )

def GetAppPrice(appid: int, currency: str, contentScriptQuery: str) -> str:
    logger.log(f"Getting app price for {appid} in {currency}")

    return Request(
        f'{API_URL}/ExtensionAppPrice/',
        {'appid': int(appid), 'currency': currency}
    )

def GetAchievementsGroups(appid: int, contentScriptQuery: str) -> str:
    logger.log(f"Getting app achievements groups for {appid}")

    return Request(
        f'{API_URL}/ExtensionGetAchievements/',
        {'appid': int(appid)}
    )

def comment_setManifestid_in_lua_files():
    """Comment out setManifestid lines in Lua files in Steam/config/stplug-in directory"""
    try:
        # Get Steam config path
        steam_path = Millennium.steam_path() if hasattr(Millennium, 'steam_path') else None
        if not steam_path:
            logger.warn('reverig-tool: Could not determine Steam path for Lua file processing')
            return
        
        stplug_in_dir = os.path.join(steam_path, 'config', 'stplug-in')
        
        if not os.path.exists(stplug_in_dir):
            logger.log(f'reverig-tool: stplug-in directory not found: {stplug_in_dir}')
            return
        
        # Process all .lua files
        lua_files_processed = 0
        lines_commented = 0
        
        for filename in os.listdir(stplug_in_dir):
            if filename.endswith('.lua'):
                filepath = os.path.join(stplug_in_dir, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    original_content = content
                    
                    # Comment out lines containing setManifestid
                    lines = content.split('\n')
                    modified_lines = []
                    for line in lines:
                        if 'setManifestid' in line and not line.lstrip().startswith('--'):
                            # Add -- comment at the beginning of the line (after whitespace)
                            indent = len(line) - len(line.lstrip())
                            modified_lines.append(line[:indent] + '--' + line[indent:])
                            lines_commented += 1
                        else:
                            modified_lines.append(line)
                    
                    modified_content = '\n'.join(modified_lines)
                    
                    # Only write if content changed
                    if modified_content != original_content:
                        with open(filepath, 'w', encoding='utf-8') as f:
                            f.write(modified_content)
                        lua_files_processed += 1
                        logger.log(f'reverig-tool: Processed {filename} ({lines_commented} setManifestid lines commented)')
                
                except Exception as e:
                    logger.error(f'reverig-tool: Error processing {filename}: {e}')
        
        if lua_files_processed > 0:
            logger.log(f'reverig-tool: Commented out setManifestid in {lines_commented} lines across {lua_files_processed} Lua files')
        else:
            logger.log('reverig-tool: No setManifestid lines found to comment in Lua files')
    
    except Exception as e:
        logger.error(f'reverig-tool: Error in comment_setManifestid_in_lua_files: {e}')

class Plugin:
    def init_http_client(self):
        global HTTP_CLIENT
        if HTTP_CLIENT is None:
            try:
                logger.log('InitApis: Initializing shared HTTPX client...')
                HTTP_CLIENT = httpx.Client(timeout=10)
                logger.log('InitApis: HTTPX client initialized')
            except Exception as e:
                logger.error(f'InitApis: Failed to initialize HTTPX client: {e}')

    def close_http_client(self):
        global HTTP_CLIENT
        if HTTP_CLIENT is not None:
            try:
                HTTP_CLIENT.close()
            except Exception:
                pass
            HTTP_CLIENT = None
            logger.log('InitApis: HTTPX client closed')

    def _get_backend_path(self, filename: str) -> str:
        return os.path.join(GetPluginDir(), 'backend', filename)

    def _read_text(self, path: str) -> str:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception:
            return ''

    def _write_text(self, path: str, text: str) -> None:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(text)


    def copy_webkit_files(self):
        webkitJsFilePath = os.path.join(GetPluginDir(), "public", WEB_UI_JS_FILE)
        steamUIPath = os.path.join(Millennium.steam_path(), "steamui", WEBKIT_DIR_NAME)
        
        # Create reverig-tool directory if it doesn't exist
        os.makedirs(steamUIPath, exist_ok=True)
        
        # Copy JavaScript file
        jsDestPath = os.path.join(steamUIPath, WEB_UI_JS_FILE)
        logger.log(f"Copying reverig-tool web UI from {webkitJsFilePath} to {jsDestPath}")
        try:
            shutil.copy(webkitJsFilePath, jsDestPath)
        except Exception as e:
            logger.error(f"Failed to copy reverig-tool web UI, {e}")

    def inject_webkit_files(self):
        # Inject JavaScript
        jsPath = os.path.join(WEBKIT_DIR_NAME, WEB_UI_JS_FILE)
        JS_ID = Millennium.add_browser_js(jsPath)
        logger.log(f"reverig-tool injected web UI: {jsPath}")

    def _front_end_loaded(self):
        self.copy_webkit_files()

    def _load(self):
        logger.log(f"bootstrapping reverig-tool plugin, millennium {Millennium.version()}")
        # Detect Steam install path via registry (fallback to Millennium.steam_path())
        try:
            detect_steam_install_path()
        except Exception as e:
            logger.warn(f'reverig-tool: steam path detection failed: {e}')
        self.init_http_client()
        self.copy_webkit_files()
        self.inject_webkit_files()
        
        # Comment out setManifestid in Lua files
        comment_setManifestid_in_lua_files()


        Millennium.ready()  # this is required to tell Millennium that the backend is ready.

    def _unload(self):
        logger.log("unloading")
        self.close_http_client()

# ---------------- Module-level wrappers for frontend callable routes ----------------

def _backend_path(filename: str) -> str:
    return os.path.join(GetPluginDir(), 'backend', filename)

def _read_text(path: str) -> str:
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception:
        return ''

def _write_text(path: str, text: str) -> None:
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)


def _ensure_http_client() -> None:
    global HTTP_CLIENT
    if HTTP_CLIENT is None:
        try:
            logger.log('InitApis: Initializing shared HTTPX client (module)...')
            HTTP_CLIENT = httpx.Client(timeout=10)
            logger.log('InitApis: HTTPX client initialized (module)')
        except Exception as e:
            logger.error(f'InitApis: Failed to initialize HTTPX client (module): {e}')


# --------------- Steam Install Path Detection and reverig-tool presence -----------

def detect_steam_install_path() -> str:
    global STEAM_INSTALL_PATH
    if STEAM_INSTALL_PATH:
        return STEAM_INSTALL_PATH
    
    # Try multiple detection methods in order
    path = None
    
    # 1. Try Windows registry first (most reliable on Windows)
    if sys.platform.startswith('win'):
        try:
            if winreg is not None:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
                    path, _ = winreg.QueryValueEx(key, 'SteamPath')
                    if path and os.path.exists(path):
                        logger.log(f'reverig-tool: Steam path found in registry: {path}')
        except Exception as e:
            logger.warn(f'reverig-tool: Registry detection failed: {e}')
    
    # 2. Try Millennium's built-in detection
    if not path or not os.path.exists(path):
        try:
            path = Millennium.steam_path()
            if path and os.path.exists(path):
                logger.log(f'reverig-tool: Steam path found via Millennium: {path}')
        except Exception as e:
            logger.warn(f'reverig-tool: Millennium detection failed: {e}')
    
    # 3. Try common install locations as last resort
    if not path or not os.path.exists(path):
        common_paths = []
        if sys.platform.startswith('win'):
            common_paths = [
                r"C:\Program Files (x86)\Steam",
                r"C:\Program Files\Steam",
                r"D:\Steam",
                os.path.expandvars(r"%ProgramFiles(x86)%\Steam"),
                os.path.expandvars(r"%ProgramFiles%\Steam"),
            ]
        elif sys.platform.startswith('darwin'):
            common_paths = [
                os.path.expanduser("~/Library/Application Support/Steam")
            ]
        else:  # Linux and others
            common_paths = [
                os.path.expanduser("~/.local/share/Steam"),
                os.path.expanduser("~/.steam/steam"),
                "/usr/share/steam"
            ]
        
        for p in common_paths:
            if os.path.exists(p):
                path = p
                logger.log(f'reverig-tool: Steam path found in common location: {path}')
                break
    
    if path and os.path.exists(path):
        STEAM_INSTALL_PATH = path
        logger.log(f'reverig-tool: Steam install path set to {STEAM_INSTALL_PATH}')
        return STEAM_INSTALL_PATH
    
    logger.warn('reverig-tool: Failed to detect Steam install path')
    return ''

def HasReverigToolForApp(appid: int, contentScriptQuery: str = '') -> str:
    try:
        appid = int(appid)
    except Exception:
        return json.dumps({ 'success': False, 'error': 'Invalid appid' })
    base = detect_steam_install_path() or Millennium.steam_path()
    candidate1 = os.path.join(base, 'config', 'stplug-in', f'{appid}.lua')
    candidate2 = os.path.join(base, 'config', 'stplug-in', f'{appid}.lua.disabled')
    exists = os.path.exists(candidate1) or os.path.exists(candidate2)
    logger.log(f'reverig-tool: HasReverigToolForApp appid={appid} -> {exists}')
    return json.dumps({ 'success': True, 'exists': exists })

def RestartSteam(contentScriptQuery: str = '') -> str:
    backend_dir = os.path.join(GetPluginDir(), 'backend')
    script_path = os.path.join(backend_dir, 'restart_steam.cmd')
    if not os.path.exists(script_path):
        logger.error(f'reverig-tool: restart script not found: {script_path}')
        return json.dumps({ 'success': False, 'error': 'restart_steam.cmd not found' })
    try:
        DETACHED_PROCESS = 0x00000008
        subprocess.Popen(['cmd', '/C', 'start', '', script_path], creationflags=DETACHED_PROCESS)
        logger.log('reverig-tool: Restart script launched')
        return json.dumps({ 'success': True })
    except Exception as e:
        logger.error(f'reverig-tool: Failed to launch restart script: {e}')
        return json.dumps({ 'success': False, 'error': str(e) })

def RemoveReverigToolForApp(appid: int, contentScriptQuery: str = '') -> str:
    try:
        appid = int(appid)
    except Exception:
        return json.dumps({ 'success': False, 'error': 'Invalid appid' })
    base = detect_steam_install_path() or Millennium.steam_path()
    target_dir = os.path.join(base or '', 'config', 'stplug-in')
    paths = [
        os.path.join(target_dir, f"{appid}.lua"),
        os.path.join(target_dir, f"{appid}.lua.disabled"),
    ]
    removed_any = False
    try:
        for p in paths:
            if os.path.exists(p):
                os.remove(p)
                removed_any = True
        return json.dumps({ 'success': True, 'removed': removed_any })
    except Exception as e:
        logger.error(f'reverig-tool: Remove failed for {appid}: {e}')
        return json.dumps({ 'success': False, 'error': str(e) })

def _set_download_state(appid: int, update: dict) -> None:
    with DOWNLOAD_LOCK:
        state = DOWNLOAD_STATE.get(appid) or {}
        state.update(update)
        DOWNLOAD_STATE[appid] = state
        # Log state changes for better debugging
        try:
            if 'status' in update:
                logger.log(f"reverig-tool: Download state for {appid} changed to {update['status']}")
        except Exception:
            pass

def _get_download_state(appid: int) -> dict:
    with DOWNLOAD_LOCK:
        state = DOWNLOAD_STATE.get(appid, {}).copy()
        # Add helpful default values if missing
        if 'status' not in state:
            state['status'] = 'unknown'
        if 'bytesRead' not in state:
            state['bytesRead'] = 0
        if 'totalBytes' not in state:
            state['totalBytes'] = 0
        return state

def _download_zip_for_app(appid: int):
    _ensure_http_client()

    # Updated list of API endpoints
    urls = [
        f"https://api.swa-recloud.fun/api/v3/file/{appid}.zip",
        f"https://raw.githubusercontent.com/sushi-dev55-alt/sushitools-games-repo-alt/refs/heads/main/{appid}.zip",
        f"http://masss.pythonanywhere.com/storage?auth=IEOIJE54esfsipoE56GE4&appid={appid}",
        f"http://167.235.229.108/m/{appid}",
        f"http://167.235.229.108/{appid}",
        f"https://pub-5b6d3b7c03fd4ac1afb5bd3017850e20.r2.dev/{appid}.zip",
        f"https://walftech.com/proxy.php?url=https%3A%2F%2Fsteamgames554.s3.us-east-1.amazonaws.com%2F{appid}.zip",
        f"https://github.com/SPIN0ZAi/SB_manifest_DB/archive/refs/heads/{appid}.zip",
        f"https://github.com/dvahana2424-web/sojogamesdatabase1/archive/refs/heads/{appid}.zip",
        f"https://github.com/LightnigFast/ProjectLightningManifests/archive/refs/heads/{appid}.zip",
        f"https://github.com/sojorepo/sojogames/archive/refs/heads/{appid}.zip",
        f"https://github.com/Fairyvmos/bruh-hub/archive/refs/heads/{appid}.zip",
        f"https://github.com/hansaes/ManifestAutoUpdate/archive/refs/heads/{appid}.zip",
        f"https://github.com/SteamAutoCracks/ManifestHub/archive/refs/heads/{appid}.zip",
    ]

    dest_path = _backend_path(f"{appid}.zip")
    _set_download_state(appid, { 'status': 'checking', 'currentApi': None, 'bytesRead': 0, 'totalBytes': 0, 'dest': dest_path })

    for (i, url) in enumerate(urls):
        _set_download_state(appid, { 'status': 'checking', 'currentApi': '', 'bytesRead': 0, 'totalBytes': 0 })
        try:
            with HTTP_CLIENT.stream('GET', url, follow_redirects=True) as resp:
                code = resp.status_code
                if code == 404:
                    continue
                if code != 200:
                    continue
                total = int(resp.headers.get('Content-Length', '0') or '0')
                _set_download_state(appid, { 'status': 'downloading', 'bytesRead': 0, 'totalBytes': total })
                with open(dest_path, 'wb') as f:
                    for chunk in resp.iter_bytes():
                        if not chunk:
                            continue
                        f.write(chunk)
                        st = _get_download_state(appid)
                        read = int(st.get('bytesRead', 0)) + len(chunk)
                        _set_download_state(appid, { 'bytesRead': read })
                logger.log(f"reverig-tool: Download complete -> {dest_path}")
                try:
                    _set_download_state(appid, { 'status': 'processing' })
                    _process_and_install_lua(appid, dest_path)
                    _set_download_state(appid, { 'status': 'done', 'success': True, 'api': '' })
                except Exception as e:
                    logger.warn(f"reverig-tool: Processing failed -> {e}")
                    _set_download_state(appid, { 'status': 'failed', 'error': f'Processing failed: {e}' })
                return
        except Exception as e:
            continue

    _set_download_state(appid, { 'status': 'failed', 'error': 'Not available on any source' })

def _process_and_install_lua(appid: int, zip_path: str) -> None:
    base_path = detect_steam_install_path() or Millennium.steam_path()
    target_dir = os.path.join(base_path or '', 'config', 'stplug-in')
    os.makedirs(target_dir, exist_ok=True)

    with zipfile.ZipFile(zip_path, 'r') as zf:
        names = zf.namelist()
        # Also extract any .manifest files into Steam's depotcache if present
        try:
            depotcache_dir = os.path.join(base_path or '', 'depotcache')
            os.makedirs(depotcache_dir, exist_ok=True)
            for name in names:
                try:
                    if name.lower().endswith('.manifest'):
                        pure = os.path.basename(name)
                        data = zf.read(name)
                        out_path = os.path.join(depotcache_dir, pure)
                        with open(out_path, 'wb') as mf:
                            mf.write(data)
                        logger.log(f"reverig-tool: Extracted manifest -> {out_path}")
                except Exception as me:
                    logger.warn(f"reverig-tool: Failed to extract manifest {name}: {me}")
        except Exception as e:
            logger.warn(f"reverig-tool: depotcache extraction failed: {e}")

        # Look for .lua files
        candidates = []
        for name in names:
            pure = os.path.basename(name)
            if re.fullmatch(r"\d+\.lua", pure):
                candidates.append(name)
        chosen = None
        preferred = f"{appid}.lua"
        for name in candidates:
            if os.path.basename(name) == preferred:
                chosen = name
                break
        if chosen is None and candidates:
            chosen = candidates[0]
        if not chosen:
            raise RuntimeError('No numeric .lua file found in zip')

        data = zf.read(chosen)
        try:
            text = data.decode('utf-8')
        except Exception:
            text = data.decode('utf-8', errors='replace')

        processed_lines = []
        for line in text.splitlines(True):
            if re.match(r"^\s*setManifestid\(", line) and not re.match(r"^\s*--", line):
                line = re.sub(r"^(\s*)", r"\1--", line)
            processed_lines.append(line)
        processed_text = ''.join(processed_lines)

        # Update state to installing and write to destination as <appid>.lua
        _set_download_state(appid, { 'status': 'installing' })
        dest_file = os.path.join(target_dir, f"{appid}.lua")
        with open(dest_file, 'w', encoding='utf-8') as out:
            out.write(processed_text)
        logger.log(f"reverig-tool: Installed lua -> {dest_file}")
        _set_download_state(appid, { 'installedPath': dest_file })

def StartAddViaReverigTool(appid: int, contentScriptQuery: str = '') -> str:
    try:
        appid = int(appid)
    except Exception:
        return json.dumps({ 'success': False, 'error': 'Invalid appid' })
    logger.log(f'reverig-tool: StartAddViaReverigTool appid={appid}')
    # Reset state
    _set_download_state(appid, { 'status': 'queued', 'bytesRead': 0, 'totalBytes': 0 })
    t = threading.Thread(target=_download_zip_for_app, args=(appid,), daemon=True)
    t.start()
    return json.dumps({ 'success': True })

def GetAddViaReverigToolStatus(appid: int, contentScriptQuery: str = '') -> str:
    try:
        appid = int(appid)
    except Exception:
        return json.dumps({ 'success': False, 'error': 'Invalid appid' })
    state = _get_download_state(appid)
    return json.dumps({ 'success': True, 'state': state })

def AddDLCs(appid: int, contentScriptQuery: str = '') -> str:
    try:
        appid = int(appid)
    except Exception:
        return json.dumps({ 'success': False, 'error': 'Invalid appid' })

    logger.log(f'reverig-tool: AddDLCs for appid={appid}')

    # Ensure HTTP client is initialized
    _ensure_http_client()

    # Fetch app details from Steam API
    url = f"https://store.steampowered.com/api/appdetails?appids={appid}"
    try:
        if HTTP_CLIENT is not None:
            resp = HTTP_CLIENT.get(url, headers=DEFAULT_HEADERS)
            resp.raise_for_status()
            data = resp.json()
        else:
            return json.dumps({ 'success': False, 'error': 'HTTP client not available' })
    except Exception as e:
        logger.error(f'reverig-tool: Failed to fetch app details: {e}')
        return json.dumps({ 'success': False, 'error': f'Failed to fetch app details: {e}' })

    if str(appid) not in data or not data[str(appid)].get('success', False):
        return json.dumps({ 'success': False, 'error': 'App not found or API error' })

    app_data = data[str(appid)]['data']
    dlc_array = app_data.get('dlc', [])
    if not dlc_array:
        return json.dumps({ 'success': True, 'message': 'No DLCs found for this app' })

    # Get Steam path
    steam_path = detect_steam_install_path() or Millennium.steam_path()
    if not steam_path:
        return json.dumps({ 'success': False, 'error': 'Steam path not found' })

    steamtools_path = os.path.join(steam_path, 'config', 'stplug-in', 'Steamtools.lua')

    # Read existing content
    try:
        with open(steamtools_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        content = ''
    except Exception as e:
        logger.error(f'reverig-tool: Failed to read Steamtools.lua: {e}')
        return json.dumps({ 'success': False, 'error': f'Failed to read Steamtools.lua: {e}' })

    added_count = 0
    for dlc_id in dlc_array:
        if isinstance(dlc_id, int):
            dlc_appid = str(dlc_id)
            line = f"addappid({dlc_appid}, 1)"
            if line not in content:
                content += f"{line}\n"
                added_count += 1
                logger.log(f'reverig-tool: Added DLC {dlc_appid}')

    # Write back if changes were made
    if added_count > 0:
        try:
            with open(steamtools_path, 'w', encoding='utf-8') as f:
                f.write(content)
            logger.log(f'Auto-added DLCs: Added {added_count} DLCs')
        except Exception as e:
            logger.error(f'reverig-tool: Failed to write Steamtools.lua: {e}')
            return json.dumps({ 'success': False, 'error': f'Failed to write Steamtools.lua: {e}' })

    return json.dumps({ 'success': True, 'message': f'Added {added_count} DLCs' })


