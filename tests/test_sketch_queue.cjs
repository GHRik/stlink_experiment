const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm');

class Element {
  constructor(tag){this.tag=tag;this.children=[];this.dataset={};this.handlers={};}
  append(...items){this.children.push(...items);}
  replaceChildren(...items){this.children=items;}
  setAttribute(){}
  addEventListener(name,handler){this.handlers[name]=handler;}
  click(){if(!this.disabled)this.handlers.click?.();}
  querySelector(){return {textContent:'Device Under Test'};}
  showModal(){this.open=true;}
}

test('Each DUT has an independent frontend queue with multi-file selection, reorder, remove and clear',()=>{
  const cards=[new Element('section'),new Element('section'),new Element('section')];
  const runQueue=new Element('button'),body=new Element('body');
  const context=vm.createContext({window:{addEventListener(){}},document:{body,querySelector:()=>runQueue,querySelectorAll:()=>cards,createElement:tag=>new Element(tag)}});
  vm.runInContext('let isRunning=false;',context);
  vm.runInContext('let previewClicks=0; function startSketchQueuePreview(){previewClicks++;}',context);
  vm.runInContext(fs.readFileSync('automation/frontend/sketch-queue.js','utf8'),context);
  const panel=cards[0].children[0];
  const list=panel.children.find(child=>child.className==='sketch-queue-list');
  const picker=panel.children.find(child=>child.tag==='input');
  const names=()=>list.children.map(row=>row.children[1].textContent);
  assert.equal(picker.multiple,true);
  picker.files=['empty.ino','wifi_off.ino','deep_sleep.ino','notes.txt'].map(name=>({name}));
  picker.handlers.change();
  assert.deepEqual(names(),['empty.ino','wifi_off.ino','deep_sleep.ino']);
  assert.equal(list.children[0].children[2].disabled,true);
  assert.equal(list.children[2].children[3].disabled,true);
  list.children[1].children[2].click();
  assert.deepEqual(names(),['wifi_off.ino','empty.ino','deep_sleep.ino']);
  list.children[0].children[4].click();
  assert.deepEqual(names(),['empty.ino','deep_sleep.ino']);
  assert.equal(cards[1].children[0].children.find(child=>child.className==='sketch-queue-list').children.length,0);
  cards[2].hidden=true;
  runQueue.click();
  assert.equal(vm.runInContext('previewClicks',context),1);
  vm.runInContext('isRunning=true;',context);
  list.children[0].children[4].click();
  assert.deepEqual(names(),['empty.ino','deep_sleep.ino']);
  vm.runInContext('isRunning=false;',context);
  const clear=panel.children.find(child=>child.className==='sketch-queue-actions').children[1];
  clear.click();assert.equal(list.children.length,0);assert.equal(clear.disabled,true);
});
