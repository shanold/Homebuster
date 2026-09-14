from pathlib import Path
import re, subprocess, tempfile

ROOT = Path(__file__).resolve().parents[1]
template = (ROOT / 'movie_catalogue/templates/shelf_detail.html').read_text()
match = re.search(r'<script>\s*(\(\(\) => \{.*?\}\)\(\);)\s*</script>', template, re.S)
assert match, 'shelf script not found'
script = match.group(1)

harness = r'''
class ClassList { constructor(){ this.s = new Set(); } toggle(n,on){ if(on) this.s.add(n); else this.s.delete(n); } }
class El {
  constructor(id=''){ this.id=id; this.hidden=false; this.value='28'; this.textContent=''; this.dataset={}; this.classList=new ClassList(); this.style={setProperty(){}}; this.handlers={}; this.href=''; this.src=''; this.alt=''; }
  addEventListener(name, fn){ this.handlers[name]=fn; }
  querySelector(sel){ if(sel === '.shelf-row') return shelfRow; if(sel === '.case-preview-close') return closeButton; return null; }
  setAttribute(){}
  removeAttribute(){}
  showModal(){}
  close(){}
}
const listView = new El('shelf-list-view');
const shelfView = new El('shelf-visual-view'); shelfView.hidden = true;
const shelfRow = new El('shelf-row');
const density = new El('shelf-density');
const densityValue = new El('shelf-density-value');
const modal = new El('shelf-case-modal');
const closeButton = new El('close');
const modalPoster = new El('case-preview-poster');
const modalPlaceholder = new El('case-preview-placeholder');
const modalFormat = new El('case-preview-format');
const modalTitle = new El('case-preview-title');
const modalMeta = new El('case-preview-meta');
const modalDetails = new El('case-preview-details');
const listButton = new El(); listButton.dataset.shelfView='list';
const shelfButton = new El(); shelfButton.dataset.shelfView='shelf';
const ids = {
  'shelf-list-view': listView, 'shelf-visual-view': shelfView, 'shelf-density': density,
  'shelf-density-value': densityValue, 'shelf-case-modal': modal, 'case-preview-poster': modalPoster,
  'case-preview-placeholder': modalPlaceholder, 'case-preview-format': modalFormat,
  'case-preview-title': modalTitle, 'case-preview-meta': modalMeta, 'case-preview-details': modalDetails
};
global.document = {
  getElementById(id){ return ids[id]; },
  querySelectorAll(sel){ if(sel === '[data-shelf-view]') return [listButton,shelfButton]; return []; },
  body: { classList: new ClassList() }
};
global.window = { innerWidth: 1200, addEventListener(){}};
Object.defineProperty(global.window, 'localStorage', { get(){ throw new Error('storage blocked'); } });
'''

def run(candidate: str):
    js = harness + '\n' + candidate + r'''
if (!shelfButton.handlers.click) throw new Error('Shelf button handler was not registered');
shelfButton.handlers.click();
if (!listView.hidden) throw new Error('List view stayed visible');
if (shelfView.hidden) throw new Error('Shelf view stayed hidden');
console.log('runtime shelf toggle survived blocked storage');
'''
    with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False) as f:
        f.write(js); path=f.name
    return subprocess.run(['node', path], text=True, capture_output=True)

# Current implementation works even when localStorage throws.
current = run(script)
assert current.returncode == 0, current.stderr

# Regression proof: replacing the safe read with the old direct access must fail before handlers register.
old = script.replace('storageGet(STORAGE_DENSITY)', 'localStorage.getItem(STORAGE_DENSITY)').replace('storageGet(STORAGE_VIEW)', 'localStorage.getItem(STORAGE_VIEW)')
old_result = run(old)
assert old_result.returncode != 0, 'old direct-localStorage behavior unexpectedly survived'

print('v0.3.33 shelf runtime storage checks passed')
