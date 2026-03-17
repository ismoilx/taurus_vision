# 🐂 TAURUS VISION & TAURUS BRAIN
### *Ferma boshqaruvining yangi avlodi*

> **O'rta Osiyo va O'zbekiston uchun ishlab chiqilgan,  
> yirik chorvachilik fermalari uchun mo'ljallangan,  
> sun'iy intellekt asosidagi avtomatik ferma boshqaruv tizimi.**

---

## TIZIM HAQIDA

**Taurus Vision** — zamonaviy chorvachilik fermasi uchun ko'p qatlamli monitoring va boshqaruv platformasi. U real vaqt rejimida kameralar, sensorlar, ma'lumotlar va hodimlar orqali fermaning barcha jarayonlarini nazorat ostiga oladi.

**Taurus Brain** — Taurus Vision ustiga qurilgan avtonom ferma intellekti. U oddiy monitoring tizimidan farqli o'laroq, fermaning butun iqtisodiy, biologik va operatsional holatini bir vaqtda tushunadi, tahlil qiladi va qaror qabul qiladi.

```
Taurus Vision  →  Ko'radi, Kuzatadi, Qayd etadi
Taurus Brain   →  Tushunadi, Bashorat qiladi, Boshqaradi
```

Bu ikki tizim bir butunlikni tashkil etadi. Taurus Vision ma'lumotlar oqimini ta'minlaydi — Taurus Brain o'sha ma'lumotlardan ma'no chiqaradi va harakat qiladi.

---

## FALSAFA — NIMA UCHUN BU TIZIM?

Dunyodagi mavjud ferma monitoring tizimlari (SCR, Afimilk, Lely va boshqalar) bir umumiy kamchilikka ega: ular fermaning alohida qismlarini ko'radi — lekin butunini tushunmaydi.

Bir sensor haroratni o'lchaydi. Boshqa tizim vaznni kuzatadi. Uchinchi narsa ozuqa miqdorini hisoblaydi. Ammo hech biri shuni aytmaydi:

> *"Bu sigirning harorati ko'tarildi, oziqlanishi 3 kunda 35% kamaydi, ADI indeksi tushmoqda — bu mastit bo'lishi ehtimoli 78%. Veterinarga vazifa yaratildi, dori zaxirasi tekshirildi, bujet yetarli."*

Taurus Brain aynan shuni qiladi. Bu faqat sensor emas — bu fermaning miyasi.

### Ferma — 6 ta o'zaro bog'liq dunyo

```
Jonivorlar  ↔  Moliya  ↔  Hodimlar  ↔  Resurslar  ↔  Infratuzilma  ↔  Tashqi dunyo
```

Hozirgi tizimlar bularni **alohida** ko'radi. Taurus Brain ularni **birgalikda** tushunadi va o'zaro bog'liqliklardan qaror chiqaradi.

### Bog'liqlikni his qiling

```
Ob-havo 3 kun sovuq bo'ladi
    → Jonivorlar ko'proq energiya sarflaydi
        → Yem normasini oshirish kerak
            → Omborxonada yem yetarlimi?
                → Yo'q → Buyurtma berish kerak
                    → Budjeti bormi?
                        → Moliyaviy holat tekshiriladi
                            → Hodim bugun bo'shmi?
                                → Vazifa avtomatik yaratiladi + belgilanadi
```

Bir ob-havo o'zgarishi → 8 ta bog'liq qaror. Taurus Brain bularni bir necha soniyada ko'radi, inson esa tongda tayyor vazifalar ro'yxatini oladi.

---

## KIM UCHUN

Taurus tizimi **yirik professional chorvachilik fermalari** uchun ishlab chiqilgan:

