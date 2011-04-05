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
#      - Displaying a brief status summary.
#      - Restarting or quitting
#      - Opening up the control panel UI in your browser
#
# TODO:
#   - Make the taskbar icon change depending on activity.
#   - Enable remote mode, for controlling a system-wide pagekite.py?
#
import sys
import threading
import webbrowser
import wx

import pagekite

EVT_NEW_LOGLINE = wx.PyEventBinder(wx.NewEventType(), 0)


class DemoTaskBarIcon(wx.TaskBarIcon):
  TBMENU_LOGVIEW = wx.NewId()
  TBMENU_RESTART = wx.NewId()
  TBMENU_CONSOLE = wx.NewId()
  TBMENU_CLOSE   = wx.NewId()
  TBMENU_STATUS  = wx.NewId()
  TBMENU_CHANGE  = wx.NewId()
  TBMENU_REMOVE  = wx.NewId()
  TBMENU_DEBUG   = wx.NewId()
  TBMENU_CHECKABLE  = wx.NewId()

  def __init__(self, main):
    wx.TaskBarIcon.__init__(self)
    self.main = main
    self.statusMenuItem = None

    # Set the image
    icon = self.MakeIcon(wx.Image('pk-logo-127.png', wx.BITMAP_TYPE_PNG))
    self.SetIcon(icon, "Click to examine your pagekites")
    self.imgidx = 1

    # bind some events
    self.Bind(wx.EVT_TASKBAR_LEFT_UP, self.OnTaskBarActivate)
#   self.Bind(wx.EVT_TASKBAR_LEFT_DCLICK, self.OnTaskBarActivate)
    self.Bind(wx.EVT_MENU, self.OnTaskBarActivate, id=self.TBMENU_LOGVIEW)
    self.Bind(wx.EVT_MENU, self.OnTaskBarConsole, id=self.TBMENU_CONSOLE)
    self.Bind(wx.EVT_MENU, self.OnTaskBarDebug, id=self.TBMENU_DEBUG)
    self.Bind(wx.EVT_MENU, self.OnTaskBarRestart, id=self.TBMENU_RESTART)
    self.Bind(wx.EVT_MENU, self.OnTaskBarClose, id=self.TBMENU_CLOSE)

    self.Bind(wx.EVT_UPDATE_UI, self.OnUpdateMenuConsole, id=self.TBMENU_CONSOLE)
    self.Bind(wx.EVT_UPDATE_UI, self.OnUpdateMenuStatus, id=self.TBMENU_STATUS)
    self.Bind(wx.EVT_UPDATE_UI, self.OnUpdateMenuDebug, id=self.TBMENU_DEBUG)

  def CreatePopupMenu(self):
    """
    This method is called by the base class when it needs to popup
    the menu for the default EVT_RIGHT_DOWN event.  Just create
    the menu how you want it and return it from this function,
    the base class takes care of the rest.
    """
    menu = self.popupMenu = wx.Menu()
    menu.Append(self.TBMENU_LOGVIEW, "Display Log Window")
    menu.Append(self.TBMENU_CONSOLE, "Open Admin Webpage")
    menu.AppendSeparator()
    self.statusMenuItem = menu.Append(self.TBMENU_STATUS, "Status: ??")
    self.statusMenuItem.Enable(False)
    menu.Append(self.TBMENU_DEBUG, "Debugging: ?")
    menu.AppendSeparator()
    menu.Append(self.TBMENU_RESTART, "Restart")
    menu.Append(self.TBMENU_CLOSE,   "Quit")
    return menu

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
    if self.main.debugging:
      self.popupMenu.SetLabel(self.TBMENU_DEBUG, "Debugging: on")
    else:
      self.popupMenu.SetLabel(self.TBMENU_DEBUG, "Debugging: off")

  def OnUpdateMenuStatus(self, event):
    # FIXME
    self.popupMenu.SetLabel(self.TBMENU_STATUS, "Status: Dead")

  def OnUpdateMenuConsole(self, event):
    if self.main.pagekite and self.main.pagekite.pk.ui_httpd:
      event.Enable(True)
    else:
      event.Enable(False)

  def OnTaskBarDebug(self, evt):
    self.main.debugging = not self.main.debugging

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
    self.alive = True
    return pagekite.Main(pagekite.PageKite, lambda pk: self.Configure(pk))

  def restart(self):
    if self.pk:
      self.pk.looping = False
      self.pk = None

  def quit(self):
    self.frame = None
    pagekite.Log = self.old_log
    if self.pk: self.pk.looping = self.alive = False


class MainFrame(wx.Frame):
  FRAME_SIZE = (600, 450)
  LOG_STYLE = wx.TE_MULTILINE|wx.TE_READONLY|wx.HSCROLL

  def __init__(self, parent):
    wx.Frame.__init__(self, parent, title="Pagekite", size=self.FRAME_SIZE)
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

