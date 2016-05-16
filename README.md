Jasper-Google-Calendar
======================

Jasper Google Calendar Module

Written By: Dan Buchta

##Steps to install Google Calendar

* Install the following dependencies:
```
sudo pip install httplib2
sudo pip install --upgrade google-api-python-client
sudo easy_install --upgrade python-gflags
```
* run the following commands in order:
```
git clone https://github.com/marclave/Jasper-Google-Calendar.git
ln -s <absolute path>/Jasper-Google-Calendar/Calendar.py <absolute path to jasper/client/modules>/Calendar.py
```
* Login to [Google developer Console](https://console.developers.google.com/project) and complete the following
* The Client ID in Google needs to be for a native application.
```
Select a project.
In the sidebar on the left, select APIs & auth. In the list of APIs, make sure the status is ON for the Google Calendar API.
In the sidebar on the left, select Credentials.
Get Client ID and Client Secret (Save for later)
```
* Open profile.yml (should be at ~/.jasper/profile.yml) and add the following lines:
```
google_calendar:
  id: XXXXXXXXXXXXXXXXXXXXXXXX.apps.googleusercontent.com
  secret: XXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
```
* You will need authenitcate in a browser the first time you run the module
* If you are using a terminal you will need to take the additional steps:
  * Add these this line to jasper.py
  ```
  parser.add_argument('--noauth_local_webserver', action='store_true', help='Allow configuration for Calendar Module')
  ```
  * Then when you start jasper provide the --noauth_local_webserver param
  ```
  ./jasper.py --noauth_local_webserver
  ```
  * You will then be provided with a link, go to it and follow the rest of the steps to enter your verification code
  * After the first time authenicating you can remove the changes to jasper.py if you'd like. You should never have to do that again.

##Congrats, JASPER Google Calendar is now installed and ready for use; here are some examples:
```
YOU: Add Calendar event
JASPER: What would you like to add?
YOU: Movie with erin Friday at 5 pm
JASPER: Added event Movie with erin on June 06 at 5:00 pm
JASPER: Is this what you wanted?
YOU: Yes
JASPER: Okay, I added it to your calendar
YOU: Do I have any Calendar events tomorrow
JASPER: Dinner with erin at 9:00 pm
YOU: Do I have any Calendar Events Today
JASPER: Dinner with erin at 6:00 pm
```
##Contributions from the following awesome debuggers/developers :)
```
@dansinclair25
@marclave
```
