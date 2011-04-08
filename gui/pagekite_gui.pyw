#!/usr/bin/python -u
#
# pagekite_gui.py, Copyright 2010, 2011, the Beanstalks Project ehf.
#                                        and Bjarni Runar Einarsson
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################
#
# This program wraps pagekite.py in a very simple GUI.
#
# Features:
#   - Creates a taskbar icon for:
#      - Opening the log viewer
#      - Opening up the control panel UI
#      - Displaying a brief status summary:
#         - List of kites
#         - List: Shared files? Recent downloads? Active users?
#      - Bandwidth quota & getting more
#      - Restarting or quitting
#
# TODO:
#   - Make the taskbar icon change depending on activity.
#   - Enable remote mode, for controlling a system-wide pagekite.py?
#
import sys
import threading
import time
import webbrowser
import wx

import pagekite


SERVICE_DOMAINS = [
  '.pagekite.me', '.pagekite.net', '.pagekite.us', '.pagekite.info'
]
URL_HOME     = 'https://pagekite.net/home/'
URL_SIGNUP   = 'https://pagekite.net/signup/'
URL_GETKITES = 'http://localhost:8000/signup/?do_login=1&more=kites&r=%s:%s/pagekite/new_kite/'
URL_GETQUOTA = 'http://localhost:8000/signup/?do_login=1&more=bw'


EVT_NEW_LOGLINE = wx.PyEventBinder(wx.NewEventType(), 0)


class DemoTaskBarIcon(wx.TaskBarIcon):
  TBMENU_LOGVIEW = wx.NewId()
  TBMENU_CONSOLE = wx.NewId()

  TBMENU_KITES   = wx.NewId()
  TBMENU_GETKITE = wx.NewId()

  TBMENU_WEBCTRL    = wx.NewId()
  TBMENU_SHARE_PATH = wx.NewId()
  TBMENU_SHARE_CB   = wx.NewId()
  TBMENU_SHARE_SCRN = wx.NewId()
  TBMENU_SHARELOG   = wx.NewId()
  TBMENU_MIRRORING  = wx.NewId()
  TBMENU_SHARING    = wx.NewId()

  TBMENU_QUOTA    = wx.NewId()
  TBMENU_GETQUOTA = wx.NewId()
  TBMENU_SIGNUP   = wx.NewId()

  TBMENU_DEBUG   = wx.NewId()
  TBMENU_ENABLE  = wx.NewId()
  TBMENU_CLOSE   = wx.NewId()

  TBMENU_KITE_IDS = [wx.NewId() for x in range(0, 100)]

  def __init__(self, main):
    wx.TaskBarIcon.__init__(self)
    self.main = main
    self.popupMenu = self.kiteMenu = self.webMenu = None

    # Set the image
    icon = self.MakeIcon(wx.Image('pk-logo-127.png', wx.BITMAP_TYPE_PNG))
    self.SetIcon(icon, "Click to examine your PageKites")
    self.imgidx = 1

    # bind some events
    self.Bind(wx.EVT_TASKBAR_LEFT_UP, self.OnTaskBarActivate)
