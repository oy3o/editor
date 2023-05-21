from oy3opy.utils.string import uni_snippets, snippet_index, Token, string_width
import curses
import curses.textpad
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
        if self.outline:
            self.container.box()
        self.container.refresh()

        # create a textpad
        self.view_height = self.height - outline*2 - padding_y*2
        self.view_width = self.width - outline*2 - padding_x*2
        self.view = self.window.derwin(self.view_height, self.view_width,  top + outline + padding_y, left + outline + padding_x)
        self.view.scrollok(True)
        self.rendered = ''
        self.lines = text[:self.max_length].split('\n')
        self.count = 0
        self.tcy = 0 # text_cursor_y
        self.tcx = 0 # text_cursor_x
        self.wcy = top + outline + padding_y
        self.wcx = left + outline + padding_x
    def update(self, text):
        self.lines = text[:self.max_length].split('\n')
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
            self.lines[self.tcy] = self.lines[self.tcy][:max(0,self.tcx-1)] + self.lines[self.tcy][self.tcx:]
            self.count -= 1
            self.tcx -= 1
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
    def edit_handler(self, wc):
        self.window.refresh()
        if wc == curses.KEY_UP:
            self.cursor_up()
        elif wc == curses.KEY_DOWN:
            self.cursor_down()
        elif wc == curses.KEY_RIGHT:
            self.cursor_right()
        elif wc == curses.KEY_LEFT:
            self.cursor_left()
        elif ord(wc) in (curses.KEY_BACKSPACE, curses.ascii.DEL, 127) or wc in ('^?'):
            self.delete()
        else:
            self.input(wc)
    def edit(self):
        curses.noecho()
        curses.cbreak()
        self.window.keypad(True)
        self.window.move(self.wcy, self.wcx)
        wc = ' '
        while not ((wc == self.release) or ((type(wc)==str) and (ord(wc) == self.release))):
            wc = self.window.get_wch()
            self.edit_handler(wc)
        self.container.erase()
        self.container.refresh()
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
        win_height, win_width = window.getmaxyx()
        width = win_width - right - left
        height = win_height - bottom - top
        view = window.derwin(height, width, top, left)
        lineview = None

        if height < 4:
            super().__init__(view,0,0,15,0,padding_y,padding_x,text,listeners,max_length,outline)
            self.char = CharCounter(view, height//2, width - 8)
            view.addstr(height//2,width-8,'/')
            self.token = TokenCounter(view, height//2, width - 15)
        elif height < 5:
            super().__init__(view,0,0,8,5,padding_y,padding_x,text,listeners,max_length,outline)
            self.char = CharCounter(view, 2, width - 8)
            self.token = TokenCounter(view, 1, width - 8)
            lineview = view.derwin(height, 5, 0, 0)
            def updatelineview(_):
                lineview.addstr(1,0, str(self.tcy).center(5))
                lineview.addstr(2,0, str(len(self.lines)-self.tcy - 1).center(5))
        elif height < 6:
            super().__init__(view,0,0,8,5,padding_y,padding_x,text,listeners,max_length,outline)
            self.char = CharCounter(view, 3, width - 8)
            self.token = TokenCounter(view, 1, width - 8)
            lineview = view.derwin(height, 5, 0, 0)
            def updatelineview(_):
                lineview.addstr(1,0, str(self.tcy).center(5))
                lineview.addstr(3,0, str(len(self.lines)-self.tcy - 1).center(5))
        elif height < 12:
            super().__init__(view,0,0,8,5,padding_y,padding_x,text,listeners,max_length,outline)
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
            super().__init__(view,0,0,0,8,padding_y,padding_x,text,listeners,max_length,outline)
            self.char = CharCounter(view, height//3+6, 0)
            self.token = TokenCounter(view, height//3+3, 0)

            view.addstr(height//3+2, 1, 'token')
            view.addstr(height//3+5, 1, 'chars')
            lineview = view.derwin(height//3+2, 8, 0, 0)
            lineview.addstr(height//3-2,0, '⭱'.center(7))
            lineview.addstr(height//3-1,0, '⭳'.center(7))
            def updatelineview(_):
                lineview.addstr(height//3-3,0, str(self.tcy).center(7))
                lineview.addstr(height//3,0, str(len(self.lines)-self.tcy - 1).center(7))
            

        def updatecountview(_):
            self.char.set(self.count)
            self.token.update(self.text())

        self.on('change',updatecountview)
        if lineview:
            updatelineview(None)
            self.on('change',updatelineview)
            self.on('move',updatelineview)
