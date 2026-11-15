# 🤖 TikTok Auto-Repost Agent

ايجنت بيراقب حسابك على تيك توك، أول ما ينزل فيديو جديد:
1. ينزّله **من غير علامة مائية** (yt-dlp)
2. الذكاء الاصطناعي يكتب **عنوان ووصف وهاشتاجات** مختلفة لكل منصة
3. ينشره **Short على يوتيوب** + **Reel على فيسبوك** + **Reel على انستجرام**

كل حاجة مجانية 100%: APIs رسمية من جوجل وميتا (مجانية)، والذكاء الاصطناعي من Gemini (مجاني) أو Ollama (على جهازك).

---

## 1) التسطيب

```bash
python3.12 -m venv venv
./venv/bin/pip install -r requirements.txt
cp .env.example .env
```

افتح ملف `.env` واكتب يوزر تيك توك بتاعك في `TIKTOK_USERNAME`.

---

## 2) الذكاء الاصطناعي (اختار واحد)

**Gemini (الأسهل):** ادخل https://aistudio.google.com/apikey → Create API key → حطه في `GEMINI_API_KEY`.

**Ollama (محلي ومن غير أي حساب):** نزّله من https://ollama.com وبعدين:
```bash
ollama pull qwen2.5:7b
```
وفي `.env` خلي `LLM_PROVIDER=ollama`.

---

## 3) يوتيوب

1. ادخل https://console.cloud.google.com → اعمل Project جديد.
2. **APIs & Services → Library** → فعّل **YouTube Data API v3**.
3. **OAuth consent screen** → External → ضيف إيميلك في **Test users**.
4. **Credentials → Create Credentials → OAuth client ID → Desktop app** → نزّل الملف وسميه `client_secret.json` وحطه جنب `agent.py`.
5. سجّل دخول مرة واحدة:
```bash
./venv/bin/python agent.py --youtube-login
```