#   self.Bind(wx.EVT_TASKBAR_LEFT_DCLICK, self.OnTaskBarActivate)
    self.Bind(wx.EVT_MENU, self.OnTaskBarActivate, id=self.TBMENU_LOGVIEW)
    self.Bind(wx.EVT_MENU, self.OnTaskBarConsole, id=self.TBMENU_CONSOLE)
    self.Bind(wx.EVT_MENU, self.OnTaskBarGetKite, id=self.TBMENU_GETKITE)
    for i in self.TBMENU_KITE_IDS:
      self.Bind(wx.EVT_MENU, self.OnTaskBarKite, id=i)
    self.Bind(wx.EVT_MENU, self.OnTaskBarGetQuota, id=self.TBMENU_GETQUOTA)
    self.Bind(wx.EVT_MENU, self.OnTaskBarDebug, id=self.TBMENU_DEBUG)
    self.Bind(wx.EVT_MENU, self.OnTaskBarEnable, id=self.TBMENU_ENABLE)
    self.Bind(wx.EVT_MENU, self.OnTaskBarClose, id=self.TBMENU_CLOSE)

    self.Bind(wx.EVT_UPDATE_UI, self.OnUpdateMenuConsole, id=self.TBMENU_CONSOLE)
    self.Bind(wx.EVT_UPDATE_UI, self.OnUpdateMenuKites, id=self.TBMENU_KITES)
    self.Bind(wx.EVT_UPDATE_UI, self.OnUpdateMenuQuota, id=self.TBMENU_QUOTA)
    self.Bind(wx.EVT_UPDATE_UI, self.OnUpdateMenuDebug, id=self.TBMENU_DEBUG)
    self.Bind(wx.EVT_UPDATE_UI, self.OnUpdateMenuEnable, id=self.TBMENU_ENABLE)

  def CreatePopupMenu(self):
    """
    This method is called by the base class when it needs to popup
    the menu for the default EVT_RIGHT_DOWN event.  Just create
    the menu how you want it and return it from this function,
    the base class takes care of the rest.
    """
    menu = self.popupMenu = wx.Menu()
    self.kiteMenu = wx.Menu()
    self.webMenu = wx.Menu()

    self.main.RefreshPageKiteInfo()

    menu.Append(self.TBMENU_LOGVIEW, "Display PageKite Log")
    menu.Append(self.TBMENU_CONSOLE, "Open PageKite Control Panel")
    menu.AppendSeparator()

    self.webMenu.Append(self.TBMENU_SHARE_CB, "Paste To Web").Enable(self.main.pk_sharing)
    self.webMenu.Append(self.TBMENU_SHARE_PATH, "Share From Disk").Enable(self.main.pk_sharing)
    self.webMenu.Append(self.TBMENU_SHARE_SCRN, "Share Screenshot").Enable(self.main.pk_sharing)
    self.webMenu.AppendSeparator()
    self.webMenu.Append(self.TBMENU_SHARELOG, "History...").Enable(self.main.pk_sharing)
    self.webMenu.AppendSeparator()
    self.webMenu.Append(self.TBMENU_MIRRORING, "Mirroring...").Enable(self.main.pk_sharing)
    self.webMenu.Append(self.TBMENU_SHARING, "Enable Sharing", kind=wx.ITEM_CHECK
                        ).Check(self.main.pk_sharing)
    menu.AppendMenu(self.TBMENU_WEBCTRL, "Quick Sharing (0.0 MB)", self.webMenu)

    count = 0
    for kite, be in self.main.pk_kites:
      item = self.kiteMenu.Append(self.TBMENU_KITE_IDS[count],
                                  self.DescribeKite(kite, be),
                                  kind=wx.ITEM_CHECK)
      item.Check(pagekite.BE_STATUS_OK == be[pagekite.BE_STATUS])
      count += 1
    if count: self.kiteMenu.AppendSeparator()
    self.kiteMenu.Append(self.TBMENU_GETKITE, "Add More Kites...")
    menu.AppendMenu(self.TBMENU_KITES, "No Kites Configured", self.kiteMenu)
    menu.AppendSeparator()

    if self.main.pk_service:
      if self.main.pk_quota:
        menu.Append(self.TBMENU_QUOTA, ("%.2f GB of Quota Left"
                                        ) % self.main.pk_quota)
      else:
        menu.Append(self.TBMENU_QUOTA, "Quota unknown")
      menu.Append(self.TBMENU_GETQUOTA, "Get More Quota...")
    else:
      menu.Append(self.TBMENU_SIGNUP, "Sign-up at PageKite.net")
    menu.AppendSeparator()

    menu.Append(self.TBMENU_DEBUG,  "Enable Verbose Logging", kind=wx.ITEM_CHECK)
    menu.Append(self.TBMENU_ENABLE, "Enable PageKite", kind=wx.ITEM_CHECK)
    menu.Append(self.TBMENU_CLOSE,  "Quit PageKite")
    return menu

  def DescribeKite(self, kite, be):
    be_port = be[pagekite.BE_PORT]
    return '%s (%s%s)' % (be[pagekite.BE_DOMAIN], be[pagekite.BE_PROTO],
                          be_port and (', port %s' % be_port) or '')
 
  def MakeIcon(self, img):
    """
    The various platforms have different requirements for the
    icon size...
    """
    if "wxMSW" in wx.PlatformInfo:
      img = img.Scale(16, 16, wx.IMAGE_QUALITY_HIGH)
    elif "wxGTK" in wx.PlatformInfo:
      img = img.Scale(22, 22, wx.IMAGE_QUALITY_HIGH)
    # wxMac can be any size upto 128x128, so leave the source img alone....
    icon = wx.IconFromBitmap(img.ConvertToBitmap())
    return icon

  def OnUpdateMenuDebug(self, event):
    event.Check(self.main.debugging)

  def OnUpdateMenuEnable(self, event):
    pagekite = self.main.pagekite
    if pagekite:
      event.Check(pagekite.IsRunning())
      if pagekite.IsStopping():
        self.popupMenu.SetLabel(self.TBMENU_ENABLE, "Shutting down...")
        event.Enable(False)
      else:
        event.Enable(True)
    else:
      event.Check(False)

  def OnUpdateMenuKites(self, event):
    if self.main.pagekite and self.main.pagekite.pk:
      event.Enable(True)
      kites = len(self.main.pagekite.pk.backends.keys())
    else:
      event.Enable(False)
      kites = 0

    if kites == 1:
      self.popupMenu.SetLabel(self.TBMENU_KITES, "Your Kite (1)")
    elif kites > 1:
      self.popupMenu.SetLabel(self.TBMENU_KITES, "Your Kites (%d)" % kites)
    else:
      self.popupMenu.SetLabel(self.TBMENU_KITES, "No Kites Configured")

  def OnUpdateMenuQuota(self, event):
    event.Enable(False)

  def OnUpdateMenuConsole(self, event):
    event.Enable((self.main.pagekite and
                  self.main.pagekite.pk and
                  self.main.pagekite.pk.ui_httpd) and True or False)

  def OnTaskBarDebug(self, evt):
    self.main.debugging = not self.main.debugging

  def OnTaskBarKite(self, evt):
    kite, be = self.main.pk_kites[self.TBMENU_KITE_IDS.index(evt.GetId())]
    # Pop up a dialog allowing:
    #   - Remove
    #   - Disable
    #   - Visit (for HTTP* kites)
    #
    print 'Kite selected: %s' % kite

  def OnTaskBarGetKite(self, evt):
    webbrowser.open_new(URL_GETKITES % self.main.pagekite.pk.ui_sspec)

  def OnTaskBarGetQuota(self, evt):
    webbrowser.open_new(URL_GETQUOTA)

  def OnTaskBarActivate(self, evt):
    if self.main.IsIconized() or not self.main.IsShown():
      self.main.Iconize(False)
      self.main.Show(True)
      self.main.Raise()
    else:
      self.main.Show(False)

  def OnTaskBarEnable(self, evt):
    if self.main.pagekite:
      if self.main.pagekite.stopped:
        self.main.pagekite.start_pk()
      else:
        self.main.pagekite.stop_pk()

  def OnTaskBarRestart(self, evt):
    self.main.pagekite.restart()

  def OnTaskBarConsole(self, evt):
    webbrowser.open_new('http://%s:%s/' % self.main.pagekite.pk.ui_sspec)

  def OnTaskBarClose(self, evt):
    self.main.Close(force=True)


