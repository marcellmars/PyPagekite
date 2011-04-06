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

EVT_NEW_LOGLINE = wx.PyEventBinder(wx.NewEventType(), 0)


class DemoTaskBarIcon(wx.TaskBarIcon):
  TBMENU_LOGVIEW = wx.NewId()
  TBMENU_CONSOLE = wx.NewId()

  TBMENU_KITES   = wx.NewId()
  TBMENU_GETKITE = wx.NewId()
  TBMENU_STATUS  = wx.NewId()

  TBMENU_QUOTA    = wx.NewId()
  TBMENU_GETQUOTA = wx.NewId()

  TBMENU_DEBUG   = wx.NewId()
  TBMENU_ENABLE  = wx.NewId()
  TBMENU_CLOSE   = wx.NewId()

  TBMENU_KITE_IDS = [wx.NewId() for x in range(0, 100)]

  def __init__(self, main):
    wx.TaskBarIcon.__init__(self)
    self.main = main
    self.popupMenu = self.kiteMenu = None
    self.kites = []

    # Set the image
    icon = self.MakeIcon(wx.Image('pk-logo-127.png', wx.BITMAP_TYPE_PNG))
    self.SetIcon(icon, "Click to examine your pagekites")
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
    self.Bind(wx.EVT_UPDATE_UI, self.OnUpdateMenuStatus, id=self.TBMENU_STATUS)
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

    menu.Append(self.TBMENU_LOGVIEW, "Display PageKite Log")
    menu.Append(self.TBMENU_CONSOLE, "Open PageKite Control Panel")
    menu.AppendSeparator()

    self.kiteMenu = wx.Menu()
    if self.main.pagekite and self.main.pagekite.pk:
      pk = self.main.pagekite.pk
      self.kites = []
      for kite in pk.backends:
        item = self.kiteMenu.Append(self.TBMENU_KITE_IDS[len(self.kites)],
                                    self.DescribeKite(kite),
                                    kind=wx.ITEM_CHECK)
        item.Check(pagekite.BE_STATUS_OK == pk.backends[kite][pagekite.BE_STATUS])
        self.kites.append(kite)
    if self.kites: self.kiteMenu.AppendSeparator()
    self.kiteMenu.Append(self.TBMENU_GETKITE, "Get More Kites...")

    menu.AppendMenu(self.TBMENU_KITES, "No Kites Configured", self.kiteMenu)
    menu.AppendSeparator()

    # FIXME: Only add these two if we are using the service.
    menu.Append(self.TBMENU_QUOTA, "0.00 GB of Quota Left")
    menu.Append(self.TBMENU_GETQUOTA, "Get More Quota...")
    menu.AppendSeparator()
    menu.Append(self.TBMENU_DEBUG,  "Enable Verbose Logging", kind=wx.ITEM_CHECK)
    menu.Append(self.TBMENU_ENABLE, "Enable PageKite", kind=wx.ITEM_CHECK)
    menu.Append(self.TBMENU_CLOSE,   "Quit PageKite")
    return menu

  def DescribeKite(self, kite):
    be = self.main.pagekite.pk.backends[kite]
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
    if self.main.pagekite and self.main.pagekite.pk:
      if self.main.pagekite.pk.looping or not self.main.pagekite.alive:
        event.Enable(True)
      else:
        event.Enable(False)
    else:
      event.Enable(True)

    event.Check(self.main.pagekite.alive)

  def OnUpdateMenuStatus(self, event):
    # FIXME
    self.popupMenu.SetLabel(self.TBMENU_STATUS, "Status: Dead")

  def OnUpdateMenuKites(self, event):
    if self.main.pagekite and self.main.pagekite.pk:
      event.Enable(True)
      kites = len(self.main.pagekite.pk.backends.keys())
    else:
      event.Enable(False)
      kites = 0

    if kites == 1:
      self.popupMenu.SetLabel(self.TBMENU_KITES, "Your Kite" % kites)
    elif kites > 1:
      self.popupMenu.SetLabel(self.TBMENU_KITES, "Your %d Kites" % kites)
    else:
      self.popupMenu.SetLabel(self.TBMENU_KITES, "No Kites Configured")

  def OnUpdateMenuQuota(self, event):
    event.Enable(False)

  def OnUpdateMenuConsole(self, event):
    if self.main.pagekite and self.main.pagekite.pk.ui_httpd:
      event.Enable(True)
    else:
      event.Enable(False)

  def OnTaskBarDebug(self, evt):
    self.main.debugging = not self.main.debugging

  def OnTaskBarKite(self, evt):
    kite = self.kites[self.TBMENU_KITE_IDS.index(evt.GetId())]
    # Pop up a dialog allowing:
    #   - Remove
    #   - Disable
    #   - Visit (for HTTP* kites)
    #
    print 'Kite selected: %s' % kite

  def OnTaskBarGetKite(self, evt):
    pass

  def OnTaskBarGetQuota(self, evt):
    pass

  def OnTaskBarActivate(self, evt):
    if self.main.IsIconized():
      self.main.Iconize(False)
    else:
      self.main.Iconize(True)

    if self.main.IsShown():
      self.main.Show(False)
    else:
      self.main.Show(True)
      self.main.Raise()

  def OnTaskBarEnable(self, evt):
    if self.main.pagekite:
      if self.main.pagekite.alive:
        self.main.pagekite.stop_pk()
      else:
        self.main.pagekite.start_pk()

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

  def Configure(self, pk):
    self.pk = pk
    if not self.alive: raise KeyboardInterrupt('Quit')

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

  def start_pk(self):
    self.stopped = False

  def stop_pk(self):
    pagekite.Log = self.old_log
    self.stopped = True
    if self.pk:
      self.pk.looping = self.alive = False
      self.pk = None

  def restart(self):
    if self.pk:
      self.pk.looping = False
      self.pk = None

  def quit(self):
    self.frame = None
    self.stop_pk()


class MainFrame(wx.Frame):
  TITLE = "PageKite Log Viewer"
  FRAME_SIZE = (600, 450)
  LOG_STYLE = wx.TE_MULTILINE|wx.TE_READONLY|wx.HSCROLL

  def __init__(self, parent):
    wx.Frame.__init__(self, parent, title=self.TITLE, size=self.FRAME_SIZE)
    self.debugging = False

    self.tbicon = DemoTaskBarIcon(self)
    self.log = wx.TextCtrl(self, -1, style=self.LOG_STYLE)

    self.Bind(wx.EVT_CLOSE, self.OnCloseWindow)
    self.Bind(EVT_NEW_LOGLINE, self.OnNewLogLine)

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
    self.main.StartPageKite()


if __name__ == '__main__':
  app = PkApp(redirect=False)
  app.MainLoop()

