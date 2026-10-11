import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {spawnSync} from 'node:child_process';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const config=JSON.parse(fs.readFileSync(path.join(root,'experiments/native-i18n/config.json')));
const installs=path.join(os.homedir(),'.local/share/mise/installs/python');
const candidates=[process.env.NATIVE_I18N_PYTHON,'python3',...(fs.existsSync(installs)?fs.readdirSync(installs).sort().reverse().map(v=>path.join(installs,v,'bin/python3')):[])].filter(Boolean);
const python=candidates.find(p=>spawnSync(p,['-c','import bs4'],{stdio:'ignore',timeout:5000}).status===0);
if(!python)throw Error('Python with Beautiful Soup is required. Set NATIVE_I18N_PYTHON to an existing interpreter with bs4 installed.');
const mode=process.argv[2]||'build';
if(!['build','serve'].includes(mode))throw Error('Usage: node scripts/native-i18n.mjs [build|serve]');
const run=args=>{const r=spawnSync(python,args,{cwd:root,stdio:'inherit'});if(r.status!==0)process.exit(r.status||1);};
run(['scripts/native-i18n.py','--catalog-dir','experiments/native-i18n','--output','.review/native-i18n/site','--origin',config.origin]);
if(mode==='serve'){
 const assets=path.resolve(root,config.asset_root);
 if(!fs.existsSync(path.join(assets,'index.html')))throw Error('Original site assets missing: '+assets);
 run(['scripts/preview-native-i18n.py','--overlay','.review/native-i18n/site','--original',assets,'--port',String(config.port)]);
}
