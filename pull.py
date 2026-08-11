import pandas as pd
import json
import numpy as np
import os
import urllib.parse
import time
import requests

import sodapy
from sodapy import Socrata
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

from datetime import datetime, timedelta
from pathlib import Path
from datetime import date, timedelta

# https://docs.slack.dev/tools/python-slack-sdk
from slack_sdk.webhook import WebhookClient
from slack_sdk.errors import SlackApiError

from dotenv import load_dotenv


##############################################
#####  pulling data and running queries  #####
##############################################

# details about the client, token and dataset:
agency = "datacatalog.cookcountyil.gov"
dataset = "cjeq-bs86" # this is the shortlink!
token = os.getenv("COOK_CO_APPTOKEN")

# set time
rightnow = datetime.now().strftime('%Y-%m-%d %I:%M:%S %p')
today = datetime.today().strftime('%Y-%m-%d')
yesterday = datetime.today() - timedelta(1)
yesterday = yesterday.strftime('%Y-%m-%d')

# set queries, using SoQL. (vom)
today_query = f"SELECT * WHERE heat_related = 'true' AND death_date BETWEEN '2026-01-01' AND '{today}'"
yesterday_query = f"SELECT * WHERE heat_related = 'true' AND death_date BETWEEN '2026-01-01' AND '{yesterday}'"
all_query = f"SELECT * WHERE heat_related = 'true'"

# set the client and authenticate
client = Socrata(agency, 
                 token, 
                 timeout=60)

# get metadata related to the dataset
meta = []
meta = client.get_metadata(dataset)

# pull heat-related deaths from socrata into a dataframe
today_download = client.get(dataset, query=today_query, exclude_system_fields=False)
yesterday_download = client.get(dataset, query=yesterday_query, exclude_system_fields=False)
all_download = client.get(dataset, query=all_query, exclude_system_fields=False)

# to dataframe
today_df = pd.DataFrame(today_download)
yesterday_df = pd.DataFrame(yesterday_download)
all_df = pd.DataFrame(all_download)

########## save copies of the data to share ##################
# ## most recent version
todaypath = f'./data/archive/today_heatdeaths_{today}.csv'
today_df.to_csv(todaypath) # most current data, in archive
today_df.to_csv('./data/today_heatdeaths.csv')
all_df.to_csv('./data/all_heatdeaths.csv') # all data pulled

# sanity check of full, queried dataset
print("all heat deaths")
print(len(all_df))

print("heat deaths as of yesterday:")
print(len(yesterday_df))

print("heat deaths as of today:")
print(len(today_df))

# diff between
print("diff between today and yesterday:")
print(len(today_df) - len(yesterday_df))


#####################################
##### slack webhook integration #####
#####################################

### setting variables ###
stringlink = f'https://{agency}/d/{dataset}'
gitlink = "https://github.com/cam-rodriguez/cpm_heatbot/tree/a207489e7adb54302c4755b1a0c7349fbddd6413/data"

SLACK_WEBHOOK = os.getenv("SLACK_CHANNEL_WEBHOOK") #data-heatbot, testing
MAX_SLACK_BLOCKS = 50

placeholder = "Heat deaths"

### creating components for messages ###

# send message to webhook
def send_message(content, webhook):  
    message = {"text": content}
    message_json = json.dumps(message)
    return requests.post(webhook, message_json)

# base text for webhook message
def textgenerator(df1, df2):
    newlen = len(df2)
    length = len(df2) - len(df1)

    if length == 0:
        txt = f"*No new data* was added to the dataset between the last scrape and this one. The current number of heat deaths this year is {newlen}. \n <{stringlink}|Click here> to view the data portal, and <{gitlink}|here> to view the most recent copy."

    elif length == 1:
        txt = f"*One new row* was added to the dataset between the last scrape and this one. The current number of heat deaths this year is {newlen}. \n <{stringlink}|Click here> to view the data portal, and <{gitlink}|here> to view the most recent copy. <!channel>"

    elif length > 1:
        txt = f"*{length} new rows* were added to the dataset between the last scrape and this one. The current number of heat deaths this year is {newlen}. \n <{stringlink}|Click here> to view the data portal, and <{gitlink}|here> to view the most recent copy. <!channel>"

    else:
        txt = f"Error of some kind..."
    
    return txt


