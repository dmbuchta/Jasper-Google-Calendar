import httplib2
import sys
import datetime
import re
import gflags
import calendar
import jasperpath

from client.app_utils import getTimezone
from dateutil import tz
from dateutil import parser
from dateutil.relativedelta import relativedelta
from apiclient.discovery import build
from oauth2client.file import Storage
from oauth2client.client import AccessTokenRefreshError
from oauth2client.client import OAuth2WebServerFlow
from oauth2client.tools import *


# Written by Marc Poul Joseph Laventure

FLAGS = gflags.FLAGS
WORDS = [ "Calendar", "Events", "Check", "My" ]

# The scope URL for read/write access to a user's calendar data
scope = 'https://www.googleapis.com/auth/calendar'
if bool(re.search('--noauth_local_webserver', str(sys.argv), re.IGNORECASE)):
    argv = FLAGS(sys.argv[1])

def convertDateToGoogleStr(timezone, d):
    dateStr = timezone.normalize(timezone.localize(d)).astimezone(tz.tzutc()).isoformat('T')
    return dateStr

def getStartOfDay( dayOfInterest ):
    return datetime.datetime(dayOfInterest.year, dayOfInterest.month, dayOfInterest.day )

def getEndOfDay(dayOfInterest):
    return getStartOfDay(dayOfInterest) + datetime.timedelta(days=1, minutes=-1 )

def convertGoogleDateStr( dateStr, tz ):
    date = parser.parse(dateStr)
    return date.astimezone( tz )


def addEvent(profile, mic, service):

    while True:
        try:
            mic.say("What would you like to add?")
            eventData = mic.activeListen()
            createdEvent = service.events().quickAdd(calendarId='primary', text=eventData).execute()
            mic.say("Added event " + createdEvent['summary'] + " on " + getReadableDateFromEvent(createdEvent, getTimezone(profile)) +
                    " " + getReadableTimeFromEvent(createdEvent, getTimezone(profile)))
            mic.say("Is this what you wanted?")
            if bool(re.search(r'\bYes\b', mic.activeListen(), re.IGNORECASE)):
                mic.say("Okay, it's on your calendar")
            else:
                mic.say("My mistake, english is my second language.")
                service.events().delete(calendarId='primary', eventId=createdEvent['id']).execute()
            return
        except KeyError:

            mic.say("Could not add event to your calender; check if internet issue.")
            mic.say("Would you like to attempt again?")
            responseRedo = mic.activeListen()

            if bool(re.search(r'\bNo\b', responseRedo, re.IGNORECASE)):
                return

#gets all events today
def getEventsToday(profile, mic, service):
    tz = getTimezone(profile)
    d = datetime.datetime.now(tz=tz)
    getEventsOn(d, tz, mic, "today", service)

#gets all events tomorrow
def getEventsTomorrow(profile, mic, service):
    tz = getTimezone(profile)
    d = datetime.datetime.now(tz=tz) + datetime.timedelta(days=1)
    getEventsOn(d, tz, mic, "tomorrow", service)

#gets all events on the provided next day of week (Monday, Tuesday, etc..)
def getEventsOnNextDayOfWeek(profile, mic, dayOfWeekStr, service ):
    tz = getTimezone(profile)
    d = datetime.datetime.now(tz=tz)
    dayOfWeek = list(calendar.day_name).index(dayOfWeekStr)
    if ( dayOfWeek == d.weekday() ):
        timediff = datetime.timedelta(days=7)
    elif ( dayOfWeek <= d.weekday() ):
        timediff = datetime.timedelta(days=(7-dayOfWeek))
    else:
        timediff = datetime.timedelta(days=(dayOfWeek-d.weekday()))
    getEventsOn(d+timediff, tz, mic, "next " + dayOfWeekStr, service)

#gets all events on the provided day
def getEventsOn( day, tz, mic, keyword, service ):
    events = queryEvents(convertDateToGoogleStr(tz, getStartOfDay(day)), convertDateToGoogleStr(tz, getEndOfDay(day)), service)
    if(len(events) == 0):
        mic.say(  "You have no events scheduled for " + keyword )
        return
    sep=""
    for event in events:
        eventTitle = getSummaryFromEvent(event)
        mic.say( sep + eventTitle + getReadableTimeFromEvent(event,tz) )
        sep = "and "

#gets all events in the next month that contain keywords
def getEventsBySummary( profile, mic, keyWords, service ):
    tz = getTimezone(profile)
    today = getStartOfDay(datetime.datetime.now(tz=tz))
    oneMonthFromToday = today + relativedelta(months=1)
    events = queryEvents(convertDateToGoogleStr(tz, today), convertDateToGoogleStr(tz, oneMonthFromToday), service, keyWords)

    if len(events) == 0:
        mic.say("You don't have any events like that")
        return
    sep=""
    for event in events:
        eventTitle = getSummaryFromEvent(event)
        mic.say(  sep + " on " + getReadableDateFromEvent(event, tz) + " " + eventTitle + getReadableTimeFromEvent(event, tz) )
        sep="and"

#returns a readable title from Google event
def getSummaryFromEvent(event):
    if 'summary' in event:
        return str(event['summary'])
    return "An Event"

