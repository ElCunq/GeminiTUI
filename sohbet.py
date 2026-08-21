import asyncio
from gemini_webapi import GeminiClient

async def main():
    print("Çerezler tarayıcıdan aranıyor ve Gemini'a bağlanılıyor...\n")
    
    try:
        # Client otomatik olarak tarayıcıdan (Chrome/Firefox/Edge vb.) çerezleri çeker
        client = GeminiClient()
        await client.init(timeout=30, auto_close=False, auto_refresh=True)
        
        # Yeni bir sohbet başlat (senkronize olduğu için web'de de görünecek)
        chat = client.start_chat()
        print("Bağlantı Başarılı! (Çıkmak için 'q', 'quit' veya 'exit' yazabilirsin)\n" + "-"*50)
        
        while True:
            user_input = input("\nSen: ")
            
            if user_input.lower() in ['q', 'quit', 'exit']:
                print("Görüşmek üzere!")
                break
                
            if not user_input.strip():
                continue
                
            print("Gemini yazıyor...")
            response = await chat.send_message(user_input)
            
            print(f"\nGemini: {response.text}")
            
    except Exception as e:
        print(f"\nBir hata oluştu: {e}")
        print("Lütfen tarayıcında gemini.google.com'a giriş yapmış olduğundan emin ol.")

if __name__ == "__main__":
    asyncio.run(main())
