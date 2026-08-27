# AI-Driven Development (ADD) — Sunum Planı

> Hedef kitle: **teknik** (yazılımcılar, mimarlar). Amaç: ADD'nin düz bir cümleyi
> **incelenmiş, testli bir pull request'e** dönüştürdüğünü; bunu şeffaf, insan
> onaylı bir hattı üzerinden yaptığını; ve altındaki mühendisliğin gerçek
> olduğunu — bir sohbet promptunun etrafına sarılmış bir kabuk olmadığını —
> göstermek.
>
> Teknik kitle için altın kural: **anlatma, göster.** Önce demoyu yap, onları
> etkiledikten sonra kaputu aç. Zekâlarına saygı duy — kısıtları onlar
> söylemeden sen söyle.

---

## 0. Tek cümle (bunu ilk söyle)

> "ADD, tek cümlelik bir niyeti alıp bir spec, kod ve testler üretir — her biri
> bir kapıda insan tarafından onaylanır — ve pull request'leri sizin için açar.
> Bu bir otomatik tamamlama değil. Bu; hafızası, doğrulaması ve GitOps
> dağıtımı olan **spec-odaklı, çok-ajanlı bir hattır.** İzin verin göstereyim,
> sonra kaputu açarım."

---

## 1. Akış planı (~25 dk + Soru-Cevap)

| # | Bölüm | Süre | Amaç |
|---|---|---|---|
| 1 | Kanca + tek cümle | 2 dk | Çerçeveyi kur; "bir Copilot daha mı?" refleksini kır |
| 2 | **Canlı demo** | 10 dk | Etki anı — tek cümle → birleştirmeye hazır PR'lar |
| 3 | Mimari derinlik | 7 dk | Mühendislerin saygısını kazan |
| 4 | Farklılaştırıcılar | 3 dk | Neden Copilot/Cursor/otonom ajan değil |
| 5 | Dağıtım & operasyon | 3 dk | Gerçek altyapı, laptop demosu değil |
| 6 | Soru-Cevap | açık | §7'deki cephaneyi kullan |

Mimariyi demodan **sonra** anlat. Süre yetmezse §3'ten önce §4'ü kes.

---

## 2. Kanca (2 dk)

Bir açılış seç:

- **Karşıtlık:** "Copilot bir satırı tamamlar. Otonom bir ajan bir dalı gözü
  kapalı yazar ve umut eder. ADD ikisini de yapmaz — **iyi bir ekibin** çalıştığı
  gibi çalışır: bir spec, bir inceleme, testler, ikinci bir inceleme, sonra
  birleştirme. Fark sadece üretim değil, **yönetişimdir.**"
- **Acı noktası:** "Yazılımdaki darboğaz kod yazmak değil — hizalanma, inceleme
  ve spec ile kodu senkron tutmaktır. ADD, kodun *etrafındaki* hattı otomatize
  eder, karar noktalarında insanlarla."

Sonra tek cümle (§0) ve doğrudan demoya.

---

## 3. Canlı demo senaryosu (10 dk)

**İçeri girmeden önce hazırlık:**
- Uygulama **giriş (login) sayfasında** açık (cilalı görünür, tonu belirler).
- İkinci sekmede hedef GitHub deposu (`xspec-demo-app`) Pull Requests sayfası.
- Üçüncü sekmede **Swagger** (`/api/v1/docs`) — sonda göstereceksin.
- Sağlayıcı = **Vertex/Gemini** (ücretsiz modellerden daha kaliteli).

**Kullanılacak prompt (public uç nokta → temiz, test edilebilir):**
> **Let users check if a username is already taken.**
> *(TR sunumda İngilizce girebilirsin; sistem İngilizce spec üretir.)*

### Adım adım