class LogLineEvent(wx.PyCommandEvent):
  def __init__(self, eventtype=EVT_NEW_LOGLINE.evtType[0], id=0):
    wx.PyCommandEvent.__init__(self, eventtype, id)
    self.logline = None

class LogTee:
  def __init__(self, frame, oldfd):
    self.frame = frame
    self.oldfd = oldfd

  def write(self, string):
    lle = LogLineEvent()
    lle.logline = string
    self.frame.AddPendingEvent(lle)
    self.oldfd.write(string)

def LogFilter(frame, func):
  def Logger(values):
    if frame.debugging: return func(values)
    words, wdict = pagekite.LogValues(values)
    if 'debug' not in wdict: return func(values)
  return Logger

class PageKiteThread(threading.Thread):
  def __init__(self, frame):
    threading.Thread.__init__(self)
    self.frame = frame
    self.alive = False
    self.stopped = False
    self.pk = None
    self.old_log = pagekite.Log
    self.old_logfile = pagekite.LogFile

  def IsRunning(self):
    return (self.pk and self.pk.IsRunning()) and True or False

  def IsStopping(self):
    return (self.IsRunning() and self.stopped) and True or False

  def Configure(self, pk):
    if self.stopped or not self.frame: raise KeyboardInterrupt('Quit')
    self.pk = pk

    # FIXME: the pagekite.py log handing is dumb, so this sucks.
    try:
      pagekite.Log = self.old_log
      pagekite.LogFile = self.old_logfile
      rv = pagekite.Configure(pk)
      pagekite.LogFile = LogTee(self.frame, pagekite.LogFile)
      pagekite.Log = LogFilter(self.frame, pagekite.Log)

      return rv
    except pagekite.ConfigError, e:
      self.frame.Close(force=True)
      raise pagekite.ConfigError(e)

  def run(self):
    while self.frame is not None:
      if self.stopped:
        time.sleep(1)
      else:
        self.alive = True
        pagekite.Main(pagekite.PageKite, lambda pk: self.Configure(pk))
        while self.pk and self.pk.IsRunning(): time.sleep(0.2)
        self.pk = None
        self.alive = False

  def start_pk(self):
    self.stopped = False

  def stop_pk(self):
    pagekite.Log = self.old_log
    self.stopped = True
    if self.pk: self.pk.looping = False

  def restart(self):
    if self.pk: self.pk.looping = False

  def quit(self):
    self.frame = None
    self.stop_pk()


