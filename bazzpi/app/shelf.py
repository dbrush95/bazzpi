#!/usr/bin/python3
"""Native Qt shelf. No HTTP server or remote executable bridge."""
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import time
from PyQt5 import QtCore as C, QtGui as G, QtWidgets as W
from model import Store, SYSTEMS, host, sunshine_url, stream_args, pin_record, verify_pin

ADMIN='/usr/local/sbin/bazzpi-admin'
APPS=['Play','Desktop','RetroPie','Game Pass','Browser','Files','Settings']
PALETTES={'Cloud':('#eaf0fa','#c8dafa','#f6ede5'), 'Ocean':('#092d45','#245c7c','#77b5bc'),
          'Dusk':('#292943','#665480','#d2a7a0'), 'Meadow':('#c1d9c5','#7ea89c','#f0e5c7')}

def label(text,size=12):
    w=W.QLabel(text); w.setTextFormat(C.Qt.PlainText); w.setWordWrap(True); w.setStyleSheet(f'font-size:{round(size*1.25)}px;'); return w

def button(text,callback):
    b=W.QPushButton(text); b.setCursor(C.Qt.PointingHandCursor); b.clicked.connect(callback); return b

def line(value='',password=False):
    w=W.QLineEdit(str(value))
    if password: w.setEchoMode(W.QLineEdit.Password)
    return w

def combo(items,current):
    w=W.QComboBox(); w.addItems([str(x) for x in items]); w.setCurrentText(str(current)); return w

def icon(name,color='#3377ef'):
    # Original simple vector line icons, rendered locally without web fonts/assets.
    p=G.QPixmap(48,48); p.fill(C.Qt.transparent)
    q=G.QPainter(p); q.setRenderHint(G.QPainter.Antialiasing)
    q.setPen(G.QPen(G.QColor(color),2.5,C.Qt.SolidLine,C.Qt.RoundCap,C.Qt.RoundJoin))
    if name=='Play':
        q.drawRoundedRect(7,13,34,23,8,8); q.drawLine(13,24,23,24); q.drawLine(18,19,18,29)
        q.drawEllipse(30,20,2,2); q.drawEllipse(34,26,2,2)
    elif name=='Desktop':
        q.drawRoundedRect(6,8,36,25,3,3); q.drawLine(24,33,24,40); q.drawLine(16,40,32,40)
    elif name=='RetroPie':
        q.drawRoundedRect(8,31,32,9,3,3); q.drawLine(24,18,24,32); q.drawEllipse(18,6,12,12)
    elif name=='Browser':
        q.drawEllipse(7,7,34,34); q.drawEllipse(17,7,14,34); q.drawLine(8,24,40,24)
    elif name=='Files':
        path=G.QPainterPath(); path.moveTo(6,15); path.lineTo(6,38); path.lineTo(42,38)
        path.lineTo(42,15); path.lineTo(24,15); path.lineTo(19,9); path.lineTo(6,9); path.closeSubpath(); q.drawPath(path)
    elif name=='Game Pass':
        path=G.QPainterPath(); path.moveTo(13,35); path.cubicTo(0,33,5,18,14,20)
        path.cubicTo(15,5,34,6,35,21); path.cubicTo(47,20,47,35,35,35); path.closeSubpath(); q.drawPath(path)
    elif name=='Settings':
        q.drawEllipse(10,10,28,28); q.drawEllipse(19,19,10,10)
        for a,b,c,d in [(24,4,24,10),(24,38,24,44),(4,24,10,24),(38,24,44,24),(9,9,14,14),(34,34,39,39),(9,39,14,34),(34,14,39,9)]: q.drawLine(a,b,c,d)
    else:
        for x in (9,27):
            for y in (9,27): q.drawRoundedRect(x,y,12,12,2,2)
    q.end(); return G.QIcon(p)

class Job(W.QDialog):
    def __init__(self,owner,title,args,intro='',done=None):
        super().__init__(owner); self.setWindowTitle(title); self.resize(760,480)
        self.setAttribute(C.Qt.WA_DeleteOnClose,False)
        l=W.QVBoxLayout(self); l.addWidget(label(intro or title,13))
        self.output=W.QPlainTextEdit(); self.output.setReadOnly(True); l.addWidget(self.output)
        self.status=label('Running…'); l.addWidget(self.status)
        self.closebtn=button('Close',self.close); self.closebtn.setEnabled(False); l.addWidget(self.closebtn)
        self.proc=C.QProcess(self); self.proc.setProcessChannelMode(C.QProcess.MergedChannels)
        self.proc.readyReadStandardOutput.connect(lambda:self.output.appendPlainText(bytes(self.proc.readAllStandardOutput()).decode(errors='replace').rstrip()))
        def finish(code,status):
            self.status.setText('Finished.' if code==0 else f'Failed (exit {code}). See details above.')
            self.closebtn.setEnabled(True)
            if done: done(code,self.output.toPlainText())
        self.proc.finished.connect(finish)
        self.proc.errorOccurred.connect(lambda e:(self.status.setText(self.proc.errorString()),self.closebtn.setEnabled(True)))
        self.proc.start(args[0],args[1:]); self.show()
    def closeEvent(self,event):
        if self.proc.state()!=C.QProcess.NotRunning: event.ignore()
        else: event.accept()

