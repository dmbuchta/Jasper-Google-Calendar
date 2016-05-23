import httplib2
import sys
import datetime
import re
import gflags
import calendar
from jasper import plugin
from jasper import paths
from jasper.app_utils import get_timezone, is_repeat, is_cancel, is_negative, \
    is_positive
from dateutil import tz
from dateutil import parser
from dateutil.relativedelta import relativedelta
from apiclient.discovery import build
from oauth2client.file import Storage
from oauth2client.client import AccessTokenRefreshError
from oauth2client.client import OAuth2WebServerFlow
from oauth2client.tools import run_flow

FLAGS = gflags.FLAGS
WORDS = ["Calendar", "Events", "Check", "My"]
last_thing_said = None


def check_if_valid(phrases, text):
    phrases = re.compile(r"\b(%s)\b" % "|".join(phrases), re.IGNORECASE)
    if type(text) is list or type(text) is tuple:
        text = ", ".join(text)
    return bool(phrases.search(text))


def ask(mic, question, tries_until_break=3):
    orig_question = question
    num_tries = tries_until_break
    while True:
        response = mic.ask(question)
        tries_until_break -= 1
        if tries_until_break <= 0 or (len(response) >= 1 and len(response[0])):
            break
        question = "I couldn't get that"
    if not len(response) or not len(response[0]):
        return False
    if is_repeat(response) and last_thing_said:
        mic.say(last_thing_said)
        return ask(mic, orig_question, num_tries)
    return response


def say(mic, statement):
    global last_thing_said
    last_thing_said = statement
    mic.say(last_thing_said)


def get_start_of_day(dayOfInterest):
    return datetime.datetime(dayOfInterest.year, dayOfInterest.month,
                             dayOfInterest.day)


def get_end_of_day(dayOfInterest):
    return get_start_of_day(dayOfInterest) + datetime.timedelta(days=1,
                                                                minutes=-1)


def get_summary(event):
    if 'summary' in event:
        return str(event['summary'])
    return "An Event"


