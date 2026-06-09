import os
import requests
from dotenv import load_dotenv

load_dotenv()

class WhatsAppDelivery:
    def __init__(self):
        self.api_url = os.getenv("WHATSAPP_API_URL", "http://waha:3000")
        self.target_number = os.getenv("WHATSAPP_TARGET_NUMBER")

    def send_message(self, text):
        if not self.target_number:
            print("Error: WHATSAPP_TARGET_NUMBER is not set.")
            return False

        payload = {
            "chatId": self.target_number,
            "text": text,
            "session": "default"
        }
        
        try:
            # WAHA endpoint for sending text
            response = requests.post(f"{self.api_url}/api/sendText", json=payload)
            if response.status_code in [200, 201]:
                print("WhatsApp message sent successfully!")
                return True
            else:
                print(f"Failed to send WhatsApp message: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"Connection error to WAHA: {e}")
            return False