> ⚠️ مهم: جوجل بتخلي الفيديوهات اللي بتترفع من مشروع API **مش متراجع (unverified)** تبقى **Private** تلقائياً. علشان تبقى Public لازم تقدّم على [YouTube API Audit](https://support.google.com/youtube/contact/yt_api_form) (مجاني، بياخد كام يوم). لحد ما يتوافق عليك، الفيديوهات هتترفع Private وتقدر تخليها Public بإيدك من YouTube Studio.
> الحد المجاني: حوالي **6 فيديوهات في اليوم**.

---

## 4) انستجرام (Creator) — من غير صفحة فيسبوك

بنستخدم **Instagram API with Instagram Login** — بيشتغل مع حسابات Creator و Business ومش محتاج صفحة.

1. ادخل https://developers.facebook.com → My Apps → **Create App**.
2. في الـ Use case اختار **Manage messaging & content on Instagram**.
3. روح **API setup with Instagram login** → **Add account** → سجّل بحساب انستا بتاعك ووافق.
4. دوس **Generate token** جنب حسابك → انسخ التوكن وحطه في `IG_ACCESS_TOKEN`.
5. سيب `IG_USER_ID` فاضي.

> التوكن عمره 60 يوم، والايجنت **بيجدده لوحده** كل أسبوع، فمش هتحتاج تلمسه تاني طول ما الايجنت شغال.
> الـ App في وضع Development بيشتغل عادي على حسابك انت، مش محتاج مراجعة من ميتا.

## 5) فيسبوك (بروفايل متابعين)

ميتا **مش بتسمح لأي برنامج ينشر على البروفايل الشخصي** (حتى لو Professional mode) — الـ API بيشتغل مع **الصفحات** بس. عندك حلين مجانيين:

**الحل الأسهل (موصى بيه):** خلي انستا ينشر على فيسبوك لوحده:
انستجرام → Settings → **Accounts Center** → **Sharing across profiles** → اختار انستا → فيسبوك → فعّل **Share your reels to Facebook** (تلقائي).
كده الايجنت ينشر على انستا، وانستا يشاركه على بروفايل فيسبوك بتاعك. وخلي `ENABLE_FACEBOOK=false`.

**أو:** اعمل صفحة فيسبوك (دقيقة ببلاش) وحط بياناتها في `FB_PAGE_ID` و `FB_PAGE_TOKEN`، وخلي `ENABLE_FACEBOOK=true`:
1. في نفس الـ App ضيف **Facebook Login for Business**.
2. من [Graph API Explorer](https://developers.facebook.com/tools/explorer) → Get User Access Token بصلاحيات `pages_show_list, pages_read_engagement, pages_manage_posts`.
3. طوّل التوكن من [Access Token Debugger](https://developers.facebook.com/tools/debug/accesstoken) → Extend Access Token.
4. ابعت `me/accounts?fields=id,name,access_token` → `id` في `FB_PAGE_ID` و `access_token` في `FB_PAGE_TOKEN` (توكن الصفحة مبيخلصش).

---

## 6) التشغيل على جهازك (للتجربة)

```bash
./venv/bin/python agent.py
```

- أول تشغيل بيعلّم الفيديوهات القديمة إنها "قديمة" وبينشر **الجديد بس** (لو عاوز ينشر القديم كمان خلي `BACKFILL=true`).
- بيشيك كل 15 دقيقة (غيرها من `CHECK_EVERY_MINUTES`).
- لو منصة فشلت، بيعيد المحاولة عليها هي بس في اللفة الجاية من غير ما يكرر النشر على الباقي.

انشر فيديو معين حالاً:
```bash
./venv/bin/python agent.py --url "https://www.tiktok.com/@user/video/123456789"
```

---

## 7) السيرفر المجاني 24 ساعة (Oracle Cloud Always Free)

### إنشاء السيرفر (مرة واحدة)
1. اعمل حساب على https://cloud.oracle.com/free (بيطلب كارت للتحقق بس، **مش بيخصم حاجة** طول ما انت على Always Free).
2. **Compute → Instances → Create instance**:
   - Image: **Ubuntu 24.04**
   - Shape: **VM.Standard.A1.Flex** (ARM — مجاني: لحد 4 CPU و 24GB RAM) — أو **VM.Standard.E2.1.Micro** لو الـ A1 مش متاح.
   - في **Add SSH keys** اختار **Generate a key pair** ونزّل الـ private key.
3. بعد ما يشتغل، انسخ **Public IP**.

### الرفع والتشغيل (أمر واحد من جهازك)
```bash
chmod 600 ~/Downloads/ssh-key-*.key
./deploy/deploy.sh ubuntu@SERVER_IP ~/Downloads/ssh-key-XXXX.key
```
السكريبت بيرفع المشروع وبيسطب كل حاجة وبيشغّل الايجنت كـ **service**:
- بيقوم لوحده لو السيرفر عمل restart أو البرنامج وقع.
- بيحدّث yt-dlp كل يوم الساعة 4 الفجر (علشان تيك توك بيغيّر حاجات كتير).

> ⚠️ اعمل `./venv/bin/./venv/bin/python agent.py --youtube-login` على **جهازك الأول** قبل الرفع، لأن السيرفر مفيهوش متصفح. السكريبت بينقل تسجيل الدخول للسيرفر.

### متابعة السيرفر
```bash
ssh -i KEY ubuntu@SERVER_IP 'journalctl -u tiktok-agent -f'
```
لو عدلت حاجة في `.env` أو الكود، شغل `deploy.sh` تاني بنفس الطريقة.

---

## مشاكل شائعة

| المشكلة | الحل |
|---|---|
| تيك توك مش راضي يجيب الفيديوهات | حدّث yt-dlp: `pip install -U yt-dlp`، ولو لسه، صدّر كوكيز تيك توك من المتصفح (إضافة "Get cookies.txt LOCALLY") وحط المسار في `TIKTOK_COOKIES_FILE` |
| يوتيوب الفيديو Private | شوف ملحوظة الـ Audit فوق |
| انستجرام `Invalid OAuth access token` | ولّد توكن جديد من صفحة الـ App وحطه في `IG_ACCESS_TOKEN` واعمل deploy تاني |
| فيسبوك `(#200)` | استخدم **Page token** مش User token |

## هيكل المشروع
```
agent.py              ← العقل: يراقب وينسّق
tiktok.py             ← جلب الفيديوهات والتحميل بدون علامة مائية
captioner.py          ← الذكاء الاصطناعي للعناوين
publishers/           ← youtube.py, facebook.py, instagram.py
deploy/               ← رفع وتشغيل على السيرفر
data/state.json       ← بيفتكر إيه اتنشر فين
```

---

## 🍎 التشغيل على الماك (الطريقة المستخدمة حالياً)

الإيجنت شغال في الخلفية لوحده، وبيقوم مع الجهاز.

| عاوز | اكتب في التيرمنال |
|---|---|
| تشوف بيعمل إيه | `tail -f ~/Library/Logs/tiktok-agent.log` |
| تعيد تشغيله (بعد تعديل `.env`) | `./deploy/mac_install.sh` |
| توقفه خالص | `./deploy/mac_install.sh uninstall` |
| تنشر فيديو معين حالاً | `./venv/bin/python agent.py --url "رابط تيك توك"` |
| تعيد تسجيل دخول يوتيوب | `./venv/bin/python agent.py --youtube-login` |

الماك لازم يكون صاحي وعليه نت.

---

## ☁️ التشغيل الحالي: GitHub (من غير الماك)

الإيجنت شغال على **GitHub Actions** في المستودع الخاص `ahmedmatwe/tiktok-agent`، كل نص ساعة، والماك ممكن يتقفل.

- **إزاي بيشتغل:** GitHub بيشيك على صفحة تيك توك العامة (ببلاش). ولما يلاقي فيديو جديد، بيطلب من **Apify** ينزله من غير علامة مائية، لأن تيك توك بيقفل التحميل من السيرفرات.
- **التكلفة:** Apify بيدي رصيد مجاني 5 دولار كل شهر، وكل فيديو بياخد حوالي سنت واحد أو أقل.
- **تشغيل يدوي:** من صفحة المستودع ← Actions ← TikTok repost agent ← Run workflow.
- **لو حاجة وقفت:** GitHub بيبعتلك إيميل لو التشغيلة فشلت.
- **تحديث مفتاح:** `gh secret set اسم_المفتاح` (المفاتيح محفوظة مشفرة في Settings ← Secrets).
- **ماتشغلش نسخة الماك والنسخة دي مع بعض**، علشان الفيديو مايتنشرش مرتين.