class MainFrame(wx.Frame):
  TITLE = "PageKite Log Viewer"
  FRAME_SIZE = (600, 450)
  LOG_STYLE = wx.TE_MULTILINE|wx.TE_READONLY|wx.HSCROLL

  def __init__(self, parent):
    wx.Frame.__init__(self, parent, title=self.TITLE, size=self.FRAME_SIZE)
    self.log = wx.TextCtrl(self, -1, style=self.LOG_STYLE)
    self.pagekite = self.tbicon = None
    self.debugging = False

    self.RefreshPageKiteInfo()

    self.Bind(wx.EVT_CLOSE, self.OnCloseWindow)
    self.Bind(EVT_NEW_LOGLINE, self.OnNewLogLine)

  def CreateTaskBarIcon(self):
    self.tbicon = DemoTaskBarIcon(self)

  def RefreshPageKiteInfo(self):
    self.pk_kites = []
    self.pk_quota = None
    self.pk_service = None
    self.pk_sharing = False
    self.pk_mirroring = False

    if self.pagekite and self.pagekite.pk:
      pk = self.pagekite.pk

      if pk.conns:
        quotas = [float(c.quota[0]) for c in pk.conns.conns if c.quota]
        if quotas: self.pk_quota = min(quotas)/(1024*1024)

      for kite in pk.backends:
        be = pk.backends[kite]
        self.pk_kites.append((kite, be))
        domain = be[pagekite.BE_DOMAIN]
        for service_domain in SERVICE_DOMAINS:
          if domain.endswith(service_domain):
            if not self.pk_service or len(domain) < len(self.pk_service[0]):
              self.pk_service = (domain, be[pagekite.BE_SECRET])

  def StartPageKite(self):
    self.pagekite = PageKiteThread(self)
    self.pagekite.start()

  def OnCloseWindow(self, evt):
    if evt.CanVeto():
      self.Hide()
      evt.Veto()
    else:
      #if we don't veto it we allow the event to propogate
      self.pagekite.quit()
      self.tbicon.Destroy()
      pagekite.LogFile = sys.stderr
      self.log.Destroy()
      evt.Skip()

  def OnNewLogLine(self, event):
    if self.log.GetNumberOfLines() > 100:
      self.log.Remove(0, self.log.GetLineLength(0)+1)
    self.log.SetInsertionPointEnd()
    self.log.WriteText(event.logline)


class PkApp(wx.App):
  def __init__(self, redirect=False):
    wx.App.__init__(self, redirect=redirect)
    self.main = MainFrame(None)
    self.main.Hide()
    self.main.CreateTaskBarIcon()
    self.main.StartPageKite()


if __name__ == '__main__':
  app = PkApp(redirect=False)
  app.MainLoop()

