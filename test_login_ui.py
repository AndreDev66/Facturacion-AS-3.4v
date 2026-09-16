from Main import LoginWindow
import tkinter as tk

root = tk.Tk()
root.withdraw()

lw = LoginWindow(lambda: None, master=root)

found = []

def find_widgets(widget):
    for c in widget.winfo_children():
        try:
            txt = c.cget('text')
        except Exception:
            txt = ''
        print(type(c), txt, c.winfo_class())
        if txt == 'Registrarse':
            found.append(c)
        find_widgets(c)

find_widgets(lw)
print('Encontrados:', len(found))
if found:
    print('Widget repr:', found[0])

lw.destroy()
root.destroy()
