from oy3opy import *
from oy3opy.utils.terminal import curses
from oy3opy.utils.string import Token, string_width, splitstrings_bywidth, split_bywidth
import oy3opy.input as input
import pyperclip
import threading

help = '''      shortcut    │      description
─────────────────────────────────────────────────────────────
      Ctrl+A      │      cursor to start
      Ctrl+E      │      cursor to end
      Ctrl+X      │      clean all content
      Ctrl+Z      │      resotre pre action
      Ctrl+C      │      copy all content to clipboard
      Ctrl+V      │      paste from your clipboard
      Esc         │      exit edit without change
      Ctrl+D      │      stop edit with change

'''

events = ['change', 'move', 'edit', 'close']

@subscribe(events)
@dataclass
class InputBox:
    window:curses.window
    top:int = 0
    bottom:int = 0
    right:int = 0
    left:int = 0
    padding_y:int = 0
    padding_x:int = 1
    text:str = help
    max_length:int = None
    outline:int = 0
    editable:bool = True
    stop:int = None

    def edit(self, text=None, editable=None):
        self.trigger('edit')
        # cache state
        if text is not None:
            cache_text = self.text
            cache_y = getattr(self, 'curs_y', 0)
            cache_x = getattr(self, 'curs_x', 0)

            self.text = text
            self.curs_y = 0
            self.curs_x = 0
        if editable is not None:
            cache_editable = self.editable
            self.editable = editable

        # init view
        __height, __width = self.window.getmaxyx()
        self.width = __width - self.right - self.left
        self.height = __height - self.bottom - self.top
        setdefault(self, 'view', self.window.derwin(self.height, self.width, self.top, self.left))
        self.abs_y, self.abs_x = self.view.getbegyx()
        self.abz_y = self.abs_y + self.height
        self.abz_x = self.abs_x + self.width

        # draw a box outline
        if self.height < 3: self.outline = 0
        else: self.view.box()

        # create a text stream an text cursor
        self.text = str(self.text)[:self.max_length]
        self.text_lines = self.text.splitlines() or ['']
        self.count = len(self.text)
        self.curs_y = getattr(self, 'curs_y', 0)
        self.curs_x = getattr(self, 'curs_x', 0)

        # create a textpad view and view offset
        self.text_height = self.height - self.outline*2 - self.padding_y*2
        self.text_width = self.width - self.outline*2 - self.padding_x*2
        self.buffer = []
        self.offset = self.curs_y
        self.line_offset = 0
        self.lineheight = len(split_bywidth(self.text_lines[self.offset], self.text_width))
        setdefault(self, 'textviewer', self.window.derwin(self.text_height, self.text_width,  self.top + self.outline + self.padding_y, self.left + self.outline + self.padding_x))

        # create a screen cursor
        self.cursbase_y = self.abs_y + self.outline + self.padding_y
        self.cursbase_x = self.abs_x + self.outline + self.padding_x
        self.win_curs_y = 0
        self.win_curs_x = 0
 

        # register key
        if type(self.stop) == int: input.onkey(self.stop, self.handle_stop)
        elif self.stop is not None: input.onchar(self.stop, self.handle_stop)
        if self.stop != input.ENTER: input.onkey(input.ENTER, self.handle_enter)
        input.onkey(input.ESC, self.handle_exit)
        input.onkey(input.CTRL + input.D, self.handle_stop)
        input.onkey(input.CTRL + input.C, self.copy)
        input.onkey(input.CTRL + input.X, self.clear)
        input.onkey(input.CTRL + input.Z, self.undo)

        input.onkey(input.CTRL + input.A, self.curs_to_start)
        input.onkey(input.CTRL + input.E, self.curs_to_end)
        input.onkey(input.DOWN, self.curs_down)
        input.onkey(input.UP, self.curs_up)
        input.onkey(input.LEFT, self.curs_left)
        input.onkey(input.RIGHT, self.curs_right)
        input.onkey(input.BACKSPACE, self.handle_delete)
        input.onmouse(input.SCROLL_DOWN, self.handle_mouse)
        input.onmouse(input.SCROLL_UP, self.handle_mouse)
        input.onmouse(input.LEFT_CLICK, self.handle_mouse)
        
        # init input
        curses.savetty()
        curses.noecho()
        curses.cbreak()
        curses.raw()
        curses.stdscr.keypad(True) 

        self.view.erase()
        if self.outline: self.view.box()
        self.view.refresh()
        self.cache = self.text
        self.rendered = None

        # input
        self.view.move(self.curs_y, self.curs_x)
        if self.text:
            self.render()

        for wc in input.listen(move=0, before=self.curs_fix):
            self.input(wc)

        # exit input
        self.view.erase()
        self.view.refresh()
        curses.resetty()

        # unregister key
        if type(self.stop) == int: input.offkey(self.stop, self.handle_stop)
        elif self.stop is not None: input.offchar(self.stop, self.handle_stop)
        if self.stop != input.ENTER: input.offkey(input.ENTER, self.handle_enter)
        input.offkey(input.ESC, self.handle_exit)
        input.offkey(input.CTRL + input.D, self.handle_stop)
        input.offkey(input.CTRL + input.C, self.copy)
        input.offkey(input.CTRL + input.X, self.clear)
        input.offkey(input.CTRL + input.Z, self.undo)

        input.offkey(input.CTRL + input.A, self.curs_to_start)
        input.offkey(input.CTRL + input.E, self.curs_to_end)
        input.offkey(input.DOWN, self.curs_down)
        input.offkey(input.UP, self.curs_up)
        input.offkey(input.LEFT, self.curs_left)
        input.offkey(input.RIGHT, self.curs_right)
        input.offkey(input.BACKSPACE, self.handle_delete)
        input.offmouse(input.SCROLL_DOWN, self.handle_mouse)
        input.offmouse(input.SCROLL_UP, self.handle_mouse)

        # restore state
        if text is not None:
            self.text = cache_text
            self.curs_y = cache_y
            self.curs_x = cache_x
        if editable is not None:
            self.editable = cache_editable

        self.trigger('close')
        return self.returnvalue

    @debounce(1.6, True)
    def update_cache(self, text=None, y=None, x=None):
        text = text if text is not None else self.value()
        if self.cache != text:
            self.cache = text
            self.cache_curs_y = y or self.curs_y
            self.cache_curs_x = x or self.curs_x
    def update(self, text:str, y=0, x=0, write=True):
        if not self.editable: return self.curs_fix()
        text = str(text)[:self.max_length]
        if self.cache is None: self.update_cache(text, 0, 0, immediate=True)
        elif self.cache != text:
            self.update_cache(self.value(), self.curs_y, self.curs_x, immediate=True)
        if write: self.text = text
        self.text_lines = text.splitlines() or ['']
        self.count = len(text)
        y = min(y, len(self.text_lines)-1)
        x = min(x, len(self.text_lines[-1]))
        self.curs_y = y
        self.curs_x = x
        self.offset = y
        self.line_offset = 0
        line = split_bywidth(self.text_lines[y][:x], self.text_width)
        self.win_curs_y = len(line)-1
        self.win_curs_x = string_width(line[-1])%self.text_width
    def value(self)->str:
        return '\n'.join(getattr(self, 'text_lines', []))
    def curs_to(self, y:int, x:int):
        self.curs_y = y
        self.curs_x = x
        self.offset = y
        self.line_offset = 0
        line = split_bywidth(self.text_lines[y][:x], self.text_width)
        self.win_curs_y = len(line)-1
        self.win_curs_x = string_width(line[-1])%self.text_width
        self.render()
    def curs_fix(self):
        if (0 <= self.win_curs_y) and (self.win_curs_y < self.text_height) and (0 <= self.win_curs_x) and (self.win_curs_x <= self.text_width):
            curses.stdscr.move(self.cursbase_y+self.win_curs_y, self.cursbase_x+self.win_curs_x)
            curses.curs_set(2)
        else:
            curses.curs_set(0)
    def edit_fix(self):
        if (getattr(self, 'cache_editing', None) is not None) and ((self.win_curs_y<0) or (self.win_curs_y>=self.text_height)):
            self.offset = self.cache_editing.offset
            self.lineheight = self.cache_editing.lineheight
            self.line_offset = self.cache_editing.line_offset
            self.win_curs_x = self.cache_editing.win_curs_x
            self.win_curs_y = self.cache_editing.win_curs_y
        self.cache_editing = None
    def view_fix(self):
        if self.win_curs_x < 0:
            if self.win_curs_y > 0:
                self.win_curs_y -= 1
                prefragment = self.buffer[self.win_curs_y]
                preline = split_bywidth(self.text_lines[prefragment[1]], self.text_width)
                self.lineheight = len(preline)
                self.line_offset = len(preline)-1
                self.win_curs_x = string_width(prefragment[0])%self.text_width
            elif self.offset > 0:
                self.offset -= 1
                preline = split_bywidth(self.text_lines[self.offset], self.text_width)
                self.lineheight = len(preline)
                self.line_offset = len(preline)-1
                self.win_curs_x = string_width(preline[-1][0])%self.text_width
            else:
                self.win_curs_x = 0
                self.win_curs_y = 0

        if self.win_curs_y < 0:
            if self.line_offset > 0:
                fragment = self.buffer[0]
                line = split_bywidth(self.text_lines[fragment[1]], self.text_width)
                self.line_offset -= 1
                self.win_curs_x = string_width(line[self.line_offset-1])%self.text_width
            elif self.offset > 0:
                self.offset -= 1
                preline = split_bywidth(self.text_lines[self.offset], self.text_width)
                self.lineheight = len(preline)
                self.line_offset = len(preline)-1
                self.win_curs_x = min(self.win_curs_x, string_width(preline[-1]))
            else:
                self.win_curs_x = 0
            self.win_curs_y = 0

        if self.win_curs_x > self.text_width:
            if self.win_curs_y + 1 < len(self.buffer):
                self.win_curs_y += 1
                self.win_curs_x = 0
            elif self.win_curs_y + 1 < self.text_height:
                self.win_curs_x = self.text_width
            else:
                last_fragment = self.buffer[-1]
                if ((last_fragment[2]+1)<len(split_bywidth(self.text_lines[last_fragment[1]], self.text_width))) or (last_fragment[1]+1 < len(self.text_lines)):
                    if self.line_offset+1 < self.lineheight:
                        self.line_offset += 1
                    else:
                        self.offset += 1
                        nextline = split_bywidth(self.text_lines[self.offset], self.text_width)
                        self.lineheight = len(nextline)
                        self.line_offset = 0
                    self.win_curs_y = self.text_height-1
                    self.win_curs_x = 0
                else:
                    self.win_curs_x = self.text_width

        if self.win_curs_y >= self.text_height:
            last_fragment = self.buffer[-1]
            next_fragment_line = split_bywidth(self.text_lines[last_fragment[1]], self.text_width)
            if ((last_fragment[2]+1)<len(next_fragment_line)) or (last_fragment[1]+1 < len(self.text_lines)):
                if self.line_offset+1 < self.lineheight:
                    self.line_offset += 1
                else: 
                    self.offset += 1
                    self.line_offset = 0

                if (last_fragment[2]+1)<len(next_fragment_line):
                    next_fragment_text = next_fragment_line[last_fragment[2]+1]
                else:
                    nextline = split_bywidth(self.text_lines[last_fragment[1]+1], self.text_width)
                    next_fragment_text = nextline[0]
                    self.lineheight = len(nextline)
                    self.line_offset = 0
                self.win_curs_x = min(self.win_curs_x, string_width(next_fragment_text))
            self.win_curs_y = self.text_height-1
    def input(self, wc:str):
        if not self.editable: return self.curs_fix()
        self.edit_fix()
        if self.count == self.max_length: return
        self.update_cache(self.value(), self.curs_y, self.curs_x)
        self.count += 1
        if ord(wc) in (curses.KEY_ENTER, 10, 13):
            line_left = self.text_lines[self.curs_y][:self.curs_x]
            line_right = self.text_lines[self.curs_y][self.curs_x:]
            self.text_lines.insert(self.curs_y + 1, line_right)
            self.text_lines[self.curs_y] = line_left
            self.curs_y += 1
            self.win_curs_y += 1
            self.curs_x = 0
            self.win_curs_x = 0
        else:
            self.text_lines[self.curs_y] = self.text_lines[self.curs_y][:self.curs_x] + wc + self.text_lines[self.curs_y][self.curs_x:]
            self.curs_x += 1
            self.win_curs_x += 1
        self.render()
    def render(self, keep_edit=True):
        if keep_edit: self.view_fix()
        elif getattr(self, 'cache_editing', None) is None:
            self.cache_editing = lambda:None
            self.cache_editing.offset = self.offset
            self.cache_editing.lineheight = self.lineheight
            self.cache_editing.line_offset = self.line_offset
            self.cache_editing.win_curs_x = self.win_curs_x
            self.cache_editing.win_curs_y = self.win_curs_y


        if self.line_offset < 0:
            if self.offset > 0:
                self.offset -= 1
                preline = split_bywidth(self.text_lines[self.offset], self.text_width)
                self.lineheight = len(preline)
                self.line_offset = len(preline)-1
                self.win_curs_y += 1
            else:
                self.line_offset = 0

        if self.buffer and (self.line_offset >= len(split_bywidth(self.text_lines[self.offset], self.text_width))):
            last_fragment = self.buffer[-1]
            if (((last_fragment[2]+1)<len(split_bywidth(self.text_lines[last_fragment[1]], self.text_width))) \
               or (last_fragment[1]+1 < len(self.text_lines))) \
            and (self.offset+1 < len(self.text_lines)):
                self.offset += 1
                nextline = split_bywidth(self.text_lines[self.offset], self.text_width)
                self.lineheight = len(nextline)
                self.line_offset = len(nextline)-1
                self.win_curs_y -= 1
            else:
                self.line_offset = self.lineheight-1
        
        if keep_edit: self.view_fix()
        preload = splitstrings_bywidth(self.text_lines, self.text_width, self.offset, min(len(self.text_lines), self.offset + self.text_height))
        self.buffer = preload[self.line_offset : min(len(preload), self.line_offset + self.text_height)]
        if self.rendered != self.buffer:
            self.textviewer.erase()
            self.rendered = self.buffer
            for i, line in enumerate(self.buffer):
                self.textviewer.addstr(i, 0, line[0])
            self.textviewer.refresh()
            self.trigger('change')
        self.curs_fix()

    def handle_exit(self, *args):
        input.stop()
        self.returnvalue = self.text
    def handle_stop(self, *args):
        input.stop()
        if self.editable: self.text = self.value()
        self.returnvalue = self.value()
    def handle_enter(self, *args):
        self.input('\n')
    def handle_delete(self, *args):
        if not self.editable: return self.curs_fix()
        self.edit_fix()
        self.update_cache(self.value(), self.curs_y, self.curs_x)
        if len(self.text_lines[self.curs_y]) > 0:
            if (self.curs_x > 0):
                self.text_lines[self.curs_y] = self.text_lines[self.curs_y][:max(0,self.curs_x-1)] + self.text_lines[self.curs_y][self.curs_x:]
                self.count -= 1
                self.curs_x -= 1
                self.win_curs_x -= 1
                self.render()
            elif self.curs_y - 1 >= 0:
                self.curs_x = len(self.text_lines[self.curs_y - 1])
                self.win_curs_x = string_width(self.text_lines[self.curs_y - 1])%self.text_width
                self.text_lines[self.curs_y - 1] += self.text_lines.pop(self.curs_y)
                self.count -= 1
                self.curs_y -= 1
                self.win_curs_y -= 1
                self.render()
        elif self.curs_y > 0:
            if not self.editable: return
            self.text_lines.pop(self.curs_y)
            self.count -= 1
            self.curs_y -= 1
            self.win_curs_y -= 1
            self.curs_x = len(self.text_lines[self.curs_y])
            self.win_curs_x = string_width(self.text_lines[self.curs_y])%self.text_width
            self.render()
    def copy(self, *args):
        pyperclip.copy(self.value())
    def clear(self, *args):
        if not self.editable: return self.curs_fix()
        self.update('', write=False)
        self.render()
    def undo(self, *args):
        if (not self.editable) or (self.cache is None): return self.curs_fix()
        self.update(self.cache, getattr(self,'cache_curs_y', self.curs_y), getattr(self,'cache_curs_x',self.curs_x), write=False)
        self.render()
    def curs_to_start(self, *args):
        self.curs_to(0, 0)
    def curs_to_end(self, *args):
        self.curs_to(len(self.text_lines)-1, len(self.text_lines[-1]))
    def curs_down(self, *args):
        self.edit_fix()
        if self.curs_y + 1 < len(self.text_lines):
            self.curs_y += 1
            self.win_curs_y += 1
            if self.curs_x > len(self.text_lines[self.curs_y]):
                self.curs_x = len(self.text_lines[self.curs_y])
                self.win_curs_x = string_width(self.text_lines[self.curs_y])%self.text_width
            self.trigger('move')
            self.render()
    def curs_up(self, *args):
        self.edit_fix()
        if self.curs_y - 1 >= 0:
            self.curs_y -= 1
            self.win_curs_y -= 1
            if self.curs_x > len(self.text_lines[self.curs_y]):
                self.curs_x = len(self.text_lines[self.curs_y])
                self.win_curs_x = string_width(self.text_lines[self.curs_y])%self.text_width
            self.trigger('move')
            self.render()
    def curs_left(self, *args):
        self.edit_fix()
        if self.curs_x - 1 >= 0:
            self.curs_x -= 1
            self.win_curs_x -= 1
            self.trigger('move')
            self.render()
        elif self.curs_y - 1 >= 0:
            self.curs_y -= 1
            self.win_curs_y -= 1
            self.curs_x = len(self.text_lines[self.curs_y])
            self.win_curs_x = string_width(self.text_lines[self.curs_y])%self.text_width
            self.trigger('move')
            self.render()
    def curs_right(self, *args):
        self.edit_fix()
        if self.curs_x < len(self.text_lines[self.curs_y]):
            self.curs_x += 1
            self.win_curs_x += 1
            self.trigger('move')
            self.render()
        elif self.curs_y + 1 < len(self.text_lines):
            self.curs_y += 1
            self.win_curs_y += 1
            self.curs_x = 0
            self.win_curs_x = 0
            self.trigger('move')
            self.render()
    def handle_mouse(self, y, x, type):
        if (self.abs_y <= y) and (y < self.abz_y) and (self.abs_x <= x) and (x < self.abz_x):
            if type == input.SCROLL_DOWN:
                self.line_offset += 1
                self.render(keep_edit=False)
            elif type == input.SCROLL_UP:
                self.line_offset -= 1
                self.render(keep_edit=False)
            elif type == input.LEFT_CLICK:
                self.win_curs_y = min(y-self.cursbase_y, len(self.buffer)-1)
                fragment = self.buffer[self.win_curs_y]
                self.win_curs_x = min(x-self.cursbase_x, string_width(fragment[0]))
                self.curs_y = fragment[1]
                self.curs_x = fragment[2]*self.text_width+self.win_curs_x
                self.cache_editing = None
                self.render()
        else: return self.curs_fix()


