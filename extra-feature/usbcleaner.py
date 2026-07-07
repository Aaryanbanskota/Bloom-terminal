import tkinter as tk
from tkinter import messagebox, ttk
import subprocess, os, json, threading

TARGET_LABEL = "MYUSB"

# -------------------------------
# GET USB (ONLY MYUSB)
# -------------------------------
def get_usb():
    try:
        result = subprocess.check_output(
            "lsblk -o NAME,SIZE,MODEL,LABEL,MOUNTPOINT,TRAN,RM -J",
            shell=True
        ).decode()

        data = json.loads(result)

        for dev in data["blockdevices"]:
            if (dev.get("label") == TARGET_LABEL and
                (dev.get("tran") == "usb" or dev.get("rm") == True)):

                return {
                    "path": f"/dev/{dev['name']}",
                    "size": dev.get("size", ""),
                    "model": dev.get("model", "Unknown"),
                    "label": dev.get("label"),
                    "mount": dev.get("mountpoint")
                }

    except Exception as e:
        print(e)

    return None

# -------------------------------
# SHOW FILES
# -------------------------------
def show_files(drive):
    file_list.delete(0, tk.END)

    if not drive:
        file_list.insert(tk.END, "❌ MYUSB not found")
        return

    if not drive["mount"]:
        file_list.insert(tk.END, "⚠️ Not mounted")
        return

    try:
        files = os.listdir(drive["mount"])
        if not files:
            file_list.insert(tk.END, "(Empty)")
        else:
            for f in files:
                file_list.insert(tk.END, f)
    except:
        file_list.insert(tk.END, "❌ Cannot read files")

# -------------------------------
# WIPE
# -------------------------------
def start_wipe():
    global drive
    if not drive:
        messagebox.showerror("Error", "MYUSB not found")
        return

    if not messagebox.askyesno("Warning", f"Wipe {drive['path']}?"):
        return

    confirm = tk.simpledialog.askstring("Confirm", "Type WIPE:")
    if confirm != "WIPE":
        return

    threading.Thread(target=wipe_drive, daemon=True).start()

# -------------------------------
# WIPE PROCESS
# -------------------------------
def wipe_drive():
    global drive
    progress["value"] = 0

    try:
        size_bytes = int(subprocess.check_output(
            f"blockdev --getsize64 {drive['path']}", shell=True
        ).decode())

        written = 0

        proc = subprocess.Popen(
            f"dd if=/dev/zero of={drive['path']} bs=4M status=none",
            shell=True
        )

        while proc.poll() is None:
            written += 4 * 1024 * 1024
            percent = min((written / size_bytes) * 100, 100)

            progress["value"] = percent
            status_var.set(f"Wiping MYUSB... {int(percent)}%")

            root.update()
            import time
            time.sleep(0.2)

        progress["value"] = 100
        status_var.set("✅ Done")

        messagebox.showinfo("Done", "MYUSB wiped!")

    except Exception as e:
        messagebox.showerror("Error", str(e))

# -------------------------------
# REFRESH
# -------------------------------
def refresh():
    global drive
    drive = get_usb()

    if drive:
        info_label.config(
            text=f"Found: {drive['label']} | {drive['model']} | {drive['size']}"
        )
    else:
        info_label.config(text="❌ MYUSB not found")

    show_files(drive)

# -------------------------------
# GUI
# -------------------------------
root = tk.Tk()
root.title("MYUSB Wiper")
root.geometry("700x450")
root.configure(bg="#121212")

tk.Label(root, text="MYUSB Wiper Tool", font=("Arial", 18, "bold"),
         fg="white", bg="#121212").pack(pady=10)

info_label = tk.Label(root, text="", fg="cyan", bg="#121212")
info_label.pack()

file_list = tk.Listbox(root, width=80, height=15)
file_list.pack(pady=10)

btn_frame = tk.Frame(root, bg="#121212")
btn_frame.pack()

tk.Button(btn_frame, text="Refresh", command=refresh).grid(row=0, column=0, padx=10)
tk.Button(btn_frame, text="WIPE MYUSB", bg="red", fg="white",
          command=start_wipe).grid(row=0, column=1, padx=10)

progress = ttk.Progressbar(root, length=600)
progress.pack(pady=10)

status_var = tk.StringVar()
tk.Label(root, textvariable=status_var, fg="cyan", bg="#121212").pack()

# INIT
drive = None
refresh()

root.mainloop()