import httplib2
import sys
import datetime
import re
import gflags
import calendar

from client.app_utils import getTimezone
from dateutil import tz
from dateutil import parser
from apiclient.discovery import build
from oauth2client.file import Storage
from oauth2client.client import AccessTokenRefreshError
from oauth2client.client import OAuth2WebServerFlow
from oauth2client.tools import *


# Written by Marc Poul Joseph Laventure

FLAGS = gflags.FLAGS
WORDS = [ "Calendar", "Events", "Check", "My" ]
client_id = 'xxxxxxxx.apps.googleusercontent.com'
client_secret = 'xxxxxxxxxxxxxx'

monthDict = {'January': '01', 
		'February': '02',
		'March': '03',
		'April': '04',
		'May': '05',
		'June': '06',
		'July': '07',
		'August': '08',
		'September': '09',
		'October': '10',
		'November': '11',
		'December': '12'}

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


def addEvent(profile, mic):

	while True:
		try:
			mic.say("What would you like to add?")
			eventData = mic.activeListen()
			createdEvent = service.events().quickAdd(calendarId='primary', text=eventData).execute()
			eventRawStartTime = createdEvent['start']

			m = re.search('([0-9]{4})-([0-9]{2})-([0-9]{2})T([0-9]{2}):([0-9]{2}):([0-9]{2})', str(eventRawStartTime))
			eventDateYear = str(m.group(1))
			eventDateMonth = str(m.group(2))
			eventDateDay = str(m.group(3))
			eventTimeHour = str(m.group(4))
			eventTimeMinute =  str(m.group(5))
			appendingTime = "am"

			if len(eventTimeMinute) == 1:
				eventTimeMinute = eventTimeMinute + "0"

			eventTimeHour = int(eventTimeHour)

			if ((eventTimeHour - 12) > 0 ):
					eventTimeHour = eventTimeHour - 12
					appendingTime = "pm"

			dictKeys = [ key for key, val in monthDict.items() if val==eventDateMonth ]
			eventDateMonth = dictKeys[0]
			mic.say("Added event " + createdEvent['summary'] + " on " + str(eventDateMonth) + " " + str(eventDateDay) + " at " + str(eventTimeHour) + ":" + str(eventTimeMinute) + " " + appendingTime)
			mic.say("Is this what you wanted?")
			userResponse = mic.activeListen()

			if bool(re.search('Yes', userResponse, re.IGNORECASE)):
				mic.say("Okay, I added it to your calendar")
				return

			service.events().delete(calendarId='primary', eventId=createdEvent['id']).execute()

		except KeyError:

			mic.say("Could not add event to your calender; check if internet issue.")
			mic.say("Would you like to attempt again?")
			responseRedo = mic.activeListen()

			if bool(re.search(r'\bNo\b', responseRedo, re.IGNORECASE)):
				return

def getEventsToday(profile, mic):
	tz = getTimezone(profile)
	d = datetime.datetime.now(tz=tz)
	getEventsOn(d, tz, mic, "today")

def getEventsTomorrow(profile, mic):
	tz = getTimezone(profile)
	d = datetime.datetime.now(tz=tz) + datetime.timedelta(days=1)
	getEventsOn(d, tz, mic, "tomorrow")

def getEventsOnNextDayOfWeek(profile, mic, dayOfWeekStr ):
	tz = getTimezone(profile)
	d = datetime.datetime.now(tz=tz);
	dayOfWeek = list(calendar.day_name).index(dayOfWeekStr)
	if ( dayOfWeek == d.weekday() ):
		timediff = datetime.timedelta(days=7)
	elif ( dayOfWeek <= d.weekday() ):
		timediff = datetime.timedelta(days=(7-dayOfWeek))
	else:
		timediff = datetime.timedelta(days=(dayOfWeek-d.weekday()))
	getEventsOn(d+timediff, tz, mic, "next " + dayOfWeekStr)


def getEventsOn( day, tz, mic, keyword ):

	dayStartTime = convertDateToGoogleStr(tz, getStartOfDay(day))
	dayEndTime = convertDateToGoogleStr(tz, getEndOfDay(day))

	page_token = None

	while True:
		# Gets events from primary calender from each page in present day boundaries
		events = service.events().list(calendarId='primary', pageToken=page_token, timeMin=dayStartTime, timeMax=dayEndTime).execute()

		if(len(events['items']) == 0):
			mic.say(  "You have no events scheduled for " + keyword )
			return

		sep = ""
		for event in events['items']:
			try:
				if 'summary' in event:
					eventTitle = str(event['summary'])
				else:
					eventTitle = "An Event"
				eventRawStartTime = event['start']
				if "dateTime" in eventRawStartTime:
					eventDate = convertGoogleDateStr(eventRawStartTime['dateTime'], tz)
					startMinute = ":" + str(eventDate.minute)
					startHour = eventDate.hour
					appendingTime = "am"
					if ((eventDate.hour - 12) > 0 ):
						startHour = eventDate.hour - 12
						appendingTime = "pm"
					if eventDate.minute == 0:
						startMinute = ""
					elif (eventDate.minute < 10):
						startMinute = " oh " + str(eventDate.minute)
					phrase = sep + eventTitle + " at " + str(startHour) +  startMinute + " " + appendingTime
				else:
					phrase = sep + eventTitle + " all day"
				mic.say( phrase )
				sep = "and "
			except KeyError, e:
				print( e )
				mic.say("You have something listed but I cannot read it.")

		page_token = events.get('nextPageToken')

		if not page_token:
			return

# Create a flow object. This object holds the client_id, client_secret, and
# scope. It assists with OAuth 2.0 steps to get user authorization and
# credentials.

flow = OAuth2WebServerFlow(client_id, client_secret, scope)


# Create a Storage object. This object holds the credentials that your
# application needs to authorize access to the user's data. The name of the
# credentials file is provided. If the file does not exist, it is
# created. This object can only hold credentials for a single user, so
# as-written, this script can only handle a single user.
storage = Storage('credentials.dat')

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
service = build('calendar', 'v3', http=http)

def handle(text, mic, profile, recursive=False):

	if not text and recursive:
		mic.say("Okay nevermind then")
	if bool(re.search(r'\b(Add|Create|Set)\b', text, re.IGNORECASE)):
		addEvent(profile,mic)
	elif bool(re.search(r'\bToday\b', text, re.IGNORECASE)):
		getEventsToday(profile,mic)
	elif bool(re.search(r'\bTomorrow\b', text, re.IGNORECASE)):
		getEventsTomorrow(profile,mic)
	elif bool(re.search(r'\b(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b', text, re.IGNORECASE)):
		for day in list(calendar.day_name):
			if ( re.search(r'\b%s\b' % day, text, re.IGNORECASE) ):
				getEventsOnNextDayOfWeek(profile, mic, day)
				break;
	elif not recursive:
		mic.say("Did you want to do something with your calendar?")
		handle( mic.activeListen(), mic, profile, True )
	else:
		mic.say("Okay nevermind then")



def isValid(text):
	return bool(re.search(r'\bCalendar\b', text, re.IGNORECASE))
