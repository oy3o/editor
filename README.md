# Editor and InputBox
Python API to Input text, edit text or input command, The following features are supported.

- arrow key to move cursor
- backpace to delete char
- utf-8 support (such as chinese)
- scroll by cursor and mouse
- click to position cursor
- eventhandler
- char count & max length
- token count(tiktok)

```
─────────────────────────────────────────────────────────
      shortcut        │       description
─────────────────────────────────────────────────────────
      Ctrl+A          │       cursor to start
      Ctrl+E          │       cursor to end 
      Ctrl+X          │       clean all content
      Ctrl+Z          │       resotre pre action
      Ctrl+C          │       copy all content to clipboard
      Ctrl+V          │       paste from your clipboard
      Esc             │       exit edit
```
## Editor
```py
from oy3opy.editor import InputBox, Editor
import curses
window = curses.initscr()
# default value of arguments
e = Editor(window, top = 0, bottom = 0, right = 0, left = 0, padding_y = 0, padding_x = 1, text = '', listeners = {'change':[],'move':[]}, max_length = None, outline = 1, editable = True, stop = None)
text = e.edit()
print(text)
```

## InputBox 
```py
# same arguments with Editor
# one line without outline version
view = screen.derwin(1, screen_width, screen_height-1, 0)
inputbox = InputBox(view, outline = 0, stop = '\n')
command = inputbox.edit()
```
