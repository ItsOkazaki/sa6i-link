import xml.etree.ElementTree as E,json,re,collections
P='/home/user/Sa6i-Arabic-work';m=json.load(open(P+'/checked-languagetool-findings.json',encoding='utf8'))
# Independently reviewed imperative forms, prompted by LanguageTool's wordiness rule.
allowed={'قم بتشغيل':'شغّل','قم بتوصيل':'وصّل','قم بإقران':'أقرن','قم بتحديث':'حدّث','قم ببث':'ابثّ','قم بمسح':'امسح','قم بإرسال':'أرسل','وقم بتشغيل':'وشغّل','قم بإعداد':'أعِدّ','قم بتبديل':'بدّل','قم بإجراء':'أجرِ','قم بإسقاط':'أسقط','قم بتعيين':'عيّن','قم بتمكين':'فعّل','قم بمشاركة':'شارك','قم بإنهاء':'أنه','قم بالتبديل':'بدّل','قم بوضع':'ضع','قم بتسجيل':'سجّل','قم بتغيير':'غيّر','قم بالسماح':'اسمح','قم بتوجيه':'وجّه','قم بتخصيص':'خصّص','قم بالتقاط':'التقط','قم بإلغاء':'ألغِ','قم بتحريك':'حرّك','قم بالتحديث':'حدّث','قم بإضافة':'أضف','قم بربط':'اربط','قم بتوسيع':'وسّع','قم بعرض':'اعرض'}
by=collections.defaultdict(dict)
for x in m:
 if x['rule']=='syntax_0000_Qam_bi_test' and x['issue'] in allowed:by[x['text']][(x['offset_utf16'],x['length_utf16'])]=(x['issue'],allowed[x['issue']])
counts=collections.Counter();bad=[];token=re.compile(r'%(?:\d+\$[a-zA-Z]|\d+|n|%)')
def transform(text):
 data=text.encode('utf-16-le')
 for (o,l),(old,new) in sorted(by.get(text,{}).items(),reverse=True):
  a,b=o*2,(o+l)*2
  if data[a:b].decode('utf-16-le')!=old:raise ValueError('offset mismatch')
  data=data[:a]+new.encode('utf-16-le')+data[b:];counts[old+' → '+new]+=1
 return data.decode('utf-16-le')
w=E.parse(P+'/nectarlink_ar-checked.ts')
for ctx in w.findall('./context'):
 for msg in ctx.findall('message'):
  source=msg.findtext('source') or '';t=msg.find('translation');
  if t is None:continue
  for n in t.findall('numerusform') or [t]:
   if n.text:
    n.text=transform(n.text)
    if collections.Counter(token.findall(source))!=collections.Counter(token.findall(n.text)):bad.append(source)
E.indent(w,space='    ');w.write(P+'/nectarlink_ar-reviewed.ts',encoding='utf-8',xml_declaration=True)
a=E.parse(P+'/android-ar-checked-strings.xml'); base={x.get('name'):''.join(x.itertext()) for x in E.parse(P+'/android-English.xml').findall('.//string')}
for e in a.findall('./string'):
 e.text=transform(e.text or '');source=base.get(e.get('name'),'')
 if collections.Counter(token.findall(source))!=collections.Counter(token.findall(e.text)):bad.append(e.get('name'))
E.indent(a,space='    ');a.write(P+'/android-ar-reviewed-strings.xml',encoding='utf-8',xml_declaration=True)
open(P+'/clarity-changes.json','w',encoding='utf8').write(json.dumps({'counts':counts,'placeholder_errors':bad},ensure_ascii=False,indent=2))
print('clarity changes',sum(counts.values()),'placeholder failures',len(bad));assert not bad
