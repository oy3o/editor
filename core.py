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
            __cache = lambda:None
            __cache.text = self.text
            __cache.text_view_offset = getattr(self, 'text_view_offset', 0)
            __cache.text_curs_x = getattr(self, 'text_curs_x', 0)
            __cache.text_curs_y = getattr(self, 'text_curs_y', 0)
            __cache.inline_offset_max = getattr(self, 'inline_offset_max', 0)
            __cache.inline_offset_cur = getattr(self, 'inline_offset_cur', 0)
            __cache.screen_curs_x = getattr(self, 'screen_curs_x', 0)
            __cache.screen_curs_y = getattr(self, 'screen_curs_y', 0)

            self.text = text
            self.text_view_offset = 0
            self.text_curs_y= 0
            self.text_curs_x = 0
            self.inline_offset_max = 0
            self.inline_offset_cur = 0
            self.screen_curs_y = 0
            self.screen_curs_x = 0

        if editable is not None:
            __cache.editable = self.editable
            self.editable = editable

        # init view
        __height, __width = self.window.getmaxyx()
        self.width = __width - self.right - self.left
        self.height = __height - self.bottom - self.top
        setdefault(self, 'view', self.window.derwin(self.height, self.width, self.top, self.left))
        self.view.erase()

        # draw a box outline
        if self.height < 3: self.outline = 0
        if self.outline: self.view.box()

        # create a text stream and text cursor
        self.text = str(self.text)[:self.max_length]
        self.text_lines = self.text.splitlines() or ['']
        self.text_char_count = len(self.text)
        self.text_curs_y = getattr(self, 'text_curs_y', 0)
        self.text_curs_x = getattr(self, 'text_curs_x', 0)

        # create a textpad view and view text_view_offset
        self.text_view_height = self.height - self.outline*2 - self.padding_y*2
        self.text_view_width = self.width - self.outline*2 - self.padding_x*2 - 1
        self.text_view_offset = self.text_curs_y
        self.inline_offset_cur = 0
        self.inline_offset_max = len(split_bywidth(self.text_lines[self.text_view_offset], self.text_view_width))
        self.rendered = None
        self.buffer = [('', 0, 0)]
        setdefault(self, 'text_viewer', self.window.derwin(
            self.text_view_height,
            self.text_view_width+1, 
            self.top + self.outline + self.padding_y,
            self.left + self.outline + self.padding_x
        ))

        # create a screen cursor
        self.__screen_curs_min_y, self.__screen_curs_min_x = self.view.getbegyx()
        self.__screen_curs_max_y = self.__screen_curs_min_y + self.height
        self.__screen_curs_max_x = self.__screen_curs_min_x + self.width
        self.__screen_curs_base_y = self.__screen_curs_min_y + self.outline + self.padding_y
        self.__screen_curs_base_x = self.__screen_curs_min_x + self.outline + self.padding_x
        self.screen_curs_y = 0
        self.screen_curs_x = 0

        # init undo cache
        self.cache = lambda:None
        self.cache.text = self.text
        self.cache.text_view_offset = self.text_view_offset
        self.cache.inline_offset_max = self.inline_offset_max
        self.cache.inline_offset_cur = self.inline_offset_cur
        self.cache.screen_curs_x = self.screen_curs_x
        self.cache.screen_curs_y = self.screen_curs_y

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
        input.onkey(input.DOWN, self.curs_to_down)
        input.onkey(input.UP, self.curs_to_up)
        input.onkey(input.LEFT, self.curs_to_left)
        input.onkey(input.RIGHT, self.curs_to_right)
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
        curses.curs_set(2)

        # input
        if self.text: self.render()
        self.view.move(self.text_curs_y, self.text_curs_x)
        self.view.refresh()

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
        input.offkey(input.DOWN, self.curs_to_down)
        input.offkey(input.UP, self.curs_to_up)
        input.offkey(input.LEFT, self.curs_to_left)
        input.offkey(input.RIGHT, self.curs_to_right)
        input.offkey(input.BACKSPACE, self.handle_delete)
        input.offmouse(input.SCROLL_DOWN, self.handle_mouse)
        input.offmouse(input.SCROLL_UP, self.handle_mouse)

        # restore state
        if text is not None:
            self.text = __cache.text
            self.text_view_offset = __cache.text_view_offset
            self.text_curs_x = __cache.text_curs_x
            self.text_curs_y = __cache.text_curs_y
            self.inline_offset_max = __cache.inline_offset_max
            self.inline_offset_cur = __cache.inline_offset_cur
            self.screen_curs_x = __cache.screen_curs_x
            self.screen_curs_y = __cache.screen_curs_y

        if editable is not None:
            self.editable = __cache.editable

        self.trigger('close')
        return self.returnvalue

    def value(self)->str:
        return '\n'.join(getattr(self, 'text_lines', []))
    def render(self, only_scroll=False):
        if self.outline < 3: self.view.box()

        if self.inline_offset_cur < 0:
            if self.text_view_offset > 0:
                self.text_view_offset -= 1
                preline = split_bywidth(self.text_lines[self.text_view_offset], self.text_view_width)
                self.inline_offset_max = len(preline)
                self.inline_offset_cur = len(preline)-1
                self.screen_curs_y += 1
            else:
                self.inline_offset_cur = 0

        if self.inline_offset_cur >= self.inline_offset_max:
            last_fragment = self.buffer[-1]
            if ((last_fragment[2]+1<len(split_bywidth(self.text_lines[last_fragment[1]], self.text_view_width))) \
            or (last_fragment[1]+1 < len(self.text_lines))):
                self.text_view_offset += 1
                nextline = split_bywidth(self.text_lines[self.text_view_offset], self.text_view_width)
                self.inline_offset_max = len(nextline)
                self.inline_offset_cur = 0
                self.screen_curs_y -= 1
            else:
                self.inline_offset_cur = self.inline_offset_max-1

        if only_scroll and getattr(self, 'cache_editing', None) is None:
            self.cache_editing = lambda:None
            self.cache_editing.text_view_offset = self.text_view_offset
            self.cache_editing.inline_offset_max = self.inline_offset_max
            self.cache_editing.inline_offset_cur = self.inline_offset_cur
            self.cache_editing.screen_curs_x = self.screen_curs_x
            self.cache_editing.screen_curs_y = self.screen_curs_y
            self.cache_editing.buffer = self.buffer

        preload_end =  min(len(self.text_lines), self.text_view_offset + self.text_view_height)
        preload = splitstrings_bywidth(self.text_lines, self.text_view_width, self.text_view_offset, preload_end)
        buffer_end = min(len(preload), self.inline_offset_cur + self.text_view_height)
        self.buffer = preload[self.inline_offset_cur : buffer_end]

        if self.rendered != self.buffer:
            self.text_viewer.erase()
            self.rendered = self.buffer
            for i, line in enumerate(self.buffer):
                self.text_viewer.addstr(i, 0, line[0])
            self.text_viewer.refresh()
            self.trigger('change')
        self.curs_fix()

    def input(self, wc:str):
        if not self.editable: return self.curs_fix()
        self.back_to_edit()
        if not wc: return
        if self.text_char_count == self.max_length: return
        self.update_cache()
        self.text_char_count += 1

        line_left = self.text_lines[self.text_curs_y][:self.text_curs_x]
        line_right = self.text_lines[self.text_curs_y][self.text_curs_x:]
        if ord(wc) in (curses.KEY_ENTER, input.ENTER, 13):
            self.text_lines.insert(self.text_curs_y + 1, line_right)
            self.text_lines[self.text_curs_y] = line_left
            self.text_curs_y += 1
            self.text_curs_x = 0
            self.screen_curs_y += 1
            self.screen_curs_x = 0
            if self.screen_curs_y >= self.text_view_height:
                self.inline_offset_cur += 1
            self.render()
        else:
            self.text_lines[self.text_curs_y] = line_left + wc + line_right
            self.curs_to_right()
    @debounce(1.6, enter=True, exit=False)
    def handle_exit(self, *args):
        input.stop()
        self.returnvalue = self.text
    @debounce(0.8, enter=True, exit=False)
    def handle_stop(self, *args):
        input.stop()
        if self.editable: self.text = self.value()
        self.returnvalue = self.value()
    def handle_enter(self, *args):
        self.input('\n')
    def handle_delete(self, *args):
        if not self.editable: return self.curs_fix()
        self.back_to_edit()
        self.update_cache()
        if self.text_curs_x > 0:
            self.curs_to_left(render=False)
            self.text_lines[self.text_curs_y] = \
                self.text_lines[self.text_curs_y][:self.text_curs_x] + self.text_lines[self.text_curs_y][self.text_curs_x+1:]
            self.render()
        elif self.text_curs_y > 0:
            self.curs_to_left(render=False)
            self.text_lines[self.text_curs_y] += self.text_lines[self.text_curs_y+1]
            self.text_lines.pop(self.text_curs_y+1)
            self.render()
        else:
            self.text_curs_x = 0
            self.text_curs_y = 0
            self.screen_curs_x = 0
            self.screen_curs_y = 0
            curses.stdscr.move(self.__screen_curs_base_y, self.__screen_curs_base_x)
    def handle_mouse(self, y, x, type):
        if (self.__screen_curs_min_y <= y) and (y < self.__screen_curs_max_y) and (self.__screen_curs_min_x <= x) and (x < self.__screen_curs_max_x):
            if type == input.SCROLL_DOWN:
                self.inline_offset_cur += 1
                self.render(only_scroll=True)
            elif type == input.SCROLL_UP:
                self.inline_offset_cur -= 1
                self.render(only_scroll=True)
            elif type == input.LEFT_CLICK:
                self.screen_curs_y = min(y-self.__screen_curs_base_y, len(self.buffer)-1)
                fragment = self.buffer[min(len(self.buffer)-1, self.screen_curs_y)] if self.buffer else ['', 0, 0]
                self.screen_curs_x = min(x-self.__screen_curs_base_x, string_width(fragment[0]))
                curs_string = split_bywidth(fragment[0], self.screen_curs_x)[0]
                self.screen_curs_x = string_width(curs_string)
                self.text_curs_y = fragment[1]
                self.text_curs_x = \
                    sum(len(str) for str in split_bywidth(self.text_lines[fragment[1]], self.text_view_width)[:fragment[2]])+len(curs_string)
                self.cache_editing = None
                self.render()
        else: return self.curs_fix()
    def curs_x_from_screen(self, inline_offset:int):
        line = split_bywidth(self.text_lines[self.text_curs_y], self.text_view_width)
        inline_x = split_bywidth(line[inline_offset], self.screen_curs_x)[0]
        return (sum(len(str) for str in line[:inline_offset]) + len(inline_x), string_width(inline_x))
    def curs_to_start(self, *args, render=True):
        self.curs_to(0, 0)
    def curs_to_end(self, *args, render=True):
        self.curs_to(len(self.text_lines)-1, len(self.text_lines[-1]))
    def curs_to_down(self, *args, render=True):
        self.back_to_edit()
        self.screen_curs_y += 1
        if self.screen_curs_y < len(self.buffer):
            self.text_curs_y = self.buffer[self.screen_curs_y][1]
            (self.text_curs_x, self.screen_curs_x) = self.curs_x_from_screen(self.buffer[self.screen_curs_y][2])
        elif self.buffer[-1][2]+1 < len(split_bywidth(self.text_lines[self.buffer[-1][1]], self.text_view_width)):
            self.text_curs_y = self.buffer[-1][1]
            (self.text_curs_x, self.screen_curs_x) = self.curs_x_from_screen(self.buffer[-1][2]+1)
            self.inline_offset_cur += 1
        elif self.buffer[-1][1]+1 < len(self.text_lines):
            self.text_curs_y = self.buffer[-1][1]+1
            (self.text_curs_x, self.screen_curs_x) = self.curs_x_from_screen(0)
            self.inline_offset_cur += 1
        else:
            self.screen_curs_y -= 1
        self.trigger('move')
        if render: self.render()
    def curs_to_up(self, *args, render=True):
        self.back_to_edit()
        self.screen_curs_y -= 1
        if self.screen_curs_y >= 0:
            self.text_curs_y = self.buffer[self.screen_curs_y][1]
            (self.text_curs_x, self.screen_curs_x) = self.curs_x_from_screen(self.buffer[self.screen_curs_y][2])
        elif self.buffer[0][2] > 0:
            self.text_curs_y = self.buffer[0][1]
            (self.text_curs_x, self.screen_curs_x) = self.curs_x_from_screen(self.buffer[0][2]-1)
            self.inline_offset_cur -= 1
        elif self.buffer[0][1] > 0:
            self.text_curs_y = self.buffer[0][1] - 1
            (self.text_curs_x, self.screen_curs_x) = self.curs_x_from_screen(-1)
            self.inline_offset_cur -= 1
        else:
            self.screen_curs_y += 1
        self.trigger('move')
        if render: self.render()
    def curs_to_left(self, *args, render=True):
        self.back_to_edit()
        if (self.text_curs_x > 0) or (self.text_curs_y > 0):
            if self.text_curs_x > 0:
                self.text_curs_x -= 1
                self.screen_curs_x -= string_width(self.text_lines[self.text_curs_y][self.text_curs_x])
                if self.screen_curs_x < 0:
                    self.screen_curs_y -= 1
                    if self.screen_curs_y >= 0:
                        self.screen_curs_x += string_width(self.buffer[self.screen_curs_y][0])
                    else:
                        self.screen_curs_x += string_width(self.text_lines[self.buffer[0][1]][self.buffer[0][2]-1])
                        self.inline_offset_cur -= 1
            else:
                self.text_curs_y -= 1
                self.text_curs_x = len(self.text_lines[self.text_curs_y])
                self.screen_curs_x = string_width(split_bywidth(self.text_lines[self.text_curs_y], self.text_view_width)[-1])
                self.screen_curs_y -= 1

            if self.screen_curs_y < 0:
                self.inline_offset_cur -= 1
            self.trigger('move')
        if render: self.render()
    def curs_to_right(self, *args, render=True):
        self.back_to_edit()
        if (self.text_curs_x < len(self.text_lines[self.text_curs_y])) or (self.text_curs_y+1 < len(self.text_lines)):
            if self.text_curs_x < len(self.text_lines[self.text_curs_y]):
                self.screen_curs_x += string_width(self.text_lines[self.text_curs_y][self.text_curs_x])
                self.text_curs_x += 1
                if self.screen_curs_x > self.text_view_width:
                    self.screen_curs_x -= string_width(self.buffer[self.screen_curs_y][0])
                    self.screen_curs_y += 1
            else:
                self.text_curs_y += 1
                self.text_curs_x = 0
                self.screen_curs_y += 1
                self.screen_curs_x = 0

            if self.screen_curs_y >= self.text_view_height:
                self.inline_offset_cur += 1
            self.trigger('move')
        if render: self.render()
    def curs_to(self, y:int, x:int):
        self.text_curs_y = y
        self.text_curs_x = x
        self.text_view_offset = y
        self.inline_offset_cur = 0
        line = split_bywidth(self.text_lines[y][:x], self.text_view_width)
        self.screen_curs_y = len(line)-1
        self.screen_curs_x = string_width(line[-1])%self.text_view_width
        self.render()
    def curs_fix(self):
        if (0 <= self.screen_curs_y) and (self.screen_curs_y < self.text_view_height) \
        and (0 <= self.screen_curs_x) and (self.screen_curs_x <= self.text_view_width):
            curses.stdscr.move(
                min(self.__screen_curs_max_y-1, max(self.__screen_curs_min_y+1, self.__screen_curs_base_y+self.screen_curs_y)),
                min(self.__screen_curs_max_x-1, max(self.__screen_curs_min_x+1, self.__screen_curs_base_x+self.screen_curs_x)),
            )

    def back_to_edit(self):
        if (getattr(self, 'cache_editing', None) is not None) and ((self.screen_curs_y<0) or (self.screen_curs_y>=self.text_view_height)):
            self.text_view_offset = self.cache_editing.text_view_offset
            self.inline_offset_max = self.cache_editing.inline_offset_max
            self.inline_offset_cur = self.cache_editing.inline_offset_cur
            self.screen_curs_x = self.cache_editing.screen_curs_x
            self.screen_curs_y = self.cache_editing.screen_curs_y
            self.buffer = self.cache_editing.buffer
        self.cache_editing = None
    def copy(self, *args):
        pyperclip.copy(self.value())
    def clear(self, *args):
        if not self.editable: return self.curs_fix()
        self.update('', write=False)
        self.render()
    def undo(self, *args):
        if (not self.editable) or (self.cache is None): return self.curs_fix()
        self.update(
            self.cache.text,
            self.cache.text_view_offset,
            self.cache.inline_offset_max,
            self.cache.inline_offset_cur,
            self.cache.screen_curs_x,
            self.cache.screen_curs_y,
            write=False,
        )
        self.render()
    @debounce(1.6, enter=True, exit=False)
    def update_cache(
        self,
        text:str=None,
        text_view_offset:int=None,
        inline_offset_max:int=None,
        inline_offset_cur:int=None,
        screen_curs_y:int=None,
        screen_curs_x:int=None,
    ):
        text = text if text is not None else self.value()
        if self.cache.text != text:
            self.cache.text = text
            self.cache.text_view_offset = text_view_offset if text_view_offset is not None else self.text_view_offset
            self.cache.inline_offset_max = inline_offset_max if inline_offset_max is not None else self.inline_offset_max
            self.cache.inline_offset_cur = inline_offset_cur if inline_offset_cur is not None else self.inline_offset_cur
            self.cache.screen_curs_x = screen_curs_x if screen_curs_x is not None else self.screen_curs_x
            self.cache.screen_curs_y = screen_curs_y if screen_curs_y is not None else self.screen_curs_y
    def update(
        self,
        text:str,
        text_view_offset:int=None,
        inline_offset_max:int=None,
        inline_offset_cur:int=None,
        screen_curs_y:int=None,
        screen_curs_x:int=None,
        write=True,
    ):
        if not self.editable: return self.curs_fix()
        text = str(text)[:self.max_length]
        if self.cache.text != text: self.update_cache(immediate=True)
        if write: self.text = text
        self.text_lines = text.splitlines() or ['']
        self.text_char_count = len(text)
        if None in (text_view_offset, inline_offset_max, inline_offset_cur , screen_curs_y, screen_curs_x):
            length = len(self.text_lines)
            fragments = splitstrings_bywidth(
                self.text_lines,
                self.text_view_width,
                max(0, length-self.text_view_height),
                length,
            )
            buffer = fragments[-min(self.text_view_height, len(fragments)):]
            (_, __offset, __line_offset) = buffer[0]
            self.buffer = buffer
        else:
            fragments = splitstrings_bywidth(
                self.text_lines,
                self.text_view_width,
                text_view_offset,
                min(len(self.text_lines),text_view_offset + self.text_view_height),
            )
            self.buffer = fragments[inline_offset_cur : min(len(fragments), inline_offset_cur + self.text_view_height)]
        self.text_view_offset = __offset if text_view_offset is None else text_view_offset
        self.inline_offset_max = inline_offset_max or len(split_bywidth(self.text_lines[self.text_view_offset], self.text_view_width))
        self.inline_offset_cur = __line_offset if inline_offset_cur is None else inline_offset_cur
        self.screen_curs_y = len(buffer)-1 if screen_curs_y is None else screen_curs_y
        self.screen_curs_x = string_width(buffer[-1][0]) if screen_curs_x is None else screen_curs_x
        self.rendered = False

