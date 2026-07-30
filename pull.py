import pandas as pd
import numpy as np
import sodapy

from sodapy import Socrata
from requests.adapteres import HTTPAdapter
from urllib3.util import Retry


client = Socrata()