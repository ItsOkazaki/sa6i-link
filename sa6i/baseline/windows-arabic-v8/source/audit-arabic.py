#!/usr/bin/env python3
"""Offline QA: LanguageTool localhost and AyaSpell/Hunspell. Reports, never auto-replaces."""
import xml.etree.ElementTree as E, re, csv, json, bisect, subprocess, collections, os, requests, concurrent.futures
P='/home/user/Sa6i-Arabic-work'; OUT=os.environ.get('AUDIT_PREFIX',''); win=os.environ.get('AUDIT_WIN','sa6i-link_ar-DRAFT.ts'); android=os.environ.get('AUDIT_ANDROID','android-ar-DRAFT-strings.xml'); records=[]
t=E.parse(P+'/'+win)
for c in t.findall('./context'):
 ctx=c.findtext('name') or ''
 for m in c.findall('message'):
  src=m.findtext('source') or ''; trans=m.find('translation');
  if trans is None:continue
  forms=trans.findall('numerusform')
  if forms:
   for i,x in enumerate(forms):records.append(('Windows',ctx,src,x.text or '',str(i)))
  else:records.append(('Windows',ctx,src,trans.text or '',''))
androidbase={x.get('name'): ''.join(x.itertext()) for x in E.parse(P+'/android-English.xml').findall('.//string')}
for x in E.parse(P+'/'+android).findall('.//string'):
 key=x.get('name');records.append(('Android',key,androidbase.get(key,''),x.text or '',''))
# Include the separately embedded local guide and Android plural forms.
for idx,line in enumerate(open(P+'/'+os.environ.get('AUDIT_GUIDE','LocalGuide.qml'),encoding='utf8')):
 for m in re.finditer(r'\bar(?:Title|Summary|Detail):\s*("(?:[^"\\]|\\.)*")',line):
  try:text=json.loads(m.group(1))
  except json.JSONDecodeError:continue
  records.append(('Windows-guide',str(idx+1),'',text,''))
for pl in E.parse(P+'/'+os.environ.get('AUDIT_PLURALS','android-ar-DRAFT-plurals.xml')).findall('./plurals'):
 for x in pl.findall('./item'):records.append(('Android-plural',pl.get('name'),'%',x.text or '',x.get('quantity')))
unique={}
for platform,ctx,source,text,plural in records:
 if text.strip():unique.setdefault(text,[]).append((platform,ctx,source,plural))
print('records',len(records),'unique values',len(unique),flush=True)
# Hunspell flags candidates for review, not certain errors; strip vowel marks before checking.
count=collections.Counter()
for text in unique:
 for w in re.findall(r'[\u0621-\u063a\u0641-\u064a\u064b-\u065f\u0670\u0671-\u06d3]+',text):
  w=re.sub('[\u064b-\u065f\u0670]','',w)
  if len(w)>1:count[w]+=1
p=subprocess.run(['hunspell','-d','ar_SA','-l'],input='\n'.join(count)+'\n',text=True,stdout=subprocess.PIPE,check=True)
miss=set(p.stdout.splitlines())
with open(P+'/'+OUT+'hunspell-flagged-words.csv','w',encoding='utf-8-sig',newline='') as f:
 w=csv.writer(f);w.writerow(['word','distinct_translations_flagged']);w.writerows(sorted(((x,count[x]) for x in miss),key=lambda x:-x[1]))
print('Hunspell tokens',len(count),'flagged unique tokens',len(miss),flush=True)
# Batch unique strings, recording offsets in UTF-16 code units (LanguageTool API semantics).
texts=list(unique); batches=[]; pack=[];size=0
for text in texts:
 if pack and (len(pack)>=25 or size+len(text)>5000):batches.append(pack);pack=[];size=0
 pack.append(text);size+=len(text)
if pack:batches.append(pack)
def units(s):return len(s.encode('utf-16-le'))//2
def cut(s,start,end):return s.encode('utf-16-le')[2*start:2*end].decode('utf-16-le','replace')
def check(batch):
 joined='\n\n'.join(batch);starts=[]; n=0
 for text in batch:starts.append(n);n+=units(text)+2
 r=requests.post('http://127.0.0.1:9081/v2/check',data={'language':'ar','text':joined},timeout=100);r.raise_for_status();o=r.json();hits=[]
 for m in o['matches']:
  off=m['offset'];i=bisect.bisect_right(starts,off)-1
  if i<0:continue
  local=off-starts[i];end=local+m['length'];text=batch[i]
  if end>units(text):continue
  issue=cut(text,local,end); reps=[x['value'] for x in m['replacements'][:5]]
  hits.append({'text':text,'offset_utf16':local,'length_utf16':m['length'],'issue':issue,'suggestions':reps,'rule':m['rule']['id'],'message':m['message'],'refs':unique[text]})
 return hits
results=[];err=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
 fs={ex.submit(check,b):i for i,b in enumerate(batches)}
 for n,f in enumerate(concurrent.futures.as_completed(fs),1):
  try:results.extend(f.result())
  except Exception as e:err.append((fs[f],str(e)))
  if n%10==0 or n==len(fs):print('LanguageTool batches',n,'/',len(fs),'findings',len(results),'failed',len(err),flush=True)
with open(P+'/'+OUT+'languagetool-findings.json','w',encoding='utf8') as f:json.dump(results,f,ensure_ascii=False,indent=1)
with open(P+'/'+OUT+'languagetool-errors.json','w',encoding='utf8') as f:json.dump(err,f,ensure_ascii=False,indent=1)
with open(P+'/'+OUT+'languagetool-findings.csv','w',encoding='utf-8-sig',newline='') as f:
 w=csv.writer(f);w.writerow(['platform','context_or_id','english_source','arabic_draft','flagged_text','suggestions','rule','explanation']);
 for m in results:
  for plat,ctx,source,plural in m['refs']:w.writerow([plat,ctx,source,m['text'],m['issue'],' | '.join(m['suggestions']),m['rule'],m['message']])
print('done; failed batches',len(err),flush=True)
