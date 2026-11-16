import xml.etree.ElementTree as E, re
P='/home/user/Sa6i-Arabic-work'; t=E.parse(P+'/android-ar-DRAFT-plurals.xml')
texts={
'app_windows_title':['لا توجد تطبيقات مفتوحة على الحاسوب (%1$d)','تطبيق واحد مفتوح في نافذة على الحاسوب (%1$d)','تطبيقان مفتوحان في نافذتين على الحاسوب (%1$d)','%1$d تطبيقات مفتوحة في نوافذ على الحاسوب','%1$d تطبيقًا مفتوحًا في نوافذ على الحاسوب','%1$d تطبيق مفتوح في نوافذ على الحاسوب'],
'banking_chosen':['لم يتم اختيار أي تطبيق (%1$d)','تم اختيار تطبيق واحد (%1$d)','تم اختيار تطبيقين (%1$d)','تم اختيار %1$d تطبيقات','تم اختيار %1$d تطبيقًا','تم اختيار %1$d تطبيق'],
'data_clipboard_count':['لم يتم حفظ أي مقطع (%1$d)','تم حفظ مقطع واحد (%1$d)','تم حفظ مقطعين (%1$d)','تم حفظ %1$d مقاطع','تم حفظ %1$d مقطعًا','تم حفظ %1$d مقطع'],
'notification_connected_pcs':['غير متصل بأي حاسوب (%1$d)','متصل بحاسوب واحد (%1$d)','متصل بحاسوبين (%1$d)','متصل بـ %1$d حواسيب','متصل بـ %1$d حاسوبًا','متصل بـ %1$d حاسوب'],
'recorder_markers_count':['لا توجد علامات (%1$d)','علامة واحدة (%1$d)','علامتان (%1$d)','%1$d علامات','%1$d علامة','%1$d علامة'],
'transfer_files':['لا توجد ملفات (%1$d)','ملف واحد (%1$d)','ملفان (%1$d)','%1$d ملفات','%1$d ملفًا','%1$d ملف'],
'transfer_items':['لا توجد عناصر (%1$d)','عنصر واحد (%1$d)','عنصران (%1$d)','%1$d عناصر','%1$d عنصرًا','%1$d عنصر']}
order=['zero','one','two','few','many','other']
for el in t.findall('./plurals'):
 rows=texts[el.get('name')];assert len(rows)==6
 for q,text in zip(order,rows):
  assert text.count('%1$d')==1; el.find("./item[@quantity='"+q+"']").text=text
E.indent(t,space='    ');t.write(P+'/android-ar-checked-plurals.xml',encoding='utf-8',xml_declaration=True)
print('Reviewed',len(texts),'plural sets')
