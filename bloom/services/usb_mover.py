import os
import shutil
import time
import tkinter as tk
from tkinter import messagebox, ttk
import threading

class VideoMoverGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Aaryan's Video Porter")
        self.root.geometry("500x350")
        self.root.configure(bg="#f0f0f0")

        # Paths
        self.src = "/home/aaryan/Downloads/ihk"
        self.dst = "/media/aaryan/MYUSB/idk"

        # --- UI SETUP ---
        tk.Label(root, text="USB Video Transfer Tool", font=("Helvetica", 16, "bold"), bg="#f0f0f0").pack(pady=15)
        
        self.info_frame = tk.Frame(root, bg="#f0f0f0")
        self.info_frame.pack(pady=10)

        self.file_count_label = tk.Label(self.info_frame, text="Files Found: Scanning...", bg="#f0f0f0")
        self.file_count_label.pack()

        self.current_file_label = tk.Label(root, text="Waiting to start...", fg="#555", wraplength=400, bg="#f0f0f0")
        self.current_file_label.pack(pady=5)

        # Progress Bar
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.style.configure("TProgressbar", thickness=20)
        
        self.progress = ttk.Progressbar(root, orient="horizontal", length=400, mode="determinate", style="TProgressbar")
        self.progress.pack(pady=10)

        self.stats_label = tk.Label(root, text="0% Complete", font=("Helvetica", 10), bg="#f0f0f0")
        self.stats_label.pack()

        # Action Button
        self.btn_start = tk.Button(root, text="START TRANSFER", command=self.run_transfer, 
                                  bg="#2ecc71", fg="white", font=("Helvetica", 12, "bold"),
                                  padx=20, pady=10, relief="flat")
        self.btn_start.pack(pady=20)

        # Initial Scan
        self.update_file_count()

    def update_file_count(self):
        if os.path.exists(self.src):
            count = len(os.listdir(self.src))
            self.file_count_label.config(text=f"Files to move: {count}")
        else:
            self.file_count_label.config(text="Source folder not found!", fg="red")

    def run_transfer(self):
        # Disable button to prevent double-clicking
        self.btn_start.config(state="disabled", text="TRANSFERRING...", bg="#95a5a6")
        # Run in thread so GUI stays responsive
        threading.Thread(target=self.start_moving, daemon=True).start()

    def start_moving(self):
        try:
            if not os.path.exists(self.dst):
                os.makedirs(self.dst)

            files = os.listdir(self.src)
            total = len(files)
            
            for i, filename in enumerate(files):
                start_time = time.time()
                
                # Update UI text
                self.current_file_label.config(text=f"Moving: {filename}", fg="#2980b9")
                self.stats_label.config(text=f"Processing {i+1} of {total}...")

                # Perform Move
                src_path = os.path.join(self.src, filename)
                dst_path = os.path.join(self.dst, filename)
                shutil.move(src_path, dst_path)

                # Update Progress Bar
                percent = int(((i + 1) / total) * 100)
                self.progress['value'] = percent
                self.stats_label.config(text=f"{percent}% Complete ({total - (i+1)} left)")
                
                # Small sleep to let the UI breathe/animate
                self.root.update_idletasks()

            messagebox.showinfo("Success", "All videos have been moved to your USB!")
            self.current_file_label.config(text="Finished!", fg="#27ae60")
            
        except Exception as e:
            messagebox.showerror("Error", f"Something went wrong: {e}")
        
        finally:
            self.btn_start.config(state="normal", text="START TRANSFER", bg="#2ecc71")
            self.update_file_count()

if __name__ == "__main__":
    root = tk.Tk()
    app = VideoMoverGUI(root)
    root.mainloop()