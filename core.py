from oy3opy.utils.string import uni_snippets, snippet_index, Token, string_width
import curses
import curses.textpad
import pyperclip
import threading

class InputBox:
    def __init__(self, window, top = 0, bottom = 0, right = 0, left = 0, padding_y = 0, padding_x = 1, text = '', listeners = {'change':[],'move':[]}, max_length = None, outline = 0, editable = True, release = 27):
        self.window = window
        self.listeners = listeners
        self.max_length = max_length
        self.editable = editable
        self.release = release
        self.outline = outline

        win_height, win_width = self.window.getmaxyx()
        self.width = win_width - right - left
        self.height = win_height - bottom - top

        # draw a box outline
        if self.height < 3:
            outline = 0
        self.container = self.window.derwin(self.height, self.width, top, left)

        # create a textpad
        self.view_height = self.height - outline*2 - padding_y*2
        self.view_width = self.width - outline*2 - padding_x*2
        self.view = self.window.derwin(self.view_height, self.view_width,  top + outline + padding_y, left + outline + padding_x)
        self.view.scrollok(True)
        self.wcy = top + outline + padding_y
        self.wcx = left + outline + padding_x
        self.update(text)
    
    def update(self, text):
        if type(text) != str:
            text = str(text)
        self.rendered = ''
        self.lines = text[:self.max_length].split('\n')
        self.count = len(text)
        self.tcy = 0 # text_cursor_y
        self.tcx = 0 # text_cursor_x
        self.additional = False
    def text(self):
        return '\n'.join(self.lines).strip()
    def cursor_set(self, y, x):
        self.tcy = y
        self.tcx = x
        self.render()
    def cursor_up(self):
        if self.tcy - 1 >= 0:
            self.tcy -= 1
            if self.tcx > len(self.lines[self.tcy]):
                self.tcx = len(self.lines[self.tcy])
            self.dispatch('move')
            self.render()
    def cursor_down(self):
        if self.tcy + 1 < len(self.lines):
            self.tcy += 1
            if self.tcx > len(self.lines[self.tcy]):
                self.tcx = len(self.lines[self.tcy])
            self.dispatch('move')
            self.render()
    def cursor_right(self):
        if self.tcx < len(self.lines[self.tcy]):
            self.tcx += 1
            self.dispatch('move')
            self.render()
        elif self.tcy + 1 < len(self.lines):
            self.tcy += 1
            self.tcx = 0
            self.dispatch('move')
            self.render()
    def cursor_left(self):
        if self.tcx - 1 >= 0:
            self.tcx -= 1
            self.dispatch('move')
            self.render()
        elif self.tcy - 1 >= 0:
            self.tcy -= 1
            self.tcx = len(self.lines[self.tcy])
            self.dispatch('move')
            self.render()
    def delete(self):
        if not self.editable:
            return
        self.additional = False
        if len(self.lines[self.tcy]) > 0:
            if (self.tcx > 0):
                self.lines[self.tcy] = self.lines[self.tcy][:max(0,self.tcx-1)] + self.lines[self.tcy][self.tcx:]
                self.count -= 1
                self.tcx -= 1
                self.dispatch('change')
                self.render()
            elif self.tcy - 1 >= 0:
                self.tcx = len(self.lines[self.tcy - 1])
                self.lines[self.tcy - 1] += self.lines.pop(self.tcy)
                self.count -= 1
                self.tcy -= 1
                self.dispatch('change')
                self.render()
        elif self.tcy > 0:
            self.lines.pop(self.tcy)
            self.count -= 1
            self.tcy -= 1
            self.tcx = len(self.lines[self.tcy])
            self.dispatch('change')
            self.render()
    def input(self, wc):
        if not self.editable:
            return
        if self.outline:
            self.container.box()
        if self.count == self.max_length:
            return 0
        self.count += 1
        self.additional = False
        if ord(wc) in (curses.KEY_ENTER, 10, 13):
            line_left = self.lines[self.tcy][:self.tcx]
            line_right = self.lines[self.tcy][self.tcx:]
            self.lines.insert(self.tcy + 1, line_right)
            self.lines[self.tcy] = line_left
            self.tcy += 1
            self.tcx = 0
        else:
            self.lines[self.tcy] = self.lines[self.tcy][:self.tcx] + wc + self.lines[self.tcy][self.tcx:]
            self.tcx += 1
        if (self.tcy == len(self.lines)-1) and (self.tcx == len(self.lines[self.tcy])):
            self.additional = True
        self.dispatch('change')
        self.render()
    def tty(self):
        curses.noecho()
        curses.cbreak()
        curses.curs_set(2)
        curses.raw()
        self.window.keypad(True)
    def close(self):
        self.container.erase()
        self.container.refresh()
    def edit(self):
        curses.savetty()
        self.container.erase()
        if self.outline:
            self.container.box()
        self.container.refresh()
        self.tty()
        self.window.move(self.wcy, self.wcx)
        if self.text:
            self.render()
            self.dispatch('change')
        cache = self.text()
        while True:
            wc = self.window.get_wch()
            if type(wc) == str:
                if wc == self.release or ord(wc) == self.release:
                    break
                if ord(wc) == 27:
                    self.close()
                    curses.resetty()
                    return ''
                if ord(wc) == 1:# Ctrl + A cursor to start
                    self.cursor_set(0,0)
                elif ord(wc) == 5:# Ctrl + E cursor to end
                    self.cursor_set(len(self.lines)-1, len(self.lines[-1]))
                elif ord(wc) == 24:# Ctrl + X clean
                    cache = self.text()
                    self.update('')
                    self.render()
                elif ord(wc) == 26:# Ctrl + Z restore
                    restore = self.text()
                    self.update(cache)
                    cache = restore
                    self.render()
                    self.cursor_set(len(self.lines)-1, len(self.lines[-1]))
                elif ord(wc) == 3:# Ctrl + C copy
                    pyperclip.copy(self.text()) # wsl2 to windows utf-8 to gbk copy failed
                elif ord(wc) in (curses.KEY_BACKSPACE, curses.ascii.DEL, 127):
                    cache = self.text()
                    self.delete()
                elif ord(wc) in (curses.KEY_ENTER, 10, 13, 22) or ord(wc)>=32:
                    cache = self.text()
                    self.input(wc)
            elif wc == self.release:
                break
            elif wc == curses.KEY_UP:
                self.cursor_up()
            elif wc == curses.KEY_DOWN:
                self.cursor_down()
            elif wc == curses.KEY_RIGHT:
                self.cursor_right()
            elif wc == curses.KEY_LEFT:
                self.cursor_left()

        self.close()
        curses.resetty()
        return self.text()
    def render(self):
        vxw = uni_snippets(self.lines[self.tcy][:self.tcx], self.view_width)
        vcy = len(vxw) - 1
        vcx = string_width(vxw[vcy][0])
        if self.additional and (vcx<=1):
            self.additional = False

        preload = []
        vyw = (self.view_height*3+1)//4 - 1
        for line in self.lines[max(0, self.tcy + vcy - vyw- 1): self.tcy]:
            preload += uni_snippets(line, self.view_width)
        vry = len(preload) + vcy
        lineview = uni_snippets(self.lines[self.tcy], self.view_width)
        preload += lineview
        for line in self.lines[self.tcy+1:min(len(self.lines), self.tcy + self.view_height)]:
            preload += uni_snippets(line, self.view_width)
        render_list = preload[max(0,vry - vyw) : min(len(preload), max(0,vry - vyw) + self.view_height)]

        willrender = str([st[0] for st in render_list])
        if willrender != self.rendered:
            if not self.additional:
                self.view.erase()
                self.rendered = willrender
            
            for i, line in enumerate(render_list):
                self.view.addstr(i, 0, line[0])
            self.view.refresh()
        self.window.move(self.wcy + snippet_index(render_list, lineview[vcy]), self.wcx + vcx)
    def dispatch(self, event):
        for listener in self.listeners[event]:
            listener(self)
    def on(self,event,listener):
        self.listeners[event].append(listener)

