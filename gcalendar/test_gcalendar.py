# -*- coding: utf-8 -*-
import unittest
from jasper import testutils, diagnose
from . import gcalendar

"""
Due to Google Calendar being different for everyone, complete test coverage
is not possible. Only the very basic methods are being tested for runtime errors
"""


class TestCalendarPlugin(unittest.TestCase):
    def setUp(self):
        self.plugin = testutils.get_plugin_instance(
            gcalendar.CalendarPlugin)

    @unittest.skipIf(not diagnose.check_network_connection(),
                     "No internet connection")
    def test_building_google_service(self):
        self.assertTrue(self.plugin.service is not None)

    def test_is_valid_method(self):
        self.assertTrue(self.plugin.is_valid(
            "What's on my calendar today?"))
        self.assertTrue(self.plugin.is_valid("Search Calendar for flight"))
        self.assertFalse(self.plugin.is_valid("What time is it?"))

    def test_get_todays_events(self):
        mic = testutils.TestMic()
        self.plugin.get_todays_events(mic)

    def test_get_tomorrows_events(self):
        mic = testutils.TestMic()
        self.plugin.get_tomorrows_events(mic)

    def test_get_tomorrows_events(self):
        mic = testutils.TestMic()
        self.plugin.get_tomorrows_events(mic)

    def test_handle_events_by_day_of_week(self):
        inputs = ["What do I have on Monday", "What do I have on Tuesday",
                  "What do I have on Wednesday", "What do I have on Thursday",
                  "What do I have on Friday",
                  "What do I have on Saturday", "What do I have on Sunday"]
        mic = testutils.TestMic(inputs)
        self.plugin.handle("Something about my Calendar", mic)
        self.assertTrue(len(mic.outputs) == 16)
        for index, output in enumerate(mic.outputs):
            if index == 0:
                self.assertTrue(
                    output == "Would you like to do something with your calendar?")
            elif index == 15:
                self.assertTrue(output == "Alright then")
            elif index % 2 == 0:
                self.assertTrue(
                    output == "Is there anything else you would like to do?")
            else:
                self.assertTrue(type(
                    output) == list or "You have no events scheduled for next" in output)

    def test_adding_and_then_cancelling(self):
        inputs = ["Dentist Tomorrow at 10 pm", "cancel"]
        mic = testutils.TestMic(inputs)
        self.plugin.handle("Add Event", mic)

    def test_handle_searching_calendar(self):
        mic = testutils.TestMic()
        self.plugin.handle("Search Calendar for Flight", mic)
        self.assertTrue(len(mic.outputs) == 3)
        self.assertTrue(type(mic.outputs[0]) == list or
                        mic.outputs[0] == "You don't have any events like that")
