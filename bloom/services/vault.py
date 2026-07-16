import os
import subprocess
import secrets
import string
from Crypto.Cipher import AES
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Util.Padding import pad, unpad
import customtkinter as ctk
from tkinter import filedialog, messagebox

# Absolute path for Ubuntu
FFMPEG_PATH = '/usr/bin/ffmpeg'

class GhostVaultPro(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("GHOST VAULT PRO | Ubuntu Edition")
        self.geometry("700x750")
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # Header
        self.header = ctk.CTkLabel(self, text="GHOST VAULT PRO", font=("Orbitron", 28, "bold"), text_color="#0ea5e9")
        self.header.pack(pady=(30, 5))

        # Credentials Card
        self.card = ctk.CTkFrame(self, fg_color="#1e293b", border_width=2, border_color="#334155")
        self.card.pack(pady=10, padx=40, fill="both")

        ctk.CTkLabel(self.card, text="SECRET ACCESS KEY (PASSWORD)", font=("Inter", 11, "bold")).pack(pady=5)
        self.pass_entry = ctk.CTkEntry(self.card, width=450, height=40, font=("Consolas", 14), justify="center")
        self.pass_entry.pack(pady=5, padx=20)

        ctk.CTkLabel(self.card, text="FAKE SYSTEM FILENAME", font=("Inter", 11, "bold")).pack(pady=5)
        self.name_entry = ctk.CTkEntry(self.card, width=450, height=40, font=("Consolas", 14), justify="center", text_color="#38bdf8")
        self.name_entry.pack(pady=10, padx=20)

        # Buttons
        self.lock_btn = ctk.CTkButton(self, text="🔒 SCRUB & LOCK VIDEO", font=("Inter", 16, "bold"), 
                                      fg_color="#e11d48", hover_color="#9f1239", height=60, command=self.ultra_lock)
        self.lock_btn.pack(pady=15, padx=60, fill="x")

        self.unlock_btn = ctk.CTkButton(self, text="🔓 REVEAL & PLAY VIDEO", font=("Inter", 16, "bold"), 
                                        fg_color="#059669", hover_color="#065f46", height=60, command=self.ultra_unlock)
        self.unlock_btn.pack(pady=5, padx=60, fill="x")

        # Status
        self.progress = ctk.CTkProgressBar(self, width=500)
        self.progress.pack(pady=20)
        self.progress.set(0)

        self.status_label = ctk.CTkLabel(self, text="READY", font=("Consolas", 12), text_color="#0ea5e9")
        self.status_label.pack()

    def generate_secrets(self):
        pwd = ''.join(secrets.choice(string.ascii_letters + string.digits + "!@#$") for _ in range(20))
        fakes = ["sys_cache_0x9.db", "WinUpdate_log.bin", "driver_idx.sys", "temp_runtime.lib"]
        name = secrets.choice(fakes)
        self.pass_entry.delete(0, 'end')
        self.pass_entry.insert(0, pwd)
        self.name_entry.delete(0, 'end')
        self.name_entry.insert(0, name)
        return pwd, name

    def ultra_lock(self):
        target = filedialog.askopenfilename()
        if not target: return
        
        pwd, fake_name = self.generate_secrets()
        self.status_label.configure(text="SCRUBBING & COMPRESSING...", text_color="#f59e0b")
        self.progress.set(0.3)
        self.update()

        try:
            temp = "ghost_temp.mp4"
            # We use 'stderr=subprocess.DEVNULL' to hide the wall of text version info
            subprocess.run([FFMPEG_PATH, '-i', target, '-map_metadata', '-1', '-c:v', 'libx265', 
                            '-crf', '22', '-preset', 'faster', '-c:a', 'aac', temp, '-y'], 
                            check=True, stderr=subprocess.DEVNULL)

            # AES Encryption
            self.progress.set(0.7)
            self.status_label.configure(text="ENCRYPTING...", text_color="#0ea5e9")
            self.update()

            salt = b'ultra_god_salt'
            key = PBKDF2(pwd, salt, dkLen=32, count=100000)
            cipher = AES.new(key, AES.MODE_CBC)
            
            with open(temp, "rb") as f:
                data = f.read()

            with open(fake_name, "wb") as f:
                f.write(cipher.iv + cipher.encrypt(pad(data, AES.block_size)))

            os.remove(temp)
            self.progress.set(1.0)
            self.status_label.configure(text=f"LOCKED: {fake_name}", text_color="#10b981")
            messagebox.showinfo("Success", f"Hidden as {fake_name}\nWrite down password.")

        except Exception as e:
            self.status_label.configure(text="ERROR OCCURRED", text_color="#e11d48")
            messagebox.showerror("Error", "Compression failed. Check if the input file is a valid video.")

    def ultra_unlock(self):
        target = filedialog.askopenfilename()
        pwd = self.pass_entry.get()
        if not target or not pwd: return

        self.status_label.configure(text="RECONSTRUCTING...", text_color="#0ea5e9")
        self.update()

        try:
            with open(target, "rb") as f:
                iv = f.read(16)
                encrypted = f.read()

            salt = b'ultra_god_salt'
            key = PBKDF2(pwd, salt, dkLen=32, count=100000)
            cipher = AES.new(key, AES.MODE_CBC, iv=iv)
            
            decrypted = unpad(cipher.decrypt(encrypted), AES.block_size)
            output = "SECRET_REVEAL.mp4"
            
            with open(output, "wb") as f:
                f.write(decrypted)

            self.status_label.configure(text="OPENING...", text_color="#10b981")
            subprocess.run(['xdg-open', output]) # Standard Ubuntu open command
            
        except:
            messagebox.showerror("Denied", "Wrong password!")

if __name__ == "__main__":
    app = GhostVaultPro()
    app.mainloop()