class TokenCounter(Token):
    def __init__(self, window, y, x, init='0'):
        super().__init__()
        self.window = window
        self.view = self.window.derwin(1, 8,  y, x)
        self.view.addstr(0,1,init.center(6))
    def update(self,text):
        def task():
            self.view.addstr(0,1,str(self.count(text)).center(6))
        threading.Thread(target=task).start()
    def set(self,value):
        self.view.addstr(0,1,str(value).center(6))

class CharCounter:
    def __init__(self, window, y, x, init='0'):
        self.window = window
        self.view = self.window.derwin(1, 8,  y, x)
        self.view.addstr(0,1,init.center(6))
    def update(self,text):
        self.view.addstr(0,1,str(len(text)).center(6))
    def set(self,value):
        self.view.addstr(0,1,str(value).center(6))

class Editor(InputBox):
    def __init__(self, window, top = 0, bottom = 0, right = 0, left = 0, padding_y = 0, padding_x = 1, text = '', listeners = {'change':[],'move':[]}, max_length = None, outline = 1, editable = True, release = 27):
        self.window = window
        self.top = top
        self.bottom = bottom
        self.right = right
        self.left = left
        self.padding_y = padding_y
        self.padding_x = padding_x
        self._text = text
        self.listeners = listeners
        self.max_length = max_length
        self.outline = outline
        self.editable = editable
        self.release = release

    def close(self):
        super().close()
        self.window.erase()
        self.window.refresh()
    def edit(self):
        self.window.erase()
        win_height, win_width = self.window.getmaxyx()
        width = win_width - self.right - self.left
        height = win_height - self.bottom - self.top
        view = self.window.derwin(height, width, self.top, self.left)
        lineview = None
        if height < 4:
            super().__init__(view,0,0,15,0,self.padding_y,self.padding_x,self._text,self.listeners,self.max_length,self.outline)
            self.char = CharCounter(view, height//2, width - 8)
            view.addstr(height//2,width-8,'/')
            self.token = TokenCounter(view, height//2, width - 15)
        elif height < 5:
            super().__init__(view,0,0,8,5,self.padding_y,self.padding_x,self._text,self.listeners,self.max_length,self.outline)
            self.char = CharCounter(view, 2, width - 8)
            self.token = TokenCounter(view, 1, width - 8)
            lineview = view.derwin(height, 5, 0, 0)
            def updatelineview(_):
                lineview.addstr(1,0, str(self.tcy).center(5))
                lineview.addstr(2,0, str(len(self.lines)-self.tcy - 1).center(5))
        elif height < 6:
            super().__init__(view,0,0,8,5,self.padding_y,self.padding_x,self._text,self.listeners,self.max_length,self.outline)
            self.char = CharCounter(view, 3, width - 8)
            self.token = TokenCounter(view, 1, width - 8)
            lineview = view.derwin(height, 5, 0, 0)
            def updatelineview(_):
                lineview.addstr(1,0, str(self.tcy).center(5))
                lineview.addstr(3,0, str(len(self.lines)-self.tcy - 1).center(5))
        elif height < 12:
            super().__init__(view,0,0,8,5,self.padding_y,self.padding_x,self._text,self.listeners,self.max_length,self.outline)
            self.char = CharCounter(view, height//2-2, width - 8)
            self.token = TokenCounter(view, height//2+1, width - 8)

            view.addstr(height//2-1, width-7, 'token')
            view.addstr(height//2, width-7, 'chars')
            lineview = view.derwin(height, 5, 0, 0)
            lineview.addstr(height//2-1,0, '⭱'.center(5))
            lineview.addstr(height//2,0, '⭳'.center(5))
            def updatelineview(_):
                lineview.addstr(height//2-2,0, str(self.tcy).center(5))
                lineview.addstr(height//2+1,0, str(len(self.lines)-self.tcy - 1).center(5))
        else:
            super().__init__(view,0,0,0,8,self.padding_y,self.padding_x,self._text,self.listeners,self.max_length,self.outline)
            padding = (height-12)//6
            self.char = CharCounter(view, height//3+6+padding, 0)
            self.token = TokenCounter(view, height//3+3+padding, 0)
            
            view.addstr(height//3+2+padding, 1, 'token')
            view.addstr(height//3+5+padding, 1, 'chars')
            lineview = view.derwin(height//3+2, 8, 0, 0)
            lineview.addstr(height//3-2-padding,0, '⭱'.center(7))
            lineview.addstr(height//3-1-padding,0, '⭳'.center(7))
            def updatelineview(_):
                lineview.addstr(height//3-3-padding,0, str(self.tcy).center(7))
                lineview.addstr(height//3-padding,0, str(len(self.lines)-self.tcy - 1).center(7))
            
        def updatecountview(_):
            self.char.set(self.count)
            self.token.update(self.text())

        self.on('change',updatecountview)
        if lineview:
            updatelineview(None)
            self.on('change',updatelineview)
            self.on('move',updatelineview)
        self.window.refresh()
        return super().edit()