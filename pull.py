import pandas as pd
import numpy as np
import sodapy

from sodapy import Socrata
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

from datetime import datetime, timedelta

# set the client and authenticate
client = Socrata("datacatalog.cookcountyil.gov", 
                 "Q6WYPYmE8Ff40YoqUQJvDXJSR", 
                 timeout=60)
me_casearchive = "cjeq-bs86"

# get metadata related to the me_casearchive
meta = []
meta = client.get_metadata(me_casearchive)

# set time
rightnow = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
today = datetime.today().strftime('%Y-%m-%d')
yesterday = datetime.today() - timedelta(1)
yesterday = yesterday.strftime('%Y-%m-%d')

# set queries
today_query = f"SELECT * WHERE heat_related = 'true' AND death_date BETWEEN '2026-01-01' AND '{today}'"
yesterday_query = f"SELECT * WHERE heat_related = 'true' AND death_date BETWEEN '2026-01-01' AND '{yesterday}'"
all_query = f"SELECT * WHERE heat_related = 'true'"

# pull heat-related deaths from socrata into a dataframe
today_download = client.get(me_casearchive, query=today_query, exclude_system_fields=False)
yesterday_download = client.get(me_casearchive, query=yesterday_query, exclude_system_fields=False)
all_download = client.get(me_casearchive, query=all_query, exclude_system_fields=False)

# to dataframe
today_df = pd.DataFrame(today_download)
yesterday_df = pd.DataFrame(yesterday_download)
all_df = pd.DataFrame(all_download)

# to file
today_df.to_csv('./data/today_heatdeaths.csv')
yesterday_df.to_csv('./data/yesterday_heatdeaths.csv')
all_df.to_csv('./data/all_heatdeaths.csv')

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