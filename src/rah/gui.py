"""Small Tk desktop client with real connect/send/cancel/download controls."""
import json
import queue
import threading
import tkinter as tk
from tkinter import filedialog, ttk

from rah.client import Client, seed


def launch(server="http://localhost:8080", token=""):
    root = tk.Tk()
    root.title("Remote Agent Harness")
    root.geometry("840x640")
    root.columnconfigure(1, weight=1)
    root.rowconfigure(5, weight=1)
    server_var, token_var = tk.StringVar(value=server), tk.StringVar(value=token)
    for row, label, variable in [(0, "Server", server_var), (1, "Client token", token_var)]:
        ttk.Label(root, text=label).grid(row=row, column=0, padx=8, pady=5, sticky="w")
        ttk.Entry(root, textvariable=variable, show="*" if row == 1 else "").grid(row=row, column=1, padx=8, sticky="ew")
    ttk.Label(root, text="Uploaded files are temporary. Download artifacts before closing or cancelling.").grid(row=2, column=0, columnspan=2, padx=8, sticky="w")
    prompt = tk.Text(root, height=5, wrap="word")
    prompt.grid(row=3, column=0, columnspan=2, padx=8, pady=8, sticky="ew")
    buttons = ttk.Frame(root)
    buttons.grid(row=4, column=0, columnspan=2, sticky="w")
    output = tk.Text(root, state="disabled", wrap="word")
    output.grid(row=5, column=0, columnspan=2, padx=8, pady=8, sticky="nsew")
    messages, state = queue.Queue(), {"session": None, "client": None, "busy": False, "connecting": False}
    def log(value):
        messages.put(str(value))
    def background(action):
        def work():
            try:
                action()
            except Exception as exc:
                log("Error: " + str(exc))
        threading.Thread(target=work, daemon=True).start()
    def connect():
        if state["client"] or state["connecting"]:
            log("Already connected or connecting.")
            return
        state["connecting"] = True
        address, secret = server_var.get(), token_var.get()
        def action():
            client = Client(address, secret)
            try:
                client.connect()
                sid = client.provision()
                state.update(client=client, session=sid)
                log("Connected. Session " + sid)
            except Exception:
                client.close()
                raise
            finally:
                state["connecting"] = False
        background(action)
    def upload():
        folder = filedialog.askdirectory(title="Select fixture folder (bounded upload)")
        if folder and state["client"]:
            def action():
                if state["busy"]:
                    raise ValueError("wait for current run")
                if state["session"]:
                    state["client"].release(state["session"])
                state["session"] = state["client"].provision(seed(folder))
                log("Fixture uploaded to new session " + state["session"])
            background(action)
    def send():
        text = prompt.get("1.0", "end").strip()
        if state["client"] and text and not state["busy"]:
            state["busy"] = True
            def action():
                try:
                    sid, client = state["session"], state["client"]
                    op = client.send(sid, text)
                    cursor = 0
                    while True:
                        for event in client.events(sid, cursor):
                            cursor = event["id"]
                            log(json.dumps(event))
                        status = client.request("GET", f"/v0/sessions/{sid}/operations/{op['request_id']}")
                        if status["state"] == "finished":
                            log(json.dumps(status["result"]))
                            break
                finally:
                    state["busy"] = False
            background(action)
    def cancel():
        if state["client"] and state["session"]:
            background(lambda: log(state["client"].cancel(state["session"])))
    def download():
        folder = filedialog.askdirectory(title="Download collected artifacts")
        if folder and state["client"] and state["session"]:
            background(lambda: log(f"Downloaded {state['client'].download(state['session'], folder)} files"))
    for label, action in [("Connect", connect), ("Upload fixture", upload), ("Send", send), ("Cancel", cancel), ("Download", download)]:
        ttk.Button(buttons, text=label, command=action).pack(side="left", padx=5)
    def poll():
        while not messages.empty():
            output.configure(state="normal")
            output.insert("end", messages.get() + "\n")
            output.see("end")
            output.configure(state="disabled")
        root.after(100, poll)
    def close():
        if state["client"] and state["session"]:
            def cleanup():
                try:
                    state["client"].http.timeout = 10
                    state["client"].release(state["session"])
                finally:
                    state["client"].close()
            threading.Thread(target=cleanup, daemon=False).start()
        root.destroy()
    root.protocol("WM_DELETE_WINDOW", close)
    poll()
    root.mainloop()
