# Machine-translated draft for testing only. Not reviewed or certified complete.
import xml.etree.ElementTree as ET, json,re,collections
root='/home/user/Sa6i-Arabic-work'; tr=json.load(open(root+'/machine-translations.json',encoding='utf-8'))
tr.update({'Text %1':'النص %1','%1+ items':'%1 عنصر أو أكثر','Settings':'الإعدادات','Home':'الرئيسية','Language':'اللغة','More':'المزيد','System':'النظام','Cancel':'إلغاء','Close':'إغلاق','Save':'حفظ','Search':'بحث','Mirror screen':'عرض الشاشة','Learn more':'المزيد من المعلومات','Show me':'أرني','Pair':'إقران','Device':'الجهاز','Phone':'الهاتف','General':'عام','English':'الإنجليزية','Arabic':'العربية','Files':'الملفات','Messages':'الرسائل','Notifications':'الإشعارات','Photos':'الصور','Calls':'المكالمات'})
tr.update({'Deck':'لوحة التحكم','Guide':'الدليل','Appearance':'المظهر','Devices':'الأجهزة','Connection & About':'الاتصال وحول التطبيق','Apps':'التطبيقات','Timeline':'الجدول الزمني','Offline':'غير متصل','Connected':'متصل','Find phone':'العثور على الهاتف','Continue':'متابعة','Done':'تم','Back':'رجوع','Off':'إيقاف','On':'تشغيل','Setup':'الإعداد','Start with Windows':'التشغيل مع Windows','Stay in system tray':'البقاء في علبة النظام','Features guide':'دليل الميزات','Open features guide':'فتح دليل الميزات','Learn more ›':'المزيد من المعلومات ›','Search features':'البحث في الميزات','Nectar Island':'Sa6i Island'})
p=re.compile(r'%(?:\d+\$[a-zA-Z]|\d+|n|%)'); invalid=[];tree=ET.parse(root+'/desktop-template.ts');top=tree.getroot();top.set('language','ar');messages=top.findall('.//message')
for m in messages:
 src=m.findtext('source') or ''; en=m.find('translation');t=tr.get(src,'');t=t.replace('NectarLink','Sa6i Link').replace('نكتار لينك','Sa6i Link').replace('نكتارلينك','Sa6i Link').replace('رابط Sa6i','Sa6i Link')
 if collections.Counter(p.findall(src))!=collections.Counter(p.findall(t)) or (src.strip() and not t.strip()):invalid.append(src); en.set('type','unfinished'); en.text='';continue
 en.attrib.pop('type',None)
 if m.get('numerus')=='yes':
  for c in list(en): en.remove(c)
  en.text=None
  for _ in range(6):ET.SubElement(en,'numerusform').text=t
 else:en.text=t
ET.indent(tree,space='    ');tree.write(root+'/nectarlink_ar-DRAFT.ts',encoding='utf-8',xml_declaration=True)
open(root+'/desktop-placeholder-errors.json','w',encoding='utf8').write(json.dumps(invalid,ensure_ascii=False,indent=2))
print('messages',len(messages),'placeholder failures',len(invalid),'plural forms: draft identical forms (require review)')
