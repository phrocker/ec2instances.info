
from datetime import datetime, timedelta, date
import yaml
import json
import pandas as pd
import matplotlib.pyplot as plt
from jinja2 import Template
import codecs
from input_analysis import StoragePricingWriteout

if __name__ == "__main__":
    storage = StoragePricingWriteout("www/index.json", "www/ebs.json")
