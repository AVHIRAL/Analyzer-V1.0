import tkinter as tk
from tkinter import ttk
import psutil
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import sys
import ctypes
import pynvml
import numpy as np

try:
    import ADL3 as ADL
    ADL_LOADED = True
except ImportError:
    ADL = None
    ADL_LOADED = False


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False


class App(tk.Tk):
    def __init__(self):
        super().__init__()

        self.geometry('620x800')
        self.configure(bg='black')
        self.attributes('-alpha', 0.9)
        self.title('AVHIRAL Monitoring Système v1.0')

        self.canvas = tk.Canvas(self, bg="black")
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.scrollbar = ttk.Scrollbar(self, command=self.canvas.yview)
        self.scrollbar.pack(side=tk.LEFT, fill=tk.Y)

        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.bind('<Configure>', lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))

        self.frame = ttk.Frame(self.canvas)
        self.canvas.create_window((0, 0), window=self.frame, anchor="nw")

        self.cpu_data = [0] * 10
        self.gpu_data = [0] * 10
        self.mem_data = [0] * 10

        self.setup_ui()
        self._update_data_id = None
        self.update_data()

    def setup_ui(self):
        datasets = [
            ("CPU", self.cpu_data, 'r'),
            ("GPU", self.gpu_data, 'b'),
            ("Mémoire", self.mem_data, 'g')
        ]

        for name, data, color in datasets:
            frame = ttk.LabelFrame(self.frame, text=name)
            frame.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)

            label = ttk.Label(frame)
            label.pack(anchor='w')
            data.append(label)

            fig, ax = plt.subplots()
            line, = ax.plot(data[:-1], label=f'Utilisation {name}', color=color)
            ax.set_ylim(0, 100)
            data.append(line)

            canvas = FigureCanvasTkAgg(fig, master=frame)
            canvas.draw()
            canvas.get_tk_widget().pack()
            data.append(canvas)

        self.conn_frame = ttk.LabelFrame(self.frame, text="Connexions")
        self.conn_frame.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)
        self.conn_text = tk.Text(self.conn_frame, height=10, width=50)
        self.conn_text.pack()

    def update_data(self):
        # CPU Info Update
        cpu_percent = psutil.cpu_percent()
        num_cpus = psutil.cpu_count()
        cpu_freq = psutil.cpu_freq().current
        temp_str = ""
        try:
            temp = psutil.sensors_temperatures()['coretemp'][0].current
            temp_str = f", Température: {temp}°C"
        except:
            pass
        self.cpu_data[-3].config(text=f"Utilisation: {cpu_percent}%, Cores: {num_cpus}, Fréquence: {cpu_freq}MHz{temp_str}")
        self.cpu_data[:-3] = self.cpu_data[1:-2]
        self.cpu_data[-4] = cpu_percent

        # GPU Info Update
        if not self.get_nvidia_gpu_info() and ADL_LOADED:
            if not self.get_amd_gpu_info():
                gpu_percent = np.random.randint(0, 100)  # Mocked GPU percentage
                self.gpu_data[-3].config(text=f"Utilisation GPU (simulé): {gpu_percent}%")
                self.gpu_data[:-3] = self.gpu_data[1:-2]
                self.gpu_data[-4] = gpu_percent
        else:
            gpu_percent = np.random.randint(0, 100)  # Mocked GPU percentage
            self.gpu_data[-3].config(text=f"Utilisation GPU (simulé): {gpu_percent}%")
            self.gpu_data[:-3] = self.gpu_data[1:-2]
            self.gpu_data[-4] = gpu_percent

        # Memory Info Update
        mem = psutil.virtual_memory()
        mem_percent = mem.percent
        mem_total = mem.total / (1024 ** 3)
        mem_used = mem.used / (1024 ** 3)
        self.mem_data[-3].config(text=f"Utilisation: {mem_percent}%, Utilisé: {mem_used:.2f}GB, Total: {mem_total:.2f}GB")
        self.mem_data[:-3] = self.mem_data[1:-2]
        self.mem_data[-4] = mem_percent

        # Network Info Update
        connections = psutil.net_connections(kind='inet')
        self.conn_text.delete(1.0, tk.END)
        unique_connections = set()
        for conn in connections:
            if conn.raddr and conn.laddr.ip != '127.0.0.1' and conn.laddr.port not in unique_connections:
                self.conn_text.insert(tk.END, f"{conn.laddr.ip}:{conn.laddr.port} -> {conn.raddr.ip}:{conn.raddr.port}\n")
                unique_connections.add(conn.laddr.port)

        # Refresh the plots
        for dataset in [self.cpu_data, self.gpu_data, self.mem_data]:
            dataset[-2].set_ydata(dataset[:-3])
            dataset[-1].draw()

        # Schedule the next update
        if self._update_data_id:
            self.after_cancel(self._update_data_id)
        self._update_data_id = self.after(1000, self.update_data)

    def get_nvidia_gpu_info(self):
        try:
            pynvml.nvmlInit()
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            gpu_percent = pynvml.nvmlDeviceGetUtilizationRates(handle).gpu
            gpu_temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
            self.gpu_data[-3].config(text=f"Utilisation NVIDIA: {gpu_percent}%, Température: {gpu_temp}°C")
            self.gpu_data[:-3] = self.gpu_data[1:-2]
            self.gpu_data[-4] = gpu_percent
            return True
        except:
            return False

    def get_amd_gpu_info(self):
        if not ADL_LOADED:
            return False

        try:
            if ADL.ADL_Main_Control_Create() == ADL.ADL_OK:
                num_adapters = ADL.ADL_Adapter_NumberOfAdapters_Get()
                for i in range(num_adapters):
                    adapter_info = ADL.ADL_Adapter_AdapterInfo_Get(i)
                    if adapter_info.iVendorID == ADL.ADL_VENDOR_ID:
                        activity = ADL.ADL_Overdrive5_CurrentActivity_Get(i)
                        if activity.iActivityPercent != -1:
                            self.gpu_data[-3].config(text=f"Utilisation AMD: {activity.iActivityPercent}%, Température: {activity.iTemperature/1000}°C")
                            self.gpu_data[:-3] = self.gpu_data[1:-2]
                            self.gpu_data[-4] = activity.iActivityPercent
                            ADL.ADL_Main_Control_Destroy()
                            return True
                ADL.ADL_Main_Control_Destroy()
            return False
        except:
            return False

if __name__ == '__main__':
    if is_admin():
        app = App()
        app.mainloop()
    else:
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
