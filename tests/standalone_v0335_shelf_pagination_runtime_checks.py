from pathlib import Path
import re, subprocess, tempfile

ROOT = Path(__file__).resolve().parents[1]
template = (ROOT / 'movie_catalogue/templates/shelf_detail.html').read_text()
match = re.search(r'<script>\s*(\(\(\) => \{.*?\}\)\(\);)\s*</script>', template, re.S)
assert match, 'shelf script not found'
script = match.group(1)

harness = r'''
class ClassList { constructor(){ this.s = new Set(); } toggle(n,on){ if(on) this.s.add(n); else this.s.delete(n); } }
class Style { constructor(){ this.props={}; } setProperty(k,v){ this.props[k]=v; } }
class El {
  constructor(id=''){ this.id=id; this.hidden=false; this.disabled=false; this.value='10'; this.textContent=''; this.dataset={}; this.classList=new ClassList(); this.style=new Style(); this.handlers={}; this.href=''; this.src=''; this.alt=''; }
  addEventListener(name, fn){ this.handlers[name]=fn; }
  querySelector(sel){ if(sel === '.shelf-row') return shelfRow; if(sel === '.case-preview-close') return closeButton; return null; }
  setAttribute(){}
  removeAttribute(){}
  showModal(){}
  close(){}
}
const listItems = Array.from({length:120},(_,i)=>new El('l'+i));
const shelfItems = Array.from({length:120},(_,i)=>new El('s'+i));
const listView = new El('shelf-list-view');
const shelfView = new El('shelf-visual-view'); shelfView.hidden=true;
const shelfRow = new El('shelf-row');
const density = new El('shelf-density'); density.value='10';
const densityValue = new El('shelf-density-value');
const listPager = new El('shelf-list-pagination');
const shelfPager = new El('shelf-visual-pagination'); shelfPager.hidden=true;
const listPageLabel = new El('shelf-list-page-label');
const shelfPageLabel = new El('shelf-visual-page-label');
const listPrev = new El(); const listNext = new El(); const shelfPrev = new El(); const shelfNext = new El();
const modal = new El('shelf-case-modal'); const closeButton = new El('close');
const modalPoster = new El(); const modalPlaceholder = new El(); const modalFormat = new El(); const modalTitle = new El(); const modalMeta = new El(); const modalDetails = new El();
const listButton = new El(); listButton.dataset.shelfView='list';
const shelfButton = new El(); shelfButton.dataset.shelfView='shelf';
const ids = {
 'shelf-list-view':listView,'shelf-visual-view':shelfView,'shelf-density':density,'shelf-density-value':densityValue,
 'shelf-list-pagination':listPager,'shelf-visual-pagination':shelfPager,'shelf-list-page-label':listPageLabel,'shelf-visual-page-label':shelfPageLabel,
 'shelf-case-modal':modal,'case-preview-poster':modalPoster,'case-preview-placeholder':modalPlaceholder,'case-preview-format':modalFormat,
 'case-preview-title':modalTitle,'case-preview-meta':modalMeta,'case-preview-details':modalDetails
};
const actionMap = {'[data-page-action="list-prev"]':listPrev,'[data-page-action="list-next"]':listNext,'[data-page-action="shelf-prev"]':shelfPrev,'[data-page-action="shelf-next"]':shelfNext};
global.document = {
 getElementById(id){ return ids[id] || null; },
 querySelector(sel){ return actionMap[sel] || null; },
 querySelectorAll(sel){
   if(sel === '[data-shelf-view]') return [listButton,shelfButton];
   if(sel === '#shelf-list-view .shelf-list-card') return listItems;
   if(sel === '#shelf-visual-view .shelf-case') return shelfItems;
   return [];
 },
 body:{classList:new ClassList()}
};
global.window = {innerWidth:1200,addEventListener(){},localStorage:{getItem(){return null;},setItem(){}}};
'''
checks = r'''
const visible = arr => arr.filter(x => !x.hidden).length;
if (visible(listItems) !== 50) throw new Error('list page did not cap at 50: '+visible(listItems));
if (visible(shelfItems) !== 40) throw new Error('10-per-row shelf page should show 40: '+visible(shelfItems));
if (listPageLabel.textContent !== 'Page 1 of 3') throw new Error('bad list page label '+listPageLabel.textContent);
if (shelfPageLabel.textContent !== 'Page 1 of 3') throw new Error('bad shelf page label '+shelfPageLabel.textContent);
shelfNext.handlers.click();
if (!shelfItems[0].hidden || shelfItems[40].hidden) throw new Error('shelf next page did not advance');
density.value='20'; density.handlers.input();
if (visible(shelfItems) !== 80) throw new Error('20-per-row shelf page should show 80: '+visible(shelfItems));
if (shelfPageLabel.textContent !== 'Page 1 of 2') throw new Error('density did not reset/repage: '+shelfPageLabel.textContent);
console.log('v0.3.35 shelf pagination runtime checks passed');
'''
with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False) as f:
    f.write(harness + '\n' + script + '\n' + checks)
    path=f.name
result=subprocess.run(['node',path],text=True,capture_output=True)
assert result.returncode==0, result.stderr
print(result.stdout.strip())