| Ferma turi | Moslik |
|------------|--------|
| Faqat sut ishlab chiqarish | ✅ |
| Faqat go'sht ishlab chiqarish | ✅ |
| Aralash (sut + go'sht) | ✅ |
| Nasl va ko'paytirish fermalari | ✅ |
| Premium zotli jonivorlar | ✅ |
| Oddiy (zotsiz) jonivorlar | ✅ |
| Qo'y, echki, ot va boshqa chorva | ✅ |

Tizim faqat qoramol uchun emas — istalgan yirik chorvachilik fermasiga moslashadi.

---

## GEOGRAFIYA

Hozirgi bosqichda tizim **O'zbekiston va O'rta Osiyo** uchun optimallashtirilgan:

- O'zbek tili interfeysi
- Mahalliy iqtisodiy realliklar hisobga olingan
- O'rta Osiyo iqlim sharoitlariga moslashtirilgan
- Mintaqaviy chorvachilik standartlariga mos

---

## ISHLASH MODELI

Taurus tizimi **on-premise** asosida ishlaydi — har bir fermaning ma'lumotlari o'sha fermaning o'z serverida saqlanadi.

```
[Ferma serveri]  ←→  [Taurus tizimi]  ←→  [Kameralar + Sensorlar + Qurilmalar]
```

Hech qanday ferma ma'lumoti tashqi serverlarga yuborilmaydi. Taurus Brain o'sha fermadagi real ma'lumotlar asosida ishlaydi — bu uning asosiy kuchi.

**Xizmat modeli:** Tizim oylik obuna asosida mijozlarda o'rnatiladi va xizmat ko'rsatiladi.

---

---

# I. JONIVORLAR DOMENI

> *Bu tizimning yuragi. Har bir jonivor — alohida shaxs. Alohida tarixi, alohida normi, alohida ehtiyoji bor.*

---

## Identifikatsiya — Kim bu jonivor?

Tizimda har bir jonivor o'zining **tag ID** si bilan ro'yxatga olinadi (masalan: JNV-047). Kamerada ko'ringanda YOLO uni aniqlaydi, burun (muzzle) skaneri esa kimligini tasdiqlaydi.

```
Kamera kadr
    → YOLO26n          bbox + class + confidence
    → MuzzleDetector   burun ROI ajratish
    → MobileNetV2      128-o'lchamli embedding
    → Cosine sim ≥ 0.85
    → JNV-047 tasdiqlandi
```

Tanilmagan jonivor paydo bo'lsa — tizim darhol ogohlantiradi. Bu begona jonivorni aniqlash yoki yangi tug'ilgan buzoqni ro'yxatga olish uchun ham ishlatiladi.

---

## ADI — Animal Development Index

Har bir jonivor uchun kunlik sog'liq indeksi. 0 dan 100 gacha. Har kecha 00:30 da avtomatik hisoblanadi.

```
ADI = D×0.35 + M×0.25 + F×0.20 + W×0.20

Komponentlar:
    D  Detection score    Kamera deteksiya chastotasi va faolligi
    M  Movement score     Harakat sifati, bbox dinamikasi
    F  Feeding score      Oziqlanish idishiga tashrif, yem miqdori
    W  Weight score       Vazn dinamikasi, o'sish trendi

Kategoriyalar:
    75–100  HEALTHY    Sog'lom
    50–74   AVERAGE    O'rtacha, kuzatuv tavsiya
    25–49   WARNING    Diqqat, tekshiruv kerak
    0–24    CRITICAL   Kritik, darhol choralar
```

ADI ning qiymati emas — **trendi** muhim. 65 dan 50 ga tushayotgan jonivor, 50 da barqaror jonivvordan ko'ra ko'proq xavf tug'diradi.

---

## Individual Baseline — Har Jonivorning O'z "Normal"i

Bu Taurus Brain ning eng kuchli qismi.

**Muammo:** Umumiy normalar ishlamaydi. JNV-047 doim sekin yuradi — bu uning normi. JNV-089 kechqurun kamroq yeydi — bu ham normal. Agar umumiy threshold ishlatsak, ko'p yolg'on alarm bo'ladi va haqiqiy muammolar o'tkazib yuboriladi.

**Yechim:** LSTM Autoencoder har bir jonivorning o'ziga xos kunlik modelini o'rganadi.

```
30 kunlik tarix → LSTM o'rganadi → "JNV-047 ning normi shu"
Yangi kun kelyapti → Reconstruction error → Anomaliya balli (0.0–1.0)

> 0.70  → Diqqat: yana kuzat
> 0.85  → Xavfli: DiseasePredictor chaqiriladi
```

---

## Kasallik Bashorati — 48-72 Soat Oldin

```python
# DiseasePredictor output:
{
    "risk_score": 0.78,
    "disease": "mastitis",
    "reasons": [
        "Oziqlanish 40% kamaygan (normal: 180 min, bugun: 108 min)",
        "ADI so'nggi 3 kunda 8 ball tushgan",
        "Harorat 1.8°C oshgan",
        "Laktatsiya raqami 3 — mastit xavfi yuqori"
    ],
    "similar_cases": [
        "JNV-034 — 2024-03-15: mastit (o'xshashlik: 91%)",
        "JNV-019 — 2024-08-02: mastit (o'xshashlik: 87%)"
    ],
    "confidence": 0.78,
    "recommended_action": "Veterinar tekshiruvi 24 soat ichida"
}
```

SHAP (explainability) — ferma egasi har qarorning **nima uchun** ekanini ko'radi. Qora quti emas.

Xato bashorat bo'lsa — ferma egasi tuzatadi → model o'rganadi (online learning).

---

## Vazn Kuzatuvi

- Tarozi qurilmalari bilan avtomatik o'lchash
- Kamera orqali vizual vazn baholash (AI)
- 30 kunlik o'zgarish foizi hisobi
- Prophet modeli orqali **keyingi 30 kunlik vazn bashorati**
- Vazn 5%+ tushsa → darhol ogohlantirish

---

## Nasl va Ko'paytirish

- Har bir urg'ochi jonivorning homiladorlik holati
- Qochirish sanasi, kutilayotgan tug'ish sanasi
- Tug'ish muddati yaqinlashganda hodimga avtomatik vazifa
- Nasldorlik ko'rsatkichlari: otasi, onasi, avlodlari
- Tug'ilgan buzoqni darhol tizimga kiritish va teg berish

---

## Sog'liq Tarixi va Veterinariya

- Har bir kasallik epizodi: sana, tashxis, davolash, natijalari
- Dori-darmon: nima berildi, qancha, qachon
- Keyingi tekshiruv sanasi: tizim eslatib turadi
- Profilaktik emlash jadvali: muddati o'tsa avtomatik vazifa
- Sog'liq yozuvlari veterinar tomonidan tasdiqlanadi

---

## Xulq-Atvor Tahlili

- Poda ichidagi ijtimoiy faollik: qancha jonivor bilan birga vaqt o'tkazadi
- Ajralish indeksi: podadan uzoqlashish necha foiz vaqt
- Zona harakati: kunlik qaysi hududlarda bo'lishi
- Tun faolligi: nocturnal anomaliyalar
- Tong va kechki oziqlanish nisbati

---

## Jonivor Profili — Bir Sahifada Hammasi

```
Asosiy ma'lumot    tag, tur, zot, jins, yosh, holat
Joriy holat        ADI ball + kategoriya + trend grafigi
Vazn               So'nggi o'lchov + 30 kunlik grafik + bashorat
Xavf belgilari     [LOW_FEEDING] [ADI_DROPPING] kabi flaglar
Faol muammolar     Ochiq sog'liq yozuvlari
Oziqlanish         Bugungi + haftalik trend
Sensor             Harorat, yurak urishi, faollik
Nasl               Otasi, onasi, avlodlari
Moliya             Shu jonivvorga sarflangan xarajat va keltirgan daromad
Kamera tarixi      So'nggi 24 soat aniqlash vaqtlari
```

---

---

# II. MOLIYA DOMENI

> *Ferma — bu tirik biznes. Har bir qaror iqtisodiy oqibat tug'diradi. Taurus Brain bu oqibatlarni oldindan ko'radi.*

---

## Tranzaksiyalar va Hisobvaraq

Fermadagi barcha pul harakati bir joyda:

```
Daromad:
    Sut sotuvi           Kun, miqdor, narx, xaridor
    Go'sht sotuvi        Jonivor, vazn, narx, xaridor
    Jonivor sotuvi       Qaysi jonivor, qachon, kimga, qancha
    Nasl sotuvi          Buzoq, narx, xaridor
    Boshqa daromadlar    Subsidiya, sug'urta va h.k.

Xarajat:
    Ozuqa                Tur, miqdor, narx, yetkazuvchi
    Dori-darmon          Preparatlar, sarflangan miqdor
    Veterinar xizmati    Tashriflar, muolajalar
    Hodimlar ish haqi    Oylik, bonus, ortiqcha ish
    Texnik xarajatlar    Uskunalar, ta'mirlash
    Kommunal             Elektr, suv, gaz
```

---

## Har Jonivor uchun ROI

Tizim har bir jonivorning iqtisodiy samaradorligini hisoblaydi:

```
JNV-047 uchun oylik hisob:
    Xarajat:   Ozuqa 450,000 so'm + Dori 80,000 so'm + Ish haqi ulushi 60,000 so'm
    Daromad:   Sut 720 litr × 4,500 = 3,240,000 so'm
    ROI:       3,240,000 / 590,000 = 5.49
    Holat:     ✅ Samarali

JNV-023 uchun oylik hisob:
    Xarajat:   Ozuqa 430,000 so'm + Dori 320,000 so'm (kasallik sababli)
    Daromad:   Sut 280 litr × 4,500 = 1,260,000 so'm
    ROI:       1,260,000 / 750,000 = 1.68
    Holat:     ⚠️ Past, kasallik sabab
```

---

## Moliyaviy Bashorat

Prophet modeli asosida keyingi 3 oy uchun prognoz:

```
Bashorat asoslari:
    Hozirgi jonivorlar soni va holati
    Tarixiy sut/go'sht hajmi
    Rejalangan nasl hodisalari (tug'ish, sotish)
    Ozuqa narxlari trendi
    Mavsumiy o'zgarishlar
    Rejalangan katta xarajatlar

Natija (misol):
    Kelgusi 90 kun uchun:
        Kutilayotgan daromad:  45,200,000 – 52,800,000 so'm
        Kutilayotgan xarajat:  31,400,000 – 36,100,000 so'm
        Prognoz foyda:         10,100,000 – 19,400,000 so'm
        Ishonch darajasi:      74%
```

---

## Xarajat Anomaliyalari

Brain moliyaviy ko'rsatkichlarni kuzatadi va g'ayritabiiy holatlarda ogohlantiradi:

```
Misol 1:
"Bu oy veterinar xarajati o'tgan oyga nisbatan 68% oshdi.
Asosiy sabab: JNV-012, JNV-034, JNV-067 — uchta ketma-ket mastit holati.
Tavsiya: Bu uchta jonivorning yashash sharoitini tekshiring."

Misol 2:
"Ozuqa xarajati o'sdi, lekin o'rtacha ADI tushdi.
Ozuqa samaradorligi muammo. Yem sifatini tekshiring."

Misol 3:
"JNV-089 uchun dori xarajati 6 oy davomida ketma-ket ortib bormoqda.
Bu jonivorni saqlab turish iqtisodiy jihatdan zarar.
Sotish yoki qayta baholash tavsiya qilinadi."
```

---

## Optimal Sotish Vaqti

```
Brain hisobi:
    JNV-012 hozir 340 kg. Bozor narxi bugun 85,000 so'm/kg.
    Agar 45 kun kutilsa: bashorat 368 kg, narx prognozi 83,000–87,000 so'm.
    Hozir sotish:    28,900,000 so'm
    45 kun kutish:   30,476,000–31,416,000 so'm
    Tavsiya: Kutish foydali (+5.4%–+8.7%),
             lekin ozuqa va ish haqi xarajati 1,800,000 so'm.
```

---

## Budjet Nazorati

- Har kategoriya uchun oylik limit belgilanadi
- Limit 80% ga yetganda — ogohlantirish
- Limit o'tganda — ADMIN ga darhol xabar
- Kutilmagan katta xarajat — alohida tasdiqlash talab qiladi

---

---

# III. HODIMLAR DOMENI

> *Ferma ishchilari ko'zdan pana yerda ishlaydi. Tizim vazifani yaratadi, bajarilishini kuzatadi, natijalari bo'yicha hisobot beradi.*

---

## Xodim Profili

```
Asosiy ma'lumot      Ism, lavozim, telefon, kirish darajasi
Ish grafigi          Qaysi kunlar, qaysi soatlar
Mas'uliyat           Qaysi jonivorlar, qaysi hududlar
Faollik tarixi       Bajarilgan va bajarilmagan vazifalar
Ishlash ko'rsatkichi Muddatida bajardi / kechiktirdi / o'tkazib yubordi
```

---

## Vazifa Tizimi — Qanday Ishlaydi

Bu tizimning eng muhim operatsional qismi. Vazifalar ikki yo'l bilan yaratiladi:

### 1. Taurus Brain tomonidan avtomatik

Brain har 5 daqiqada barcha domenlarni tekshiradi va zarur vazifalarni o'zi yaratadi:

```
Sog'liq vazifasi:
    "JNV-047 ni veterinar ko'rsin"
    Sabab:    Mastit xavfi 78%, anomaliya indeksi kritik
    Muddat:   24 soat ichida
    Kim:      Navezbek (navbatchi veterinar)
    Prioritet: YUQORI

Ozuqa vazifasi:
    "A sektor uchun qo'shimcha yem bering"
    Sabab:    A sektordagi 12 ta jonivorning oziqlanishi -22%
    Muddat:   Bugun kechqurun
    Kim:      Bekzod (ozuqa mas'uli)
    Prioritet: O'RTA

Nasl vazifasi:
    "JNV-089 tug'ishga tayyor, kuzatuvga oling"
    Sabab:    Homiladorlik 282-kunida, tug'ish ±3 kun
    Muddat:   Doimiy kuzatuv, 3 kun
    Kim:      Sherzod (nasl bo'limi)
    Prioritet: YUQORI

Profilaktika vazifasi:
    "15 ta jonivorga iyun emlanishi"
    Sabab:    Jadval bo'yicha muddati keldi
    Muddat:   3 kun ichida
    Kim:      Navezbek (veterinar)
    Prioritet: O'RTA

Texnik vazifa:
    "CAM-NORTH-02 kamerasi signal yo'qotmoqda"
    Sabab:    So'nggi 2 soatda 14 marta uzilish qayd etildi
    Muddat:   Bugun
    Kim:      Jasur (texnik)
    Prioritet: YUQORI
```

### 2. Qo'lda, Menejer Tomonidan

Menejer ixtiyoriy vazifa yaratadi:
- Nima qilish kerak
- Kim uchun (xodim tanlash)
- Qachonga muddat
- Prioritet
- Izoh

---

## Vazifa Holatlari — To'liq Zanjir

```
YARATILDI    →  Brain yoki menejer yaratdi
BILDIRILDI   →  Xodim push/Telegram orqali xabar oldi
QABUL QILDI  →  Xodim "qabul qilaman" tasdiqladi
JARAYONDA    →  Xodim "boshladim" deb belgiladi
BAJARILDI    →  Xodim "tugatdim" + natija izohi yozdi
TASDIQLANDII →  Menejer bajarilganini ko'rib tasdiqadi
KECHIKDI     →  Muddat o'tdi, hali bajarilmagan
BEKOR QILINDI → Sabab ko'rsatib bekor qilindi
```

---

## Kechikish va Eslatmalar

Muddati o'tgan vazifalar avtomatik eslatma zanjirini ishga tushiradi:

```
Muddat + 1 soat   → Xodimga Telegram eslatma
Muddat + 3 soat   → Menejerga ogohlantirish
Muddat + 6 soat   → ADMIN ga xabar
                    Brain qayta baholaydi:
                    boshqa xodimga o'tkazish yoki prioritet oshirish
```

---

## Hodim Samaradorligi — Statistika

Tizim har bir xodim bo'yicha avtomatik statistika saqlaydi:

```
Bajarilgan vazifalar:     243 / 251  (96.8%)
O'rtacha kechikish:       18 daqiqa
Eng ko'p kechiktirilgan:  Tun navbati vazifalari
Eng samarali smena:       Ertalab 06:00–14:00

Vazifa turlari bo'yicha:
    Sog'liq vazifalar      98.2%  o'z vaqtida
    Texnik vazifalar       89.4%  o'z vaqtida
    Ozuqa vazifalar        99.1%  o'z vaqtida
```

Bu ma'lumot bonuslash, lavozim oshirish va jadval optimizatsiyasi uchun asos bo'ladi.

---

## Ish Jadvali va Navbat

- Haftalik ish grafigi tizimda belgilanadi
- Kim bugun navbatda — har doim ko'rinib turadi
- Brain vazifa yaratganda faqat **hozir navbatda bo'lgan** xodimga belgilaydi
- Xodim kasal bo'lsa yoki bo'lmasa — menejer o'zgartiradi, Brain darhol biladi
- Workforce optimizer: kim qaysi vazifaga eng mos — tajriba va yuklamaga qarab

---

## Xodimlar Bilan Muloqot

```
Tizim interfeysi    Kompyuter yoki telefon orqali kirish
Telegram bot        Darhol bildirishnoma + vazifa qabul qilish
Push notification   Mobil ilova (kelajakda)
```

Xodim vazifani to'g'ridan-to'g'ri Telegram orqali qabul qilib, bajarib, "tugatdim" deb belgilashi mumkin — tizimga kirmasdan.

---

---

# IV. RESURSLAR DOMENI

> *Ferma resurslari — ozuqa, dori, suv, energiya. Yetishmasa muammo, ortiqcha sarflansa zarar. Tizim muvozanatni saqlaydi.*

---

## Ozuqa Boshqaruvi

### Zaxira Kuzatuvi

```
Har turdagi yem alohida kuzatiladi (misol):
    Silos       Hozir: 4,200 kg | Kunlik sarflash: 180 kg | Qoladi: 23.3 kun
    Kunjara     Hozir:   820 kg | Kunlik sarflash:  45 kg | Qoladi: 18.2 kun
    Bug'doy     Hozir: 1,100 kg | Kunlik sarflash:  62 kg | Qoladi: 17.7 kun
    Mineral     Hozir:    95 kg | Kunlik sarflash:   3 kg | Qoladi: 31.6 kun
```

Zaxira 7 kunga yetadigan miqdorga tushganda — **buyurtma vazifasi** avtomatik yaratiladi.

### Oziqlantiruv Yozuvi

Har bir oziqlantiruv hodisasi qayd etiladi:
- Kim oziqlantirildi (jonivor yoki sektorlar bo'yicha)
- Qancha yem berildi (kg)
- Qaysi vaqtda
- Qaysi xodim bajardi

### FeedOptimizer (Brain)

```
Har jonivorning individual yem normasini hisoblaydi:
    Vazni, yoshi, laktatsiya holati
    ADI trendi (kamayayotgan bo'lsa yem oshiriladi)
    Mavsumiy norma (qish — ko'proq energiya)
    Bozor narxi (arzon va foydali aralashmani tavsiya qiladi)

Natija (misol):
    "A sektordagi jonivorlar uchun optimal aralashma:
    Silos 62% + Kunjara 24% + Mineral 14% = kunlik 8.4 kg/bosh"
```

---

## Dori-Darmon Inventari

```
Har bir preparatni kuzatish:
    Nomi, turi, miqdori
    Sotib olingan sana, yaroqlilik muddati
    Sarflangan miqdor va qaysi jonivvorda ishlatilgani
    Qolgan zaxira + kunlik sarflanish trendi

Avtomatik ogohlantirishlar:
    Zaxira kamligi            10 dozadan kam
    Yaroqlilik muddati        30 kun qolsa eslatma
    Bir jonivvorga ko'p dori  noodatiy sarflash anomaliyasi
```

---

## Inventar Bashorati

InventoryManager modeli asosida:
- Hozirgi sarflash tezligida resurs qachon tugashi
- Kelgusi nasl va kasallik xavflariga qarab ehtiyot zaxira hisoblash
- Mavsum bo'yicha sarflash prognozi

---

---

# V. INFRATUZILMA DOMENI

> *Ko'rinmas, lekin hamma narsa shuning ustiga qurilgan. Kamera ishlamasa — ko'r bo'lamiz. Sensor uzilsa — kar bo'lamiz.*

---

## Kameralar

```
Har bir kamerani kuzatish:
    Holat               Online / Offline / Signal zaif
    Kadrlar/soniya      FPS monitoring
    Bugungi aniqlashlar Nechta deteksiya amalga oshdi
    Signal sifati       So'nggi 24 soatda uzilishlar soni
    Oxirgi kadr vaqti   Oxirgi muvaffaqiyatli signal

Qo'llab-quvvatlanadiganlar:
    IP kamera (RTSP)    Asosiy
    USB kamera          Mahalliy test
    ONVIF protokol      Standart
```

Kamera 30 daqiqadan ko'p offline bo'lsa → texnikga avtomatik vazifa yaratiladi.

---

## IoT Sensorlar

```
Sensor turlari:
    Harorat sensori     Tana harorati °C (collar qurilma)
    Yurak urishi        Bpm o'lchash
    Faollik sensori     Akselerometr
    Tarozi sensori      Avtomatik vazn o'lchash
    Muhit sensori       Ferma harorati, namlik, CO2

Har bir qurilma kuzatuvi:
    Device ID, tur, holat
    So'nggi o'lchov vaqti
    Batareya darajasi
    Xatolik tarixi
```

---

## Tarozi Qurilmalari

- Bir nechta tarozi qurilmasi boshqariladi
- Har tarozi uchun kalibrlash tarixi
- Avtomatik o'lchash natijalarini jonivor profiliga bog'lash
- AI vizual vazn baholash bilan solishtirish

---

## Tizim Sog'lik Monitoringi

```
/health endpointi:
    PostgreSQL    ✅  Ulanish va javob vaqti
    Redis         ✅  Cache ishlashi
    Celery        ✅  Worker va beat holati
    Kameralar     ⚠️  2 ta offline
    Sensorlar     ✅  Barchasi ishlaydi
    AI modellar   ✅  YOLO, MuzzleDetector yuklangan
    Brain         ✅  Oxirgi sikl: 4 daqiqa oldin
```

---

## Audit Log

Tizimda har qanday o'zgarish qayd etiladi:

```
Kim o'zgartirdi     Foydalanuvchi
Nima o'zgartirdi    Jadval va maydon
Qanday o'zgartirdi  Eski qiymat → yangi qiymat
Qachon              Aniq timestamp
Qayerdan            IP manzil, qurilma
```

Bu xavfsizlik, hisobot va tartib uchun zarur.

---

## Bildirishnomalar

```
Push notification   Veb va mobil ilovaga
Telegram bot        Darhol xabar, vazifa qabul qilish
SMS                 Kritik holatlarda (konfiguratsiya mumkin)
Email               Hisobotlar va kunlik xulosa
Tizim ichida        Ko'rsatkich, badge, pop-up
```

Har foydalanuvchi qaysi hodisalar haqida, qaysi kanal orqali xabar olishini o'zi belgilaydi.

---

---

# VI. TASHQI DUNYO DOMENI

> *Ferma vakuumda yashay olmaydi. Bozor narxi, ob-havo, yetkazuvchilar — bularning barchasi ferma qarorlariga ta'sir qiladi.*

---

## Tashqi Integratsiyalar

```
REST API        Tashqi tizimlar bilan ma'lumot almashish
Webhook         Real-time hodisalarni tashqariga yuborish
API Key tizimi  Xavfsiz kirish boshqaruvi
```

---

## Bozor Narxlari (Brain)

Brain tashqi bozor signallarini qarorlariga qo'shadi:

```
Go'sht narxi bugun 87,000 so'm/kg
So'nggi 30 kun: 81,000 → 87,000 (7.4% o'sish)

Brain tavsiyasi:
"JNV-112 va JNV-156 hozir sotish foydali.
Narx yana o'sishi ehtimoli past — market signal tushishni ko'rsatmoqda."
```

---

## Ob-Havo Integratsiyasi (Kelajak)

```
3 kunlik bashorat asosida:
    Brain ozuqa normalarini moslashtiradi
    Sovuq tushganda issiqlashtirish vazifalari yaratiladi
    Jazirama issiqda suv normasi oshiriladi
    Shamol va yomg'ir — kamera ishlash rejimi moslashtiriladi
```

---

## Hisobot va Export

```
Formatlar:     PDF, CSV, Excel

Hisobot turlari:
    Oylik moliya hisoboti
    Jonivorlar holati umumiy ko'rinishi
    Veterinar yozuvlari xulosasi
    Ozuqa sarflash hisoboti
    Hodimlar samaradorligi
    AI bashoratlar to'g'riligi (accuracy report)
    Ferma umumiy KPI hisoboti
```

---

---

# TAURUS BRAIN — ARXITEKTURA

## 5 Qatlam Modeli

```
L1  KO'RISH       Kameralar, YOLO, ADI, sensorlar
L2  TUSHUNISH     Individual baseline (LSTM), anomaliya aniqlash
L3  BASHORAT      Kasallik (XGBoost), vazn (Prophet), moliya, hosildorlik
L4  QAROR         DecisionEngine — barcha domenlarni birlashtiradi
L5  NAZORAT       Avtonom boshqaruv — IoT, hodimlar, moliya
```

---

## Feature Pipeline — Asosiy Ma'lumot Zanjiri

Har jonivor uchun har kun bitta standartlashtirilgan feature vektori yaratiladi. Bu vektor barcha Brain modellarining "tili" — hech bir modul DB ga to'g'ridan-to'g'ri murojaat qilmaydi.

```
AnimalDayFeatures:
    movement    Hourly deteksiyalar, faol soatlar, bbox trend, zona entropiyasi
    feeding     Kunlik yem kg, sessiyalar soni, regulyarlik, normadan og'ish %
    social      Poda qo'shnilari, ijtimoiy indeks, ajralish indeksi
    sensor      O'rtacha harorat, yurak urishi, faollik darajasi
    health      ADI ball + 3 kunlik trend, vazn 30 kunlik o'zgarishi, vet tarixi
    static      Yosh, zot, jins, laktatsiya raqami
```

Bu vektor 40 o'lchamli float ro'yxatiga tekislanadi (XGBoost uchun) yoki `(30, 40)` tensorda saqlanadi (LSTM uchun).

---

## DecisionEngine — Har 5 Daqiqada

```python
run_cycle():
    check_animal_health()       # Anomaliya + kasallik xavfi
    check_feed_inventory()      # Zaxira yetarliligi
    check_financial_alerts()    # Budjet chegaralari
    check_employee_schedule()   # Vazifalar o'z vaqtidami?
    check_environmental()       # Sensor anomaliyalari
    check_breeding_calendar()   # Nasl rejasi
    check_market_prices()       # Bozor signallari
    → prioritet bo'yicha tartiblab vazifalar yaratadi
    → tegishli xodimga push/Telegram notification
    → IoT buyruq (critical + avtonom rejimda)
    → natijani logga yozadi (RL uchun)

Prioritet darajalari:
    CRITICAL  anomaliya > 0.9 + kasallik > 80% → veterinar darhol
    HIGH      ADI < 30 yoki vazn 5%+ tushgan
    MEDIUM    Ozuqa kam, anomaliya 0.6–0.9
    LOW       Jadval bo'yicha profilaktika
    AUTO      IoT sensor → avtomatik harakat (avtonom rejim)
```

---

## FarmIntelligence — Markaziy Miya

```python
class FarmIntelligence:
    feature_pipeline       # Barcha ma'lumot shu yerdan keladi
    baseline_models        # Har jonivor uchun alohida LSTM
    disease_predictor      # XGBoost + SHAP
    weight_forecaster      # Prophet
    feed_optimizer         # RL agent
    herd_analyzer          # K-Means klasterizatsiya
    yield_predictor        # Gradient Boosting
    decision_engine        # Qaror qabul qilish
    financial_analyzer     # Moliya AI
    workforce_optimizer    # Hodim AI
    inventory_manager      # Resurs AI

    get_farm_pulse()       # Ferma bir lahzadagi to'liq holati
    ask()                  # Natural language so'rov → real javob
```

---

## Brain Dizayn Prinsiplari

### 1. Har qaror tushuntiriladigan bo'lsin

```python
# NOTO'G'RI:
{"risk": 0.78}

# TO'G'RI:
{
    "risk": 0.78,
    "disease": "mastitis",
    "reasons": [
        "Oziqlanish 40% kamaygan (normal: 180 min, bugun: 108 min)",
        "ADI 3 kunda 8 ball tushgan",
        "Harorat 1.8°C oshgan",
        "Laktatsiya raqami 3 — mastit xavfi yuqori"
    ],
    "similar_cases": ["JNV-034 — 2024-03-15: mastit (91%)"],
    "confidence": 0.78
}
```

### 2. Domain bilimini kod ichiga yoz

```python
# NOTO'G'RI:
if score > threshold: alert()

# TO'G'RI:
if (
    feeding_drop_pct > 30 and      # 30%+ tushish xavfli
    adi_trend_3d < -5 and          # 3 kunda 5+ ball tushish
    temperature_rise > 1.5 and     # 1.5°C+ ko'tarilish
    animal.lactation_number > 2    # Ko'p laktatsiyali → mastit xavfi
):
    trigger_mastitis_check(animal)
```

### 3. Xato qilganda o'rgansin

```
Har yolg'on alarm       = o'rganish imkoniyati → model yangilanadi
Har o'tkazib yuborish   = o'rganish imkoniyati → sensitivity oshadi
Online learning         = tizimning hayot kuchi
```

### 4. Kengayish yo'li

```
Hozir:       Rule-based + ML aralash
→            Ma'lumot to'planganda ML ustunlashuvi
→            Yetarli data bo'lganda Deep Learning
→            Ko'p ferma bo'lganda Federated Learning
```

---

# TEXNIK STACK

## Backend

```
FastAPI (async)        Python web framework
SQLAlchemy 2.0         ORM (async)
PostgreSQL 15          Asosiy ma'lumotlar bazasi
Redis 7                Cache va real-time ma'lumotlar
Alembic                DB migratsiyalari (22+ versiya)
Celery + Celery Beat   Fon vazifalar va jadval (11 modul)
PyJWT + bcrypt         Autentifikatsiya va parol
Pydantic v2            Ma'lumot validatsiyasi
```

## AI / ML

```
Ultralytics YOLO26n    Real-time jonivor aniqlash
MobileNetV2            128-dim embedding (identifikatsiya)
Cosine similarity      Jonivor tanish (≥ 0.85 threshold)
scikit-learn           Klassifikatsiya va klasterizatsiya
XGBoost + SHAP         Kasallik bashorati va tushuntirish
Prophet                Vaqt qatori bashorat
LSTM Autoencoder       Individual norm o'rganish
K-Means                Poda klasterizatsiya
```

## Frontend

```
React 18 + TypeScript  UI framework
Vite                   Build tool
TailwindCSS            Styling
React Query (TanStack) Server state boshqaruvi
Recharts               Grafiklar va vizualizatsiya
Lucide React           Ikonlar
```

## Infratuzilma

```
Docker + docker-compose    8 servis konteyneri
Nginx                      Reverse proxy (server rejimida)
Telegram Bot               Xabarlar va vazifa kanali
```

## Docker Servislari

```
postgres          Ma'lumotlar bazasi
redis             Cache
backend           FastAPI asosiy server
celery-worker     Fon vazifalar
celery-beat       Jadval vazifalar
celery-flower     Task monitoring
frontend          React UI
telegram-bot      Bot server
```

---

# FAYL TUZILMASI

```
taurus_vision/
│
├── backend/
│   ├── app/
│   │   ├── api/v1/
│   │   │   ├── endpoints/             35+ HTTP endpoint
│   │   │   ├── websocket.py           Real-time WebSocket
│   │   │   └── exception_handlers.py
│   │   │
│   │   ├── models/                    28 SQLAlchemy model
│   │   ├── schemas/                   27 Pydantic v2 schema
│   │   ├── repositories/              24 repository (faqat DB)
│   │   ├── services/                  40+ servis (biznes logika)
│   │   │   └── ai/
│   │   │       ├── brain/             Taurus Brain modullari
│   │   │       │   ├── feature_pipeline.py
│   │   │       │   ├── animal_baseline.py
│   │   │       │   ├── disease_predictor.py
│   │   │       │   ├── weight_forecaster.py
│   │   │       │   ├── decision_engine.py
│   │   │       │   ├── farm_intelligence.py
│   │   │       │   ├── financial_analyzer.py
│   │   │       │   ├── workforce_optimizer.py
│   │   │       │   ├── feed_optimizer.py
│   │   │       │   ├── herd_analyzer.py
│   │   │       │   └── inventory_manager.py
│   │   │       ├── yolo_service.py
│   │   │       ├── muzzle_detector.py
│   │   │       └── feature_extractor.py
│   │   │
│   │   └── core/
│   │       ├── config.py
│   │       ├── database.py
│   │       ├── security.py
│   │       ├── cache.py
│   │       └── exceptions.py
│   │
│   ├── alembic/versions/              22+ migratsiya fayllari
│   ├── workers/tasks/                 11 Celery task moduli
│   └── tests/
│       ├── test_api/                  15 API test moduli
│       └── test_integration/          4 integratsiya test
│
├── frontend/src/
│   ├── pages/                         35+ sahifa
│   ├── components/                    UI komponentlar
│   ├── hooks/                         Custom React hooks
│   ├── api/                           API integratsiya qatlami
│   └── types/                         TypeScript tiplar
│
├── brain/
│   ├── models/                        Saqlangan .pt, .joblib, .onnx
│   ├── training/                      Model o'qitish skriptlari
│   ├── notebooks/                     Jupyter eksperimentlar
│   └── data/parquet/                  Batch training ma'lumotlari
│
├── docker-compose.yml                 Lokal muhit
├── docker-compose.server.yml          Server (HTTPS) muhit
└── Makefile                           Qulay buyruqlar
```

---

# MA'LUMOT BAZASI — ASOSIY JADVALLAR

```
animals                 Jonivorlar: tag, tur, zot, jins, yosh, holat
detections              YOLO hodisalari: bbox, confidence, timestamp, kamera
health_records          Veterinar yozuvlari, kasallik, davolash
feeding_records         Oziqlantiruv log: miqdor, vaqt, jonivor
sensor_readings         IoT: harorat, yurak urishi, faollik
weight_measurements     Vazn o'lchov tarixi
milk_productions        Sut mahsuldorligi
meat_production         Go'sht ishlab chiqarish
employees               Hodimlar va ish grafigi
tasks                   Vazifalar: holat, prioritet, muddat, mas'ul xodim
farms                   Ferma ma'lumotlari va sozlamalari
alerts                  Ogohlantirishlar log
adi_logs                Kunlik ADI indeks tarixi (time-series)
health_predictions      AI sog'liq bashoratlari
breeding                Nasl va ko'paytirish yozuvlari
finance                 Moliyaviy tranzaksiyalar
medicine                Dori-darmon inventari va sarflash
cameras                 Kamera konfiguratsiyalari
scales                  Tarozi qurilmalari
notifications           Push/SMS/Telegram bildirishnomalar
integrations            Tashqi API kalitlari va webhook-lar
audit_logs              Barcha o'zgarishlar tarixi
brain_animal_features   Kunlik feature vektorlar
brain_decisions         Brain qarorlari log
brain_predictions       Bashorat log (monitoring uchun)
```

---

# AUTENTIFIKATSIYA VA XAVFSIZLIK

## Rol Tizimi

```
ADMIN      To'liq nazorat: sozlamalar, foydalanuvchilar, barcha ma'lumotlar
MANAGER    Operatsion boshqaruv: jonivorlar, hodimlar, moliya, vazifalar
VIEWER     Faqat ko'rish: monitoring, hisobotlar, statistika
```

## Xavfsizlik

```
PyJWT              Access / Refresh token tizimi
bcrypt             Parol hashlash (salted)
Audit log          Kim, nima, qachon — barchasi yoziladi
Rate limiting      API so'rovlar cheklovi (production)
On-premise         Ma'lumotlar faqat ferma serverida, tashqariga chiqmaydi
```

---

# API ENDPOINTLAR

```
/api/v1/auth/           Login, logout, token yangilash
/api/v1/animals/        Jonivorlar CRUD, qidiruv, filter
/api/v1/detections/     YOLO deteksiyalar, statistika
/api/v1/health/         Sog'liq yozuvlari
/api/v1/adi/            ADI log va trend tahlili
/api/v1/sensors/        Sensor o'lchovlari va konfiguratsiya
/api/v1/feed/           Oziqlantiruv, zaxira boshqaruvi
/api/v1/breeding/       Nasl, ko'paytirish, homiladorlik
/api/v1/milk/           Sut mahsuldorligi
/api/v1/meat/           Go'sht yozuvlari
/api/v1/medicine/       Dori inventari va sarflash
/api/v1/employees/      Hodimlar va ish grafigi
/api/v1/tasks/          Vazifalar: yaratish, holat, statistika
/api/v1/finance/        Tranzaksiyalar, hisobot, forecast
/api/v1/cameras/        Kamera konfiguratsiya va holati
/api/v1/scales/         Tarozi qurilmalari
/api/v1/alerts/         Ogohlantirishlar va sozlamalar
/api/v1/analytics/      Tahlil va statistika
/api/v1/predictions/    AI bashoratlar
/api/v1/reports/        Hisobotlar generatsiya
/api/v1/export/         Ma'lumotlarni export (PDF/CSV/Excel)
/api/v1/farms/          Ferma boshqaruvi
/api/v1/users/          Foydalanuvchilar va rollar
/api/v1/notifications/  Bildirishnomalar va sozlamalar
/api/v1/integrations/   Tashqi API kalitlari, webhook
/api/v1/behavior/       Xulq-atvor tahlili
/api/v1/live/           Real-time stream
/api/v1/pipeline/       AI pipeline boshqaruvi
/api/v1/training/       Model o'qitish jarayoni
/api/v1/registration/   Jonivor ro'yxatga olish
/api/v1/brain/          Taurus Brain API
```

## Taurus Brain API

```
GET   /api/v1/brain/pulse/{farm_id}          Ferma bir lahzadagi to'liq holati
GET   /api/v1/brain/animals/{id}/score       Risk bahosi + sabablar
GET   /api/v1/brain/animals/{id}/features    Kunlik feature vektor
GET   /api/v1/brain/animals/{id}/baseline    Individual norm va anomaliya tarixi
GET   /api/v1/brain/decisions/pending        Kutayotgan qarorlar
POST  /api/v1/brain/decisions/{id}/approve   Qarorni tasdiqlash
POST  /api/v1/brain/decisions/{id}/reject    Qarorni rad etish (sabab bilan)
GET   /api/v1/brain/financial/forecast       Moliya bashorati
GET   /api/v1/brain/herd/clusters            Poda klaster tahlili
GET   /api/v1/brain/feed/optimization        Ozuqa optimallashtirish
POST  /api/v1/brain/ask                      Natural language so'rov
GET   /api/v1/brain/metrics                  Pipeline ishlash ko'rsatkichlari
```

---

# FRONTEND SAHIFALAR

```
/login                  Kirish
/dashboard              Asosiy boshqaruv paneli
/animals                Jonivorlar ro'yxati + qidiruv + filter
/animals/:id            Jonivor batafsil profili
/live                   Jonli kamera feed
/adi                    ADI monitoring + trend grafiklar
/health                 Sog'liq va veterinariya
/predictions            AI bashoratlar
/breeding               Nasl va ko'paytirish
/sensors                Sensorlar real-time
/feed                   Ozuqa boshqaruvi va zaxira
/milk                   Sut mahsuldorligi
/meat                   Go'sht ishlab chiqarish
/medicine               Dori-darmon inventari
/scales                 Tarozi qurilmalari
/behavior               Xulq-atvor tahlili
/employees              Hodimlar + jadval + samaradorlik
/tasks                  Vazifalar: barchasi / mening / muddati o'tgan
/finance                Moliya: tranzaksiyalar, grafik, forecast
/analytics              Tahlil va KPI dashboard
/cameras                Kameralar holati va konfiguratsiya
/reports                Hisobotlar generatsiya
/alerts                 Ogohlantirishlar + sozlamalar
/notifications          Bildirishnomalar markazi
/farms                  Fermalar boshqaruvi
/users                  Foydalanuvchilar va rollar
/integrations           Tashqi integratsiyalar
/training               AI model o'qitish paneli
/audit                  Audit log
/brain                  Taurus Brain bosh paneli
/brain/animals/:id      Jonivor AI profili + anomaliya trend + risk
```

---

# CELERY TASK MODULLARI

```
adi_tasks           Kunlik ADI hisoblash (00:30 da, barcha jonivorlar)
alert_tasks         Ogohlantirishlar tekshiruvi va yuborish
brain_tasks         Brain modellari sikli (har 5 daqiqa)
feature_tasks       Feature vektor hisoblash (har 15 daqiqa)
detection_tasks     Video qayta ishlash va YOLO pipeline
weight_tasks        Vazn ma'lumotlari normalizatsiya
notification_tasks  Push, SMS, Telegram xabar yuborish
export_tasks        PDF, CSV, Excel hisobot generatsiya
backup_tasks        PostgreSQL backup (jadval bo'yicha)
health_tasks        Sog'liq yozuvlari monitoring
training_tasks      Model o'qitish triggerlari
```

---

# ISHGA TUSHIRISH

## Talab

```
Docker Desktop (yoki Docker Engine + Compose)
Git
```

## Lokal Muhit

```bash
git clone <repo_url>
cd taurus_vision

cp backend/.env.example backend/.env
# backend/.env ni tahrirlang

make gen-secret
make up-build
make migrate
```

## Manzillar (lokal)

```
http://localhost:5173          Frontend
http://localhost:8000/docs     API hujjatlari (Swagger)
http://localhost:8000/health   Backend holati
http://localhost:5555          Celery Flower
```

## Server Muhiti

```bash
make up-server-build
```

## Buyruqlar

```bash
make up-build          Qayta qurish va ishga tushirish
make down              To'xtatish
make logs              Barcha servislar loglari
make migrate           Yangi migratsiyalar
make test              Testlar
make gen-secret        Yangi SECRET_KEY
make shell-backend     Backend konteyneriga kirish
make shell-db          DB konteyneriga kirish
```

---

# MUHIT O'ZGARUVCHILARI

```env
DATABASE_URL=postgresql+asyncpg://taurus:taurus123@postgres:5432/taurus_vision
REDIS_URL=redis://redis:6379/0

SECRET_KEY=<make gen-secret>
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

YOLO_MODEL=yolo26n.pt
MUZZLE_STRICT_MODE=false

TELEGRAM_BOT_TOKEN=<botfather>
TELEGRAM_CHAT_ID=<admin chat ID>

SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=<email>
SMTP_PASSWORD=<app password>

BRAIN_ENABLED=true
BRAIN_ANOMALY_THRESHOLD_WARN=0.70
BRAIN_ANOMALY_THRESHOLD_CRITICAL=0.85
BRAIN_DISEASE_RISK_THRESHOLD=0.60
BRAIN_MIN_HISTORY_DAYS=14
BRAIN_BASELINE_TRAINING_DAYS=30
BRAIN_DECISION_CYCLE_MINUTES=5
BRAIN_FEATURE_COMPUTE_MINUTES=15
BRAIN_MODEL_PATH=./brain/models
BRAIN_PARQUET_PATH=./brain/data/parquet

MLFLOW_TRACKING_URI=http://mlflow:5000
```

---

# KODLASH STANDARTLARI

```python
logger = get_logger(__name__)

async def get_animal(animal_id: int, db: AsyncSession) -> Animal:
    """
    Jonivorni ID bo'yicha olish.

    Args:
        animal_id: Jonivor identifikatori
        db: Async database session

    Returns:
        Animal obyekti

    Raises:
        EntityNotFoundError: Jonivor topilmasa
    """
    try:
        result = await db.execute(
            select(Animal).where(Animal.id == animal_id)
        )
        animal = result.scalar_one_or_none()
        if animal is None:
            raise EntityNotFoundError(f"animal_id={animal_id}")
        return animal
    except EntityNotFoundError:
        raise
    except Exception as e:
        logger.error(f"get_animal xatosi: animal_id={animal_id}, error={e}")
        raise DatabaseError(str(e))
```

| Qoida | |
|-------|---|
| `async def` | Barcha funksiyalar async |
| Type hints | Har argument va qaytish tipi |
| Docstring | Har public metod |
| Logger | `get_logger(__name__)` orqali |
| try/except | Har DB operatsiyada |
| **HECH QACHON** | `print()`, sync DB, hardcode secret |

---

# GITGA YUKLANMAGAN FAYLLAR

```
backend/.env                         Maxfiy konfiguratsiya
backend/ml/models/yolo26n.pt         Auto-download (Ultralytics 8.4+)
backend/ml/models/best.pt            Custom muzzle detector
backend/ml/models/prediction/        RF + IsolationForest modellari
brain/models/                        O'qitilgan Brain modellari
brain/data/parquet/                  Training ma'lumotlari
```

---

# MUVAFFAQIYAT MEZONLARI

```
6 oy:
    Kasallik 48 soat oldin aniqlash    70%+ accuracy
    Yolg'on alarm                       15% dan kam
    Hodim vazifalari                    90%+ o'z vaqtida
    Ferma egasi: "bu foydali"

12 oy:
    Kasallik bashorati                  85%+ accuracy
    Veterinar xarajati                  20%+ kamaydi
    Brain qarorlari ishonchliligi       80%+
    Ferma egasi: "bu bo'lmasam bo'lmaydi"

2 yil:
    Ko'p ferma                          Federated Learning ishlaydi
    O'zbekistondagi eng yaxshi          Chorvachilik AI tizimi
    O'rta Osiyo standarti               Taurus Brain
```

---

# LITSENZIYA

Loyiha yopiq manba (proprietary). GitHub da private holatda saqlanadi.
Barcha huquqlar himoyalangan.

---

```
Chorvachilik — dunyoning eng qadimiy kasbi.
Ammo u hali raqamli inqilobni kutmoqda.

Taurus Vision ko'radi.
Taurus Brain tushunadi.
Tizim harakat qiladi.
```

---

*Taurus Vision & Taurus Brain | O'zbekiston va O'rta Osiyo uchun | 2026*