#returns a readable date phrase from Google event
def getReadableDateFromEvent(event, tz):
    eventRawStartTime = event['start']
    if "dateTime" in eventRawStartTime:
        date = convertGoogleDateStr(eventRawStartTime['dateTime'], tz)
    else:
        date = eventRawStartTime['date'].split("-")
        date = datetime.datetime(year=int(date[0]), month=int(date[1]), day=int(date[2]), tzinfo=tz)
    #if it's with 7 days, say the name of day
    if (date - datetime.datetime.now(tz=tz)).days <= 7:
        return " next " + calendar.day_name[date.weekday()]
    #else return Month, Day Number
    return calendar.month_name[date.month] + " " + str(date.day)

#returns a readable time phrase from Google event
def getReadableTimeFromEvent(event, tz):
    eventRawStartTime = event['start']
    if "dateTime" in eventRawStartTime:
        date = convertGoogleDateStr(eventRawStartTime['dateTime'], tz)
        startMinute = ":" + str(date.minute)
        startHour = date.hour
        appendingTime = "am"
        if ((date.hour - 12) > 0 ):
            startHour = date.hour - 12
            appendingTime = "pm"
        if date.minute == 0:
            startMinute = ""
        elif (date.minute < 10):
            startMinute = " OH " + str(date.minute)
        return " at " + str(startHour) + startMinute + " " + appendingTime
    return " all day"

#querys google events, expecting start and end to be already converted to google format
def queryEvents(start, end, service, keyWords=None, ):
    page_token = None
    myEvents = []
    while True:
        # Gets events from primary calender from each page in present day boundaries
        if not keyWords:
            events = service.events().list(calendarId='primary', pageToken=page_token, timeMin=start, timeMax=end, singleEvents=True, orderBy="startTime").execute()
        else:
            events = service.events().list(calendarId='primary', pageToken=page_token, timeMin=start, timeMax=end, q=keyWords, singleEvents=True, orderBy="startTime").execute()
        myEvents.extend(events['items'])
        page_token = events.get('nextPageToken')
        if not page_token:
            break
    return myEvents

def handle(text, mic, profile, recursive=False):
    print ("****")
    if not text and recursive:
        mic.say("Okay nevermind then")
    if bool(re.search(r'\b(Add|Create|Set)\b', text, re.IGNORECASE)):
        addEvent(profile,mic, getService(profile))
    elif bool(re.search(r'\bToday\b', text, re.IGNORECASE)):
        getEventsToday(profile,mic, getService(profile))
    elif bool(re.search(r'\bTomorrow\b', text, re.IGNORECASE)):
        getEventsTomorrow(profile,mic, getService(profile))
    elif bool(re.search(r'\b(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b', text, re.IGNORECASE)):
        for day in list(calendar.day_name):
            if ( re.search(r'\b%s\b' % day, text, re.IGNORECASE) ):
                getEventsOnNextDayOfWeek(profile, mic, day, getService(profile))
                break;
    elif bool(re.search(r'\b(Search)\b', text, re.IGNORECASE)):
        if bool(re.search(r'\b(calendar for)\b', text, re.IGNORECASE)):
            text = str(text).lower().replace("search calendar for","")
            if len(str.strip(text)) > 0:
                mic.say("I am searching for " + text)
                getEventsBySummary( profile, mic, text, getService(profile) )
                return
        mic.say("What events would you like to search for?")
        getEventsBySummary( profile, mic, mic.activeListen(), getService(profile) )
    elif not recursive:
        mic.say("Did you want to do something with your calendar?")
        handle( mic.activeListen(), mic, profile, True )
    else:
        mic.say("Okay nevermind then")

def getService(profile):
    print ("TESTTEST")
    client_id = profile["google_calendar"]["id"]
    client_secret = profile["google_calendar"]["secret"]

    print ("TEST")

    # Create a flow object. This object holds the client_id, client_secret, and
    # scope. It assists with OAuth 2.0 steps to get user authorization and
    # credentials.
    flow = OAuth2WebServerFlow(client_id, client_secret, scope)


    # Create a Storage object. This object holds the credentials that your
    # application needs to authorize access to the user's data. The name of the
    # credentials file is provided. If the file does not exist, it is
    # created. This object can only hold credentials for a single user, so
    # as-written, this script can only handle a single user.

    print( jasperpath.config('calendar/credentials.dat') )

    storage = Storage(jasperpath.config('calendar/credentials.dat'))
    # storage = Storage('credentials.dat')

    # The get() function returns the credentials for the Storage object. If no
    # credentials were found, None is returned.
    credentials = storage.get()

    # If no credentials are found or the credentials are invalid due to
    # expiration, new credentials need to be obtained from the authorization
    # server. The oauth2client.tools.run_flow() function attempts to open an
    # authorization server page in your default web browser. The server
    # asks the user to grant your application access to the user's data.
    # If the user grants access, the run_flow() function returns new credentials.
    # The new credentials are also stored in the supplied Storage object,
    # which updates the credentials.dat file.
    if credentials is None or credentials.invalid:
        credentials = run_flow(flow, storage)

    # Create an httplib2.Http object to handle our HTTP requests, and authorize it
    # using the credentials.authorize() function.
    http = httplib2.Http()
    http = credentials.authorize(http)

    # The apiclient.discovery.build() function returns an instance of an API service
    # object can be used to make API calls. The object is constructed with
    # methods specific to the calendar API. The arguments provided are:
    #   name of the API ('calendar')
    #   version of the API you are using ('v3')
    #   authorized httplib2.Http() object that can be used for API calls
    return build('calendar', 'v3', http=http)

def isValid(text):
    return bool(re.search(r'\bCalendar\b', text, re.IGNORECASE))
