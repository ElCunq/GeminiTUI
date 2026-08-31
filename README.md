# ⚡ GeminiTUI

🌐 **[Türkçe](README.md)** │ **[English](README_EN.md)**

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Textual](https://img.shields.io/badge/TUI-Textual-green.svg)](https://textual.textualize.io/)
[![Google Gemini](https://img.shields.io/badge/AI-Google%20Gemini%203.7%20Flash-orange.svg)](https://gemini.google.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**GeminiTUI**, Google Gemini web chatbot arayüzünün birebir mantığını terminal estetiğiyle buluşturan; **şeffaf (naked/transparent) terminal temalı**, aşırı hafif ve akıcı bir **Google Gemini Terminal İstemcisidir**.

Gereksiz karmaşıklıktan arındırılmış saf chatbot arayüzüdür.

---

## ✨ Öne Çıkan Özellikler

- 💎 **Aşırı Şeffaf Terminal Tasarımı (Naked UI):** Çerçeve kirliliği ve renk karmaşası yok! Terminalinizin arka plan şeffaflığıyla %100 uyumlu minimal görünüm.
- ⚡ **0ms Cold-Start & Yerel Önbellekleme:** Sohbet listeniz ve istemci verileriniz açılışta yerel cache'ten anında yüklenir.
- 🤖 **Varsayılan Gemini 3.7 Flash:** Otomatik olarak varsayılan **3.7 Flash** modeline bağlanır (3.1 Pro ve 3.5 Flash-Lite tek tuşla değiştirilebilir).
- 🖼️ **Imagen 3 Görsel Üretimi (2 Yönlü Görünüm):**
  - **Sohbet İçi Görünüm:** Üretilen görseller sohbet akışında 2x HD ANSI RGB (Half-Block `▀`) grafik olarak anında çizdirilir.
  - **Tam Çözünürlük:** `Alt+V` veya `/view` yazarak ürettirdiğiniz görseli orijinal %100 FullHD kalitesinde pencerede (`mpv`) inceleyebilirsiniz.
- 🔗 **Web Araştırma & Kaynak Tespiti (Grounding Citations):** Gemini'ın web aramalarında kullandığı kaynak siteler cevabın altına tıklanabilir alıntılar olarak eklenir.
- 📋 **Akıllı Pano Kopyalama:** `Alt+C` veya `/copy` ile yanıtın tamamını panoya kopyalayabilirsiniz.
- 🔑 **Kolay Oturum Yönetimi:** `/login <1PSID> <1PSIDTS>` komutu ile TUI içerisinden anında oturum açabilirsiniz.
- 📎 **Multimodal Dosya/Görsel Yükleme:** `F3` / `Alt+F` veya `/file /yol/resim.png` ile görsellerinizi ve kod dosyalarınızı Gemini'a yükleyebilirsiniz.

---

## 🚀 Kurulum

### Gereksinimler
- Linux (Arch, Fedora, Ubuntu, Debian vb.)
- Python 3.10 veya üzeri
- `wl-clipboard` (Wayland için) veya `xclip` (X11 için)
- `mpv` *(Görselleri tam çözünürlükte açmak için)*

### Hızlı Kurulum
```bash
# Repoyu klonlayın
git clone https://github.com/ElCunq/GeminiTUI.git
cd GeminiTUI

# Çalıştırma izni verin ve başlatın (Sanal ortam otomatik kurulur)
chmod +x run.sh
./run.sh
```

---

## 🔑 Oturum Açma (Çerez Tanımlama)

Google hesabınızdaki sohbet geçmişinize erişmek ve kısıtlamasız model kullanmak için `GEMINI_1PSID` ve `GEMINI_1PSIDTS` çerezlerinizi tanımlayabilirsiniz:

### Yöntem A (TUI İçerisinden):
Sohbet kutusuna yazın:
```text
/login <GEMINI_1PSID_DEGERINIZ> <GEMINI_1PSIDTS_DEGERINIZ>
```

### Yöntem B (Ortam Değişkeni):
```bash
export GEMINI_1PSID="senin_1psid_cookie_degerin"
export GEMINI_1PSIDTS="senin_1psidts_cookie_degerin"

./run.sh
```

---

## ⌨️ Klavye Kısayolları

| Kısayol | Açıklama |
| :--- | :--- |
| **F1** / **Alt+N** | Yeni sohbet başlatır |
| **F2** / **Alt+M** | AI Modelleri arasında geçiş yapar (3.7 Flash, 3.1 Pro, 3.5 Flash-Lite) |
| **F3** / **Alt+F** | Sohbete görsel veya dosya ekler (`/file`) |
| **F4** / **Alt+D** | Aktif sohbeti hesabınızdan siler |
| **Alt+C** | En son yanıtın tamamını panoya kopyalar |
| **Alt+V** | Üretilen görseli mpv ile tam çözünürlüklü pencerede açar |
| **F7** / **Alt+H** | Komut yardım menüsünü açar |
| **Yukarı Ok (↑)** | Boş input alanında son gönderdiğiniz mesajı geri çağırır |

---

## 💬 Slash Komutları

| Komut | Açıklama |
| :--- | :--- |
| **`/login <1PSID> <1PSIDTS>`** | Çerez bilgilerinizi kaydedip hesaba bağlanır |
| **`/copy`** | Yanıtın tamamını kopyalar |
| **`/view`** | Son üretilen görseli mpv ile açar |
| **`/file <yol>`** | Görsel (PNG/JPG/WEBP), PDF veya kod dosyası ekler |
| **`/rename <başlık>`** | Sohbetin adını değiştirir |
| **`/pin`** | Sohbeti sol panele iğneler (📌) |
| **`/new`** | Yeni sohbet açar |
| **`/model`** | Model değiştirir |
| **`/clear`** | Eklenmiş dosyaları temizler |
| **`/exit`** | Uygulamadan çıkar |

---

## 🙏 Teşekkürler ve Atıflar (Credits & Acknowledgements)

Bu projenin çekirdeğinde Google Gemini Web API iletişimini sağlayan harika Python kütüphanesi **[`Gemini-API`](https://github.com/HanaokaYuzu/Gemini-API)** motoru kullanılmaktadır.

Çekirdek kütüphaneyi geliştiren **[HanaokaYuzu](https://github.com/HanaokaYuzu)** arkadaşımıza ve `Gemini-API` projesine katkıda bulunan tüm açık kaynak geliştiricilerine yürekten teşekkür ederiz!

Ayrıca zengin TUI ve terminal arayüz bileşenleri için **[Textualize (Textual & Rich)](https://github.com/Textualize/textual)** ekibine teşekkürler.

---

## 📄 Lisans

Bu proje [MIT Lisansı](LICENSE) altında lisanslanmıştır.
