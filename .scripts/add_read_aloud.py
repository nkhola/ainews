import os
import glob

def add_read_aloud_to_files():
    html_files = glob.glob('/Users/nitinkhola/github_website/ainews/*.html')
    
    button_html = """
        <button id="readAloudBtn" style="background: rgba(59, 130, 246, 0.15); color: #60a5fa; border: 1px solid rgba(59, 130, 246, 0.3); padding: 10px 20px; border-radius: 8px; cursor: pointer; font-family: 'Outfit', sans-serif; font-weight: 600; font-size: 1rem; margin-bottom: 30px; transition: all 0.2s ease; display: flex; align-items: center; gap: 8px;">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon><path d="M15.54 8.46a5 5 0 0 1 0 7.07"></path><path d="M19.07 4.93a10 10 0 0 1 0 14.14"></path></svg>
            <span id="readAloudText">Read Briefing Aloud</span>
        </button>
"""

    script_html = """
    <script>
        const readAloudBtn = document.getElementById('readAloudBtn');
        const readAloudText = document.getElementById('readAloudText');
        let isReading = false;

        if (readAloudBtn) {
            readAloudBtn.addEventListener('click', function() {
                if (!('speechSynthesis' in window)) {
                    alert("Sorry, your browser doesn't support text-to-speech!");
                    return;
                }

                if (isReading) {
                    window.speechSynthesis.cancel();
                    isReading = false;
                    readAloudText.textContent = "Read Briefing Aloud";
                    return;
                }

                window.speechSynthesis.cancel();
                
                const sections = document.querySelectorAll('.section-card');
                let textToRead = "";
                sections.forEach(section => {
                    textToRead += section.innerText + ". ";
                });

                const utterance = new SpeechSynthesisUtterance(textToRead);
                const voices = window.speechSynthesis.getVoices();
                const preferredVoice = voices.find(v => v.lang.includes('en') && (v.name.includes('Samantha') || v.name.includes('Google')));
                if(preferredVoice) utterance.voice = preferredVoice;
                
                utterance.onend = function() {
                    isReading = false;
                    readAloudText.textContent = "Read Briefing Aloud";
                };

                window.speechSynthesis.speak(utterance);
                isReading = true;
                readAloudText.textContent = "Stop Reading";
            });
        }
    </script>
"""

    for file_path in html_files:
        if file_path.endswith('index.html'):
            continue
            
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        if 'id="readAloudBtn"' in content:
            continue
            
        # Insert button before the first section-card
        if '<div class="section-card" id="ai-news">' in content:
            content = content.replace('<div class="section-card" id="ai-news">', button_html + '\n        <div class="section-card" id="ai-news">')
            
        # Insert script before </body>
        if '</body>' in content:
            content = content.replace('</body>', script_html + '</body>')
            
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
            
    print("Finished updating existing files.")

if __name__ == "__main__":
    add_read_aloud_to_files()
