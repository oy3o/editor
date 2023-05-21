# Editor and InputBox
Python API to Input text, edit text or input command, The following features are supported.

- arrow key to move cursor
- backpace to delete char
- utf-8 support (such as chinese)
- scroll by cursor
- eventhandler
- char count & max length
- token count(tiktok)

## Editor
```py
# default value of arguments
e = Editor(window, top = 0, bottom = 0, right = 0, left = 0, padding_y = 0, padding_x = 1, text = '', listeners = {'change':[],'move':[]}, max_length = None, outline = 1, editable = True, release = 27)# esc(27) to end edit
text = e.edit()
print(text)
```

## InputBox 
```py
# same arguments with Editor
# one line without outline version
view = screen.derwin(1, screen_width, screen_height-1, 0)
inputbox = InputBox(view, outline = 0, release = '\n')
command = inputbox.edit()
```
