# Unreviewed machine translation: draft only, validate on a real Android device.
import xml.etree.ElementTree as E, json,re,collections,os
w='/home/user/Sa6i-Arabic-work';d='/home/user/.cache/sa6i-ar/android';cache=json.load(open(w+'/machine-translations.json',encoding='utf-8'));src=E.parse(w+'/android-English.xml').getroot(); out=E.Element('resources'); bad=[]
pattern=re.compile(r'%(?:\d+\$[a-zA-Z]|\d+|n|%)')
overrides={'Settings':'الإعدادات','Home':'الرئيسية','Language':'اللغة','More':'المزيد','System':'النظام','Cancel':'إلغاء','Close':'إغلاق','Save':'حفظ','Search':'بحث','Mirror screen':'عرض الشاشة','Learn more':'المزيد من المعلومات','Show me':'أرني','Pair':'إقران','Device':'الجهاز','Phone':'الهاتف','General':'عام','Files':'الملفات','Messages':'الرسائل','Notifications':'الإشعارات','Photos':'الصور','Calls':'المكالمات','Deck':'لوحة التحكم','Guide':'الدليل','Apps':'التطبيقات','Back':'رجوع','Done':'تم','Continue':'متابعة','Off':'إيقاف','Setup':'الإعداد','App name':'اسم التطبيق','Text %1':'النص %1','%1+ items':'%1 عنصر أو أكثر'}
for item in src.findall('string'):
 if item.get('translatable')=='false':continue
 s=''.join(item.itertext()); t=overrides.get(s,cache.get(s,''));t=t.replace('$د','$d').replace('Sa6i Link','Sa6i Link').replace('رابط Sa6i','Sa6i Link').replace('نكتار لينك','Sa6i Link').replace('نكتارلينك','Sa6i Link')
 if collections.Counter(pattern.findall(s))!=collections.Counter(pattern.findall(t)) or (s.strip() and not t.strip()):bad.append(item.get('name'));continue
 # Android resource text must escape apostrophes and quotes. Preserve standard backslash escapes.
 t=t.replace("\\'", "'").replace("'", "\\'").replace('"','\\"')
 el=E.SubElement(out,'string',dict(item.attrib));el.text=t
os.makedirs(d+'/res/values-ar',exist_ok=True);E.indent(out,space='    ');E.ElementTree(out).write(d+'/res/values-ar/strings.xml',encoding='utf-8',xml_declaration=True)
# Arabic plurals: include all six categories; number is retained for formatting.
vals={'app_windows_title':'%1$d من التطبيقات مفتوحة في نوافذ على الحاسوب','banking_chosen':'تم اختيار %1$d من التطبيقات','data_clipboard_count':'تم حفظ %1$d من المقاطع','notification_connected_pcs':'متصل بـ %1$d من أجهزة الحاسوب','recorder_markers_count':'%1$d من العلامات','transfer_files':'%1$d من الملفات','transfer_items':'%1$d من العناصر'}
r=E.Element('resources')
for key,text in vals.items():
 pl=E.SubElement(r,'plurals',{'name':key})
 for q in ['zero','one','two','few','many','other']:E.SubElement(pl,'item',{'quantity':q}).text=text
E.indent(r,space='    ');E.ElementTree(r).write(d+'/res/values-ar/plurals.xml',encoding='utf-8',xml_declaration=True)
open(w+'/android-placeholder-errors.json','w',encoding='utf-8').write(json.dumps(bad,ensure_ascii=False,indent=2)); print('wrote',len(out),'strings; failures',len(bad),'7 plural sets')
# Android 13+ language picker; Android 11 follows system language unchanged.
p=d+'/smali/app/sa6i-link/android/ui/AppLanguage.smali';s=open(p).read();s=s.replace('.method static constructor <clinit>()V\n    .locals 6','.method static constructor <clinit>()V\n    .locals 7',1);old='    filled-new-array {v0, v1, v2, v3}, [Lkotlin/Pair;';new='''    new-instance v4, Lkotlin/Pair;
    const-string v5, "ar"
    const-string v6, "\\u0627\\u0644\\u0639\\u0631\\u0628\\u064a\\u0629"
    invoke-direct {v4, v5, v6}, Lkotlin/Pair;-><init>(Ljava/lang/Object;Ljava/lang/Object;)V
    filled-new-array {v0, v1, v2, v3, v4}, [Lkotlin/Pair;''';assert s.count(old)==1;s=s.replace(old,new);open(p,'w').write(s)
p=d+'/res/xml/locales_config.xml';s=open(p).read();assert '<locale android:name="ar"' not in s;s=s.replace('<locale android:name="tr" />','<locale android:name="tr" />\n    <locale android:name="ar" />');open(p,'w').write(s)