class Desktop(W.QWidget):
    def __init__(self,shelf):
        super().__init__(); self.shelf=shelf; self.setWindowTitle('Bazzpi')
        self.setWindowFlags(C.Qt.FramelessWindowHint|C.Qt.WindowStaysOnBottomHint)
        self.wall=G.QPixmap(); self.refresh()
    def refresh(self):
        self.wall=G.QPixmap(self.shelf.store.settings.get('wallpaper_file','')); self.update()
    def paintEvent(self,event):
        p=G.QPainter(self); p.setRenderHint(G.QPainter.Antialiasing)
        s=self.shelf.store.settings; dark=s['theme']=='dark'
        colors=PALETTES.get(s['wallpaper'],PALETTES['Cloud'])
        if dark and s['wallpaper']=='Cloud': colors=('#171e2d','#243248','#343849')
        g=G.QLinearGradient(0,0,self.width(),self.height())
        for stop,col in zip((0,.6,1),colors):g.setColorAt(stop,G.QColor(col))
        p.fillRect(self.rect(),g)
        if not self.wall.isNull():
            img=self.wall.scaled(self.size(),C.Qt.KeepAspectRatioByExpanding,C.Qt.SmoothTransformation)
            p.drawPixmap((self.width()-img.width())//2,(self.height()-img.height())//2,img)
        else:
            p.setPen(C.Qt.NoPen)
            p.setBrush(G.QColor(255,255,255,10 if dark else 48))
            p.drawEllipse(C.QRectF(self.width()*.45,-self.height()*.45,self.width()*.9,self.width()*.9))
            p.setBrush(G.QColor(255,255,255,8 if dark else 40))
            p.drawEllipse(C.QRectF(-self.width()*.15,self.height()*.55,self.width()*.8,self.width()*.8))
        p.setPen(G.QColor('#b7c7e5' if dark else '#48638a')); p.setFont(G.QFont('DejaVu Sans',14,G.QFont.Bold))
        p.drawText(42,52,'bazzpi'); p.setFont(G.QFont('DejaVu Sans',10)); p.drawText(42,77,'Your living room. Your way.')
    def closeEvent(self,e):e.ignore()

class Gate(W.QDialog):
    def __init__(self,shelf):
        super().__init__(); self.shelf=shelf
        self.setWindowFlags(C.Qt.FramelessWindowHint|C.Qt.WindowStaysOnTopHint)
        self.setWindowTitle('Bazzpi profile'); self.setObjectName('Gate')
        outer=W.QVBoxLayout(self); outer.addStretch(); row=W.QHBoxLayout(); row.addStretch()
        card=W.QFrame(); card.setObjectName('Card'); card.setFixedWidth(430); l=W.QVBoxLayout(card); l.setContentsMargins(36,36,36,36); l.setSpacing(18)
        profile=shelf.store.data['profile']; self.first=profile is None
        l.addWidget(label('bazzpi',30)); l.addWidget(label('Make yourself at home.' if self.first else 'Welcome back, '+profile['name'],20))
        self.name=line(); self.name.setPlaceholderText('Your name')
        if self.first: l.addWidget(self.name)
        self.pin=line(password=True); self.pin.setMaxLength(4); self.pin.setValidator(G.QRegularExpressionValidator(C.QRegularExpression('[0-9]{0,4}')))
        self.pin.setPlaceholderText('4-digit code (optional)' if self.first else 'Enter your 4-digit code'); l.addWidget(self.pin)
        self.error=label(''); l.addWidget(self.error)
        l.addWidget(button('Create profile' if self.first else 'Unlock',self.submit))
        keypad=W.QGridLayout()
        for i,digit in enumerate('1234567890'):
            b=button(digit,lambda _,d=digit:self.pin.setText((self.pin.text()+d)[:4])); keypad.addWidget(b,i//3,i%3)
        keypad.addWidget(button('⌫',lambda:self.pin.backspace()),3,1); l.addLayout(keypad)
        l.addWidget(label('This profile code locks the shelf. It is separate from your Linux password.',10))
        row.addWidget(card); row.addStretch(); outer.addLayout(row); outer.addStretch()
        self.pin.returnPressed.connect(self.submit)
    def submit(self):
        try:
            if self.first:self.shelf.store.create_profile(self.name.text(),self.pin.text())
            elif not self.shelf.store.unlock(self.pin.text()):
                delay=max(0,int(self.shelf.store.data['retry_at']-time.time())+1)
                self.error.setText(f'Try again in {delay} seconds.' if delay else 'Incorrect code. Try again.'); self.pin.clear(); return
            self.shelf.unlocked=True; self.hide(); self.shelf.show_shelf()
        except ValueError as e:self.error.setText(str(e))
    def reject(self):pass
    def closeEvent(self,e):e.ignore()

class Shelf:
    def __init__(self,app,store):
        self.app=app; self.store=store; self.windows=[]; self.jobs=[]; self.unlocked=False; self.launcher=None
        self.apply_theme(); self.desktop=Desktop(self)
        self.dock=W.QWidget(); self.dock.setObjectName('Dock'); self.dock.setWindowTitle('Bazzpi shelf')
        self.dock.setWindowFlags(C.Qt.FramelessWindowHint|C.Qt.Tool|C.Qt.WindowStaysOnTopHint)
        row=W.QHBoxLayout(self.dock); row.setContentsMargins(16,8,16,8); row.setSpacing(8)
        for name in ['Launcher']+APPS:
            b=button('',lambda _,n=name:self.open(n)); b.setIcon(icon(name)); b.setIconSize(C.QSize(32,32)); b.setFixedSize(54,48); b.setToolTip(name); b.setAccessibleName(name); row.addWidget(b)
        row.addStretch()
        row.addWidget(button('Windows',self.window_menu))
        row.addWidget(button('Lock',self.lock))
        self.clock=button('',lambda:self.open('Settings')); self.clock.setMinimumWidth(116);row.addWidget(self.clock)
        self.timer=C.QTimer(); self.timer.timeout.connect(lambda:self.clock.setText(C.QDateTime.currentDateTime().toString('h:mm AP'))); self.timer.start(1000)
        self.clock.setText(C.QDateTime.currentDateTime().toString('h:mm AP'))
        self.desktop.setGeometry(app.primaryScreen().geometry()); self.desktop.show()
        app.primaryScreen().geometryChanged.connect(lambda _:self.position())
        profile=store.data['profile']
        self.gate=None
        if profile is None or profile['pin'] is not None:self.lock()
        else:self.unlocked=True; self.show_shelf()
        self.controller=Controller(self)
    def position(self):
        g=self.app.primaryScreen().geometry(); self.desktop.setGeometry(g)
        self.dock.setGeometry(g.x(),g.bottom()-71,g.width(),72)
    def show_shelf(self):
        self.position(); self.dock.show(); self.dock.raise_(); self.set_dock_properties(); self.restore_display()
    def set_dock_properties(self):
        try:
            from Xlib import display, Xatom
            d=display.Display(); w=d.create_resource_object('window',int(self.dock.winId()))
            w.change_property(d.intern_atom('_NET_WM_WINDOW_TYPE'),Xatom.ATOM,32,[d.intern_atom('_NET_WM_WINDOW_TYPE_DOCK')])
            w.change_property(d.intern_atom('_NET_WM_STRUT_PARTIAL'),Xatom.CARDINAL,32,[0,0,0,72,0,0,0,0,0,0,0,self.dock.width()-1]);d.flush();d.close()
        except Exception:pass # Offscreen preview has no X server.
    def apply_theme(self):
        dark=self.store.settings['theme']=='dark'
        bg,card,fg,border,field=('#192131','#222c3e','#edf3ff','#40516b','#2d3a50') if dark else ('#eef3fa','#ffffff','#213653','#cbd7e8','#f1f5fc')
        self.app.setStyle('Fusion')
        palette=G.QPalette()
        for role,col in [(G.QPalette.Window,bg),(G.QPalette.WindowText,fg),(G.QPalette.Base,card),
                         (G.QPalette.AlternateBase,field),(G.QPalette.Text,fg),(G.QPalette.Button,field),
                         (G.QPalette.ButtonText,fg),(G.QPalette.Highlight,'#3377ef'),(G.QPalette.HighlightedText,'#ffffff')]:
            palette.setColor(role,G.QColor(col))
        self.app.setPalette(palette)
        self.app.setStyleSheet(f'''
        QWidget {{font-family: DejaVu Sans; font-size:14px; color:{fg};}}
        QDialog, #Gate {{background:{bg};}}
        #Card,#Dock {{background:{card}; border:1px solid {border}; border-radius:20px;}}
        QPushButton {{background:{field};border:1px solid {border};border-radius:10px;padding:10px 15px;min-height:20px;}}
        QToolButton {{background:{field};border:1px solid {border};border-radius:12px;padding:8px;}}
        QToolButton:focus {{border:2px solid #357bea;}}
        QPushButton:hover,QToolButton:hover {{background:#c9dcfa;color:#18345c;}}
        QPushButton:focus {{border:2px solid #357bea;}}
        QPushButton:disabled {{color:#8190a7;}}
        QLineEdit,QComboBox,QSpinBox,QPlainTextEdit,QListWidget,QTableWidget {{background:{card};border:1px solid {border};border-radius:8px;padding:8px;}}
        QTabWidget::pane {{border:1px solid {border};background:{bg};}}
        QTabBar::tab {{background:{field};padding:12px;border-radius:6px;}}
        QTabBar::tab:selected {{background:#3377ef;color:white;}}
        QHeaderView::section {{background:{field};padding:8px;border:0;}}
        QScrollArea {{border:0;background:{bg};}}
        QToolTip {{background:{card};color:{fg};}}
        ''')
    def lock(self):
        if any(j.proc.state()!=C.QProcess.NotRunning for j in self.jobs):
            self.info('Finish or quit the active task before locking.');return
        for w in self.windows:w.hide()
        self.dock.hide(); self.unlocked=False
        self.gate=Gate(self); self.gate.showFullScreen(); self.gate.raise_();self.gate.activateWindow()
    def info(self,text):W.QMessageBox.information(self.dock,'Bazzpi',text)
    def dialog(self,title,width=800,height=550):
        d=W.QDialog(); d.setWindowTitle(title); d.setWindowFlags(d.windowFlags()|C.Qt.WindowMinMaxButtonsHint); d.resize(width,height)
        l=W.QVBoxLayout(d); l.setContentsMargins(26,24,26,24); l.setSpacing(14)
        l.addWidget(label(title,23));self.windows.append(d);d.show();return d,l
    def job(self,title,args,intro='',done=None):
        j=Job(None,title,args,intro,done);self.jobs.append(j);return j
    def start(self,args):
        if not C.QProcess.startDetached(args[0],args[1:]):self.info('Could not start '+args[0]+'. Check the install log in /var/log/bazzpi.')
    def admin(self,action,*args):return self.job('System setting',['sudo',ADMIN,action]+list(args))
    def terminal(self,action):self.start(['xterm','-T','Bazzpi settings','-e','sudo',ADMIN,action])
    def open(self,name):
        if not self.unlocked:return
        if self.launcher and name!='Launcher':self.launcher.hide()
        {'Launcher':self.launch,'Play':self.play,'Desktop':self.pc_desktop,'RetroPie':self.retro,
         'Game Pass':self.gamepass,'Browser':lambda:self.browser('https://www.google.com'),
         'Files':self.files,'Settings':self.settings}[name]()
    def browser(self,url):self.start([shutil.which('chromium') or 'chromium-browser','--new-window',url])
    def launch(self):
        if self.launcher and self.launcher.isVisible():self.launcher.hide();return
        d=W.QDialog(self.dock,C.Qt.Popup);d.setObjectName('Card');d.resize(520,430);l=W.QVBoxLayout(d);l.setContentsMargins(22,22,22,22);l.setSpacing(18);l.setAlignment(C.Qt.AlignTop)
        search=line();search.setPlaceholderText('Search your apps');search.setFixedHeight(44);l.addWidget(search);grid=W.QGridLayout();grid.setSpacing(10);l.addLayout(grid)
        tiles=[]
        for i,name in enumerate(APPS):
            b=W.QToolButton();b.setText(name);b.clicked.connect(lambda _,n=name:self.open(n));b.setToolButtonStyle(C.Qt.ToolButtonTextUnderIcon);b.setIcon(icon(name));b.setIconSize(C.QSize(40,40));b.setFixedSize(148,94);b.setCursor(C.Qt.PointingHandCursor);grid.addWidget(b,i//3,i%3);tiles.append((name,b))
        search.textChanged.connect(lambda text:[b.setVisible(text.lower() in name.lower()) for name,b in tiles])
        d.move(16,max(10,self.dock.y()-450));self.launcher=d;d.show();search.setFocus()
    def window_menu(self):
        menu=W.QMenu(self.dock)
        for w in self.windows+self.jobs:
            menu.addAction(w.windowTitle(),lambda w=w:(w.showNormal(),w.raise_(),w.activateWindow()))
        menu.addAction('Cycle all windows (Alt+Tab)',lambda:self.start(['xdotool','key','alt+Tab']))
        menu.exec_(G.QCursor.pos())
    def save_host(self,edit):
        self.store.settings['host']=host(edit.text());self.store.save();return self.store.settings['host']
    def play(self):
        d,l=self.dialog('Play · your Bazzite PC');f=W.QFormLayout();l.addLayout(f)
        pc=line(self.store.settings['host']);pc.setPlaceholderText('192.168.1.100 or bazzite.local');f.addRow('PC address',pc)
        l.addWidget(label('Pair on your home network. Sunshine will ask for the PIN shown here. Its local HTTPS certificate may show a browser warning.',11))
        def pair():
            try:
                address=self.save_host(pc);pin=f'{secrets.randbelow(10000):04d}'
                self.job('Pair with Sunshine',['moonlight-qt','pair','--pin',pin,address],f'Enter PIN {pin} at {sunshine_url(address)}. Leave this window open until pairing finishes.')
            except ValueError as e:self.info(str(e))
        def sunshine():
            try:self.browser(sunshine_url(self.save_host(pc)))
            except ValueError as e:self.info(str(e))
        row=W.QHBoxLayout();row.addWidget(button('Pair PC',pair));row.addWidget(button('Open Sunshine',sunshine));l.addLayout(row)
        apps=W.QListWidget();apps.addItems(['Steam','Desktop']);l.addWidget(apps)
        custom=line('Steam');f2=W.QFormLayout();f2.addRow('Sunshine app',custom);l.addLayout(f2)
        apps.currentTextChanged.connect(custom.setText)
        def refresh():
            try:
                address=self.save_host(pc)
                def done(code,out):
                    if code==0:
                        names=[x.strip() for x in out.splitlines() if x.strip() and not x.startswith(('Establishing','Loading','00:','Warning','Qt'))]
                        apps.clear();apps.addItems(names)
                self.job('Sunshine apps',['moonlight-qt','list',address],done=done)
            except ValueError as e:self.info(str(e))
        def stream():
            try:self.save_host(pc);self.stream(custom.text())
            except ValueError as e:self.info(str(e))
        row=W.QHBoxLayout();row.addWidget(button('Refresh apps',refresh));row.addWidget(button('Launch',stream));l.addLayout(row)
        l.addWidget(label('Quit: Ctrl+Alt+Shift+Q · or hold Start + Select + LB + RB\nDefault picture: 1080p · 60 fps · H.264 · 20 Mb/s',11))
    def stream(self,name):
        try:
            s=self.store.settings;args=stream_args(s,name)
            if s['stream_tty']:
                args=['sudo',ADMIN,'stream',s['host'],name,s['resolution'],str(s['fps']),str(s['bitrate']),s['codec']]
            else:args=['moonlight-qt']+args
            self.job('Streaming '+name,args,'The stream opens full screen. Quit it to return to your shelf.')
        except ValueError as e:self.info(str(e))
    def pc_desktop(self):
        if self.store.settings['desktop_mode']=='Moonlight':self.stream(self.store.settings['desktop_app'])
        else:
            address=self.store.settings['rdp_host'] or self.store.settings['host']
            try:address=host(address)
            except ValueError as e:self.info(str(e));return
            # Remmina handles credential prompts and certificate validation; no password in argv.
            from urllib.parse import quote
            self.start(['remmina','-c','rdp://'+quote(address,safe='')])
    def gamepass(self):
        d,l=self.dialog('Game Pass · cloud gaming',600,310)
        l.addWidget(label('For this setup, use Game Pass Ultimate and a compatible controller. Games run in the cloud; nothing is emulated or installed on the Pi.'))
        l.addWidget(label('Chromium on Raspberry Pi is not a guaranteed supported Xbox Cloud Gaming device. Service, browser and region restrictions can apply.',11))
        l.addWidget(button('Open Xbox Cloud Gaming',lambda:self.browser('https://www.xbox.com/play')))
    def files(self):
        d,l=self.dialog('Files',620,350)
        l.addWidget(button('Home · /home/play',lambda:self.start(['pcmanfm',str(Path.home())])))
        l.addWidget(button('SD card · /',lambda:self.start(['pcmanfm','/'])))
        l.addWidget(button('USB drives · /media/play',lambda:self.start(['pcmanfm','/media/play'])))
        def share():
            s=self.store.settings['share']
            if not s.startswith('smb://'):self.info('Set an smb://PC/share address in Settings → Connections.');return
            self.start(['pcmanfm',s])
        l.addWidget(button('Bazzite network share',share))
    def retro(self):
        d,l=self.dialog('RetroPie · native on this Pi',1000,690)
        row=W.QHBoxLayout();row.addWidget(button('Launch EmulationStation',lambda:self.admin('retro')))
        def install():
            if W.QMessageBox.question(d,'Native build','Build RetroPie and the requested emulator modules now? This can take hours. Keep power connected.')==W.QMessageBox.Yes:
                self.admin('retropie-install')
        row.addWidget(button('Install / retry emulator builds',install));l.addLayout(row)
        l.addWidget(label('Connect a controller to the Pi. Copy your own games to the folders below. No games or BIOS files are included. “Full speed” is a target; demanding games and settings vary.',11))
        table=W.QTableWidget(len(SYSTEMS),4);table.setHorizontalHeaderLabels(['System','Pi 4 target','Your game folder','Installed config']);table.setEditTriggers(W.QAbstractItemView.NoEditTriggers)
        table.horizontalHeader().setSectionResizeMode(W.QHeaderView.ResizeToContents)
        for i,(name,folder,module) in enumerate(SYSTEMS):
            ready=Path('/opt/retropie/configs',folder,'emulators.cfg').exists()
            for j,v in enumerate((name,'Full speed' if i<26 else 'Hit or miss','~/RetroPie/roms/'+folder,'Present' if ready else 'Not installed')):table.setItem(i,j,W.QTableWidgetItem(v))
        table.cellDoubleClicked.connect(lambda r,c:self.start(['pcmanfm',str(Path.home()/'RetroPie/roms'/SYSTEMS[r][1])]))
        l.addWidget(table)
        l.addWidget(label('Double-click a system to open its folder. PC Engine CD shares pcengine. Nintendo DS uses DeSmuME on ARM64 and can be especially slow. Some systems need your own BIOS files in ~/RetroPie/BIOS.',11))
        l.addWidget(button('View build results',lambda:self.view_file('/var/log/bazzpi/retropie-modules.tsv')))
    def view_file(self,path):
        d,l=self.dialog('Build results');text=W.QPlainTextEdit();text.setReadOnly(True);l.addWidget(text)
        text.setPlainText(Path(path).read_text() if Path(path).exists() else 'No build report yet.')
    def settings(self):
        d,l=self.dialog('Settings',850,690);tabs=W.QTabWidget();l.addWidget(tabs);s=self.store.settings
        def tab(name):
            scroll=W.QScrollArea();scroll.setWidgetResizable(True);body=W.QWidget();f=W.QFormLayout(body);f.setSpacing(16);scroll.setWidget(body);tabs.addTab(scroll,name);return f
        appearance=tab('Appearance');theme=combo(['light','dark'],s['theme']);wall=combo(PALETTES,s['wallpaper'])
        appearance.addRow('Theme',theme);appearance.addRow('Desktop background',wall)
        def visual():
            s.update(theme=theme.currentText(),wallpaper=wall.currentText());self.store.save();self.apply_theme();self.desktop.refresh()
        theme.currentTextChanged.connect(visual);wall.currentTextChanged.connect(visual)
        def choose():
            p,_=W.QFileDialog.getOpenFileName(d,'Choose desktop wallpaper',str(Path.home()),'Images (*.png *.jpg *.jpeg *.webp)')
            if p:
                pix=G.QPixmap(p)
                if pix.isNull():self.info('Cannot read this image.');return
                dest=self.store.directory/'wallpaper.png';pix.scaled(3840,2160,C.Qt.KeepAspectRatio,C.Qt.SmoothTransformation).save(str(dest),'PNG')
                s['wallpaper_file']=str(dest);visual()
        appearance.addRow(button('Choose your own wallpaper…',choose))
        def clear_wall():s['wallpaper_file']='';visual()
        appearance.addRow(button('Use built-in background',clear_wall))
        appearance.addRow(label('Changes are saved immediately and survive reboots.',11))
        con=tab('Connections');pc=line(s['host']);mode=combo(['Moonlight','RDP'],s['desktop_mode']);desk=line(s['desktop_app']);rdp=line(s['rdp_host']);share=line(s['share'])
        for name,w in [('Bazzite PC',pc),('Desktop mode',mode),('Sunshine Desktop app',desk),('RDP host (optional)',rdp),('Network share · smb://PC/share',share)]:con.addRow(name,w)
        con.addRow(label('On Bazzite Deck, switch the PC to Desktop Mode once, then configure Sunshine to capture KDE. RDP requires an enabled RDP server on the PC. A network share must also be configured on the PC.',11))
        def save_con():
            try:
                address=host(pc.text()) if pc.text().strip() else ''
                rhost=host(rdp.text()) if rdp.text().strip() else ''
                uri=share.text().strip()
                if uri and (not uri.startswith('smb://') or any(x in uri for x in '\r\n')):raise ValueError('Use smb://PC/share for the network share.')
                s.update(host=address,desktop_mode=mode.currentText(),desktop_app=desk.text().strip() or 'Desktop',rdp_host=rhost,share=uri);self.store.save();self.info('Connections saved.')
            except ValueError as e:self.info(str(e))
        con.addRow(button('Save connections',save_con));con.addRow(button('Wi-Fi networks',lambda:self.terminal('wifi')))
        con.addRow(button('Bluetooth controllers',lambda:self.start(['blueman-manager'])))
        picture=tab('Picture');res=combo(['1920x1080','1280x720'],s['resolution']);fps=combo([60,30],s['fps']);codec=combo(['H.264','HEVC'],s['codec']);rate=W.QSpinBox();rate.setRange(5,40);rate.setValue(s['bitrate'])
        tty=W.QCheckBox('Use a direct console for streaming (recommended on Pi 4)');tty.setChecked(s['stream_tty'])
        for name,w in [('Stream resolution',res),('Frames per second',fps),('Video codec',codec),('Bitrate · Mb/s',rate)]:picture.addRow(name,w)
        picture.addRow(tty)
        def save_picture():
            s.update(resolution=res.currentText(),fps=int(fps.currentText()),codec=codec.currentText(),bitrate=rate.value(),stream_tty=tty.isChecked());self.store.save();self.info('Picture settings saved.')
        picture.addRow(button('Save picture settings',save_picture));picture.addRow(label('H.264 / 1080p60 / 20 Mb/s is the default. Try 720p60 / 10 Mb/s on a weak connection. Wired Ethernet and a TV’s Game Mode usually reduce delay.',11))
        display=tab('Display / sound');display.addRow(button('Resolution and display layout',lambda:self.start(['arandr'])))
        display.addRow(label('For a persistent preset, select one here. A failed change automatically reverts after 15 seconds unless confirmed.',11))
        modes=combo(['1920x1080','1280x720'],s['display_mode'] or '1920x1080');display.addRow('Persistent mode',modes)
        display.addRow(button('Apply display mode',lambda:self.change_display(modes.currentText())))
        overscan=W.QSpinBox();overscan.setRange(0,100);overscan.setValue(s['underscan']);display.addRow('TV border compensation · pixels',overscan)
        display.addRow(button('Apply TV border compensation',lambda:self.set_overscan(overscan.value())))
        display.addRow(label('Uses the KMS HDMI underscan property. If your display driver lacks it, turn off overscan in the TV’s picture settings.',11))
        display.addRow(button('HDMI output and volume',lambda:self.start(['pavucontrol'])))
        display.addRow(button('Select HDMI automatically',self.hdmi_audio))
        system=tab('System');hostname=line();hostname.setPlaceholderText('bazzpi');country=line();country.setMaxLength(2);country.setPlaceholderText('US');zone=line('America/New_York');gpu=combo(['64','128','256'],'128')
        for title,w,action,transform in [('Hostname',hostname,'hostname',lambda x:x),('Wi-Fi country',country,'country',str.upper),('Timezone',zone,'timezone',lambda x:x),('GPU memory · reboot required',gpu,'gpu',lambda x:x)]:
            row=W.QHBoxLayout();row.addWidget(w)
            row.addWidget(button('Apply',lambda _,w=w,a=action,t=transform:self.admin(a,t(w.currentText() if isinstance(w,W.QComboBox) else w.text()))));system.addRow(title,row)
        system.addRow(label('SSH is off on a fresh install. To use it, set a Linux password for play, then explicitly enable SSH.',11))
        system.addRow(button('Set play Linux password',lambda:self.terminal('password')))
        row=W.QHBoxLayout();row.addWidget(button('Enable SSH',lambda:self.admin('ssh','on')));row.addWidget(button('Disable SSH',lambda:self.admin('ssh','off')));system.addRow(row)
        system.addRow(button('Connection and Pi diagnostics',self.diagnostics))
        system.addRow(button('Change profile code',self.change_pin))
        def power(action):
            if W.QMessageBox.question(d,'Bazzpi',action.capitalize()+' the Pi now?')==W.QMessageBox.Yes:self.admin(action)
        row=W.QHBoxLayout();row.addWidget(button('Reboot',lambda:power('reboot')));row.addWidget(button('Power off',lambda:power('poweroff')));system.addRow(row)
    def change_pin(self):
        old,ok=W.QInputDialog.getText(self.dock,'Profile code','Current code (empty if none)',W.QLineEdit.Password)
        if not ok:return
        if not self.store.unlock(old):self.info('Incorrect code or retry delay active.');return
        new,ok=W.QInputDialog.getText(self.dock,'Profile code','New 4-digit code (empty to remove)',W.QLineEdit.Password)
        if not ok:return
        try:self.store.data['profile']['pin']=pin_record(new);self.store.save();self.info('Profile code updated.')
        except ValueError as e:self.info(str(e))
    def output(self,args):return subprocess.check_output(args,text=True,timeout=5,stderr=subprocess.STDOUT)
    def connected_display(self):
        text=self.output(['xrandr','--query'])
        current=None
        for ln in text.splitlines():
            m=re.match(r'^(\S+) connected',ln)
            if m:current=m.group(1)
            elif ln and not ln.startswith(' '):current=None
            if current and '*' in ln:return current,ln.split()[0]
        raise ValueError('No active X11 display detected.')
    def change_display(self,mode):
        try:
            output,old=self.connected_display();self.output(['xrandr','--output',output,'--mode',mode])
            box=W.QMessageBox(W.QMessageBox.Question,'Keep display mode?','Keep this mode? Reverts automatically in 15 seconds.',W.QMessageBox.Yes|W.QMessageBox.No,self.dock)
            timer=C.QTimer(box);timer.setSingleShot(True);timer.timeout.connect(lambda:box.done(W.QMessageBox.No));timer.start(15000)
            if box.exec_()==W.QMessageBox.Yes:self.store.settings['display_mode']=mode;self.store.save()
            else:self.output(['xrandr','--output',output,'--mode',old])
        except (ValueError,subprocess.SubprocessError,OSError) as e:self.info(str(e))
    def set_overscan(self,n,quiet=False):
        try:
            output,_=self.connected_display();props=self.output(['xrandr','--prop'])
            if 'underscan hborder' not in props:raise ValueError('This driver does not expose TV border adjustment. Disable overscan on your TV.')
            self.output(['xrandr','--output',output,'--set','underscan','on' if n else 'off'])
            if n:
                self.output(['xrandr','--output',output,'--set','underscan hborder',str(n)])
                self.output(['xrandr','--output',output,'--set','underscan vborder',str(n)])
            self.store.settings['underscan']=n;self.store.save()
        except (ValueError,subprocess.SubprocessError,OSError) as e:
            if not quiet:self.info(str(e))
    def restore_display(self):
        if os.environ.get('QT_QPA_PLATFORM')=='offscreen':return
        try:
            if self.store.settings['display_mode']:
                out,_=self.connected_display();self.output(['xrandr','--output',out,'--mode',self.store.settings['display_mode']])
            if self.store.settings['underscan']:self.set_overscan(self.store.settings['underscan'],True)
        except (ValueError,subprocess.SubprocessError,OSError):pass
    def hdmi_audio(self):
        try:
            sinks=self.output(['pactl','list','short','sinks']).splitlines()
            hdmi=next((x.split()[1] for x in sinks if 'hdmi' in x.lower()),None)
            if not hdmi:raise ValueError('No HDMI sink active. Open HDMI output and volume, then select an HDMI profile under Configuration.')
            self.output(['pactl','set-default-sink',hdmi]);self.info('HDMI selected for new audio streams.')
        except (ValueError,subprocess.SubprocessError,OSError) as e:self.info(str(e))
    def diagnostics(self):
        self.job('Connection and Pi diagnostics',[sys.executable,str(Path(__file__).with_name('diagnostics.py')),self.store.settings['host']])

class Controller:
    """Non-grabbing evdev navigation; only generates keys into Bazzpi windows."""
    def __init__(self,shelf):
        self.shelf=shelf;self.devices=[];self.last=0;self.scan_count=0
        self.timer=C.QTimer();self.timer.timeout.connect(self.poll);self.timer.start(60)
    def poll(self):
        try:import evdev
        except ImportError:return
        self.scan_count+=1
        if self.scan_count%50==1:
            for path in evdev.list_devices():
                if any(d.path==path for d in self.devices):continue
                try:
                    d=evdev.InputDevice(path)
                    if evdev.ecodes.BTN_GAMEPAD in d.capabilities().get(evdev.ecodes.EV_KEY,[]):self.devices.append(d)
                    else:d.close()
                except OSError:pass
        for dev in self.devices[:]:
            try:
                for e in dev.read():
                    # Do not steal controller input from Moonlight, ES, or external windows.
                    if self.shelf.app.activeWindow() is None:continue
                    key=None
                    if e.type==evdev.ecodes.EV_KEY and e.value==1:
                        key={evdev.ecodes.BTN_SOUTH:C.Qt.Key_Return,evdev.ecodes.BTN_EAST:C.Qt.Key_Escape,
                             evdev.ecodes.BTN_TR:C.Qt.Key_Tab,evdev.ecodes.BTN_TL:C.Qt.Key_Backtab}.get(e.code)
                    elif e.type==evdev.ecodes.EV_ABS and e.code in (evdev.ecodes.ABS_HAT0X,evdev.ecodes.ABS_HAT0Y) and e.value:
                        key=C.Qt.Key_Tab if e.value>0 else C.Qt.Key_Backtab
                    target=self.shelf.app.focusWidget()
                    if key==C.Qt.Key_Return and isinstance(target,W.QAbstractButton):
                        target.click();continue
                    if key and target:
                        self.shelf.app.postEvent(target,G.QKeyEvent(C.QEvent.KeyPress,key,C.Qt.NoModifier))
                        self.shelf.app.postEvent(target,G.QKeyEvent(C.QEvent.KeyRelease,key,C.Qt.NoModifier))
            except BlockingIOError:pass
            except OSError:self.devices.remove(dev);dev.close()

def main():
    app=W.QApplication(sys.argv);app.setQuitOnLastWindowClosed(False)
    try:store=Store()
    except Exception as e:
        W.QMessageBox.critical(None,'Bazzpi profile could not load',str(e)+'\nThe shelf will remain locked. Restore ~/.config/bazzpi/state.json.');return 1
    shelf=Shelf(app,store)
    # Deterministic offscreen rendering only; never bypasses an installed profile.
    if '--preview' in sys.argv and os.environ.get('QT_QPA_PLATFORM')=='offscreen':
        out=Path(sys.argv[sys.argv.index('--preview')+1]);out.mkdir(parents=True,exist_ok=True)
        shelf.desktop.resize(1440,900)
        if shelf.gate:shelf.gate.resize(1440,900);shelf.gate.grab().save(str(out/'profile.png'))
        shelf.desktop.grab().save(str(out/'desktop.png'))
        return 0
    return app.exec_()

if __name__=='__main__':sys.exit(main())