class TokenCounter(Token):
    def __init__(self, window, y, x, init='0'):
        super().__init__()
        self.view = window
        self.y = y
        self.x = x
        self.view.addstr(y, x, init.center(6))
    def update(self, text):
        def task():
            self.view.addstr(self.y, self.x, str(self.count(text)).center(6))
        threading.Thread(target=task).start()
    def set(self, value):
        self.view.addstr(self.y, self.x, str(value).center(6))

class CharCounter:
    def __init__(self, window, y, x, init='0'):
        self.view = window
        self.y = y
        self.x = x
        self.view.addstr(y, x, init.center(6))
    def update(self,text):
        self.view.addstr(self.y, self.x, str(len(text)).center(6))
        self.view.refresh()
    def set(self,value):
        self.view.addstr(self.y, self.x, str(value).center(6))

@dataclass
class Editor(InputBox):
    outline:int = 1
    def __new__(klass, *args, **kwargs):
        self = object.__new__(klass)
        InputBox.__init__(self, *args, **kwargs)
        return self
    def edit(self, text=None, editable=None):
        self.root_view = getattr(self, 'root_view', self.window)
        self.root_top = getattr(self, 'root_top', self.top)
        self.root_right = getattr(self, 'root_right', self.right)
        self.root_bottom = getattr(self, 'root_bottom', self.bottom)
        self.root_left = getattr(self, 'root_left', self.left)
        root_view:curses._CursesWindow = self.root_view
        root_height, root_width = root_view.getmaxyx()
        width = root_width - self.root_right - self.root_left
        height = root_height - self.root_bottom - self.root_top
        editor_view:curses._CursesWindow = root_view.derwin(height, width, self.root_top, self.root_left)
        editor_view.erase()
        lineview = None

        self.window = editor_view
        self.top = 0
        self.right = 8
        self.bottom = 0
        self.left = 5
        if height < 4:
            self.left = 0
            self.right = 15
            self.char = CharCounter(editor_view, height//2, width - 7)
            self.token = TokenCounter(editor_view, height//2, width - 14)
            editor_view.addstr(height//2,width-8,'/')
        elif height < 5:
            self.char = CharCounter(editor_view, 2, width - 7)
            self.token = TokenCounter(editor_view, 1, width - 7)
            lineview = editor_view.derwin(height, 5, 0, 0)
            def updatelineview(*args):
                lineview.addstr(1,0, str(getattr(self, 'curs_y', 0)).center(5))
                lineview.addstr(2,0, str(len(getattr(self, 'text_lines', []))-getattr(self, 'curs_y', 0)-1).center(5))
        elif height < 6:
            self.char = CharCounter(editor_view, 3, width - 7)
            self.token = TokenCounter(editor_view, 1, width - 7)
            lineview = editor_view.derwin(height, 5, 0, 0)
            def updatelineview(*args):
                lineview.addstr(1,0, str(getattr(self, 'curs_y', 0)).center(5))
                lineview.addstr(3,0, str(len(getattr(self, 'text_lines', []))-getattr(self, 'curs_y', 0)-1).center(5))
        elif height < 12:
            self.char = CharCounter(editor_view, height//2-2, width - 7)
            self.token = TokenCounter(editor_view, height//2+1, width - 7)

            editor_view.addstr(height//2-1, width-7, 'token')
            editor_view.addstr(height//2, width-7, 'chars')
            lineview = editor_view.derwin(height, 5, 0, 0)
            lineview.addstr(height//2-1,0, '⭱'.center(5))
            lineview.addstr(height//2,0, '⭳'.center(5))
            def updatelineview(*args):
                lineview.addstr(height//2-2,0, str(getattr(self, 'curs_y', 0)).center(5))
                lineview.addstr(height//2+1,0, str(len(getattr(self, 'text_lines', []))-getattr(self, 'curs_y', 0)-1).center(5))
        else:
            self.left = 8
            self.right = 0
            padding = (height-12)//6
            self.char = CharCounter(editor_view, height//3+6+padding, 1)
            self.token = TokenCounter(editor_view, height//3+3+padding, 1)
            
            editor_view.addstr(height//3+2+padding, 1, 'token')
            editor_view.addstr(height//3+5+padding, 1, 'chars')
            lineview = editor_view.derwin(height//3+2, 8, 0, 0)
            lineview.addstr(height//3-2-padding,0, '⭱'.center(7))
            lineview.addstr(height//3-1-padding,0, '⭳'.center(7))
            def updatelineview(*args):
                lineview.addstr(height//3-3-padding,0, str(getattr(self, 'curs_y', 0)).center(7))
                lineview.addstr(height//3-padding,0, str(len(getattr(self, 'text_lines', []))-getattr(self, 'curs_y', 1)-1).center(7))

        def updatecountview():
            self.char.set(self.count)
            self.token.update(self.value())
            editor_view.refresh()

        self.subscribe('change',updatecountview)
        if lineview:
            updatelineview()
            self.subscribe('change',updatelineview)
            self.subscribe('move',updatelineview)
            self.subscribe('change',lineview.refresh)
            self.subscribe('move',lineview.refresh)
        editor_view.refresh()
        value = InputBox.edit(self, text, editable)
        editor_view.erase()
        editor_view.refresh()
        self.trigger('close')
        return value