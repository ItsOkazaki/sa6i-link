// SPDX-License-Identifier: GPL-3.0-or-later
// Sa6i Link's local quick guide. No external URLs; Arabic follows the application language setting.
import QtQuick
import sa6i.link

Item {
    id: guide
    property bool active: true
    property string deviceId: ""
    property string deviceName: ""
    readonly property bool arabic: Preferences.language === "ar"
    signal showMeRequested(string targetId)
    signal pairRequested()
    signal restartWalkthroughRequested()
    readonly property var topics: [
        { title: "Pair your phone", arTitle: "إقران الهاتف",
          summary: "Connect your phone and PC on the same Wi-Fi network.", arSummary: "صِل الهاتف والحاسوب بشبكة Wi-Fi نفسها.",
          detail: "1. Open Sa6i Link on the phone and PC.\n2. On the PC choose Pair a device.\n3. Scan the QR code or choose a nearby device and confirm the matching code.\n4. Accept the permissions for the features you want.",
          arDetail: "١. افتح Sa6i Link على الهاتف والحاسوب.\n٢. على الحاسوب اختر إقران جهاز.\n٣. امسح رمز QR أو اختر جهازاً قريباً وأكّد تطابق الرمز.\n٤. وافق على الأذونات اللازمة للميزات التي تريدها.", target: "pair" },
        { title: "Mirror the phone", arTitle: "عرض شاشة الهاتف",
          summary: "See your phone screen in a window on your PC.", arSummary: "اعرض شاشة هاتفك في نافذة على الحاسوب.",
          detail: "1. Connect your paired phone.\n2. On Home, choose Mirror screen.\n3. Approve Android's screen-capture prompt on the phone when asked.\nThe prompt may be required each time, depending on your phone and mode.",
          arDetail: "١. صِل هاتفك المقترن.\n٢. من الصفحة الرئيسية اختر عرض الشاشة.\n٣. وافق على طلب التقاط الشاشة في الهاتف عند ظهوره.\nقد تحتاج إلى الموافقة في كل مرة حسب الهاتف والوضع المستخدم.", target: "home:mirror" },
        { title: "Control the phone", arTitle: "التحكم في الهاتف",
          summary: "Use the mouse and keyboard in the mirror window.", arSummary: "استخدم الفأرة ولوحة المفاتيح في نافذة العرض.",
          detail: "Allow the phone's requested control/accessibility permission before trying mouse or keyboard input. In the mirror window, left-click acts as touch; right-click is Back. If control stops, review the phone's permissions and reconnect.",
          arDetail: "اسمح بإذن التحكم أو إمكانية الوصول المطلوب على الهاتف قبل استخدام الفأرة أو لوحة المفاتيح. في نافذة العرض تعمل النقرة اليسرى كلمسة، واليمنى للرجوع. إذا توقف التحكم فراجع الأذونات وأعد الاتصال.", target: "home:mirror" },
        { title: "Send files", arTitle: "إرسال الملفات",
          summary: "Send a file from your PC to the phone.", arSummary: "أرسل ملفاً من الحاسوب إلى الهاتف.",
          detail: "On Home, choose Send files, select a file and confirm the transfer. The phone may ask for permission to save it. The experimental Windows 7 Cloud Files/Explorer integration is not implemented; do not use it for phone storage.",
          arDetail: "من الصفحة الرئيسية اختر إرسال الملفات، وحدد الملف وأكّد الإرسال. قد يطلب الهاتف إذناً للحفظ. تكامل ملفات الهاتف مع مستكشف Windows 7 غير مطبّق في هذه النسخة التجريبية؛ لا تستخدمه لتصفح تخزين الهاتف.", target: "home:transfers" },
        { title: "Share clipboard", arTitle: "مشاركة الحافظة",
          summary: "Send copied content between your devices.", arSummary: "أرسل المحتوى المنسوخ بين أجهزتك.",
          detail: "Copy text on your PC, then choose Send clipboard on Home. Availability in the other direction depends on the phone's permissions and Android version. Check the phone app if clipboard sharing is off.",
          arDetail: "انسخ النص على الحاسوب، ثم اختر إرسال الحافظة من الصفحة الرئيسية. يعتمد الإرسال في الاتجاه الآخر على أذونات الهاتف وإصدار Android. راجع تطبيق الهاتف إذا كانت المشاركة متوقفة.", target: "home:clipboard" },
        { title: "Phone notifications", arTitle: "إشعارات الهاتف",
          summary: "View supported phone notifications on the PC.", arSummary: "اعرض إشعارات الهاتف المدعومة على الحاسوب.",
          detail: "Enable notification access for the phone app if you want to share notifications. Return to Home on the PC to see them. Notification actions depend on the originating phone app.",
          arDetail: "فعّل إذن الوصول إلى الإشعارات لتطبيق الهاتف إذا أردت مشاركتها. عُد إلى الصفحة الرئيسية على الحاسوب لرؤيتها. تختلف الإجراءات المتاحة حسب تطبيق الهاتف الأصلي.", target: "home:notifications" },
        { title: "Photos and messages", arTitle: "الصور والرسائل",
          summary: "Open Photos or Messages from the left navigation rail.", arSummary: "افتح الصور أو الرسائل من الشريط الجانبي.",
          detail: "Choose Photos to browse available phone media, or Messages to view supported conversations. Grant the appropriate permissions on the phone. Available functions depend on Android, app configuration and permissions.",
          arDetail: "اختر الصور لتصفح الوسائط المتاحة على الهاتف، أو الرسائل لعرض المحادثات المدعومة. امنح الأذونات المناسبة على الهاتف. تختلف الميزات المتاحة حسب Android وإعدادات التطبيق والأذونات.", target: "photos:main" },
        { title: "Connection help", arTitle: "المساعدة في الاتصال",
          summary: "If the devices do not connect, start with these checks.", arSummary: "إذا لم يتصل الجهازان، ابدأ بهذه الخطوات.",
          detail: "Check that Wi-Fi is enabled on both devices and that they are on the same network. Open the phone app, then reconnect on the PC. If needed, open Connection Doctor. Avoid running two PC copies at the same time.",
          arDetail: "تأكد من تشغيل Wi-Fi على الجهازين ومن اتصالهما بالشبكة نفسها. افتح تطبيق الهاتف ثم أعد الاتصال من الحاسوب. عند الحاجة افتح أداة تشخيص الاتصال. تجنب تشغيل نسختين على الحاسوب في الوقت نفسه.", target: "doctor:open" },
        { title: "Windows 7 test limitations", arTitle: "قيود نسخة Windows 7 التجريبية",
          summary: "This is a private compatibility test, not a finished release.", arSummary: "هذه نسخة اختبار توافق خاصة وليست إصداراً نهائياً.",
          detail: "Keep the previous working version as a fallback. Do not use the upstream updater. Phone storage through Explorer is not implemented by the compatibility patch. PC-to-phone capture is unverified, and some features may not work on Windows 7.",
          arDetail: "احتفظ بالنسخة السابقة العاملة للرجوع إليها. لا تستخدم محدّث التطبيق الأصلي. تصفح تخزين الهاتف في المستكشف غير مطبق في تصحيح التوافق. بث شاشة الحاسوب إلى الهاتف غير مُختبر، وقد لا تعمل بعض الميزات على Windows 7.", target: "settings:general" }
    ]

    Flickable {
        anchors.fill: parent
        anchors.margins: 20
        contentWidth: width
        contentHeight: content.implicitHeight + 24
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        Column {
            id: content
            width: Math.max(0, parent.width - 14)
            spacing: 12
            Row {
                width: parent.width
                spacing: 12
                Text { text: guide.arabic ? "دليل Sa6i Link" : "Sa6i Link guide"; color: Theme.surfaceContent; font.family: Theme.fontUi; font.pixelSize: 22; font.bold: true; anchors.verticalCenter: parent.verticalCenter }
            }
            Text {
                width: parent.width; wrapMode: Text.WordWrap
                horizontalAlignment: guide.arabic ? Text.AlignRight : Text.AlignLeft
                text: guide.arabic ? "دليل محلي داخل التطبيق. اضغط عرض للتنقل أو اقرأ المزيد للتفاصيل." : "Your local guide. Select Show me to navigate, or Learn more for the steps."
                color: Theme.surfaceContentVariant; font.family: guide.arabic ? "Tahoma" : Theme.fontUi; font.pixelSize: 14
            }
            Repeater {
                model: guide.topics
                delegate: Rectangle {
                    required property var modelData
                    property bool expanded: false
                    width: content.width
                    height: cardContent.implicitHeight + 32
                    radius: Theme.radiusLg
                    color: Theme.cardColor
                    border.width: 1; border.color: Theme.cardBorder
                    Column {
                        id: cardContent
                        x: 16; y: 16; width: parent.width - 32; spacing: 8
                        Text {
                            width: parent.width; wrapMode: Text.WordWrap
                            horizontalAlignment: guide.arabic ? Text.AlignRight : Text.AlignLeft
                            text: guide.arabic ? modelData.arTitle : modelData.title
                            color: Theme.surfaceContent; font.family: guide.arabic ? "Tahoma" : Theme.fontUi; font.pixelSize: 16; font.bold: true
                        }
                        Text {
                            width: parent.width; wrapMode: Text.WordWrap
                            horizontalAlignment: guide.arabic ? Text.AlignRight : Text.AlignLeft
                            text: guide.arabic ? modelData.arSummary : modelData.summary
                            color: Theme.surfaceContentVariant; font.family: guide.arabic ? "Tahoma" : Theme.fontUi; font.pixelSize: 14
                        }
                        Text {
                            visible: parent.parent.expanded
                            width: parent.width; wrapMode: Text.WordWrap
                            horizontalAlignment: guide.arabic ? Text.AlignRight : Text.AlignLeft
                            text: guide.arabic ? modelData.arDetail : modelData.detail
                            textFormat: Text.PlainText; lineHeight: 1.25
                            color: Theme.surfaceContent; font.family: guide.arabic ? "Tahoma" : Theme.fontUi; font.pixelSize: 14
                        }
                        Row {
                            spacing: 8
                            Rectangle {
                                width: 106; height: 30; radius: 8; color: Theme.primaryContainer
                                Text { anchors.centerIn: parent; text: guide.arabic ? "عرض" : "Show me"; color: Theme.primaryContainerContent; font.family: guide.arabic ? "Tahoma" : Theme.fontUi; font.pixelSize: 13 }
                                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: { if (modelData.target === "pair") guide.pairRequested(); else guide.showMeRequested(modelData.target) } }
                            }
                            Rectangle {
                                width: 120; height: 30; radius: 8; color: Theme.surfaceContainerLow
                                Text { anchors.centerIn: parent; text: guide.arabic ? (parent.parent.parent.parent.expanded ? "إخفاء" : "اقرأ المزيد") : (parent.parent.parent.parent.expanded ? "Hide" : "Learn more"); color: Theme.surfaceContent; font.family: guide.arabic ? "Tahoma" : Theme.fontUi; font.pixelSize: 13 }
                                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: parent.parent.parent.parent.expanded = !parent.parent.parent.parent.expanded }
                            }
                        }
                    }
                }
            }
        }
    }
}