class CalendarPlugin(plugin.SpeechHandlerPlugin):
    def __init__(self, *args, **kwargs):
        super(CalendarPlugin, self).__init__(*args, **kwargs)
        # check if the noauth_local_webserver param was provided
        # this is necessary for first time authentication only
        if bool(re.search('--noauth_local_webserver', str(sys.argv),
                          re.IGNORECASE)):
            argv = FLAGS(sys.argv[1])

        self.service = build_google_service(self.profile)

    def add_event(self, mic):
        while True:
            try:
                event_data = ask(mic,
                                 self.gettext("What would you like to add?"))
                if not event_data or is_cancel(event_data):
                    return False
                event = self.service.events().quickAdd(
                    calendarId='primary',
                    text=event_data[0]).execute()

                while True:
                    say(mic, self.gettext(
                        "Added event {summary} on {date} {time}").format(
                        summary=get_summary(event),
                        date=self.get_readable_date(event),
                        time=self.get_readable_time(event)))
                    confirmation = ask(mic, self.gettext(
                        "Is this what you wanted?"))
                    if not confirmation:
                        confirmation = ""
                    if is_positive(confirmation):
                        mic.say(self.gettext("Okay, it's on your calendar"))
                        return True
                    elif is_negative(confirmation):
                        mic.say(self.gettext(
                            "My mistake, english is my second language."))
                        self.service.events().delete(calendarId='primary',
                                                     eventId=event[
                                                         'id']).execute()
                        return self.add_event(mic)
                    else:
                        mic.say(self.gettext(
                            "My mistake, english is my second language."))
                        self.service.events().delete(calendarId='primary',
                                                     eventId=event[
                                                         'id']).execute()
                        return False
            except KeyError:
                mic.say(self.gettext(
                    "For some reason I am having trouble doing that."))
                return False

    # gets all events today
    def get_todays_events(self, mic):
        date = datetime.datetime.now(tz=get_timezone(self.profile))
        return self.get_events_on(mic, date, "today")

    # gets all events tomorrow
    def get_tomorrows_events(self, mic):
        date = datetime.datetime.now(
            tz=get_timezone(self.profile)) + datetime.timedelta(days=1)
        return self.get_events_on(mic, date, "tomorrow")

    # gets all events on the provided next day of week (Monday, Tuesday, etc..)
    def get_events_on_next_day_of_week(self, mic, text):
        day_of_week = None
        for phrase in text:
            for day in list(calendar.day_name):
                if (re.search(r'\b%s\b' % day, phrase, re.IGNORECASE)):
                    day_of_week = day
                    break;
            if day_of_week:
                break
        date = datetime.datetime.now(tz=get_timezone(self.profile))
        day_of_week_idx = list(calendar.day_name).index(day_of_week)
        if day_of_week_idx == date.weekday():
            time_diff = datetime.timedelta(days=7)
        elif day_of_week_idx <= date.weekday():
            time_diff = datetime.timedelta(days=(7 - day_of_week_idx))
        else:
            time_diff = datetime.timedelta(
                days=(day_of_week_idx - date.weekday()))
        return self.get_events_on(mic, date + time_diff, "next " + day_of_week)

    def get_events_on(self, mic, date, keyword):
        events = self.query_events(
            self.convert_date_to_google_str(get_start_of_day(date)),
            self.convert_date_to_google_str(get_end_of_day(date)))
        if len(events) == 0:
            mic.say(self.gettext(
                "You have no events scheduled for {keyword}").format(
                keyword=keyword))
        else:
            sep = ""
            output = []
            for event in events:
                event_title = get_summary(event)
                output.append(sep + event_title + self.get_readable_time(event))
                sep = self.gettext("AND") + " "
            say(mic, output)
        return True

    def search_calendar(self, mic, text):
        search_term = None
        for phrase in text:
            if "search" in phrase.lower():
                search_term = phrase.lower().replace("search", "")
                break
        search_term = search_term.replace("calendar for", "").strip()
        today = get_start_of_day(
            datetime.datetime.now(tz=get_timezone(self.profile)))
        one_month_from_today = today + relativedelta(months=1)
        events = self.query_events(self.convert_date_to_google_str(today),
                                   self.convert_date_to_google_str(
                                       one_month_from_today), search_term)

        if len(events) == 0:
            mic.say(self.gettext("You don't have any events like that"))
        else:
            sep = ""
            output = []
            for event in events:
                event_title = get_summary(event)
                output.append(
                    sep + self.gettext("ON") + " " + self.get_readable_date(
                        event) + " " + event_title + self.get_readable_time(
                        event))
                sep = self.gettext("AND") + " "
            say(mic, output)
        return True

    def handle(self, text, mic):
        global last_thing_said
        last_thing_said = None
        do_continue = True
        first_time = True
        text = [text]
        while True:
            if not text:
                text = ""
            if check_if_valid(self.get_phrases_for_adding(), text):
                do_continue = self.add_event(mic)
            elif check_if_valid([self.gettext("TODAY")], text):
                do_continue = self.get_todays_events(mic)
            elif check_if_valid([self.gettext("TOMORROW")], text):
                do_continue = self.get_tomorrows_events(mic)
            elif check_if_valid(self.get_day_of_week_phrases(), text):
                do_continue = self.get_events_on_next_day_of_week(mic, text)
            elif check_if_valid([self.gettext("SEARCH")], text):
                do_continue = self.search_calendar(mic, text)
            elif first_time:
                text = ask(mic, self.gettext(
                    "Would you like to do something with your calendar?"),
                           tries_until_break=0)
                do_continue = False
                first_time = False
                continue

            if do_continue:
                text = ask(mic, self.gettext(
                    "Is there anything else you would like to do?"),
                           tries_until_break=0)
                do_continue = False
            else:
                mic.say(self.gettext("Alright then"))
                break
            first_time = False

        return False

    def get_phrases_for_adding(self):
        return [self.gettext("ADD"), self.gettext("CREATE"),
                self.gettext("SET")]

    def get_phrases(self):
        return [self.gettext("CALENDAR")]

    def get_day_of_week_phrases(self):
        return [self.gettext("Monday"), self.gettext("Tuesday"),
                self.gettext("Wednesday"), self.gettext("Thursday"),
                self.gettext("Friday"), self.gettext("Saturday"),
                self.gettext("Sunday")]

    def is_valid(self, text):
        """
        Returns True if input is related to the time.

        Arguments:
        text -- user-input, typically transcribed speech
        """
        return check_if_valid(self.get_phrases(), text)

    # querys google events, expecting start and end to be
    # already converted to google format
    def query_events(self, start, end, keywords=None, ):
        page_token = None
        my_events = []
        while True:
            # Gets events from primary calender from each page in present day boundaries
            if not keywords:
                events = self.service.events().list(calendarId='primary',
                                                    pageToken=page_token,
                                                    timeMin=start, timeMax=end,
                                                    singleEvents=True,
                                                    orderBy="startTime").execute()
            else:
                events = self.service.events().list(calendarId='primary',
                                                    pageToken=page_token,
                                                    timeMin=start, timeMax=end,
                                                    q=keywords,
                                                    singleEvents=True,
                                                    orderBy="startTime").execute()
            my_events.extend(events['items'])
            page_token = events.get('nextPageToken')
            if not page_token:
                break
        return my_events

    # returns a readable date phrase from Google event
    def get_readable_date(self, event):
        event_start_time = event['start']
        if "dateTime" in event_start_time:
            date = self.convert_google_date_str(event_start_time['dateTime'])
        else:
            date = event_start_time['date'].split("-")
            date = datetime.datetime(year=int(date[0]), month=int(date[1]),
                                     day=int(date[2]),
                                     tzinfo=get_timezone(self.profile))
        # if it's with 7 days, say the name of day
        if (date - datetime.datetime.now(
                tz=get_timezone(self.profile))).days <= 7:
            return " " + self.gettext("next") + " " + calendar.day_name[
                date.weekday()]
        # else return Month, Day Number
        return calendar.month_name[date.month] + " " + str(date.day)

    # returns a readable time phrase from Google event
    def get_readable_time(self, event):
        event_start_time = event['start']
        if "dateTime" in event_start_time:
            date = self.convert_google_date_str(event_start_time['dateTime'])
            startMinute = ":" + str(date.minute)
            startHour = date.hour
            appendingTime = self.gettext("am")
            if ((date.hour - 12) > 0):
                startHour = date.hour - 12
                appendingTime = self.gettext("pm")
            if date.minute == 0:
                startMinute = ""
            elif (date.minute < 10):
                startMinute = " O " + str(date.minute)
            return " " + self.gettext("at") + " " + str(
                startHour) + startMinute + " " + appendingTime
        return " " + self.gettext("all day")

    def convert_google_date_str(self, dateStr):
        date = parser.parse(dateStr)
        return date.astimezone(get_timezone(self.profile))

    def convert_date_to_google_str(self, d):
        date_str = get_timezone(self.profile).normalize(
            get_timezone(self.profile).localize(d)).astimezone(
            tz.tzutc()).isoformat('T')
        return date_str


