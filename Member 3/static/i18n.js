/* Arabic interface.
   The page is written in English. When Arabic is on, every English text node and
   label (placeholder, title, aria-label, alt) that has a translation below is swapped,
   including text the app adds later (a MutationObserver watches the page). Switching
   back to English restores the originals. Anything the user typed or revealed
   (secret messages, stego text, names) is never touched. */
(function () {
  'use strict';

  const AR = {
    // ---- navigation and titles
    'Stego Studio': 'ستيغو ستوديو',
    'Hide': 'إخفاء', 'Reveal': 'كشف', 'Gallery': 'المعرض', 'Learn': 'تعلّم', 'History': 'السجل', 'Settings': 'الإعدادات',
    'Sign out': 'تسجيل الخروج', 'My account': 'حسابي', 'Menu': 'القائمة', 'Back': 'رجوع', 'Close': 'إغلاق',

    // ---- sign in / register / verify
    'Sign in': 'تسجيل الدخول', 'Sign-in': 'تسجيل الدخول', 'Email': 'البريد الإلكتروني', 'Password': 'كلمة المرور',
    'New here?': 'جديد هنا؟', 'Create an account': 'أنشئ حسابًا', 'Create account': 'إنشاء حساب',
    'Already have one?': 'لديك حساب؟', 'First name': 'الاسم الأول', 'Last name': 'اسم العائلة',
    'Check your email': 'تحقّق من بريدك', 'We sent a 6-digit code to': 'أرسلنا رمزًا من 6 أرقام إلى',
    'Code': 'الرمز', 'Verify': 'تأكيد', 'Resend code': 'إعادة إرسال الرمز', 'Email verified': 'تم تأكيد البريد',
    'Fill in every field.': 'املأ جميع الحقول.', 'Enter the 6-digit code.': 'أدخل الرمز المكوّن من 6 أرقام.',
    'Wrong e-mail or password.': 'البريد أو كلمة المرور غير صحيحة.', 'Wrong code.': 'الرمز غير صحيح.',
    'Enter the 6-digit code from the e-mail.': 'أدخل الرمز المكوّن من 6 أرقام من البريد.',
    'That code has expired. Request a new one.': 'انتهت صلاحية الرمز. اطلب رمزًا جديدًا.',
    'Too many wrong tries. Request a new code.': 'محاولات خاطئة كثيرة. اطلب رمزًا جديدًا.',
    'That e-mail is already registered. Sign in instead.': 'هذا البريد مسجّل مسبقًا. سجّل الدخول بدلًا من ذلك.',
    'This e-mail is already verified. Sign in.': 'هذا البريد مؤكَّد مسبقًا. سجّل الدخول.',
    'Start by creating an account.': 'ابدأ بإنشاء حساب.', 'Please sign in.': 'يرجى تسجيل الدخول.',
    'Please enter your first name.': 'يرجى إدخال اسمك الأول.', 'First name cannot be empty.': 'لا يمكن ترك الاسم الأول فارغًا.',

    // ---- hide
    'Image': 'صورة', 'Text': 'نص', 'Choose a picture': 'اختر صورة', 'Pick a picture': 'اختر صورة', 'Pick a picture.': 'اختر صورة.',
    'from the gallery or this computer, or drop one here': 'من المعرض أو من هذا الجهاز، أو أفلتها هنا',
    'Change': 'تغيير', 'Change picture': 'تغيير الصورة', 'Image type': 'نوع الصورة',
    'Visible text everyone will see': 'النص الظاهر الذي يراه الجميع', 'Secret message': 'الرسالة السرية',
    'Lock with a password': 'قفل بكلمة مرور', 'No password: anyone can read the message.': 'بدون كلمة مرور: يستطيع أي شخص قراءة الرسالة.',
    'Password (at least 6 characters)': 'كلمة المرور (6 أحرف على الأقل)', 'Suggest a strong password': 'اقترح كلمة مرور قوية',
    'Too short': 'قصيرة جدًا', 'Weak': 'ضعيفة', 'Fair': 'مقبولة', 'Good': 'جيدة', 'Strong': 'قوية',
    'Hide password': 'إخفاء كلمة المرور', 'Show password': 'إظهار كلمة المرور',
    'Copied. Keep it somewhere safe': 'تم النسخ. احفظها في مكان آمن', 'Write it down somewhere safe': 'دوّنها في مكان آمن',
    'Self-destruct': 'إتلاف ذاتي', 'Never': 'أبدًا', 'After 1 hour': 'بعد ساعة', 'After 1 day': 'بعد يوم',
    'After 7 days': 'بعد 7 أيام', 'After 30 days': 'بعد 30 يومًا',
    'Split into two pictures': 'تقسيم على صورتين',
    'Choose the second picture': 'اختر الصورة الثانية', 'Choose the second picture.': 'اختر الصورة الثانية.',
    'Second picture': 'الصورة الثانية',
    'Add another picture': 'أضف صورة أخرى',
    'Download all': 'تنزيل الكل', 'Previous picture': 'الصورة السابقة', 'Next picture': 'الصورة التالية',
    'The secret message is too long for text mode.': 'الرسالة السرية أطول من أن يتسع لها وضع النص.', 'Added picture': 'صورة مضافة',
    'For a split or spread message, choose all its pictures, in any order': 'لرسالة مقسّمة أو موزّعة، اختر كل صورها بأي ترتيب',
    'A split message has exactly two halves. Remove the extra pictures.': 'للرسالة المقسّمة نصفان فقط. أزل الصور الزائدة.', 'the message is spread across them': 'الرسالة موزّعة عليها',
    'Still too long. Add another picture.': 'ما زالت طويلة. أضف صورة أخرى.',
    'One of the added pictures is missing. Choose it again.': 'إحدى الصور المضافة مفقودة. اخترها مجددًا.',
    'One of the added files is not an image we can read.': 'أحد الملفات المضافة ليس صورة يمكننا قراءتها.',
    'One of these pictures is not part of this message.': 'إحدى هذه الصور ليست جزءًا من هذه الرسالة.',
    'These pictures belong to different messages.': 'هذه الصور من رسائل مختلفة.',
    'Each picture alone holds only random noise; both together give the message': 'كل صورة وحدها تحمل ضجيجًا عشوائيًا فقط، والصورتان معًا تعطيان الرسالة',
    'Hide and download': 'إخفاء وتنزيل', 'Hide in two pictures': 'إخفاء في صورتين', 'Hiding…': 'جارٍ الإخفاء…',
    'Checking…': 'جارٍ التحقق…', 'Picture too small': 'الصورة صغيرة جدًا',
    'Write the visible text.': 'اكتب النص الظاهر.', 'Write the secret message.': 'اكتب الرسالة السرية.',
    'Enter a password.': 'أدخل كلمة مرور.', 'Cannot reach the server.': 'تعذّر الوصول إلى الخادم.',
    'Choose a picture from the gallery or upload one.': 'اختر صورة من المعرض أو ارفع صورة.',
    'Unknown image type.': 'نوع صورة غير معروف.', 'Unknown self-destruct time.': 'مدة إتلاف غير معروفة.',
    'A self-destruct date needs the password lock, so nobody can change it.': 'يحتاج موعد الإتلاف إلى قفل كلمة المرور حتى لا يستطيع أحد تغييره.',
    'Downloaded': 'تم التنزيل', 'Downloaded both halves': 'تم تنزيل النصفين', 'Done': 'تم',
    'From gallery': 'من المعرض', 'Built-in pictures and your own': 'صور جاهزة وصورك الخاصة',
    'From this computer': 'من هذا الجهاز', 'PNG, JPEG, BMP or HEIC': 'PNG أو JPEG أو BMP أو HEIC',
    'Could not load the gallery': 'تعذّر تحميل المعرض', 'Hide in this picture': 'أخفِ في هذه الصورة',

    // ---- result panel
    'Hello': 'مرحبًا', 'Download': 'تنزيل', 'Part 1': 'الجزء 1', 'Part 2': 'الجزء 2', 'Copy text': 'نسخ النص',
    'QR code': 'رمز QR', 'Open in Reveal': 'افتح في الكشف', 'Copied': 'تم النسخ',
    'Select the text and press Ctrl+C': 'حدّد النص واضغط Ctrl+C',
    'Compare': 'مقارنة', 'Changes': 'التغييرات', 'X-ray': 'أشعة سينية', 'Show hidden': 'إظهار المخفي',
    'Original': 'الأصلية', 'With message': 'مع الرسالة', 'Original picture': 'الصورة الأصلية',
    'Compare original and result': 'قارن الأصل بالنتيجة', 'Slide between the original and the result': 'اسحب بين الأصل والنتيجة',
    'Light up every value that changed': 'أضئ كل قيمة تغيّرت', 'See the hidden-bit layer': 'اعرض طبقة البتات المخفية',
    'Show the invisible characters': 'أظهر الأحرف غير المرئية', 'Move over the picture': 'حرّك المؤشر فوق الصورة',
    'Drag across the picture': 'اسحب عبر الصورة', 'None found': 'لم يُعثر على شيء',
    'Image still loading': 'الصورة ما زالت تُحمَّل', 'Picture still loading': 'الصورة ما زالت تُحمَّل',
    'X-ray is not available for this image': 'الأشعة السينية غير متاحة لهذه الصورة',
    'Cannot compare: the picture was turned when it was loaded': 'تعذّرت المقارنة: تم تدوير الصورة عند تحميلها',
    'Identical': 'مطابقة', 'picture quality (PSNR)': 'جودة الصورة (PSNR)',
    'of colour values changed': 'من قيم الألوان تغيّرت', 'of colour values changed (each by 1)': 'من قيم الألوان تغيّرت (كلٌّ بمقدار 1)',
    "of the picture's space used": 'من مساحة الصورة مستخدمة', 'Unchanged': 'دون تغيير', 'visible text': 'النص الظاهر',
    'invisible characters added': 'حرفًا غير مرئي أُضيف', '2 halves': 'نصفان', 'each one alone is random noise': 'كل نصف وحده ضجيج عشوائي',
    'self-destructs': 'موعد الإتلاف الذاتي',
    'Looks identical to the original. Above 40 dB the eye cannot see a difference.': 'تبدو مطابقة للأصل. فوق 40 dB لا تستطيع العين رؤية أي فرق.',
    'Close to the original, but small changes may be visible up close.': 'قريبة من الأصل، لكن قد تظهر تغييرات صغيرة عن قرب.',
    'Looks exactly like the sentence you wrote.': 'تبدو تمامًا مثل الجملة التي كتبتها.',
    'Scan on a phone': 'امسح بالهاتف', 'Scan it, copy the text, and paste it into Reveal.': 'امسحه، وانسخ النص، والصقه في صفحة الكشف.',
    'QR code of the text with the hidden message': 'رمز QR للنص الذي يحمل الرسالة المخفية',
    'This text is too long for a QR code. Use a shorter message or cover.': 'هذا النص أطول من أن يتسع له رمز QR. استخدم رسالة أو نصًا أقصر.',
    'Nothing to put in the QR code.': 'لا يوجد ما يوضع في رمز QR.',

    // ---- tips
    'Share pictures as files, not photos: apps that shrink photos erase the hidden message.': 'شارك الصور كملفات لا كصور: التطبيقات التي تصغّر الصور تمحو الرسالة المخفية.',
    'Share the password another way, like a phone call.': 'شارك كلمة المرور بطريقة أخرى، كمكالمة هاتفية.',
    'PNG holds the most. JPEG holds less but survives a re-save.': 'PNG يتسع لأكثر. JPEG يتسع لأقل لكنه يصمد عند إعادة الحفظ.',
    'Text mode hides your secret in invisible characters inside a normal sentence.': 'وضع النص يخفي سرّك في أحرف غير مرئية داخل جملة عادية.',
    'Add your own pictures in Gallery to use them again and again.': 'أضف صورك الخاصة في المعرض لاستخدامها مرارًا.',

    // ---- reveal
    'Upload or drop the picture': 'ارفع الصورة أو أفلتها هنا', 'Paste the text': 'الصق النص',
    'Password (if it has one)': 'كلمة المرور (إن وُجدت)', 'Revealing…': 'جارٍ الكشف…',
    'Add the other half': 'أضف النصف الآخر', 'Other half': 'النصف الآخر', 'Remove': 'إزالة',
    'Choose a picture first.': 'اختر صورة أولًا.', 'Paste the text first.': 'الصق النص أولًا.', 'Paste the text first': 'الصق النص أولًا',
    'That file is not an image we can read.': 'هذا الملف ليس صورة يمكننا قراءتها.',
    'The other half is not an image we can read.': 'النصف الآخر ليس صورة يمكننا قراءتها.',
    'This picture holds half of a split message. Add the other half.': 'تحمل هذه الصورة نصف رسالة مقسّمة. أضف النصف الآخر.',
    'These two halves belong to different messages.': 'هذان النصفان من رسالتين مختلفتين.',
    'That is the same half twice. Add the other half.': 'هذا النصف نفسه مرتين. أضف النصف الآخر.',
    'Both pictures must be halves of a split message.': 'يجب أن تكون الصورتان نصفَي رسالة مقسّمة.',
    'This message needs its password.': 'هذه الرسالة تحتاج إلى كلمة مرورها.',
    'This message is protected. Enter the password to reveal it.': 'هذه الرسالة محمية. أدخل كلمة المرور لكشفها.',
    'Wrong password or image damaged; authentication failed.': 'كلمة المرور خاطئة أو الصورة تالفة، فشل التحقق.',
    'Wrong password, or the text was changed after the message was hidden.': 'كلمة المرور خاطئة، أو تغيّر النص بعد إخفاء الرسالة.',
    'No hidden message found in this text.': 'لم يُعثر على رسالة مخفية في هذا النص.',
    'No readable Image Stego Lab payload; the file may be unsupported or altered.': 'لا توجد رسالة قابلة للقراءة، قد يكون الملف غير مدعوم أو معدَّلًا.',
    'Hidden message is damaged.': 'الرسالة المخفية تالفة.', 'Hidden message is incomplete or corrupted.': 'الرسالة المخفية ناقصة أو تالفة.',
    'Hidden message failed CRC32 check; text was modified.': 'فشل فحص CRC32 للرسالة المخفية، تم تعديل النص.',
    'Image is too small to contain a compatible message.': 'الصورة أصغر من أن تحتوي على رسالة.',
    'This text cannot carry a message safely. Please use a different sentence.': 'لا يمكن لهذا النص حمل رسالة بأمان. استخدم جملة أخرى.',
    'Carrier already contains a hidden message. Use clean text.': 'النص يحتوي على رسالة مخفية مسبقًا. استخدم نصًا نظيفًا.',
    'This image has transparency. Choose PNG to preserve it.': 'لهذه الصورة شفافية. اختر PNG للحفاظ عليها.',
    'That file is too large. Please use an image under 40 MB.': 'الملف كبير جدًا. استخدم صورة أصغر من 40 ميغابايت.',
    'That picture is too large. Use one under 25 megapixels.': 'الصورة كبيرة جدًا. استخدم صورة أقل من 25 ميغابكسل.',
    'JPEG is not available on this server yet. Please choose PNG.': 'JPEG غير متاح على هذا الخادم بعد. اختر PNG.',
    'Something went wrong on the server. Please try again.': 'حدث خطأ في الخادم. حاول مرة أخرى.',
    'Server error.': 'خطأ في الخادم.', 'File too large (max 40 MB).': 'الملف كبير جدًا (الحد 40 ميغابايت).', 'Not found.': 'غير موجود.',

    // ---- gallery
    'Add picture': 'إضافة صورة', 'Add a picture to your gallery': 'أضف صورة إلى معرضك', 'Removed': 'تمت الإزالة',
    'Remove from my gallery': 'إزالة من معرضي', 'Only pictures you added can be removed.': 'يمكن إزالة الصور التي أضفتها فقط.',
    'Ocean': 'محيط', 'Sunset': 'غروب', 'Forest': 'غابة', 'Lavender': 'خزامى', 'Ember': 'جمر',
    'Glacier': 'جليد', 'Dune': 'كثبان', 'Rose': 'وردة', 'Slate': 'أردواز', 'Mint': 'نعناع',

    // ---- learn (Member 3's steps at the top)
    'Pick a picture, or choose': 'اختر صورة، أو اختر',
    'to hide inside a sentence. Write the secret and, if you want, add a password.': 'للإخفاء داخل جملة. اكتب السر، وأضف كلمة مرور إن أردت.',
    'Save the picture, or copy the text. It looks completely ordinary.': 'احفظ الصورة أو انسخ النص. يبدو عاديًا تمامًا.',
    'Upload the picture or paste the text in': 'ارفع الصورة أو الصق النص في',
    'and enter the password if it has one.': 'وأدخل كلمة المرور إن وُجدت.',
    'Start hiding': 'ابدأ الإخفاء', 'How it hides': 'كيف يتم الإخفاء',

    // ---- settings
    'Profile': 'الملف الشخصي', 'Appearance': 'المظهر', 'Security': 'الأمان', 'Privacy': 'الخصوصية', 'About': 'حول',
    'Save': 'حفظ', 'Saved': 'تم الحفظ', 'Update': 'تحديث', 'Current': 'الحالية', 'New': 'الجديدة',
    'Password updated': 'تم تحديث كلمة المرور', 'Picture updated': 'تم تحديث الصورة', 'Fill in both fields.': 'املأ الحقلين.',
    'Your current password is wrong.': 'كلمة مرورك الحالية خاطئة.', 'Wrong password.': 'كلمة المرور خاطئة.',
    'Theme': 'السمة', 'System': 'النظام', 'Light': 'فاتح', 'Dark': 'داكن', 'Colour': 'اللون', 'Language': 'اللغة',
    'Navy': 'كحلي', 'Light blue': 'أزرق فاتح', 'Red': 'أحمر', 'Green': 'أخضر', 'Purple': 'بنفسجي', 'Unknown colour.': 'لون غير معروف.',
    'Always': 'دائمًا', 'You are signed out every time you leave or reload': 'يتم تسجيل خروجك في كل مرة تغادر فيها أو تعيد التحميل',
    'Your data': 'بياناتك', 'Download my data': 'تنزيل بياناتي', 'Delete account': 'حذف الحساب', 'Delete my account': 'حذف حسابي',
    'Removes your pictures, history and profile. Cannot be undone.': 'يحذف صورك وسجلك وملفك الشخصي. لا يمكن التراجع عن ذلك.',
    'Your password': 'كلمة مرورك', 'Enter your password.': 'أدخل كلمة مرورك.', 'Account deleted': 'تم حذف الحساب',
    'Member since': 'عضو منذ', 'My pictures': 'صوري', 'Cancel': 'إلغاء', 'Adjust picture': 'ضبط الصورة',
    'Zoom': 'تكبير', 'Zoom in': 'تكبير', 'Zoom out': 'تصغير',
    'Pictures and text are made on the spot and handed straight to you.': 'تُصنع الصور والنصوص فورًا وتُسلَّم إليك مباشرة.',
    'Nothing you hide or reveal is saved': 'لا يُحفظ أي شيء تخفيه أو تكشفه',
    ', and your password is used only for that moment.': '، وتُستخدم كلمة مرورك في تلك اللحظة فقط.',
  };

  const N = (s) => s;   // numbers stay as written
  const PATTERNS = [
    [/^Good (morning|afternoon|evening), (.+)$/, (m) => `${m[1] === 'morning' ? 'صباح الخير' : 'مساء الخير'}، ${m[2]}`],
    [/^([\d,]+) \/ ([\d,]+) characters$/, (m) => `${N(m[1])} / ${N(m[2])} بايت`],
    [/^Self-destructs (.+)$/, (m) => `يُتلف ذاتيًا: ${m[1]}`],
    [/^This message self-destructed on (.+) UTC\.$/, (m) => `أُتلفت هذه الرسالة ذاتيًا في ${m[1]} (UTC).`],
    [/^Too many wrong passwords\. Try again in (\d+) minutes?\.$/, (m) => `محاولات خاطئة كثيرة. حاول مجددًا بعد ${m[1]} دقيقة.`],
    [/^Use a (new )?password of at least (\d+) characters\.$/, (m) => `استخدم كلمة مرور ${m[1] ? 'جديدة ' : ''}من ${m[2]} أحرف على الأقل.`],
    [/^A code was just sent\. Wait (\d+) seconds before asking for another\.$/, (m) => `أُرسل رمز للتو. انتظر ${m[1]} ثانية قبل طلب رمز آخر.`],
    [/^Your gallery is full \((\d+) pictures\)\. Remove one first\.$/, (m) => `معرضك ممتلئ (${m[1]} صورة). احذف واحدة أولًا.`],
    [/^([\d,]+) invisible characters · ([\d,]+) bytes$/, (m) => `${m[1]} حرفًا غير مرئي · ${m[2]} بايت`],
    [/^([\d,]+) invisible characters$/, (m) => `${m[1]} حرفًا غير مرئي`],
    [/^([\d,]+) of ([\d,]+) pixels changed \((.+)\)$/, (m) => `تغيّر ${m[1]} من ${m[2]} بكسل (${m[3]})`],
    [/^Added "(.+)"$/, (m) => `أُضيفت "${m[1]}"`],
    [/^([\d,]+) \/ ([\d,]+) characters · (\d+) pictures$/, (m) => `${m[1]} / ${m[2]} بايت · ${m[3]} صور`],
    [/^Picture (\d+) has no hidden message from this site\.$/, (m) => `الصورة ${m[1]} لا تحمل رسالة مخفية من هذا الموقع.`],
    [/^Picture (\d+)$/, (m) => `الصورة ${m[1]}`],
    [/^Download part (\d+)$/, (m) => `تنزيل الجزء ${m[1]}`],
    [/^Part (\d+)$/, (m) => `الجزء ${m[1]}`],
    [/^(\d+) pictures$/, (m) => `${m[1]} صور`],
    [/^Downloaded (\d+) pictures$/, (m) => `تم تنزيل ${m[1]} صور`],
    [/^Up to (\d+) pictures$/, (m) => `حتى ${m[1]} صور`],
    [/^This message is spread over (\d+) pictures\. Add the others\.$/, (m) => `هذه الرسالة موزّعة على ${m[1]} صور. أضف البقية.`],
    [/^This message is spread over (\d+) pictures\. Add pictures? ([\d, ]+(?: and \d+)?) of (\d+)\.$/, (m) => `هذه الرسالة موزّعة على ${m[1]} صور. أضف ${/and|,/.test(m[2]) ? 'الصور' : 'الصورة'} ${m[2].replace(' and ', ' و')} من ${m[3]}.`],
    [/^✓ (.+)$/, (m) => `✓ ${AR[m[1]] || m[1]}`],
  ];

  // Never translate what the user typed, a revealed secret, stego text, or names.
  const SKIP = '[data-secret],[data-out-text],[data-r-text],textarea,pre,script,style,[data-me-name],[data-cover-name],' +
               '[data-part2-name],[data-verify-email],.avatar,[translate="no"],code,kbd,.m4';   // .m4: Member 4's Learn and History text stays English
  const ATTRS = ['placeholder', 'title', 'aria-label', 'alt'];
  const original = new WeakMap();          // text node -> English it replaced
  let lang = 'en';
  try { lang = localStorage.getItem('lang') === 'ar' ? 'ar' : 'en'; } catch (e) { /* private mode */ }

  function translate(s) {
    const k = s.trim();
    if (!k || !/[A-Za-z]/.test(k)) return null;
    if (Object.prototype.hasOwnProperty.call(AR, k)) return AR[k];
    for (const [re, fn] of PATTERNS) { const m = k.match(re); if (m) return fn(m); }
    return null;
  }
  function doText(n) {
    const p = n.parentElement;
    if (!p || p.closest(SKIP)) return;
    const v = n.nodeValue, a = translate(v);
    if (a == null) return;
    const nv = v.match(/^\s*/)[0] + a + v.match(/\s*$/)[0];
    if (nv === v) return;
    original.set(n, v); n.nodeValue = nv;
  }
  function doEl(el) {
    if (el.closest(SKIP) && !el.matches('textarea,[data-r-text]')) return;   // a textarea's placeholder is fine
    for (const at of ATTRS) {
      const v = el.getAttribute(at);
      if (!v) continue;
      const a = translate(v);
      if (a == null || a === v) continue;
      (el.__en || (el.__en = {}))[at] = v;
      el.setAttribute(at, a);
    }
  }
  function apply(root) {
    if (lang !== 'ar') return;
    if (root.nodeType === 3) return doText(root);
    if (root.nodeType !== 1) return;
    doEl(root);
    const w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT);
    for (let n = w.nextNode(); n; n = w.nextNode()) n.nodeType === 3 ? doText(n) : doEl(n);
  }
  function restore() {
    const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT);
    for (let n = w.nextNode(); n; n = w.nextNode()) {
      if (n.nodeType === 3) { if (original.has(n)) { n.nodeValue = original.get(n); original.delete(n); } }
      else if (n.__en) { for (const at in n.__en) n.setAttribute(at, n.__en[at]); n.__en = null; }
    }
  }

  const observer = new MutationObserver((muts) => {
    if (lang !== 'ar') return;
    for (const m of muts) {
      if (m.type === 'characterData') doText(m.target);
      else if (m.type === 'attributes') doEl(m.target);
      else m.addedNodes.forEach(apply);
    }
  });

  function paintSwitches() {
    document.querySelectorAll('[data-lang]').forEach(b => b.classList.toggle('active', b.dataset.lang === lang));
    document.querySelectorAll('[data-lang-toggle]').forEach(b => { b.textContent = lang === 'ar' ? 'English' : 'العربية'; });
  }
  function setLang(l) {
    lang = l === 'ar' ? 'ar' : 'en';
    try { localStorage.setItem('lang', lang); } catch (e) { /* private mode */ }
    document.documentElement.lang = lang;
    document.documentElement.dir = lang === 'ar' ? 'rtl' : 'ltr';
    if (lang === 'ar') apply(document.body); else restore();
    paintSwitches();
    document.dispatchEvent(new CustomEvent('langchange', { detail: lang }));
  }

  document.addEventListener('click', (e) => {
    const t = e.target.closest('[data-lang-toggle]');
    if (t) return setLang(lang === 'ar' ? 'en' : 'ar');
    const b = e.target.closest('[data-lang]');
    if (b) setLang(b.dataset.lang);
  });

  observer.observe(document.body, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ATTRS });
  setLang(lang);
  window.i18n = { setLang, get lang() { return lang; }, t: (s) => (lang === 'ar' ? translate(s) ?? s : s) };
})();