### set the different dataframes (df1, df2) ###
newpull = today_df # the most recent version of the data
oldpull = pd.read_csv('./data/archive/lastversion.csv') # the archived version from the last pull

#### data cleaning ###
def splitdate(df):
    df[['inc_date','inc_time']] = df['incident_date'].str.split('T', expand=True)
    df[['dth_date', 'dth_time']] = df['death_date'].str.split('T', expand=True)

splitdate(newpull)
splitdate(oldpull)


#######################################################
# if the new scrape DOES NOT EQUAL the last scrape... #
#######################################################

if newpull.equals(oldpull) != 'True': # in this case, it'll be the newest scrape against the penultimate scrape
    # get the row difference
    numdiff = len(newpull) - len(oldpull) 

    # drop nonmatching rows (and yes, there's probably a better way to do this)
    newrows = newpull[~newpull.isin(oldpull)] 
    newrows = newrows[~newrows['casenumber'].isna()]

    # generating things for text
    caselist = newrows['casenumber']
    
    # data table
    # data cleaning that could literally be done anywhere else but for some reason i'm doing it here ugh
    newrows['age'] = newrows['age'].astype('str')
    newrows['age'] = newrows['age'].str.replace('.0','',regex=True)

    newrows['latino'] = newrows['latino'].astype('str')
    newrows['latino'] = newrows['latino'].str.replace('False','',regex=True)
    newrows['latino'] = newrows['latino'].str.replace('True','Latino',regex=True)

    newrows['incident_zip'] = newrows['incident_zip'].astype('str')
    newrows['incident_zip'] = newrows['incident_zip'].str.replace('.0','',regex=False)


    newrows['inc_loc'] = newrows['incident_street'].str.upper() + ', ' + newrows['incident_city'] + ', IL ' + newrows['incident_zip']
    newrows['inc_loc'] = newrows['inc_loc'].str.title()


    newrows['maploc'] = newrows['inc_loc'].str.replace(' ','+',regex=True)
    gmaps_start = "https://google.com/maps/place/"
    newrows['gmaps_link'] = "<" + gmaps_start + newrows['maploc'] + "/ | here >"

    # newrows['gmaps_link'] = f'<{gmaps_start}/{maploc}/ | >'

    # concatenate to get a big string
    newrows_trunc = newrows[['casenumber','inc_date','dth_date','age', 'incident_city', 'gender','race','latino','primarycause','secondarycause','inc_loc','chi_ward','chi_commarea','residence_city','gmaps_link']]
    
    # make it a string list
    newrows_trunc['stringy'] = "• *Case number " + newrows_trunc['casenumber'] + "* — a " + newrows_trunc['age'] + "-year-old " + newrows_trunc['latino'] + " " + newrows_trunc['race'] + " " + newrows_trunc['gender'].str.lower() + " in " + newrows_trunc['incident_city'].str.title() + ". \n The determined cause of death is " + newrows_trunc['primarycause'] + " and " + newrows_trunc['secondarycause'] + ". The death date was *" + newrows_trunc['dth_date'] + "* and the incident that led to their death was on *" + newrows_trunc['inc_date'] + "* at " + newrows_trunc['inc_loc'] + ". 📍 view incident location " + newrows_trunc['gmaps_link'] + ". \n"
    stringy_list = newrows_trunc['stringy']

    ########
    # send leading message about the update with the diff#

    text = textgenerator(oldpull, newpull)
    formatted = f'❗️ *{placeholder} update — {today}* \n {text} \n'
    send_message(formatted, SLACK_WEBHOOK)

    # send the details about each row in the diff #
    # for every new row in the new data, send a message with that row's contents
    for item in list(stringy_list):

        # dataformat = f'The updated data rows are below: \n {list}'
        send_message(item, SLACK_WEBHOOK)
        print("sent!")



#############################################
#############################################
# have a version that can be pulled in and run as a comparison
archiveversion = today_df
archiveversion.to_csv('./data/archive/lastversion.csv')
# ^ this will now become the oldpull for the next scrape!