def build_google_service(profile):
    # The scope URL for read/write access to a user's calendar data
    scope = 'https://www.googleapis.com/auth/calendar'
    client_id = profile["google_calendar"]["id"]
    client_secret = profile["google_calendar"]["secret"]
    try:
        credentials_home = profile["google_calendar"]["credentials"]
    except KeyError:
        credentials_home = paths.config('calendar/credentials.dat')

    # Create a flow object. This object holds the client_id, client_secret,
    # and scope. It assists with OAuth 2.0 steps to get user authorization
    # and credentials.
    flow = OAuth2WebServerFlow(client_id, client_secret, scope)

    # Create a Storage object. This object holds the credentials that your
    # application needs to authorize access to the user's data. The name of
    # the credentials file is provided. If the file does not exist, it is
    # created. This object can only hold credentials for a single user, so
    # as-written, this script can only handle a single user.

    storage = Storage(credentials_home)
    # storage = Storage('credentials.dat')

    # The get() function returns the credentials for the Storage object.
    # If no credentials were found, None is returned.
    credentials = storage.get()

    # If no credentials are found or the credentials are invalid due to
    # expiration, new credentials need to be obtained from the authorization
    # server. The oauth2client.tools.run_flow() function attempts to open an
    # authorization server page in your default web browser. The server
    # asks the user to grant your application access to the user's data.
    # If the user grants access, the run_flow() function returns new
    # credentials. The new credentials are also stored in the supplied
    # Storage object, which updates the credentials.dat file.
    if credentials is None or credentials.invalid:
        credentials = run_flow(flow, storage)

    # Create an httplib2.Http object to handle our HTTP requests, and
    # authorize it using the credentials.authorize() function.
    http = httplib2.Http()
    http = credentials.authorize(http)

    # The apiclient.discovery.build() function returns an instance of an
    # API service object can be used to make API calls. The object is
    # constructed with methods specific to the calendar API. The arguments
    # provided are:
    #   name of the API ('calendar')
    #   version of the API you are using ('v3')
    #   authorized httplib2.Http() object that can be used for API calls
    return build('calendar', 'v3', http=http)