1. **Giriş** — "Önce giriş yapalım." *Use demo credentials* → Sign in.
   *(Tek cümle: "demo için kozmetik bir kapı — gerçek SSO yeniden yazım değil,
   bir konfigürasyon.")* Fazla abartma.

2. **Cümleyi yaz.** "Tüm girdi bu. Tek cümle." Gönder.

3. **Spec Discovery** — ekranda olanları anlat:
   - "Niyeti çözümler, sonra tüm önceki spec'lerin bir **vektör veritabanında
     (Qdrant)** aramasını yapar — hem *içerik* hem *özet* üzerinden — ilgili
     işleri bulmak ve **kopyaları tespit etmek** için. Bu, sistemin hafızasıdır.
     Zaten spec'lediğiniz bir şeyi yeniden icat etmez."

4. **Spec Generation → Validation** — "Yapılandırılmış bir spec yazar, sonra
   **deterministik doğrulayıcılar** çalıştırır — XML geçerliliği, zorunlu
   bölümler, çapraz referanslar. 'LLM iyi diyor' değil — gerçek kontroller."

5. **Onay Kapısı #1 (spec).** ⏸ "İşte ilk insan kapısı. AI önerir; bir insan
   karar verir. Onay olmadan hiçbir şey ilerlemez." — Onayla.
   - GitHub sekmesine geç: **bir spec PR'ı açıldı.** "Spec artık git'te
     versiyonlanmış durumda. Kaynak gerçek, spec'tir — geçici bir prompt değil."

6. **Namespace Resolver → Code Developer** — asıl kısım:
   - "Hedef depoyu tarar, **etki analizi** yapar (hangi dosyalar değişecek),
     sonra bir alt-ajan hattı: **görev planla → kod yaz → test yaz → entegrasyon
     kontrolü → lint → testleri çalıştır → onar.**"
   - **Koruma kontrolünü (preservation check)** vurgula: "Mevcut route veya
     fonksiyonları *silecek* düzenlemeleri reddeden deterministik bir koruma. Bir
     LLM'in dosyanızı 'yardımsever' bir şekilde baştan yazıp bir şeyleri
     düşürmesini böyle engelliyoruz."

7. **Onay Kapısı #2 (kod).** ⏸ "İkinci kapı. Testler çalıştı. Başarısız olursa
   PR **taslak (draft)** olarak açılır — sistem doğrulanmamış kodu bitmiş gibi
   sunmayı reddeder. Bu bir özelliktir." — Onayla.
   - GitHub sekmesi: yeni uç nokta + testlerle **kod PR'ı.**

8. **Maliyet + süre.** Başlık çiplerini göster: "Her aşama kendi süresini ve LLM
   maliyetini takip eder. AI'ın ne harcadığında tam şeffaflık."

9. **Swagger sekmesi.** "Ve yeni uç nokta API dokümanlarında canlı." İsteğe
   bağlı: *Try it out.*

**Demoyu kapat:** "Tek cümle girdi. Versiyonlanmış bir spec, çalışan kod,
testler ve iki pull request çıktı — her adım incelenebilir, her karar bir insan
tarafından kapılandı."

---

## 4. Mimari derinlik (7 dk) — mühendisler için

Bunu çiz veya göster. Vızıltı kelimeler değil, **mekanizma.**

**Hat — bir LangGraph durum makinesi, 10 aşama:**

```
spec_discovery → spec_generator → spec_validator → [SPEC KAPISI 👤]
   → spec_publisher → namespace_resolver → code_developer
   → code_publisher → [KOD KAPISI 👤] → code_review_handoff → merge
```

Bunu gerçek kılan beş şey (bunlarla başla):

1. **Kalıcı, devam ettirilebilir durum.** Her aşama Postgres'e yazılır
   (`state_snapshot`, `token_usage` JSON olarak). Onaylar dakikalar veya saatler
   sonra gelebilir; graph, DB anlık görüntüsünden devam eder. Yeniden başlatmaya
   dayanıklı.

2. **Vektör hafıza (Qdrant), çift-vektör.** Spec'ler iki kez gömülür — tam
   içerik ve LLM üretimi bir özet — böylece discovery, ilgili spec'leri getirir
   ve kopyaları anahtar kelimeyle değil, anlamla işaretler.

3. **İnsan-döngüde kapılar.** İki sert durak (spec, kod). Ürünün tezi bu:
   **AI-yapımı, insan-onaylı.** Otonom birleştirme değil.

4. **Önemli yerde determinizm.** Doğrulama, koruma kontrolü (yıkıcı düzenleme
   yok), sözdizimi kontrolleri ve **testleri gerçekten çalıştırmak** deterministik
   — LLM çıktısına *güvenilmez*, o *kontrol edilir.*

5. **LiteLLM ile sağlayıcı-bağımsız.** Her model çağrısı tek bir soyutlamadan
   geçer. **Her ajanı farklı bir modele** bir YAML dosyasıyla yönlendiririz —
   NLP aşamaları için ucuz/hızlı modeller, kod için güçlü bir model. Gemini →
   Claude → yerel bir model geçişi **sıfır kod değişikliğiyle.** Sağlayıcı
   kilidi yok.

**Yığın (tek slayt):** Django 5 + DRF, Channels/Daphne (canlı ilerleme için
WebSocket), Redis (kanal katmanı), PostgreSQL (durum), Qdrant (vektörler),
LangGraph (orkestrasyon), LiteLLM (modeller), React + Vite + MUI (arayüz).

---

## 5. Farklılaştırıcılar (3 dk) — "neden X değil?"

| Araç | Ne yapar | ADD ne ekler |
|---|---|---|
| **Copilot / Cursor** | Editör içi otomatik tamamlama | Bir *hat*: spec, inceleme kapıları, testler, PR'lar, hafıza |
| **Otonom ajanlar** (Devin tarzı) | Serbest koşar, umut eder | **Yönetişim** — insanlar her geri dönülemez adımı kapılar |
| **Ham ChatGPT** | Tek seferlik üretim | Kalıcı durum, doğrulama, vektör hafıza, GitOps |

Asansör versiyonu: **"Onlar kod üretir. Biz yönetilen bir yazılım teslim hattı
üretiriz."**

---

## 6. Dağıtım & operasyon (3 dk) — gerçek altyapı

- **GKE Autopilot**, **Terraform** ile Kod-olarak-Altyapı (uzak durum GCS'te).
- **Her yerde anahtarsız:** GitHub Actions, GCP'ye **Workload Identity
  Federation** ile kimlik doğrular (JSON anahtar yok); pod'lar **Vertex AI'a**
  **Workload Identity** ile ulaşır (kümede API anahtarı yok).
- **Üç GitHub Actions**, temiz ayrım: altyapı (oluştur/güncelle), uygulama
  dağıtımı (imaj derle → dağıt) ve korumalı bir yıkım (maliyet kontrolü).
- "Yalnızca CI dağıtır — kimse laptop'tan push yapmaz. Tekrarlanabilir ve
  denetlenebilir."

---

## 7. Soru-Cevap cephaneliği (zor soruları öngör)

**"Halüsinasyon / bozuk kodu nasıl engelliyorsunuz?"**
Üç katman: deterministik doğrulayıcılar, yıkıcı düzenlemeleri bloklayan bir
koruma kontrolü ve üretilen testleri **gerçekten çalıştırmak.** Başarısız
olurlarsa PR **taslaktır** — asla bitmiş gibi sunulmaz. Ve kapıda bir insan
inceler.

**"Copilot'tan farkı ne?"**
Copilot editörün *içinde* üretir. ADD kodun *etrafındaki* hattı yönetir — spec,
inceleme, testler, PR'lar ve önceki spec'lerin hafızası. Problemin farklı
katmanı.

**"Maliyet / token harcaması?"**
Aşama başına takip edilir ve arayüzde canlı gösterilir. Model-yönlendirme
katmanı sayesinde kolay aşamalara ucuz, işe yaradığı yere güçlü model
koyarsınız. Ajan başına maliyet/kalite dengesini siz kontrol edersiniz.

**"Sağlayıcı kilidi? Ya Google istemezsek?"**
LiteLLM soyutlaması. Bugün Gemini, yarın Claude veya kendi barındırdığınız bir
model — bir YAML satırı, kod değişikliği yok. Ollama (yerel), Groq, OpenRouter
ve Vertex üzerinde çalıştırdık.

**"Ölçeklenir mi / gerçek bir monorepo?"**
Bugün bir demo deposunda POC. Mimari bunun için kurulu: kalıcı durum,
değişiklikleri kapsamak için etki analizi, namespace başına depo yönlendirme.
Nerede olduğu konusunda dürüst: *hat* üretim-şeklinde; *kapsam* erken.

**"Veri gizliliği — kodumuz nereye gidiyor?"**
GCP üzerinde Vertex ile çağrılar sizin projenizde/bölgenizde, sizin IAM'iniz
altında kalır. Kümeden anahtar çıkmaz (Workload Identity). Model seçimi sizin.

**"Hangi modeli kullanıyor?"**
Tek model değil — her aşama bağımsız yönlendirilir. Bu demo için: Vertex
üzerinden Gemini (NLP için 2.5-flash, kod için 2.5-pro).

**"Mevcut kodu sadece eklemek değil, güvenle değiştirebilir mi?"**
Evet — etki analizi dosyaları seçer, koruma kontrolü mevcut route/tanımları
kaldıracak düzenlemeleri reddeder. Bu koruma deterministiktir.

---

## 8. Demo bozulursa (bunu hazır tut, sakin kal)

- **Bir aşama canlı hata verirse:** "Kapıların neden var olduğuna harika bir
  örnek — daha önce kaydettiğim aynı çalıştırmayı göstereyim." → hazır bir
  **kayıt veya ekran görüntüsü** bulundur. Zarif toparlanmak *yönetişim
  hikâyesini satar.*
- **Canlı çalıştırmada testler başarısızsa:** üzerine git — "ve dikkat edin, PR'ı
  *taslak* olarak açtı çünkü testler geçmedi. Sistem sizi koruyor." Bu bir hata
  değil, özellik.
- **Kod aşaması yavaşsa:** çalışırken mimariyi (§4) anlat; bekleme senin derinlik
  slotun olur.
- **Model NOT_FOUND / 403:** sağlayıcı değişimi bir konfig çevirmesidir — ama bu
  gece test et ki canlıda asla olmasın.

**Uçuş öncesi kontrol listesi (bu gece yap):**
- [ ] Vertex üzerinde, tam demo promptuyla bir tam prova — HER İKİ kapıya ulaşsın.
- [ ] Spec PR + kod PR gerçekten GitHub'da görünsün.
- [ ] Giriş sayfası açılsın; demo kimlik bilgileri çalışsın.
- [ ] Swagger açılsın; admin açılsın.
- [ ] İyi bir çalıştırmanın ekran görüntüleri/kaydı yedek olarak saklansın.
- [ ] Küme gece boyunca AÇIK bırakılsın (toplantıdan önce yıkma).

---

## 9. Kapanış (30 sn)

> "Vaat 'AI kod yazar' değil — bu herkeste var. Vaat: **'AI teslim hattınızı
> yürütür ve bir insan önemli olan her kararı onaylar.'** Spec-odaklı, testli,
> kapılı, gerçek IaC ile dağıtılmış. Bir demo ile kod tabanınıza yaklaştıracağınız
> bir sistem arasındaki fark budur."

Sonra çağrı: gerçek bir depoda pilot / sonraki adım görüşmesi.