class TokenCounter(Token):
    def __init__(self, window, y, x, init='0'):
        super().__init__()
        self.view = window
        self.y = y
        self.x = x
        self.view.addstr(y, x, init.center(6))
        self.value = init

    def update(self, text):
        def task(): self.set(self.count(text))
        threading.Thread(target=task).start()
    def set(self, value):
        self.value = value
        self.render()
    def render(self):
        self.view.addstr(self.y, self.x, str(self.value).center(6))

class CharCounter:
    def __init__(self, window, y, x, init='0'):
        self.view = window
        self.y = y
        self.x = x
        self.view.addstr(y, x, init.center(6))
        self.value = init
    def update(self,text):
        self.set(len(text))
    def set(self, value):
        self.value = value
        self.render()
    def render(self):
        self.view.addstr(self.y, self.x, str(self.value).center(6))

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
            self.char = getattr(self, 'char', CharCounter(editor_view, height//2, width - 7))
            self.token = getattr(self, 'token', TokenCounter(editor_view, height//2, width - 14))
            editor_view.addstr(height//2,width-8,'/')
        elif height < 5:
            self.char = getattr(self, 'char', CharCounter(editor_view, 2, width - 7))
            self.token = getattr(self, 'token', TokenCounter(editor_view, 1, width - 7))
            lineview = editor_view.derwin(height, 5, 0, 0)
            def updatelineview(*args):
                lineview.addstr(1,0, str(getattr(self, 'text_curs_y', 0)).center(5))
                lineview.addstr(2,0, str(len(getattr(self, 'text_lines', []))-getattr(self, 'text_curs_y', 0)-1).center(5))
        elif height < 6:
            self.char = getattr(self, 'char', CharCounter(editor_view, 3, width - 7))
            self.token = getattr(self, 'token', TokenCounter(editor_view, 1, width - 7))
            lineview = editor_view.derwin(height, 5, 0, 0)
            def updatelineview(*args):
                lineview.addstr(1,0, str(getattr(self, 'text_curs_y', 0)).center(5))
                lineview.addstr(3,0, str(len(getattr(self, 'text_lines', []))-getattr(self, 'text_curs_y', 0)-1).center(5))
        elif height < 12:
            self.char = getattr(self, 'char', CharCounter(editor_view, height//2-2, width - 7))
            self.token = getattr(self, 'token', TokenCounter(editor_view, height//2+1, width - 7))

            lineview = editor_view.derwin(height, 5, 0, 0)
            def updatelineview(*args):
                editor_view.addstr(height//2-1, width-7, 'token')
                editor_view.addstr(height//2, width-7, 'chars')
                lineview.addstr(height//2-1,0, '⭱'.center(5))
                lineview.addstr(height//2,0, '⭳'.center(5))
                lineview.addstr(height//2-2,0, str(getattr(self, 'text_curs_y', 0)).center(5))
                lineview.addstr(height//2+1,0, str(len(getattr(self, 'text_lines', []))-getattr(self, 'text_curs_y', 0)-1).center(5))
        else:
            self.left = 8
            self.right = 0
            padding = (height-12)//6
            self.char = getattr(self, 'char', CharCounter(editor_view, height//3+6+padding, 1))
            self.token = getattr(self, 'token', TokenCounter(editor_view, height//3+3+padding, 1))

            lineview = editor_view.derwin(height//3+2, 8, 0, 0)
            def updatelineview(*args):
                editor_view.addstr(height//3+2+padding, 1, 'token')
                editor_view.addstr(height//3+5+padding, 1, 'chars')
                lineview.addstr(height//3-2-padding,0, '⭱'.center(7))
                lineview.addstr(height//3-1-padding,0, '⭳'.center(7))
                lineview.addstr(height//3-3-padding,0, str(getattr(self, 'text_curs_y', 0)).center(7))
                lineview.addstr(height//3-padding,0, str(len(getattr(self, 'text_lines', []))-getattr(self, 'text_curs_y', 1)-1).center(7))

        def update_com_count():
            self.char.set(self.text_char_count)
            self.token.update(self.value())

        def update_com_view():
            if lineview: updatelineview()
            self.char.render()
            self.token.render()
            editor_view.refresh()

        self.update_com_view = update_com_view
        self.subscribe('change',update_com_count)
        self.subscribe('change',update_com_view)
        self.subscribe('move',update_com_view)
        
        update_com_view()
        editor_view.refresh()
        value = InputBox.edit(self, text, editable)
        editor_view.erase()
        editor_view.refresh()
        self.trigger('close')
        return value
    def render(self, only_scroll=False):
        super().render(only_scroll)
        self.update_com_view()