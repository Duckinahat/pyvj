#!/usr/bin/env python3

import sys
import os
import logging
import threading
import time
import math

import gi
gi.require_version('Gst', '1.0')
gi.require_version('Gtk', '3.0')
gi.require_version('GstVideo', '1.0')
from gi.repository import GObject, Gst, GstVideo, Gtk, Gdk
from pythonosc import dispatcher, osc_server

from player import TrickPlayer


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class GTK_Main():

    def __init__(self):
        user_path = os.path.expanduser('~')
        vid_path = user_path + '/vids/'
        cue_list = os.listdir(vid_path)
        cue_list.sort()
        self.cues = {'0':cue_list,'1':cue_list}
        self.data = {'file_0' : self.cues['0'][0],
                     'file_1' : self.cues['1'][0],
                     'alpha_0' : 0.5,
                     'alpha_1' : 0.5,
                     'alpha_main' : 1.0,
                     'rate_0' : 1.0,
                     'rate_1' : 1.0,
                     'ipaddr' : '127.0.0.1',
                     'port' : 7701,
                     'mode_0' : 0,
                     'mode_1' : 0,
                     'filepath' : vid_path,
                     'cue_0' : 0,
                     'cue_1' : 0,
                     }
        self.controls = {}


        # Create The control window
        self.create_ctrl_win()
        
        # Create the viewer window
        self.create_view_win()
 
        # Create Players
        self.players = []
        self.players.append(TrickPlayer(0))
        self.players.append(TrickPlayer(1))

        # Create monitors
        self.monitors = []
        self.monitors.append(self.create_monitor(0))
        self.monitors.append(self.create_monitor(1))
        self.monitors.append(self.create_monitor(2))

        # Create Output
        self.create_output()

        self.create_busses()

        self.monitors[0].set_state(Gst.State.PLAYING)
        self.monitors[1].set_state(Gst.State.PLAYING)
        self.monitors[2].set_state(Gst.State.PLAYING)
        self.out.set_state(Gst.State.PLAYING)
        self.players[0].file=self.data['filepath']+self.data['file_0']
        self.players[1].file=self.data['filepath']+self.data['file_1']
        for player in self.players:

            player.run()
            player.start()



        self.ctrl_win.show_all()
        self.view_win.show_all()

        # Set up OSC server
        self.create_dispatcher()
        self.server = osc_server.ThreadingOSCUDPServer(
            (self.data['ipaddr'], self.data['port']), self.dispatcher)
        self.server_thread = threading.Thread(target=self.server.serve_forever)
        self.server_thread.start()

    def create_dispatcher(self):
        self.dispatcher = dispatcher.Dispatcher()
        for control in self.controls.items():
            self.dispatcher.map('/video/'+control[0], self.udp_update, control[1])

    def udp_update(self, address, target, value):
        if type(target[0])==Gtk.Scale:
            target[0].set_value(value)
        elif type(target[0])==Gtk.Button:
            if value == 1.0:
                target[0].clicked()
        elif type(target[0])==Gtk.ToggleButton:
            if value == 1.0:
                target[0].toggled()


    def create_output(self):
        output = Gst.parse_launch("""
            videomixer
                name=mix
                    background=black
                    sink_0::alpha=0.5
                    sink_1::alpha=0.5 !
                intervideosink channel=2
            intervideosrc channel=2 !
                queue !
                video/x-raw,width=800,height=600 !
                xvimagesink name=output
            intervideosrc channel=0 !
                videoscale !
                video/x-raw,width=800,height=600 !
                queue !
                mix.sink_0
            intervideosrc channel=1 !
                videoscale !
                video/x-raw,width=800,height=600 !
                queue !
                mix.sink_1
            """)
        self.out = output

    def create_monitor(self, ident):
        mon = Gst.parse_launch("""
            intervideosrc channel=%d !
            queue !
            videoconvert !
            videoscale !
            video/x-raw,width=240,height=180 !
            xvimagesink name=mon_%d
            """ % (ident,ident))
        return mon

    def create_busses(self):
        busses = {'output' : self.out.bus,
                  # 'play_0' : self.players[0].bus,
                  # 'play_1' : self.players[1].bus,
                  'mon_0'  : self.monitors[0].bus,
                  'mon_1'  : self.monitors[1].bus,
                  'mon_2'  : self.monitors[2].bus
                  }
        for bus in busses.values():
            bus.add_signal_watch()
            bus.enable_sync_message_emission()
            bus.connect('sync-message::element', self.on_sync_message)
        self.busses=busses

    def on_next_cue(self, button):
        streamnum = int(button.props.name[-1])
        if self.data['cue_%d' % streamnum] < len(self.cues[str(streamnum)])-1:
            self.data['cue_%d' % streamnum] += 1
            self.data['file_%d' % streamnum] = self.data['filepath']+self.cues[str(streamnum)][self.data['cue_%d'%streamnum]]
            self.players[streamnum].change_file(self.data['file_%d'%streamnum])

    def on_prev_cue(self, button):
        streamnum = int(button.props.name[-1])
        if self.data['cue_%d' % streamnum] > 0:
            self.data['cue_%d' % streamnum] -= 1
            self.data['file_%d' % streamnum] = self.data['filepath']+self.cues[str(streamnum)][self.data['cue_%d'%streamnum]]
            self.players[streamnum].change_file(self.data['file_%d'%streamnum])

    def on_reverse(self, button):
        streamnum = int(button.props.name[-1])
        self.players[streamnum].reverse()

    def on_jump(self, button):
        streamnum = int(button.props.name[-1])
        self.players[streamnum].jump_loop()

    def on_alpha_move(self, slider):
        if slider.props.name == 'alpha_main':
            self.data[slider.props.name] = slider.get_value()
        else:
            self.data['alpha_0'] = 1 - slider.get_value()
            self.data['alpha_1'] = slider.get_value()
        self.update_alpha_channels()

    def on_slider_move(self, slider, channel):
        streamnum = int(slider.props.name[-1])
        self.players[streamnum].update_color_channel(channel, slider.get_value())

    def on_channel_reset(self, button, slider):
        slider.set_value(0)

    def on_pause(self, button):
        streamnum=int(button.props.name[-1])
        if self.players[streamnum].playing:
            self.monitors[streamnum].set_state(Gst.State.PAUSED)
        else:
            self.monitors[streamnum].set_state(Gst.State.PLAYING)
        self.players[streamnum].pause_play()

    def on_bounce(self, button):
        streamnum=int(button.props.name[-1])
        if button.get_active():
            self.players[streamnum].loop = 2
        else:
            self.players[streamnum].loop = 1

    def on_fullscreen(self, button):
        self.view_win.fullscreen()

    def on_change_speed(self, slider):
        streamnum = int(slider.props.name[-1])
        current_speed = slider.get_value()
        if current_speed >= 1:
            new_speed = current_speed ** 4
        else:
            new_speed = math.log(current_speed+1,2)
        self.data['rate_%d' % streamnum] = new_speed
        self.players[streamnum].set_speed(new_speed)


    def on_sync_message(self, bus, msg):
        msg.src.set_property('force-aspect-ratio', True)
        if msg.src.name == "output":
            msg.src.set_window_handle(self.xid2)
        elif msg.src.name == "mon_0":
            msg.src.set_window_handle(self.monitor.get_property('window').get_xid())
            msg.src.set_render_rectangle(0,0,240,180)
        elif msg.src.name == "mon_1":
            msg.src.set_render_rectangle(480,0,240,180)
            msg.src.set_window_handle(self.monitor.get_property('window').get_xid())
        elif msg.src.name == "mon_2":
            msg.src.set_render_rectangle(240,0,240,180)
            msg.src.set_window_handle(self.monitor.get_property('window').get_xid())
        msg.src.expose()

    def update_alpha_channels(self):
        alpha_0 = self.data['alpha_0'] * self.data['alpha_main']
        alpha_1 = self.data['alpha_1'] * self.data['alpha_main']
        mixer = self.out.get_by_name('mix')
        sink_0 = mixer.get_static_pad('sink_0')
        sink_1 = mixer.get_static_pad('sink_1')
        sink_0.set_property('alpha', alpha_0)
        sink_1.set_property('alpha', alpha_1)

    def clean_quit(self, destroy, *args):
        self.players[0].stop()
        self.players[1].stop()
        self.monitors[0].set_state(Gst.State.NULL)
        self.monitors[1].set_state(Gst.State.NULL)
        self.monitors[2].set_state(Gst.State.NULL)
        self.out.set_state(Gst.State.NULL)
        Gtk.main_quit(destroy,*args)
        self.server.shutdown()

    def build_speed_controls(self):
        control_box = Gtk.Grid()
        for i in range(2):
            speed_slider = Gtk.Scale.new_with_range(0,0,2,.01)
            speed_slider.set_size_request(240,40)
            speed_slider.add_mark(1, Gtk.PositionType.BOTTOM, None)
            speed_slider.set_value(1)
            speed_slider.set_name('speed%d' % i)
            speed_slider.connect("value_changed", self.on_change_speed)
            self.controls['speed%d' % i] = speed_slider
            reverse_button = Gtk.Button(label='REV')
            reverse_button.set_name('reverse%d' % i)
            reverse_button.connect("clicked", self.on_reverse)
            self.controls['reverse%d' % i] = reverse_button
            control_box.attach(speed_slider,i*7,0,7,2)
            control_box.attach_next_to(reverse_button,speed_slider,3,1,1)
            jump_button = Gtk.Button(label='JMP')
            jump_button.set_name('jump%d' % i)
            jump_button.connect("clicked", self.on_jump)
            self.set_control(jump_button)
            control_box.attach_next_to(jump_button,reverse_button,Gtk.PositionType.RIGHT,1,1)
            pause_button = Gtk.Button(label='PP',name='pause%d'%i)
            pause_button.connect("clicked", self.on_pause)
            self.set_control(pause_button)
            control_box.attach_next_to(pause_button,jump_button,Gtk.PositionType.RIGHT,1,1)
            bounce_button = Gtk.ToggleButton(label='BNC', name='bounce%d'%i)
            bounce_button.connect("toggled", self.on_bounce)
            self.set_control(bounce_button)
            control_box.attach_next_to(bounce_button,pause_button,Gtk.PositionType.RIGHT,1,1)
            next_cue = Gtk.Button(label="NXT",name="next%d"%i)
            next_cue.connect("clicked", self.on_next_cue)
            self.set_control(next_cue)
            prev_cue = Gtk.Button(label="PRV",name="prev%d"%i)
            prev_cue.connect("clicked", self.on_prev_cue)
            self.set_control(prev_cue)
            control_box.attach_next_to(prev_cue,bounce_button,Gtk.PositionType.RIGHT,1,1)
            control_box.attach_next_to(next_cue,prev_cue,Gtk.PositionType.RIGHT,1,1)
        return control_box

    def set_control(self, widget):
        self.controls[widget.props.name] = widget


    def build_color_sliders(self):
        slider_box = Gtk.Grid()
        channels = ["HUE","SATURATION","CONTRAST","BRIGHTNESS"]
        for i in range(2):
            j = 0
            for channel in channels:
                slider = Gtk.Scale.new_with_range(1,-1000,1000,50)
                slider.set_name(channel.lower() + "_%d" % i)
                slider.label = channel
                slider.set_size_request(40,400)
                slider.set_value(0)
                slider.add_mark(0, Gtk.PositionType.LEFT, None)
                slider.connect("value_changed", self.on_slider_move, channel)
                slider_box.attach(slider,j+i*4,0,1,1)
                button = Gtk.Button(label=channel[0:3])
                button.connect("clicked", self.on_channel_reset, slider)
                slider_box.attach(button,j+i*4,1,1,1)
                self.controls[channel.lower()+str(i)] = slider
                self.controls[channel.lower()+"_rst%d"%i] = button
                # self.controls[channel.lower()+'button'+str(i)] = button
                j += 1
        return slider_box

    def create_grandmaster(self):
        grandmaster = Gtk.Scale.new_with_range(1,0,1,.01)
        grandmaster.set_inverted(True)
        grandmaster.set_value(1.0)
        grandmaster.set_name('alpha_main')
        grandmaster.connect('value_changed', self.on_alpha_move)
        grandmaster.set_size_request(40, 230)
        self.controls['master'] = grandmaster
        return grandmaster

    def create_crossfader(self):
        crossfader = Gtk.Scale.new_with_range(0,0,1,.01)
        crossfader.set_value(0.5)
        crossfader.set_show_fill_level(True)
        crossfader.set_name('alpha_both')
        crossfader.connect('value_changed', self.on_alpha_move)
        crossfader.set_size_request(480,40)
        self.controls['crossfader'] = crossfader
        return crossfader

    def create_view_win(self):
        self.view_win = Gtk.Window(Gtk.WindowType.TOPLEVEL)
        self.view_win.set_default_size(800,600)
        drawing_area = Gtk.DrawingArea()
        self.view_win.add(drawing_area)
        self.view_win.show_all()
        self.xid2 = drawing_area.get_property("window").get_xid()

    def create_ctrl_win(self):
        self.ctrl_win = Gtk.Window(Gtk.WindowType.TOPLEVEL)
        self.ctrl_win.connect("destroy", self.clean_quit, "WM destroy")
        self.ctrl_win.set_default_size(800,800)
        grid = Gtk.Grid()
        self.monitor = Gtk.DrawingArea()
        self.monitor.set_size_request(720,180)
        grid.attach(self.monitor,0,0,10,1)
        gm = self.create_grandmaster()
        grid.attach_next_to(gm,self.monitor,Gtk.PositionType.RIGHT,1,2)
        speed_ctrls = self.build_speed_controls()
        grid.attach_next_to(speed_ctrls,self.monitor,3,1,1)
        cf = self.create_crossfader()
        grid.attach_next_to(cf,speed_ctrls,Gtk.PositionType.BOTTOM,1,1)
        fs = Gtk.Button(label="FS")
        fs.connect("clicked", self.on_fullscreen)
        grid.attach_next_to(fs,gm,Gtk.PositionType.BOTTOM,1,1)
        sliders = self.build_color_sliders()
        grid.attach_next_to(sliders,cf,Gtk.PositionType.BOTTOM,8,8)

        self.ctrl_win.add(grid)
        self.ctrl_win.show_all()
        self.xid1 = self.ctrl_win.get_property("window").get_xid()        

if __name__=='__main__':
    Gdk.threads_init()
    Gst.init()
    g = GTK_Main()
    Gtk.main()
