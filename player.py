#!/usr/bin/env python3

import logging
import time

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst


logger = logging.getLogger(__name__)

class TrickPlayer():

    def __init__(self, ident):
        self.ident = ident
        self.file = None
        self.pipeline = None
        self.video_sink = None
        self.bus = None
        self.playing = False
        self.rate = 1.0
        self.loop = 1

    def set_pipeline(self):
        """Initialize the pipeline."""
        self.pipeline = Gst.parse_launch("playbin uri=file://%s flags=0x00000611" 
            % self.file)
        self.pipeline.set_state(Gst.State.READY)

    def set_video_sink(self):
        """Initialize videosink"""
        intervidsink = Gst.ElementFactory.make("intervideosink")
        intervidsink.set_property("name", ("ivs_%d" % self.ident))
        intervidsink.set_property("channel", self.ident)
        self.pipeline.set_property('video_sink', intervidsink)
        self.video_sink = self.pipeline.get_property('video_sink')
        
    def run(self):
        """Setup and start playback."""
        self.set_pipeline()
        self.set_video_sink()
        self.bus = self.pipeline.get_bus()
        self.bus.add_signal_watch()
        self.bus.connect("message", self.on_message)
     
    def on_message(self, bus, message):
        """Handle EOS message."""
        t = message.type
        if t == Gst.MessageType.EOS:
            self.jump_loop()    

    def __send_seek_event(self):
        """Format and send seek event."""
        fmat = Gst.Format.TIME
        ret, position = self.pipeline.query_position(fmat)
        if (not ret):
            logger.warning("Unable to retrieve current position.")
            return 

        if (self.rate > 0):
            seek_event = Gst.Event.new_seek(self.rate,
                Gst.Format.TIME,
                (Gst.SeekFlags.FLUSH | Gst.SeekFlags.ACCURATE),
                Gst.SeekType.SET,
                position,
                Gst.SeekType.SET,
                -1)
        else:
            seek_event = Gst.Event.new_seek(self.rate,
                Gst.Format.TIME,
                (Gst.SeekFlags.FLUSH | Gst.SeekFlags.ACCURATE),
                Gst.SeekType.SET,
                -1,
                Gst.SeekType.SET,
                position)
                
        self.video_sink.send_event(seek_event)
        logger.info("Current rate: %d", self.rate)

    def update_color_channel(self, channel_name, value):
        """Update color channel to new value."""
        channels = self.pipeline.list_channels()
        for ch in channels:
            if (ch.label == channel_name):
                channel = ch
        if (not channel):
            logger.error("Channel:%s not supported." % channel_name)
            return
        # Constrain the value.
        if (value > channel.max_value):
            value = channel.max_value
        elif (value < channel.min_value):
            value = channel.min_value
        self.pipeline.set_value(channel, value)

    def start(self):
        """Start the pipeline and set playing flag."""
        self.pipeline.set_state(Gst.State.PLAYING)
        self.playing = True

    def stop(self):
        """Stop the pipeline and unset playing flag."""
        self.pipeline.set_state(Gst.State.NULL)
        self.playing = False

    def change_file(self, newfile):
        """Change the current file."""
        self.file = newfile
        # Set pipeline to NULL before messing with it.
        self.pipeline.set_state(Gst.State.NULL)
        self.pipeline.set_property('uri', "file://%s" % newfile)
        # Reset the video sink.
        self.set_video_sink()
        # Return the pipeline to it's previous state.
        if self.playing:
            self.pipeline.set_state(Gst.State.PLAYING)
        else:
            self.pipeline.set_state(Gst.State.PAUSED)
        # IMPORTANT: Give the pipeline some time before sending seek event.
        time.sleep(.1)
        self.__send_seek_event()


    def cleanup(self):
        """Cleanly stop everything."""
        self.pipeline.set_state(Gst.State.NULL)
        if (self.video_sink):
            self.video_sink.unref()
        self.pipeline.unref()

    def pause_play(self):
        """Toggle paused/playing status and set flag."""
        self.pipeline.set_state(Gst.State.PAUSED if self.playing 
                                                 else Gst.State.PLAYING)
        self.playing = not self.playing

    def set_speed(self, rate):
        """Change playback speed."""
        self.rate = rate
        self.__send_seek_event()

    def reverse(self):
        """Reverse playback."""
        self.rate *= -1.0
        self.__send_seek_event()
    
    def jump_loop(self):
        """Restart clip or reverse."""
        if self.loop:
            if self.loop > 1:
                self.reverse()
            if (self.rate > 0):
                self.jump(0)
            else:
                self.jump(-1)
        
    def jump(self, position):
        """Restart clip from beginning or end."""
        if (self.rate > 0):
            seek_event = Gst.Event.new_seek(self.rate,
                Gst.Format.TIME,
                (Gst.SeekFlags.FLUSH | Gst.SeekFlags.ACCURATE),
                Gst.SeekType.SET,
                position,
                Gst.SeekType.SET,
                -1)
        else:
            seek_event = Gst.Event.new_seek(self.rate,
                Gst.Format.TIME,
                (Gst.SeekFlags.FLUSH | Gst.SeekFlags.ACCURATE),
                Gst.SeekType.SET,
                -1,
                Gst.SeekType.SET,
                position)

        self.video_sink.send_event(seek_event)
