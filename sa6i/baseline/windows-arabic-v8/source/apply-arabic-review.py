#!/usr/bin/env python3
"""Apply reviewed terminology and a narrow allow-list of LanguageTool suggestions.
This never blindly accepts spelling/grammar suggestions. Placeholder validation is mandatory.
"""
import xml.etree.ElementTree as E,json,re,collections
P='/home/user/Sa6i-Arabic-work'; overrides=json.load(open(P+'/curated-overrides.json',encoding='utf-8')); findings=json.load(open(P+'/languagetool-findings.json',encoding='utf-8'))
allowed={'الكمبيوتر':'الحاسوب','كمبيوتر':'حاسوب','أولاً':'أولًا','بدلاً':'بدلًا','متصلاً':'متصلًا','قابلاً':'قابلًا','ليلاً':'ليلًا','أبداً':'أبدًا','وقابلاً':'وقابلًا','طويلاً':'طويلًا','اتصالاً':'اتصالًا','تلقائيا':'تلقائيًا','دائما':'دائمًا','صحيحا':'صحيحًا','بعيدا':'بعيدًا','خارجيا':'خارجيًا'}
bytext=collections.defaultdict(dict)
for m in findings:
 if m['rule'] not in ('AR_DARJA_REPLACE','typo_000_tanwin_nasb','typo_000_tanwin_nasb2'):continue
 x=m['issue'];r=allowed.get(x)
 if r and r in m['suggestions']:bytext[m['text']][(m['offset_utf16'],m['length_utf16'])]=(x,r)
stat=collections.Counter();counts=collections.Counter();errors=[];token=re.compile(r'%(?:\d+\$[a-zA-Z]|\d+|n|%)')
def approved(text):
 edits=bytext.get(text,{}); data=text.encode('utf-16-le')
 for (off,length),(old,new) in sorted(edits.items(),reverse=True):
  a,b=off*2,(off+length)*2
  if data[a:b].decode('utf-16-le')!=old:raise ValueError('invalid match offset')
  data=data[:a]+new.encode('utf-16-le')+data[b:];counts[old+' → '+new]+=1;stat['approved_tool_fixes']+=1
 return data.decode('utf-16-le')
def finish(src,text,ctx='',platform=''):
 if src in overrides:
  text=overrides[src];stat['curated_entries']+=1
 else:text=approved(text)
 if src=='Back' and ctx in ('HomePage','SettingsPage') and platform=='Windows':text='خلفية'
 if collections.Counter(token.findall(src))!=collections.Counter(token.findall(text)):errors.append((platform,ctx,src,text))
 return text
win=E.parse(P+'/sa6i-link_ar-DRAFT.ts')
plural={
 '%n min ago':['قبل %n دقيقة','قبل دقيقة واحدة (%n)','قبل دقيقتين (%n)','قبل %n دقائق','قبل %n دقيقة','قبل %n دقيقة'],
 '%n h ago':['قبل %n ساعة','قبل ساعة واحدة (%n)','قبل ساعتين (%n)','قبل %n ساعات','قبل %n ساعة','قبل %n ساعة'],
 '%n min':['%n دقيقة','دقيقة واحدة (%n)','دقيقتان (%n)','%n دقائق','%n دقيقة','%n دقيقة'],
 '%1 characters · %n text(s)':['%1 حرفًا · %n نص','%1 حرفًا · نص واحد (%n)','%1 حرفًا · نصان (%n)','%1 حرفًا · %n نصوص','%1 حرفًا · %n نصًا','%1 حرفًا · %n نص']
}
for context in win.findall('./context'):
 ctx=context.findtext('name') or ''
 for m in context.findall('message'):
  src=m.findtext('source') or '';trans=m.find('translation')
  if trans is None:continue
  forms=trans.findall('numerusform')
  if forms:
   new=plural.get(src)
   if new:
    assert len(forms)==len(new)==6
    for node,text in zip(forms,new):
     if collections.Counter(token.findall(src))!=collections.Counter(token.findall(text)):errors.append(('Windows',ctx,src,text))
     node.text=text;stat['reviewed_plural_forms']+=1
   else:
    for x in forms:x.text=finish(src,x.text or '',ctx,'Windows')
  else:trans.text=finish(src,trans.text or '',ctx,'Windows')
E.indent(win,space='    ');win.write(P+'/sa6i-link_ar-checked.ts',encoding='utf-8',xml_declaration=True)
androidbase={x.get('name'):''.join(x.itertext()) for x in E.parse(P+'/android-English.xml').findall('.//string')}
android=E.parse(P+'/android-ar-DRAFT-strings.xml')
for x in android.findall('./string'):
 key=x.get('name');source=androidbase.get(key,'');x.text=finish(source,x.text or '',key,'Android')
E.indent(android,space='    ');android.write(P+'/android-ar-checked-strings.xml',encoding='utf-8',xml_declaration=True)
# Original Android English uses escaped apostrophes; replacements contain none.
open(P+'/applied-review.json','w',encoding='utf-8').write(json.dumps({'counts':stat,'tool_fixes':counts,'placeholder_errors':errors},ensure_ascii=False,indent=2))
print('results',stat,'placeholder failures',len(errors),'unique curated source terms',len(overrides))
if errors:
 print(errors[:8]);raise SystemExit(1)
